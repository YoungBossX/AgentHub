"use client"

import { GitBranch, MessageSquare, Plus } from "lucide-react"
import { usePathname, useRouter, useSearchParams } from "next/navigation"
import { FormEvent, useEffect, useMemo, useState, useTransition } from "react"

import { Button } from "@/components/ui/button"
import { TaskCardList } from "@/components/task-card-list"
import {
  createSessionMessage,
  createTaskRun,
  createWorkspaceSession,
  interruptTaskRun,
  listSessionMessages,
  listSessionTasks,
  retryTaskRun,
  retryTaskRunWithFallback,
  sessionEventsUrl,
  type ChatMessage,
  type SessionTask,
  type Workspace,
  type WorkspaceSession,
} from "@/lib/api"
import { cn } from "@/lib/utils"

type WorkspaceShellProps = {
  backendUrl: string
  workspace: Workspace | null
  initialSessions: WorkspaceSession[]
}

function formatSessionTime(value: string | null) {
  if (!value) {
    return "No messages"
  }

  return new Intl.DateTimeFormat(undefined, {
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    month: "short",
  }).format(new Date(value))
}

export function WorkspaceShell({
  backendUrl,
  workspace,
  initialSessions,
}: WorkspaceShellProps) {
  const router = useRouter()
  const pathname = usePathname()
  const searchParams = useSearchParams()
  const [isPending, startTransition] = useTransition()
  const [sessions, setSessions] = useState(initialSessions)
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [tasks, setTasks] = useState<SessionTask[]>([])
  const [draft, setDraft] = useState("")
  const [lastEventSequence, setLastEventSequence] = useState(0)

  const selectedSessionId = searchParams.get("session") ?? sessions[0]?.id ?? null
  const selectedSession = useMemo(
    () => sessions.find((session) => session.id === selectedSessionId) ?? null,
    [selectedSessionId, sessions],
  )
  const visibleMessages = selectedSessionId ? messages : []

  useEffect(() => {
    if (!selectedSessionId) {
      return
    }

    let cancelled = false
    listSessionMessages(backendUrl, selectedSessionId).then((nextMessages) => {
      if (!cancelled) {
        setMessages(nextMessages)
      }
    })

    return () => {
      cancelled = true
    }
  }, [backendUrl, selectedSessionId])

  useEffect(() => {
    if (!selectedSessionId) {
      return
    }

    let cancelled = false
    listSessionTasks(backendUrl, selectedSessionId).then((nextTasks) => {
      if (!cancelled) {
        setTasks(nextTasks)
      }
    })

    return () => {
      cancelled = true
    }
  }, [backendUrl, selectedSessionId])

  useEffect(() => {
    if (!selectedSessionId) {
      return
    }

    const source = new EventSource(
      sessionEventsUrl(backendUrl, selectedSessionId, lastEventSequence),
    )
    source.onmessage = (event) => {
      const payload = JSON.parse(event.data) as { sequence?: number }
      if (typeof payload.sequence === "number") {
        setLastEventSequence((current) => Math.max(current, payload.sequence ?? 0))
      }
      listSessionTasks(backendUrl, selectedSessionId).then(setTasks)
    }
    source.onerror = () => {
      source.close()
    }

    return () => {
      source.close()
    }
  }, [backendUrl, lastEventSequence, selectedSessionId])

  function selectSession(sessionId: string) {
    const params = new URLSearchParams(searchParams.toString())
    params.set("session", sessionId)
    router.replace(`${pathname}?${params.toString()}`)
  }

  function handleCreateSession() {
    if (!workspace) {
      return
    }

    const title = `Session ${sessions.length + 1}`
    startTransition(async () => {
      const created = await createWorkspaceSession(backendUrl, workspace.id, title)
      setSessions((current) => [created, ...current])
      const params = new URLSearchParams(searchParams.toString())
      params.set("session", created.id)
      router.replace(`${pathname}?${params.toString()}`)
    })
  }

  async function refreshSelectedTasks() {
    if (!selectedSessionId) {
      return
    }
    const nextTasks = await listSessionTasks(backendUrl, selectedSessionId)
    setTasks(nextTasks)
  }

  function handleCreateTaskRun(taskId: string) {
    startTransition(async () => {
      await createTaskRun(backendUrl, taskId)
      await refreshSelectedTasks()
    })
  }

  function handleInterruptTaskRun(taskRunId: string) {
    startTransition(async () => {
      await interruptTaskRun(backendUrl, taskRunId)
      await refreshSelectedTasks()
    })
  }

  function handleRetryTaskRun(taskRunId: string) {
    startTransition(async () => {
      await retryTaskRun(backendUrl, taskRunId)
      await refreshSelectedTasks()
    })
  }

  function handleRetryTaskRunWithFallback(taskRunId: string) {
    startTransition(async () => {
      await retryTaskRunWithFallback(backendUrl, taskRunId)
      await refreshSelectedTasks()
    })
  }

  function handleSendMessage(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!selectedSessionId || draft.trim().length === 0) {
      return
    }

    const content = draft.trim()
    setDraft("")
    startTransition(async () => {
      const created = await createSessionMessage(backendUrl, selectedSessionId, content)
      const nextTasks = await listSessionTasks(backendUrl, selectedSessionId)
      setMessages((current) => [...current, created])
      setTasks(nextTasks)
      setSessions((current) =>
        current.map((session) =>
          session.id === selectedSessionId
            ? { ...session, lastMessageAt: created.createdAt }
            : session,
        ),
      )
    })
  }

  if (!workspace) {
    return (
      <section className="rounded-lg border border-[var(--border)] bg-[var(--card)] p-5">
        <h2 className="text-lg font-semibold">Workspace unavailable</h2>
        <p className="mt-3 text-sm leading-6 text-[var(--muted-foreground)]">
          Start the API and seed the SQLite database, then refresh AgentHub.
        </p>
      </section>
    )
  }

  return (
    <section className="grid min-h-[560px] overflow-hidden rounded-lg border border-[var(--border)] bg-[var(--card)] md:grid-cols-[320px_1fr]">
      <aside className="border-b border-[var(--border)] bg-slate-50 md:border-b-0 md:border-r">
        <div className="border-b border-[var(--border)] p-4">
          <div className="flex items-start justify-between gap-3">
            <div>
              <p className="text-xs font-medium uppercase tracking-normal text-[var(--muted-foreground)]">
                Workspace
              </p>
              <h2 className="mt-1 text-lg font-semibold">{workspace.name}</h2>
              <p className="mt-1 text-sm text-[var(--muted-foreground)]">
                {workspace.rootPath}
              </p>
            </div>
            <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md bg-blue-600 text-white">
              <GitBranch aria-hidden="true" size={18} />
            </span>
          </div>

          <Button
            className="mt-4 w-full"
            disabled={isPending}
            onClick={handleCreateSession}
            type="button"
          >
            <Plus aria-hidden="true" size={16} />
            New session
          </Button>
        </div>

        <div className="grid gap-2 p-3">
          {sessions.map((session) => {
            const selected = session.id === selectedSessionId
            return (
              <button
                className={cn(
                  "grid min-h-24 w-full gap-2 rounded-md border p-3 text-left transition",
                  selected
                    ? "border-blue-600 bg-white shadow-sm"
                    : "border-transparent bg-transparent hover:border-[var(--border)] hover:bg-white",
                )}
                key={session.id}
                onClick={() => selectSession(session.id)}
                type="button"
              >
                <span className="flex items-center justify-between gap-3">
                  <span className="truncate text-sm font-semibold">{session.title}</span>
                  <span className="rounded-sm border border-[var(--border)] px-2 py-0.5 text-xs text-[var(--muted-foreground)]">
                    {session.status}
                  </span>
                </span>
                <span className="text-xs text-[var(--muted-foreground)]">
                  {formatSessionTime(session.lastMessageAt)}
                </span>
                <span className="truncate text-xs text-[var(--muted-foreground)]">
                  {session.worktreePath}
                </span>
              </button>
            )
          })}

          {sessions.length === 0 ? (
            <div className="rounded-md border border-dashed border-[var(--border)] bg-white p-4 text-sm text-[var(--muted-foreground)]">
              No sessions yet.
            </div>
          ) : null}
        </div>
      </aside>

      <div className="flex min-h-[560px] flex-col">
        <header className="flex items-center justify-between gap-4 border-b border-[var(--border)] p-5">
          <div>
            <p className="text-xs font-medium uppercase tracking-normal text-[var(--muted-foreground)]">
              Selected session
            </p>
            <h2 className="mt-1 text-xl font-semibold">
              {selectedSession?.title ?? "No session selected"}
            </h2>
          </div>
          <span className="flex h-10 w-10 items-center justify-center rounded-md bg-slate-900 text-white">
            <MessageSquare aria-hidden="true" size={19} />
          </span>
        </header>

        <div className="flex flex-1 flex-col justify-between gap-6 p-5">
          <div className="grid max-h-[360px] gap-3 overflow-y-auto pr-1">
            {visibleMessages.map((message) => (
              <article
                className={cn(
                  "max-w-[82%] rounded-md border border-[var(--border)] p-3",
                  message.senderType === "user"
                    ? "ml-auto bg-blue-600 text-white"
                    : "bg-slate-50 text-[var(--foreground)]",
                )}
                key={message.id}
              >
                <p
                  className={cn(
                    "text-xs font-medium uppercase tracking-normal",
                    message.senderType === "user"
                      ? "text-blue-100"
                      : "text-[var(--muted-foreground)]",
                  )}
                >
                  {message.senderType}
                </p>
                <p className="mt-2 whitespace-pre-wrap text-sm leading-6">
                  {message.contentMd}
                </p>
              </article>
            ))}

            {selectedSession && visibleMessages.length === 0 ? (
              <div className="rounded-md border border-[var(--border)] bg-slate-50 p-4">
                <p className="text-sm font-medium text-[var(--muted-foreground)]">
                  system
                </p>
                <p className="mt-2 text-base leading-7">
                  This session has its own worktree and is ready for the first
                  request.
                </p>
              </div>
            ) : null}

            {selectedSession && tasks.length > 0 ? (
              <TaskCardList
                artifactRefreshKey={lastEventSequence}
                backendUrl={backendUrl}
                busy={isPending}
                onCreateRun={handleCreateTaskRun}
                onInterruptRun={handleInterruptTaskRun}
                onRetryRun={handleRetryTaskRun}
                onRetryWithFallback={handleRetryTaskRunWithFallback}
                tasks={tasks}
              />
            ) : null}
          </div>

          {selectedSession ? (
            <div className="grid gap-4">
              <form className="flex gap-2" onSubmit={handleSendMessage}>
                <input
                  className="min-w-0 flex-1 rounded-md border border-[var(--border)] bg-white px-3 py-2 text-sm outline-none focus:border-blue-600"
                  onChange={(event) => setDraft(event.target.value)}
                  placeholder="@orchestrator build a login page"
                  type="text"
                  value={draft}
                />
                <Button disabled={isPending || draft.trim().length === 0} type="submit">
                  Send
                </Button>
              </form>

              <dl className="grid gap-3 rounded-md border border-[var(--border)] bg-white p-4 text-sm sm:grid-cols-3">
                <div>
                  <dt className="text-[var(--muted-foreground)]">Status</dt>
                  <dd className="mt-1 font-medium">{selectedSession.status}</dd>
                </div>
                <div>
                  <dt className="text-[var(--muted-foreground)]">Last message</dt>
                  <dd className="mt-1 font-medium">
                    {formatSessionTime(selectedSession.lastMessageAt)}
                  </dd>
                </div>
                <div className="min-w-0">
                  <dt className="text-[var(--muted-foreground)]">Worktree</dt>
                  <dd className="mt-1 truncate font-medium">
                    {selectedSession.worktreePath}
                  </dd>
                </div>
              </dl>
            </div>
          ) : null}
        </div>
      </div>
    </section>
  )
}
