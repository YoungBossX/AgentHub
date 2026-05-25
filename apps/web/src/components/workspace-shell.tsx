"use client"

import {
  Check,
  Circle,
  CircleDot,
  Radio,
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

import { ArtifactPanel } from "@/components/artifact-panel"
import { ChatThread } from "@/components/chat-thread"
import { MessageComposer } from "@/components/message-composer"
import { MissionPanel } from "@/components/mission-panel"
import { type ArtifactPanelItem } from "@/components/preview-card"
import { SessionSidebar } from "@/components/session-sidebar"
import { TaskCardList } from "@/components/task-card-list"
import {
  approveTaskRun,
  createPreviewDeployment,
  createSessionMessage,
  createTaskRun,
  createTaskRunReview,
  createWorkspaceSession,
  denyTaskRun,
  forceCodexFailure,
  getSessionLedger,
  interruptTaskRun,
  listTaskRunPreviews,
  listSessionMessages,
  listSessionTasks,
  retryTaskRun,
  retryTaskRunWithFallback,
  sessionEventsUrl,
  startTaskRunPreview,
  stopPreview,
  type AgentContact,
  type ChatMessage,
  type PreviewArtifact,
  type SessionExecutionLedger,
  type SessionTask,
  type Workspace,
  type WorkspaceSession,
} from "@/lib/api"
import { cn } from "@/lib/utils"

type WorkspaceShellProps = {
  backendUrl: string
  healthSlot?: ReactNode
  workspace: Workspace | null
  initialAgents: AgentContact[]
  initialSessions: WorkspaceSession[]
}

export function WorkspaceShell({
  backendUrl,
  healthSlot,
  workspace,
  initialAgents,
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
  const [contextArtifactId, setContextArtifactId] = useState<string | null>(null)
  const [previewFrameKey, setPreviewFrameKey] = useState(0)
  const [syncError, setSyncError] = useState<string | null>(null)
  const [ledger, setLedger] = useState<SessionExecutionLedger | null>(null)
  const [agentMode, setAgentMode] = useState<"direct" | "group">("group")
  const [selectedAgentId, setSelectedAgentId] = useState<string | null>(
    initialAgents[0]?.id ?? null,
  )

  const selectedSessionId = searchParams.get("session") ?? sessions[0]?.id ?? null
  const selectedSession = useMemo(
    () => sessions.find((session) => session.id === selectedSessionId) ?? null,
    [selectedSessionId, sessions],
  )
  const selectedArtifact =
    artifactItems.find((artifact) => artifact.id === selectedArtifactId) ?? null
  const contextArtifact =
    artifactItems.find((artifact) => artifact.id === contextArtifactId) ?? null
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
  const reportSyncError = useCallback(
    (action: string, error: unknown) => {
      void error
      setSyncError(
        `${action}。请确认 FastAPI 后端可访问：${backendUrl}。`,
      )
    },
    [backendUrl],
  )

  const runClientAction = useCallback(
    (action: () => Promise<void>, failureMessage: string) => {
      startTransition(() => {
        void action().catch((error) => reportSyncError(failureMessage, error))
      })
    },
    [reportSyncError, startTransition],
  )

  const refreshLedger = useCallback(async () => {
    if (!selectedSessionId) {
      setLedger(null)
      return
    }
    const nextLedger = await getSessionLedger(backendUrl, selectedSessionId)
    setLedger(nextLedger)
  }, [backendUrl, selectedSessionId])

  useEffect(() => {
    if (!selectedSessionId) {
      return
    }

    let cancelled = false
    Promise.all([
      listSessionMessages(backendUrl, selectedSessionId),
      getSessionLedger(backendUrl, selectedSessionId),
    ])
      .then(([nextMessages, nextLedger]) => {
        if (!cancelled) {
          setMessages(nextMessages)
          setLedger(nextLedger)
          setSyncError(null)
        }
      })
      .catch((error) => {
        if (!cancelled) {
        reportSyncError("无法加载会话消息", error)
        }
      })

    return () => {
      cancelled = true
    }
  }, [backendUrl, reportSyncError, selectedSessionId])

  useEffect(() => {
    if (!selectedSessionId) {
      return
    }

    let cancelled = false
    listSessionTasks(backendUrl, selectedSessionId)
      .then((nextTasks) => {
        if (!cancelled) {
          setTasks(nextTasks)
          setSyncError(null)
          if (nextTasks.length === 0) {
            setArtifactItems([])
            setSelectedArtifactId(null)
          }
        }
      })
      .catch((error) => {
        if (!cancelled) {
          reportSyncError("无法加载会话任务", error)
        }
      })

    return () => {
      cancelled = true
    }
  }, [backendUrl, reportSyncError, selectedSessionId])

  useEffect(() => {
    if (!selectedSessionId) {
      return
    }

    const source = new EventSource(
      sessionEventsUrl(backendUrl, selectedSessionId, lastEventSequence),
    )
    source.onmessage = (event) => {
      try {
        const payload = JSON.parse(event.data) as { sequence?: number }
        if (typeof payload.sequence === "number") {
          setLastEventSequence((current) => Math.max(current, payload.sequence ?? 0))
        }
      } catch (error) {
        reportSyncError("无法解析会话事件", error)
        return
      }
      listSessionTasks(backendUrl, selectedSessionId)
        .then((nextTasks) => {
          setTasks(nextTasks)
          setSyncError(null)
          void refreshLedger().catch((error) =>
            reportSyncError("无法刷新工作区上下文", error),
          )
        })
        .catch((error) => reportSyncError("无法刷新任务时间线", error))
    }
    source.onerror = () => {
      source.close()
    }

    return () => {
      source.close()
    }
  }, [backendUrl, lastEventSequence, refreshLedger, reportSyncError, selectedSessionId])

  function selectSession(sessionId: string) {
    setSyncError(null)
    setArtifactItems([])
    setSelectedArtifactId(null)
    setLedger(null)
    const params = new URLSearchParams(searchParams.toString())
    params.set("session", sessionId)
    router.replace(`${pathname}?${params.toString()}`)
  }

  function handleCreateSession() {
    if (!workspace) {
      return
    }

    const title = `会话 ${sessions.length + 1}`
    runClientAction(async () => {
      const created = await createWorkspaceSession(backendUrl, workspace.id, title)
      setSessions((current) => [created, ...current])
      const params = new URLSearchParams(searchParams.toString())
      params.set("session", created.id)
      router.replace(`${pathname}?${params.toString()}`)
      setSyncError(null)
    }, "无法创建会话")
  }

  async function refreshSelectedTasks() {
    if (!selectedSessionId) {
      return
    }
    try {
      const nextTasks = await listSessionTasks(backendUrl, selectedSessionId)
      setTasks(nextTasks)
      await refreshLedger()
      setSyncError(null)
      if (nextTasks.length === 0) {
        setArtifactItems([])
        setSelectedArtifactId(null)
      }
    } catch (error) {
      reportSyncError("无法刷新任务时间线", error)
    }
  }

  function refreshArtifacts() {
    setArtifactRefreshVersion((current) => current + 1)
  }

  function handleCreateTaskRun(taskId: string) {
    runClientAction(async () => {
      await createTaskRun(backendUrl, taskId)
      await refreshSelectedTasks()
    }, "无法启动任务运行")
  }

  function handleForceCodexFailure(taskId: string) {
    runClientAction(async () => {
      await forceCodexFailure(backendUrl, taskId)
      await refreshSelectedTasks()
      refreshArtifacts()
    }, "无法模拟 Codex 失败")
  }

  function handleInterruptTaskRun(taskRunId: string) {
    runClientAction(async () => {
      await interruptTaskRun(backendUrl, taskRunId)
      await refreshSelectedTasks()
    }, "无法中断任务运行")
  }

  function handleRetryTaskRun(taskRunId: string) {
    runClientAction(async () => {
      await retryTaskRun(backendUrl, taskRunId)
      await refreshSelectedTasks()
    }, "无法重试任务运行")
  }

  function handleRetryTaskRunWithFallback(taskRunId: string) {
    runClientAction(async () => {
      await retryTaskRunWithFallback(backendUrl, taskRunId)
      await refreshSelectedTasks()
    }, "无法使用 ScriptedMockAdapter 兜底重试")
  }

  function handleApproveTaskRun(taskRunId: string) {
    runClientAction(async () => {
      await approveTaskRun(backendUrl, taskRunId)
      await refreshSelectedTasks()
    }, "无法批准任务运行")
  }

  function handleDenyTaskRun(taskRunId: string) {
    runClientAction(async () => {
      await denyTaskRun(
        backendUrl,
        taskRunId,
        "用户已在 AgentHub 界面拒绝审批请求。",
      )
      await refreshSelectedTasks()
    }, "无法拒绝任务运行")
  }

  function handleOpenPreview(preview: PreviewArtifact) {
    setSelectedArtifactId(`preview:${preview.id}`)
    setPreviewFrameKey((current) => current + 1)
  }

  function handleRefreshPreviews(taskRunId: string) {
    runClientAction(async () => {
      const previews = await listTaskRunPreviews(backendUrl, taskRunId)
      const latestPreview = previews[previews.length - 1] ?? null
      if (latestPreview && selectedPreview?.taskRunId === taskRunId) {
        setSelectedArtifactId(`preview:${latestPreview.id}`)
        setPreviewFrameKey((current) => current + 1)
      }
      await refreshLedger()
      refreshArtifacts()
      setSyncError(null)
    }, "无法刷新预览")
  }

  function handleStartPreview(taskRunId: string) {
    runClientAction(async () => {
      const preview = await startTaskRunPreview(backendUrl, taskRunId)
      setSelectedArtifactId(`preview:${preview.id}`)
      setPreviewFrameKey((current) => current + 1)
      await refreshLedger()
      refreshArtifacts()
      setSyncError(null)
    }, "无法启动预览")
  }

  function handleCreateReview(taskRunId: string) {
    runClientAction(async () => {
      const review = await createTaskRunReview(backendUrl, taskRunId)
      setSelectedArtifactId(`review:${review.id}`)
      await refreshLedger()
      refreshArtifacts()
      setSyncError(null)
    }, "无法创建评审产物")
  }

  function handleCreateDeployment(previewId: string) {
    runClientAction(async () => {
      const deployment = await createPreviewDeployment(backendUrl, previewId)
      setSelectedArtifactId(`deployment:${deployment.id}`)
      await refreshLedger()
      refreshArtifacts()
      setSyncError(null)
    }, "无法创建部署卡片")
  }

  function handleStopPreview(previewId: string) {
    runClientAction(async () => {
      await stopPreview(backendUrl, previewId)
      if (selectedPreview?.id === previewId) {
        setPreviewFrameKey((current) => current + 1)
      }
      refreshArtifacts()
      setSyncError(null)
    }, "无法停止预览")
  }

  const handleArtifactsChange = useCallback((artifacts: ArtifactPanelItem[]) => {
    setArtifactItems(artifacts)
    setSelectedArtifactId((current) => {
      if (current && artifacts.some((artifact) => artifact.id === current)) {
        return current
      }

      return artifacts[artifacts.length - 1]?.id ?? null
    })
    setContextArtifactId((current) => {
      if (current && artifacts.some((artifact) => artifact.id === current)) {
        return current
      }

      return null
    })
  }, [])

  function handleUseArtifactContext(artifact: ArtifactPanelItem) {
    setContextArtifactId(artifact.id)
    setSelectedArtifactId(artifact.id)
  }

  function handleQuoteMessage(message: ChatMessage) {
    setDraft((current) => {
      const quote = `> ${message.contentMd}`
      return current.trim() ? `${current}\n${quote}` : quote
    })
  }

  function handleSendMessage(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!selectedSessionId || draft.trim().length === 0) {
      return
    }

    const content = draft.trim()
    setDraft("")
    runClientAction(async () => {
      const created = await createSessionMessage(backendUrl, selectedSessionId, content)
      const nextTasks = await listSessionTasks(backendUrl, selectedSessionId)
      setMessages((current) => [...current, created])
      setTasks(nextTasks)
      await refreshLedger()
      setSessions((current) =>
        current.map((session) =>
          session.id === selectedSessionId
            ? { ...session, lastMessageAt: created.createdAt }
            : session,
        ),
      )
      setSyncError(null)
    }, "无法发送消息")
  }

  if (!workspace) {
    return (
      <section className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-5">
        <h2 className="text-lg font-semibold">工作区不可用</h2>
        <p className="mt-3 text-sm leading-6 text-[var(--muted-foreground)]">
          请先启动 API 并初始化 SQLite 数据库，然后刷新 AgentHub。
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
                代码 Agent 指挥中心
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

      <SessionSidebar
        agents={initialAgents}
        isPending={isPending}
        mode={agentMode}
        onCreateSession={handleCreateSession}
        onModeChange={setAgentMode}
        onSelectAgent={setSelectedAgentId}
        onSelectSession={selectSession}
        selectedAgentId={selectedAgentId}
        selectedSessionId={selectedSessionId}
        sessions={sessions}
        taskCount={tasks.length}
        workspace={workspace}
      />

      <main className="flex min-h-0 flex-col overflow-hidden bg-white">
        <header className="shrink-0 border-b border-[var(--border)] px-5 py-3">
          <p className="text-[11px] font-bold uppercase tracking-normal text-[var(--text-muted)]">
            当前会话
          </p>
          <h2 className="mt-1 text-xl font-semibold text-slate-950">
            {selectedSession?.title ?? "未选择会话"}
          </h2>
          <p className="mt-1 text-sm text-[var(--muted-foreground)]">
            {workspace.rootPath} · {tasks.length} 个任务 ·{" "}
            {hasCompletedRun ? "已有执行证据" : "等待运行"}
          </p>
        </header>

        <div className="flex min-h-0 flex-1 flex-col gap-4 overflow-hidden bg-[#FDFBFF] p-5">
          {syncError ? (
            <div
              className="mx-auto w-full max-w-3xl rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-900"
              role="alert"
            >
              {syncError}
            </div>
          ) : null}

          {selectedSession ? <MissionPanel ledger={ledger} /> : null}

          <ChatThread
            messages={visibleMessages}
            onQuoteMessage={handleQuoteMessage}
            selectedSession={selectedSession}
            taskCount={tasks.length}
            taskListSlot={
              selectedSession && tasks.length > 0 ? (
                <section className="rounded-xl border border-[var(--border)] bg-white p-4 shadow-sm">
                  <div className="mb-4 flex items-center justify-between gap-3">
                    <div>
                      <p className="text-[11px] font-bold uppercase tracking-normal text-[var(--text-muted)]">
                        Agent 任务时间线
                      </p>
                      <h3 className="mt-1 text-base font-semibold text-slate-950">
                        执行计划与操作
                      </h3>
                    </div>
                    <span className="rounded bg-white px-2 py-1 text-xs font-medium text-[var(--muted-foreground)]">
                      {tasks.length} 个任务
                    </span>
                  </div>
                  <TaskCardList
                    artifactRefreshKey={lastEventSequence + artifactRefreshVersion}
                    backendUrl={backendUrl}
                    busy={isPending}
                    onApproveRun={handleApproveTaskRun}
                    onArtifactsChange={handleArtifactsChange}
                    onCreateDeploy={handleCreateDeployment}
                    onCreateReview={handleCreateReview}
                    onCreateRun={handleCreateTaskRun}
                    onDenyRun={handleDenyTaskRun}
                    onForceCodexFailure={handleForceCodexFailure}
                    onInterruptRun={handleInterruptTaskRun}
                    onOpenPreview={handleOpenPreview}
                    onRetryRun={handleRetryTaskRun}
                    onRetryWithFallback={handleRetryTaskRunWithFallback}
                    onSelectArtifact={setSelectedArtifactId}
                    onStartPreview={handleStartPreview}
                    onUseArtifactContext={handleUseArtifactContext}
                    selectedArtifactId={selectedArtifactId}
                    tasks={tasks}
                  />
                </section>
              ) : null
            }
          />

          {selectedSession ? (
            <MessageComposer
              contextArtifact={contextArtifact}
              draft={draft}
              isPending={isPending}
              onClearContext={() => setContextArtifactId(null)}
              onDraftChange={setDraft}
              onSubmit={handleSendMessage}
            />
          ) : null}
        </div>
      </main>

      <ArtifactPanel
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
    { label: "需求", state: hasRequirement ? "complete" : "pending" },
    { label: "计划", state: hasTasks ? "complete" : "pending" },
    {
      label: "运行",
      state: hasRecoveredRun
        ? "recovered"
        : hasCompletedRun
          ? "complete"
          : hasRunningTask
            ? "running"
            : "pending",
    },
    { label: "Diff", state: hasCompletedRun ? "ready" : "pending" },
    { label: "预览", state: "pending" },
    { label: "部署", state: "pending" },
  ]

  return (
    <div className="flex flex-col items-start gap-1 xl:items-center">
      <p className="text-[11px] font-bold uppercase tracking-normal text-[var(--text-muted)]">
        演示流程
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
