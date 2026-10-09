"use client"

import {
  type Dispatch,
  type SetStateAction,
  type RefObject,
  useEffect,
  useRef,
} from "react"

import {
  listSessionTasks,
  listSessionMessages,
  type ChatMessage,
  sessionEventsUrl,
  type SessionTask,
} from "@/lib/api"

import { visualEvent, type SessionVisualEvent } from "./session-event-timeline"

const SSE_TASK_REFRESH_MAX_RETRIES = 3
const SSE_TASK_REFRESH_INITIAL_DELAY_MS = 250

type SessionEventRefreshOptions = {
  summaryPending?: boolean
  onVisualEvent?: (event: SessionVisualEvent) => void
  setMessages?: Dispatch<SetStateAction<ChatMessage[]>>
  messageRevisionRef?: RefObject<number>
  backendUrl: string
  reportSyncError: (action: string, error: unknown) => void
  selectedSessionId: string | null
  setArtifactRefreshVersion: Dispatch<SetStateAction<number>>
  setSyncError: Dispatch<SetStateAction<string | null>>
  setTasks: Dispatch<SetStateAction<SessionTask[]>>
}

export function useSessionEventRefresh({
  backendUrl,
  reportSyncError,
  selectedSessionId,
  setArtifactRefreshVersion,
  setSyncError,
  setTasks,
  setMessages,
  onVisualEvent,
  summaryPending = false,
  messageRevisionRef,
}: SessionEventRefreshOptions) {
  const sessionEventCursorsRef = useRef(new Map<string, string>())
  const summaryPendingRef = useRef(summaryPending)
  useEffect(() => { summaryPendingRef.current = summaryPending }, [summaryPending])

  useEffect(() => {
    if (!selectedSessionId) {
      return
    }

    const sessionId = selectedSessionId
    let active = true
    let refreshInFlight = false
    let refreshRequested = false
    let retryAttempt = 0
    let retryTimer: number | null = null
    const source = new EventSource(
      sessionEventsUrl(
        backendUrl,
        sessionId,
        sessionEventCursorsRef.current.get(sessionId),
      ),
    )
    source.onmessage = (event) => {
      if (!active) {
        return
      }
      try {
        const payload = JSON.parse(event.data) as { cursor?: unknown }
        if (typeof payload.cursor === "string" && payload.cursor.length > 0) {
          sessionEventCursorsRef.current.set(sessionId, payload.cursor)
        }
        const record = visualEvent(payload, sessionId)
        if (record) onVisualEvent?.(record)
        setArtifactRefreshVersion((current) => current + 1)
      } catch (error) {
        reportSyncError("无法解析会话事件", error)
        return
      }
      requestTaskRefresh()
    }

    function requestTaskRefresh() {
      if (!active) {
        return
      }
      refreshRequested = true
      retryAttempt = 0
      if (retryTimer !== null) {
        window.clearTimeout(retryTimer)
        retryTimer = null
      }
      void runTaskRefresh()
    }

    async function runTaskRefresh() {
      if (!active || refreshInFlight || !refreshRequested) {
        return
      }
      refreshRequested = false
      refreshInFlight = true
      const messageRevision = messageRevisionRef?.current
      try {
        const [nextTasks, nextMessages] = await Promise.all([listSessionTasks(backendUrl, sessionId), setMessages ? listSessionMessages(backendUrl, sessionId) : Promise.resolve(null)])
        if (!active) {
          return
        }
        retryAttempt = 0
        setTasks(nextTasks)
        if (messageRevision !== messageRevisionRef?.current) {
          refreshRequested = true
        } else if (nextMessages) setMessages?.(nextMessages)
        setSyncError(null)
      } catch (error) {
        if (!active) {
          return
        }
        reportSyncError("无法刷新任务时间线", error)
        if (retryAttempt < SSE_TASK_REFRESH_MAX_RETRIES) {
          const retryDelayMs =
            SSE_TASK_REFRESH_INITIAL_DELAY_MS * 2 ** retryAttempt
          retryAttempt += 1
          refreshRequested = true
          retryTimer = window.setTimeout(() => {
            retryTimer = null
            void runTaskRefresh()
          }, retryDelayMs)
        }
      } finally {
        refreshInFlight = false
        if (active && retryTimer === null && refreshRequested) {
          void runTaskRefresh()
        }
      }
    }

    // Preparations rejected before the first run have no TaskRunEvent stream.
    const summaryTimer = window.setInterval(() => {
      if (summaryPendingRef.current) requestTaskRefresh()
    }, 2000)
    return () => {
      active = false
      if (retryTimer !== null) {
        window.clearTimeout(retryTimer)
      }
      source.close()
      window.clearInterval(summaryTimer)
    }
  }, [
    backendUrl,
    reportSyncError,
    selectedSessionId,
    setArtifactRefreshVersion,
    setSyncError,
    setTasks,
    setMessages,
    onVisualEvent,
    messageRevisionRef,
  ])
}
