"use client"

import { useCallback, useEffect, useRef, useState } from "react"
import { deletePendingAttachment, uploadMessageAttachment, type MessageAttachment } from "@/lib/api"

export type DraftAttachment = {
  key: string
  filename: string
  state: "uploading" | "ready" | "error" | "removing"
  attachment?: MessageAttachment
  error?: string
}

export function useMessageAttachments(backendUrl: string, sessionId: string | null) {
  const [drafts, setDrafts] = useState<Record<string, DraftAttachment[]>>({})
  const draftsRef = useRef(drafts)
  const controllers = useRef(new Map<string, AbortController>())
  const live = useRef(true)
  useEffect(() => {
    live.current = true
    const pending = controllers.current
    return () => { live.current = false; pending.forEach((controller) => controller.abort()); pending.clear() }
  }, [])
  const update = useCallback((sid: string, change: (items: DraftAttachment[]) => DraftAttachment[]) => {
    if (!live.current) return
    draftsRef.current = { ...draftsRef.current, [sid]: change(draftsRef.current[sid] ?? []) }
    setDrafts(draftsRef.current)
  }, [])

  function add(files: File[]) {
    if (!sessionId) return
    const sid = sessionId
    const capacity = Math.max(0, 4 - (draftsRef.current[sid]?.length ?? 0))
    for (const file of files.slice(0, capacity)) {
      const key = crypto.randomUUID()
      const controller = new AbortController()
      controllers.current.set(key, controller)
      update(sid, (items) => [...items, { key, filename: file.name, state: "uploading" }])
      // Every completion remains associated with the original Session.
      void (async () => {
        try {
          if (!file.size || file.size > 8 * 1024 * 1024) throw new Error("文件为空或超过 8 MiB")
          const attachment = await uploadMessageAttachment(backendUrl, sid, file, controller.signal)
          if (attachment.sessionId !== sid || attachment.messageId) throw new Error("附件归属校验失败，请重新上传")
          update(sid, (items) => items.map((item) => item.key === key ? { ...item, state: "ready", attachment } : item))
        } catch (error) {
          if (!controller.signal.aborted) update(sid, (items) => items.map((item) => item.key === key ? { ...item, state: "error", error: error instanceof Error ? error.message : "上传失败" } : item))
        } finally { controllers.current.delete(key) }
      })()
    }
  }

  async function remove(key: string) {
    if (!sessionId) return
    const sid = sessionId
    const item = draftsRef.current[sid]?.find((entry) => entry.key === key)
    if (!item || item.state === "uploading" || item.state === "removing") return
    if (item.attachment) {
      update(sid, (items) => items.map((entry) => entry.key === key ? { ...entry, state: "removing" } : entry))
      try { await deletePendingAttachment(backendUrl, sid, item.attachment.id) }
      catch (error) {
        update(sid, (items) => items.map((entry) => entry.key === key ? { ...entry, state: "error", error: error instanceof Error ? error.message : "移除失败" } : entry))
        return
      }
    }
    update(sid, (items) => items.filter((entry) => entry.key !== key))
  }

  function sent(sid: string, ids: string[]) {
    update(sid, (items) => items.filter((item) => !item.attachment || !ids.includes(item.attachment.id)))
  }
  const items = sessionId ? drafts[sessionId] ?? [] : []
  return { items, add, remove, sent, blocked: items.some((item) => item.state !== "ready"),
    ids: items.flatMap((item) => item.state === "ready" && item.attachment ? [item.attachment.id] : []) }
}
