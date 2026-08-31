"use client"

import {
  type Dispatch,
  type SetStateAction,
  useEffect,
  useRef,
} from "react"

import {
  listSessionTasks,
  sessionEventsUrl,
  type SessionTask,
} from "@/lib/api"

const SSE_TASK_REFRESH_MAX_RETRIES = 3
const SSE_TASK_REFRESH_INITIAL_DELAY_MS = 250

type SessionEventRefreshOptions = {
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
}: SessionEventRefreshOptions) {
  const sessionEventCursorsRef = useRef(new Map<string, string>())

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
      try {
        const nextTasks = await listSessionTasks(backendUrl, sessionId)
        if (!active) {
          return
        }
        retryAttempt = 0
        setTasks(nextTasks)
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

    return () => {
      active = false
      if (retryTimer !== null) {
        window.clearTimeout(retryTimer)
      }
      source.close()
    }
  }, [
    backendUrl,
    reportSyncError,
    selectedSessionId,
    setArtifactRefreshVersion,
    setSyncError,
    setTasks,
  ])
}
