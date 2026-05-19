"use client"

import {
  Bot,
  Check,
  Circle,
  CircleDot,
  GitBranch,
  MessageSquare,
  Plus,
  Radio,
  Send,
} from "lucide-react"
import { usePathname, useRouter, useSearchParams } from "next/navigation"
import {
  type FormEvent,
  type ReactNode,
  useCallback,
  useEffect,
  useMemo,
  useState,
  useTransition,
} from "react"

import { Button } from "@/components/ui/button"
import { PreviewPanel, type ArtifactPanelItem } from "@/components/preview-card"
import { TaskCardList } from "@/components/task-card-list"
import {
  approveTaskRun,
  createPreviewDeployment,
  createSessionMessage,
  createTaskRun,
  createWorkspaceSession,
  denyTaskRun,
  forceCodexFailure,
  interruptTaskRun,
  listTaskRunPreviews,
  listSessionMessages,
  listSessionTasks,
  retryTaskRun,
  retryTaskRunWithFallback,
  sessionEventsUrl,
  startTaskRunPreview,
  stopPreview,
  type ChatMessage,
  type PreviewArtifact,
  type SessionTask,
  type Workspace,
  type WorkspaceSession,
} from "@/lib/api"
import { formatCompactDateTime } from "@/lib/date-format"
import { cn } from "@/lib/utils"

type WorkspaceShellProps = {
  backendUrl: string
  healthSlot?: ReactNode
  workspace: Workspace | null
  initialSessions: WorkspaceSession[]
}

function formatSessionTime(value: string | null) {
  if (!value) {
    return "No messages"
  }

  return formatCompactDateTime(value)
}

export function WorkspaceShell({
  backendUrl,
  healthSlot,
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
  const [artifactRefreshVersion, setArtifactRefreshVersion] = useState(0)
  const [artifactItems, setArtifactItems] = useState<ArtifactPanelItem[]>([])
  const [selectedArtifactId, setSelectedArtifactId] = useState<string | null>(null)
  const [previewFrameKey, setPreviewFrameKey] = useState(0)

  const selectedSessionId = searchParams.get("session") ?? sessions[0]?.id ?? null
  const selectedSession = useMemo(
    () => sessions.find((session) => session.id === selectedSessionId) ?? null,
    [selectedSessionId, sessions],
  )
  const selectedArtifact =
    artifactItems.find((artifact) => artifact.id === selectedArtifactId) ?? null
  const selectedPreview =
    selectedArtifact?.kind === "preview" ? selectedArtifact.artifact : null
  const visibleMessages = selectedSessionId ? messages : []
  const hasRequirement = visibleMessages.some((message) => message.senderType === "user")
  const hasRunningTask = tasks.some((task) =>
    task.taskRuns.some((run) =>
      ["created", "queued", "streaming", "waiting_approval", "applying_changes"].includes(
        run.state,
      ),
    ),
  )
  const hasCompletedRun = tasks.some((task) =>
    task.taskRuns.some((run) => run.state === "completed"),
  )
  const hasRecoveredRun = tasks.some((task) =>
    task.taskRuns.some(
      (run) =>
        run.adapterType === "scripted_mock" &&
        (run.metricsJson.retryOfRunId || run.metricsJson.fallbackFromRunId),
    ),
  )

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
        if (nextTasks.length === 0) {
          setArtifactItems([])
          setSelectedArtifactId(null)
        }
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
    setArtifactItems([])
    setSelectedArtifactId(null)
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
    if (nextTasks.length === 0) {
      setArtifactItems([])
      setSelectedArtifactId(null)
    }
  }

  function refreshArtifacts() {
    setArtifactRefreshVersion((current) => current + 1)
  }

  function handleCreateTaskRun(taskId: string) {
    startTransition(async () => {
      await createTaskRun(backendUrl, taskId)
      await refreshSelectedTasks()
    })
  }

  function handleForceCodexFailure(taskId: string) {
    startTransition(async () => {
      await forceCodexFailure(backendUrl, taskId)
      await refreshSelectedTasks()
      refreshArtifacts()
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

  function handleApproveTaskRun(taskRunId: string) {
    startTransition(async () => {
      await approveTaskRun(backendUrl, taskRunId)
      await refreshSelectedTasks()
    })
  }

  function handleDenyTaskRun(taskRunId: string) {
    startTransition(async () => {
      await denyTaskRun(
        backendUrl,
        taskRunId,
        "User denied approval request from AgentHub UI.",
      )
      await refreshSelectedTasks()
    })
  }

  function handleOpenPreview(preview: PreviewArtifact) {
    setSelectedArtifactId(`preview:${preview.id}`)
    setPreviewFrameKey((current) => current + 1)
  }

  function handleRefreshPreviews(taskRunId: string) {
    startTransition(async () => {
      const previews = await listTaskRunPreviews(backendUrl, taskRunId)
      const latestPreview = previews[previews.length - 1] ?? null
      if (latestPreview && selectedPreview?.taskRunId === taskRunId) {
        setSelectedArtifactId(`preview:${latestPreview.id}`)
        setPreviewFrameKey((current) => current + 1)
      }
      refreshArtifacts()
    })
  }

  function handleStartPreview(taskRunId: string) {
    startTransition(async () => {
      const preview = await startTaskRunPreview(backendUrl, taskRunId)
      setSelectedArtifactId(`preview:${preview.id}`)
      setPreviewFrameKey((current) => current + 1)
      refreshArtifacts()
    })
  }

  function handleCreateDeployment(previewId: string) {
    startTransition(async () => {
      const deployment = await createPreviewDeployment(backendUrl, previewId)
      setSelectedArtifactId(`deployment:${deployment.id}`)
      refreshArtifacts()
    })
  }

  function handleStopPreview(previewId: string) {
    startTransition(async () => {
      await stopPreview(backendUrl, previewId)
      if (selectedPreview?.id === previewId) {
        setPreviewFrameKey((current) => current + 1)
      }
      refreshArtifacts()
    })
  }

  const handleArtifactsChange = useCallback((artifacts: ArtifactPanelItem[]) => {
    setArtifactItems(artifacts)
    setSelectedArtifactId((current) => {
      if (current && artifacts.some((artifact) => artifact.id === current)) {
        return current
      }

      return artifacts[artifacts.length - 1]?.id ?? null
    })
  }, [])

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
      <section className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-5">
        <h2 className="text-lg font-semibold">Workspace unavailable</h2>
        <p className="mt-3 text-sm leading-6 text-[var(--muted-foreground)]">
          Start the API and seed the SQLite database, then refresh AgentHub.
        </p>
      </section>
    )
  }

  return (
    <section
      className="grid h-screen grid-rows-[auto_minmax(0,1fr)] overflow-hidden bg-[var(--surface)] lg:grid-cols-[280px_minmax(0,1fr)_400px]"
      data-region="app-shell"
    >
      <header
        className="col-span-full border-b border-[var(--border)] bg-[var(--surface)] px-5 py-3"
        data-region="top-header"
      >
        <div className="flex flex-col gap-3 xl:flex-row xl:items-center xl:justify-between">
          <div className="flex items-center gap-3">
            <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-[var(--code-bg)] text-blue-400">
              <Radio aria-hidden="true" size={17} />
            </span>
            <div>
              <h1 className="text-lg font-bold text-[var(--primary-strong)]">
                AgentHub
              </h1>
              <p className="text-xs font-medium text-[var(--text-secondary)]">
                Coding Agent Command Center
              </p>
            </div>
          </div>

          <DemoPipeline
            hasCompletedRun={hasCompletedRun}
            hasRecoveredRun={hasRecoveredRun}
            hasRequirement={hasRequirement}
            hasRunningTask={hasRunningTask}
            hasTasks={tasks.length > 0}
          />

          <div className="flex items-center gap-3">{healthSlot}</div>
        </div>
      </header>

      <aside className="flex min-h-0 flex-col overflow-hidden border-b border-[var(--border)] bg-[#FBF9FF] lg:border-b-0 lg:border-r">
        <div className="shrink-0 p-4">
          <div className="rounded-lg bg-transparent p-2">
            <div className="flex items-start gap-3">
              <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-[var(--primary-soft)] text-[var(--primary)]">
                <GitBranch aria-hidden="true" size={18} />
              </span>
              <div className="min-w-0">
                <p className="text-[11px] font-bold uppercase tracking-normal text-[var(--text-muted)]">
                  Workspace
                </p>
                <h2 className="mt-1 truncate text-base font-semibold text-slate-950">
                  {workspace.name}
                </h2>
                <p className="mt-1 truncate font-mono text-xs text-[var(--muted-foreground)]">
                  {workspace.rootPath}
                </p>
              </div>
            </div>

            <div className="mt-4 grid grid-cols-2 gap-2 text-xs">
              <WorkspaceMeta label="Sessions" value={String(sessions.length)} />
              <WorkspaceMeta label="Current tasks" value={String(tasks.length)} />
            </div>
          </div>

          <Button
            className="mt-4 w-full"
            disabled={isPending}
            onClick={handleCreateSession}
            type="button"
          >
            <Plus aria-hidden="true" size={16} />
            New Session
          </Button>
        </div>

        <nav
          className="min-h-0 flex-1 overflow-y-auto px-3 pb-4"
          data-region="sidebar-scroll"
        >
          <div className="mb-2 px-1 text-[11px] font-bold uppercase tracking-normal text-[var(--text-muted)]">
            Recent Sessions
          </div>
          <div className="grid gap-1.5">
            {sessions.map((session) => {
              const selected = session.id === selectedSessionId
              const smoke = session.title.toLowerCase().includes("smoke")
              return (
                <button
                  className={cn(
                    "grid gap-1.5 rounded-lg border-r-4 p-2.5 text-left transition",
                    selected
                      ? "border-r-[var(--primary)] bg-[var(--primary-soft)]/80 text-slate-950 shadow-sm"
                      : "border-r-transparent bg-transparent text-slate-700 hover:bg-white/80",
                    smoke && !selected && "opacity-55",
                  )}
                  key={session.id}
                  onClick={() => selectSession(session.id)}
                  type="button"
                >
                  <span className="flex items-start justify-between gap-3">
                    <span className="min-w-0">
                      <span className="block truncate text-sm font-semibold">
                        {session.title}
                      </span>
                      <span className="mt-1 block truncate text-xs text-[var(--muted-foreground)]">
                        {formatSessionTime(session.lastMessageAt)}
                      </span>
                    </span>
                    {smoke && !selected ? null : <SessionStatusDot status={session.status} />}
                  </span>
                  {selected ? (
                    <span className="text-xs font-semibold text-[var(--primary)]">
                      {tasks.length} tasks in focus
                    </span>
                  ) : null}
                </button>
              )
            })}

            {sessions.length === 0 ? (
              <div className="rounded-md border border-dashed border-[var(--border)] bg-white p-4 text-sm text-[var(--muted-foreground)]">
                No sessions yet.
              </div>
            ) : null}
          </div>
        </nav>

        <div className="shrink-0 border-t border-[var(--border)] p-4 text-xs text-[var(--muted-foreground)]">
          <div className="flex items-center justify-between">
            <span>Docs</span>
            <span>API</span>
            <span>Support</span>
          </div>
        </div>
      </aside>

      <main className="flex min-h-0 flex-col overflow-hidden bg-white">
        <header className="shrink-0 border-b border-[var(--border)] px-5 py-3">
          <p className="text-[11px] font-bold uppercase tracking-normal text-[var(--text-muted)]">
            Current Session
          </p>
          <h2 className="mt-1 text-xl font-semibold text-slate-950">
            {selectedSession?.title ?? "No session selected"}
          </h2>
          <p className="mt-1 text-sm text-[var(--muted-foreground)]">
            {workspace.rootPath} · {tasks.length} tasks ·{" "}
            {hasCompletedRun ? "execution evidence available" : "waiting for run"}
          </p>
        </header>

        <div className="flex min-h-0 flex-1 flex-col gap-4 overflow-hidden bg-[#FDFBFF] p-5">
          <section
            className="min-h-0 flex-1 overflow-y-auto pr-1"
            data-region="center-scroll"
          >
            <div className="mx-auto grid max-w-3xl gap-4">
              {selectedSession && visibleMessages.length === 0 ? (
                <div className="rounded-xl border border-[var(--border)] bg-white p-5 shadow-sm">
                  <div className="flex items-start gap-3">
                    <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-[var(--primary)] text-white">
                      <Bot aria-hidden="true" size={16} />
                    </span>
                    <div>
                      <p className="text-sm font-semibold text-slate-950">
                        @orchestrator
                      </p>
                      <p className="mt-1 text-sm leading-6 text-[var(--text-secondary)]">
                        This session has its own worktree. Send a requirement to
                        generate the execution plan and task timeline.
                      </p>
                    </div>
                  </div>
                </div>
              ) : null}

              {visibleMessages.map((message) => (
                <MessageBubble message={message} key={message.id} />
              ))}

              {tasks.length > 0 ? (
                <OrchestratorPlanCard taskCount={tasks.length} />
              ) : null}

              {selectedSession && tasks.length > 0 ? (
                <section className="rounded-xl border border-[var(--border)] bg-white p-4 shadow-sm">
                  <div className="mb-4 flex items-center justify-between gap-3">
                    <div>
                      <p className="text-[11px] font-bold uppercase tracking-normal text-[var(--text-muted)]">
                        Agent Task Timeline
                      </p>
                      <h3 className="mt-1 text-base font-semibold text-slate-950">
                        Execution plan and controls
                      </h3>
                    </div>
                    <span className="rounded bg-white px-2 py-1 text-xs font-medium text-[var(--muted-foreground)]">
                      {tasks.length} tasks
                    </span>
                  </div>
                  <TaskCardList
                    artifactRefreshKey={lastEventSequence + artifactRefreshVersion}
                    backendUrl={backendUrl}
                    busy={isPending}
                    onApproveRun={handleApproveTaskRun}
                    onArtifactsChange={handleArtifactsChange}
                    onCreateRun={handleCreateTaskRun}
                    onDenyRun={handleDenyTaskRun}
                    onForceCodexFailure={handleForceCodexFailure}
                    onInterruptRun={handleInterruptTaskRun}
                    onRetryRun={handleRetryTaskRun}
                    onRetryWithFallback={handleRetryTaskRunWithFallback}
                    onSelectArtifact={setSelectedArtifactId}
                    onStartPreview={handleStartPreview}
                    selectedArtifactId={selectedArtifactId}
                    tasks={tasks}
                  />
                </section>
              ) : null}
            </div>
          </section>

          {selectedSession ? (
            <form
              className="mx-auto flex w-full max-w-3xl shrink-0 gap-2 rounded-xl border border-[var(--border)] bg-white p-2 shadow-sm"
              data-region="composer"
              onSubmit={handleSendMessage}
            >
              <div className="flex min-w-0 flex-1 items-center gap-2 rounded-lg bg-[var(--surface-muted)] px-3">
                <MessageSquare
                  aria-hidden="true"
                  className="shrink-0 text-[var(--muted-foreground)]"
                  size={16}
                />
                <input
                  className="min-w-0 flex-1 bg-transparent py-3 text-sm outline-none"
                  onChange={(event) => setDraft(event.target.value)}
                  placeholder="@orchestrator build a login page for the demo app"
                  type="text"
                  value={draft}
                />
              </div>
              <Button disabled={isPending || draft.trim().length === 0} type="submit">
                <Send aria-hidden="true" size={16} />
                Send
              </Button>
            </form>
          ) : null}
        </div>
      </main>

      <PreviewPanel
        artifactItems={artifactItems}
        busy={isPending}
        frameKey={previewFrameKey}
        onClose={() => setSelectedArtifactId(null)}
        onCreateDeploy={handleCreateDeployment}
        onOpenPreview={handleOpenPreview}
        onRefresh={handleRefreshPreviews}
        onSelectArtifact={setSelectedArtifactId}
        onStopPreview={handleStopPreview}
        selectedArtifactId={selectedArtifactId}
      />
    </section>
  )
}

function WorkspaceMeta({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded bg-[var(--surface-muted)] p-2">
      <p className="text-[11px] text-[var(--text-muted)]">{label}</p>
      <p className="mt-1 font-semibold text-slate-950">{value}</p>
    </div>
  )
}

function SessionStatusDot({ status }: { status: string }) {
  return (
    <span
      aria-label={status}
      className={cn(
        "mt-1 h-2.5 w-2.5 shrink-0 rounded-full",
        status === "active" ? "bg-blue-600" : "bg-slate-300",
      )}
    />
  )
}

function MessageBubble({ message }: { message: ChatMessage }) {
  const isUser = message.senderType === "user"
  return (
    <article className={cn("flex gap-3", isUser ? "justify-end" : "justify-start")}>
      {!isUser ? (
        <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-[var(--primary-soft)] text-[var(--primary)]">
          <Bot aria-hidden="true" size={16} />
        </span>
      ) : null}
      <div
        className={cn(
          "max-w-[82%] rounded-xl px-4 py-3 text-sm leading-6",
          isUser
            ? "bg-[var(--primary)] text-white"
            : "border border-[var(--border)] bg-white text-slate-800",
        )}
      >
        <p
          className={cn(
            "mb-1 text-[11px] font-bold uppercase tracking-normal",
            isUser ? "text-indigo-100" : "text-[var(--text-muted)]",
          )}
        >
          {message.senderType}
        </p>
        <p className="whitespace-pre-wrap">{message.contentMd}</p>
      </div>
    </article>
  )
}

function OrchestratorPlanCard({ taskCount }: { taskCount: number }) {
  return (
    <section className="rounded-xl border border-indigo-200 bg-indigo-50/70 p-4 shadow-sm">
      <div className="flex items-start gap-3">
        <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-white text-[var(--primary)]">
          <Bot aria-hidden="true" size={17} />
        </span>
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <p className="font-mono text-sm font-semibold text-[var(--primary-strong)]">
              @orchestrator
            </p>
            <span className="rounded bg-white/80 px-2 py-1 text-[11px] font-bold uppercase tracking-normal text-[var(--primary)]">
              Planning complete
            </span>
          </div>
          <p className="mt-2 text-sm leading-6 text-slate-800">
            Generated a command-center execution plan with {taskCount} tasks.
            Use the timeline below to start runs, recover failures, inspect diff
            evidence, launch preview, and create a mock deploy card.
          </p>
        </div>
      </div>
    </section>
  )
}

function DemoPipeline({
  hasCompletedRun,
  hasRecoveredRun,
  hasRequirement,
  hasRunningTask,
  hasTasks,
}: {
  hasCompletedRun: boolean
  hasRecoveredRun: boolean
  hasRequirement: boolean
  hasRunningTask: boolean
  hasTasks: boolean
}) {
  const stages = [
    { label: "Requirement", state: hasRequirement ? "complete" : "pending" },
    { label: "Plan", state: hasTasks ? "complete" : "pending" },
    {
      label: "Run",
      state: hasRecoveredRun
        ? "recovered"
        : hasCompletedRun
          ? "complete"
          : hasRunningTask
            ? "running"
            : "pending",
    },
    { label: "Diff", state: hasCompletedRun ? "ready" : "pending" },
    { label: "Preview", state: "pending" },
    { label: "Deploy", state: "pending" },
  ]

  return (
    <div className="flex flex-col items-start gap-1 xl:items-center">
      <p className="text-[11px] font-bold uppercase tracking-normal text-[var(--text-muted)]">
        Demo flow
      </p>
      <ol className="flex flex-wrap items-center gap-1.5 text-xs font-semibold">
        {stages.map((stage, index) => (
          <li className="flex items-center gap-1.5" key={stage.label}>
            <span
              className={cn(
                "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1.5",
                stage.state === "complete" &&
                  "border-emerald-200 bg-emerald-50 text-emerald-700",
                stage.state === "ready" && "border-cyan-200 bg-cyan-50 text-cyan-700",
                stage.state === "running" && "border-blue-200 bg-blue-50 text-blue-700",
                stage.state === "recovered" &&
                  "border-purple-200 bg-purple-50 text-purple-700",
                stage.state === "pending" && "border-transparent text-slate-500",
              )}
            >
              {stage.state === "pending" ? (
                <Circle aria-hidden="true" size={12} />
              ) : stage.state === "running" ? (
                <CircleDot aria-hidden="true" size={12} />
              ) : (
                <Check aria-hidden="true" size={12} />
              )}
              {stage.label}
            </span>
            {index < stages.length - 1 ? (
              <span className="text-slate-300" aria-hidden="true">
                -
              </span>
            ) : null}
          </li>
        ))}
      </ol>
    </div>
  )
}
