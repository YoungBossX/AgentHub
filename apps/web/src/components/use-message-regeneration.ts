"use client"

import { useRef, useState } from "react"
import { listSessionMessages, listSessionTasks, regenerateSessionMessage, RegenerationRequestError, type ChatMessage, type SessionTask } from "@/lib/api"

export function useMessageRegeneration(backendUrl: string, selectedSessionId: string | null,
  apply: (sessionId: string, messages: ChatMessage[], tasks: SessionTask[], created: ChatMessage) => void) {
  const inFlight = useRef(new Set<string>())
  const operations = useRef(new Map<string, string>())
  const [pending, setPending] = useState<string[]>([])

  async function run(message: ChatMessage) {
    const sessionId = message.sessionId
    if (inFlight.current.has(sessionId)) return
    inFlight.current.add(sessionId)
    setPending([...inFlight.current])
    const key = `agenthub:regeneration:${backendUrl}:${sessionId}:${message.id}`
    let operationId = operations.current.get(key)
    if (!operationId) {
      try { operationId = sessionStorage.getItem(key) ?? undefined } catch { /* in-memory fallback */ }
      if (!operationId || !/^[0-9a-f-]{36}$/i.test(operationId)) operationId = crypto.randomUUID()
      operations.current.set(key, operationId)
      try { sessionStorage.setItem(key, operationId) } catch { /* in-memory fallback */ }
    }
    const forget = () => {
      operations.current.delete(key)
      try { sessionStorage.removeItem(key) } catch { /* optional persistence */ }
    }
    try {
      let created: ChatMessage
      try { created = await regenerateSessionMessage(backendUrl, sessionId, message.id, operationId) }
      catch (error) {
        // A response can be lost after persistence. Resolve by identity before
        // offering another deliberate generation; never resend a fresh UUID.
        const history = await listSessionMessages(backendUrl, sessionId).catch(() => [])
        const saved = history.find((row) => row.id === operationId && row.regeneration?.sourceMessageId === message.id)
        if (saved) created = saved
        else {
          if (error instanceof RegenerationRequestError && error.status >= 400 && error.status < 500) {
            forget()
            throw error
          }
          throw new Error("网络结果尚未确认。再次确认会检查同一次操作，不会重复提交新任务。")
        }
      }
      const [messages, tasks] = await Promise.all([listSessionMessages(backendUrl, sessionId), listSessionTasks(backendUrl, sessionId)])
      apply(sessionId, messages, tasks, created)
      forget()
      if (created.regeneration?.state === "failed") throw new Error("原请求已保留，但本次规划未完成。请查看消息和已有任务，再决定是否重新生成。")
    } finally {
      inFlight.current.delete(sessionId)
      setPending([...inFlight.current])
    }
  }
  return { run, pending: !!selectedSessionId && pending.includes(selectedSessionId) }
}
