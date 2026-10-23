"use client"

import { useEffect, useLayoutEffect, useRef, useState, type ReactNode } from "react"
import { ArrowDown } from "lucide-react"
import type { ChatMessage } from "@/lib/api"

type Reading = {
  key: string | null; active: boolean; following: boolean; top: number; historical: boolean
  ready: boolean; seen: Map<string, string>; unread: Set<string>; changed: boolean
}
const fresh = (key: string | null): Reading => ({ key, active: false, following: true, top: 0,
  historical: false, ready: false, seen: new Map(), unread: new Set(), changed: false })

export function ConversationScroll({ sessionId, active, loading, historical, messages, children }: {
  sessionId: string | null; active: boolean; loading: boolean; historical: boolean; messages: ChatMessage[]; children: ReactNode
}) {
  const root = useRef<HTMLDivElement>(null)
  const content = useRef<HTMLDivElement>(null)
  const reading = useRef<Reading>(fresh(sessionId))
  const [notice, setNotice] = useState({ key: sessionId, count: 0, changed: false })

  useLayoutEffect(() => {
    if (reading.current.key !== sessionId) reading.current = fresh(sessionId)
    const state = reading.current, node = root.current
    if (!active) { state.active = false; return }
    if (!node || loading) return
    const returning = !state.active
    const latest = state.historical && !historical
    state.active = true
    state.historical = historical
    if (latest) { state.following = true; state.unread.clear(); state.changed = false }
    if (historical) state.following = false
    if (state.ready && !historical && !latest && !state.following) {
      for (const message of messages) {
        if (!state.seen.has(message.id)) state.unread.add(message.id)
        else if (state.seen.get(message.id) !== message.contentMd) state.changed = true
      }
    }
    state.seen = new Map(messages.map(message => [message.id, message.contentMd]))
    state.ready = true
    if (returning && !state.following) node.scrollTop = state.top
    if (state.following) {
      node.scrollTop = Math.max(0, node.scrollHeight - node.clientHeight)
      state.unread.clear(); state.changed = false
    }
    state.top = node.scrollTop
    const frame = requestAnimationFrame(() => setNotice({ key: sessionId, count: state.unread.size, changed: state.changed }))
    return () => cancelAnimationFrame(frame)
  }, [sessionId, active, loading, historical, messages])

  useEffect(() => {
    const node = root.current, child = content.current
    if (!node || !child || !active || typeof ResizeObserver === "undefined") return
    const observer = new ResizeObserver(() => {
      const state = reading.current
      if (state.key !== sessionId || !state.active || !state.following || state.historical || !state.ready) return
      node.scrollTop = Math.max(0, node.scrollHeight - node.clientHeight)
      state.top = node.scrollTop
    })
    observer.observe(child)
    observer.observe(node)
    return () => observer.disconnect()
  }, [sessionId, active])

  function clearNotice() {
    reading.current.unread.clear(); reading.current.changed = false
    setNotice({ key: sessionId, count: 0, changed: false })
  }
  const visibleNotice = active && !historical && notice.key === sessionId && (notice.count > 0 || notice.changed)
  return <div className="relative min-h-0 flex-1">
    <div ref={root} className="h-full overflow-y-auto px-5 py-5" data-region="center-scroll" onScroll={event => {
      const state = reading.current, node = event.currentTarget
      if (!active || state.key !== sessionId) return
      state.top = node.scrollTop
      state.following = !historical && node.scrollHeight - node.clientHeight - node.scrollTop <= 80
      if (state.following && (state.unread.size || state.changed)) clearNotice()
    }}>
      <div ref={content} data-region="scroll-content">{children}</div>
    </div>
    {visibleNotice ? <button type="button" className="new-message-notice absolute bottom-4 left-1/2 inline-flex -translate-x-1/2 items-center gap-2 whitespace-nowrap rounded-full bg-[var(--foreground)] px-4 py-2 text-xs text-[var(--surface)] shadow-sm" onClick={() => {
      const node = root.current
      if (!node) return
      reading.current.following = true
      node.scrollTop = Math.max(0, node.scrollHeight - node.clientHeight)
      reading.current.top = node.scrollTop
      clearNotice()
    }}><ArrowDown aria-hidden="true" size={14} />{notice.count ? `${notice.count} 条新消息` : "有新内容"} · 回到底部</button> : null}
  </div>
}
