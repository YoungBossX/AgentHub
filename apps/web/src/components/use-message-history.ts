"use client"

import { useCallback, useEffect, useRef, useState, type Dispatch, type RefObject, type SetStateAction } from "react"
import type { ChatMessage } from "@/lib/api"
import { HISTORY_WINDOW_SIZE, listMessagePage, type HistoryQuery, type MessagePage } from "@/lib/message-history-api"

type Window = { key: string; rows: ChatMessage[]; latestRows: ChatMessage[]; pins: ChatMessage[]; pinnedTotal: number; hasOlder: boolean; hasNewer: boolean; latestId: string | null; mode: "latest" | "history"; loaded: boolean }
const empty = (key: string): Window => ({ key, rows: [], latestRows: [], pins: [], pinnedTotal: 0, hasOlder: false, hasNewer: false, latestId: null, mode: "latest", loaded: false })
export function mergeHistoryRows(current: ChatMessage[], incoming: ChatMessage[], keep: "older" | "newer") {
  const map = new Map(current.map(row => [row.id, row]))
  for (const row of incoming) map.set(row.id, row)
  const rows = [...map.values()].sort((a, b) => String(a.createdAt ?? "").localeCompare(String(b.createdAt ?? "")) || a.id.localeCompare(b.id))
  return keep === "older" ? rows.slice(0, HISTORY_WINDOW_SIZE) : rows.slice(-HISTORY_WINDOW_SIZE)
}

function updatedPins(previous: Window, rows: ChatMessage[]) {
  const known = new Map(previous.rows.map(row => [row.id, row]))
  const pins = new Map(previous.pins.map(row => [row.id, row]))
  let total = previous.pinnedTotal
  for (const row of rows) {
    const old = known.get(row.id)
    if (old) total += Number(Boolean(row.pinnedAt)) - Number(Boolean(old.pinnedAt))
    if (row.pinnedAt) pins.set(row.id, row)
    else pins.delete(row.id)
  }
  return { pins: [...pins.values()].sort((a, b) => String(b.pinnedAt).localeCompare(String(a.pinnedAt)) || b.id.localeCompare(a.id)).slice(0, 16), pinnedTotal: Math.max(0, total) }
}

export function useMessageHistory(backendUrl: string, sessionId: string | null, revision: RefObject<number>, onError: (error: unknown) => void, onReady: () => void) {
  const key = `${backendUrl}:${sessionId}`
  const [window, setWindow] = useState<Window>(() => empty(key))
  const [pending, setPending] = useState<string | null>(null)
  const owner = useRef({ key, generation: 0 })
  const busy = useRef(new Set<string>())
  const navigation = useRef(0)
  const scrollIntent = useRef<{ key: string; generation: number; id: string; block: ScrollLogicalPosition } | null>(null)
  const callbacks = useRef({ onError, onReady })
  useEffect(() => { callbacks.current = { onError, onReady } }, [onError, onReady])
  const visible = window.key === key ? window : empty(key)
  useEffect(() => {
    const intent = scrollIntent.current
    if (!intent || intent.key !== key || intent.generation !== owner.current.generation) return
    const element = document.getElementById(`message-${intent.id}`)
    if (!element) return
    scrollIntent.current = null
    element.scrollIntoView?.({ behavior: "smooth", block: intent.block })
  }, [window, key])
  useEffect(() => {
    owner.current = { key, generation: owner.current.generation + 1 }
    if (!sessionId) return
    let active = true
    const startRevision = revision.current
    listMessagePage(backendUrl, sessionId).then(page => {
      if (!active || revision.current !== startRevision) return
      setWindow({ key, rows: mergeHistoryRows([], page.messages, "newer"), latestRows: page.messages.slice(-80), pins: page.pinnedMessages.slice(0, 16), pinnedTotal: page.pinnedTotal, loaded: true,
        hasOlder: page.hasOlder, hasNewer: page.hasNewer, latestId: page.latestMessageId, mode: "latest" })
      callbacks.current.onReady()
    }).catch(error => { if (active) callbacks.current.onError(error) })
    return () => { active = false }
  }, [backendUrl, sessionId, key, revision])

  const setMessages: Dispatch<SetStateAction<ChatMessage[]>> = useCallback(action => {
    if (owner.current.key !== key) return
    setWindow(previous => {
      const current = previous.key === key ? previous : empty(key)
      const incoming = (typeof action === "function" ? action(current.rows) : action).filter(row => row.sessionId === sessionId)
      const patch = typeof action === "function"
      const latestId = patch ? current.latestId : incoming.at(-1)?.id ?? current.latestId
      let rows: ChatMessage[]
      if (patch) rows = mergeHistoryRows([], incoming, current.mode === "history" ? "older" : "newer")
      else if (current.mode === "history") {
        const replacements = new Map(incoming.map(row => [row.id, row]))
        rows = current.rows.map(row => replacements.get(row.id) ?? row)
      } else rows = mergeHistoryRows(current.rows, incoming, "newer")
      const patches = new Map(incoming.map(row => [row.id, row]))
      const latestRows = patch ? current.latestRows.map(row => patches.get(row.id) ?? row) : incoming.slice(-80)
      return { ...current, rows, latestRows, latestId, loaded: true, ...updatedPins(current, incoming),
        hasOlder: current.hasOlder || current.rows.length + incoming.filter(row => !current.rows.some(old => old.id === row.id)).length > HISTORY_WINDOW_SIZE,
        hasNewer: current.mode === "history" && Boolean(latestId && rows.at(-1)?.id !== latestId) }
    })
  }, [key, sessionId])

  function showLatestMessages(rows: ChatMessage[]) {
    if (owner.current.key !== key) return
    navigation.current++
    setWindow(previous => {
      const current = previous.key === key ? previous : empty(key)
      const included = rows.filter(row => row.sessionId === sessionId)
      return { ...current, rows: mergeHistoryRows([], included, "newer"), latestRows: included.slice(-80), loaded: true, mode: "latest", hasNewer: false,
        latestId: included.at(-1)?.id ?? null, hasOlder: current.hasOlder || included.length >= 80, ...updatedPins(current, included) }
    })
  }

  function showLatestPage(page: MessagePage) {
    if (owner.current.key !== key) return
    navigation.current++
    setWindow({ key, rows: mergeHistoryRows([], page.messages, "newer"), latestRows: page.messages.slice(-80), loaded: true,
      pins: page.pinnedMessages.slice(0, 16), pinnedTotal: page.pinnedTotal, mode: "latest", latestId: page.latestMessageId,
      hasOlder: page.hasOlder, hasNewer: page.hasNewer })
  }

  async function refresh() {
    if (!sessionId || owner.current.key !== key) return
    const token = { ...owner.current }, viewRevision = navigation.current, messageRevision = revision.current
    const midpoint = visible.rows[Math.floor(visible.rows.length / 2)]
    const needsWindow = midpoint && (visible.mode === "history" || visible.rows.length > 80)
    const [tail, selected] = await Promise.all([listMessagePage(backendUrl, sessionId), needsWindow
      ? listMessagePage(backendUrl, sessionId, { around: midpoint.id, limit: visible.rows.length }) : Promise.resolve(null)])
    if (owner.current.key !== token.key || owner.current.generation !== token.generation || revision.current !== messageRevision) return
    setWindow(previous => {
      if (previous.key !== key || navigation.current !== viewRevision) return previous
      const incoming = [...(selected?.messages ?? []), ...tail.messages]
      const replacements = new Map(incoming.map(row => [row.id, row]))
      const rows = previous.mode === "history" ? previous.rows.map(row => replacements.get(row.id) ?? row)
        : mergeHistoryRows(previous.rows, incoming, "newer")
      return { ...previous, rows, loaded: true, latestRows: tail.messages.slice(-80), latestId: tail.latestMessageId,
        pins: tail.pinnedMessages.slice(0, 16), pinnedTotal: tail.pinnedTotal,
        hasOlder: previous.rows.length ? (rows[0]?.id === previous.rows[0]?.id ? previous.hasOlder : true) : tail.hasOlder,
        hasNewer: Boolean(tail.latestMessageId && rows.at(-1)?.id !== tail.latestMessageId) }
    })
  }

  async function navigate(query: HistoryQuery, direction: "latest" | "older" | "newer" | "around", jumpId?: string) {
    if (!sessionId || busy.current.has(key) || owner.current.key !== key) return
    busy.current.add(key); setPending(key)
    navigation.current++
    const token = { ...owner.current }, startRevision = revision.current
    if (direction !== "latest") setWindow(previous => previous.key === key ? { ...previous, mode: "history" } : previous)
    try {
      const page: MessagePage = await listMessagePage(backendUrl, sessionId, query)
      if (owner.current.key !== token.key || owner.current.generation !== token.generation) return
      // Latest scrolling belongs to ConversationScroll, including the results footer.
      const destination = jumpId ?? null
      scrollIntent.current = destination ? { ...token, id: destination, block: direction === "latest" ? "end" : "center" } : null
      setWindow(previous => {
        const current = previous.key === key ? previous : empty(key)
        const freshPins = startRevision === revision.current ? { pins: page.pinnedMessages.slice(0, 16), pinnedTotal: page.pinnedTotal } : { pins: current.pins, pinnedTotal: current.pinnedTotal }
        if (direction === "latest" || direction === "around") return { ...current, ...freshPins, rows: mergeHistoryRows([], page.messages, "newer"), loaded: true,
          latestRows: direction === "latest" ? page.messages.slice(-80) : current.latestRows,
          hasOlder: page.hasOlder, hasNewer: page.hasNewer, latestId: page.latestMessageId, mode: direction === "latest" ? "latest" : "history" }
        // Current rows win overlapping responses, preserving a more recent pin
        // or SSE patch received while this older/newer page was in flight.
        const rows = mergeHistoryRows(page.messages, current.rows, direction === "older" ? "older" : "newer")
        return { ...current, ...freshPins, rows, latestId: page.latestMessageId,
          hasOlder: direction === "older" ? page.hasOlder : current.hasOlder || rows[0]?.id !== current.rows[0]?.id,
          hasNewer: Boolean(page.latestMessageId && rows.at(-1)?.id !== page.latestMessageId), mode: "history" }
      })
      callbacks.current.onReady()
    } catch (error) { if (owner.current.key === token.key && owner.current.generation === token.generation) callbacks.current.onError(error) }
    finally { busy.current.delete(key); setPending(current => current === key ? null : current) }
  }
  async function refreshManually() {
    if (!sessionId || busy.current.has(key) || owner.current.key !== key) return
    const token = { ...owner.current }
    busy.current.add(key); setPending(key)
    try {
      await refresh()
      if (owner.current.key === token.key && owner.current.generation === token.generation) callbacks.current.onReady()
    }
    catch (error) {
      if (owner.current.key === token.key && owner.current.generation === token.generation) callbacks.current.onError(error)
    } finally {
      busy.current.delete(key); setPending(current => current === key ? null : current)
    }
  }
  function openMessage(id: string) {
    if (visible.rows.some(row => row.id === id)) document.getElementById(`message-${id}`)?.scrollIntoView?.({ behavior: "smooth", block: "center" })
    else void navigate({ around: id }, "around", id)
  }
  return { messages: visible.rows, latestMessages: visible.latestRows, latestMessageId: visible.latestId, setMessages, showLatestMessages, showLatestPage, refresh, refreshManually, pins: visible.pins, pinnedTotal: visible.pinnedTotal, loading: !visible.loaded,
    hasOlder: visible.hasOlder, hasNewer: visible.hasNewer, historical: visible.mode === "history", pending: pending === key,
    older: () => visible.rows.length ? navigate({ before: visible.rows[0].id }, "older") : Promise.resolve(),
    newer: () => visible.rows.length ? navigate({ after: visible.rows.at(-1)!.id }, "newer") : Promise.resolve(),
    latest: () => navigate({}, "latest"), openMessage }
}
