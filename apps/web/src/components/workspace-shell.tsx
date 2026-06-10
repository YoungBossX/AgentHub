"use client"

import {
  Check,
  Circle,
  CircleDot,
  Radio,
  UserRound,
  Users,
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
import {
  buildComposerMessageContext,
  contextItemFromArtifact,
  contextItemFromMessage,
  type ComposerContextItem,
  MessageComposer,
} from "@/components/message-composer"
import { type ArtifactPanelItem } from "@/components/preview-card"
import { SessionSidebar } from "@/components/session-sidebar"
import { type ArtifactContextIntent, TaskCardList } from "@/components/task-card-list"
import {
  approveTaskRun,
  createPreviewDeployment,
  createSessionMessage,
  createTaskRun,
  createTaskRunReview,
  createWorkspaceSession,
  decideTaskPlan,
  denyTaskRun,
  forceCodexFailure,
  getSessionArtifactWorkbench,
  interruptTaskRun,
  listTaskRunPreviews,
  listSessionMessages,
  listSessionTasks,
  retryTaskRun,
  retryTaskRunWithFallback,
  saveArtifactWorkbenchEdit,
  sessionEventsUrl,
  startTaskRunPreview,
  stopPreview,
  ApiRequestError,
  type ArtifactWorkbenchArtifact,
  type AgentContact,
  type ChatMessage,
  type PreviewArtifact,
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
  const [evidenceArtifactItems, setEvidenceArtifactItems] = useState<ArtifactPanelItem[]>([])
  const [workbenchArtifacts, setWorkbenchArtifacts] = useState<ArtifactWorkbenchArtifact[]>([])
  const [selectedArtifactId, setSelectedArtifactId] = useState<string | null>(null)
  const [contextItems, setContextItems] = useState<ComposerContextItem[]>([])
  const [conversationMode, setConversationMode] = useState<"direct" | "group">("group")
  const [previewFrameKey, setPreviewFrameKey] = useState(0)
  const [syncError, setSyncError] = useState<string | null>(null)

  const selectedSessionId = searchParams.get("session") ?? sessions[0]?.id ?? null
  const selectedSession = useMemo(
    () => sessions.find((session) => session.id === selectedSessionId) ?? null,
    [selectedSessionId, sessions],
  )
  const artifactItems = useMemo(
    () => mergeArtifactPanelItems(evidenceArtifactItems, workbenchArtifacts),
    [evidenceArtifactItems, workbenchArtifacts],
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
  const reportSyncError = useCallback(
    (action: string, error: unknown) => {
      const detail = error instanceof ApiRequestError ? error.message : null
      setSyncError(
        detail && detail.trim().length > 0
          ? `${action}：${detail}`
          : `${action}。请确认 FastAPI 后端可访问：${backendUrl}。`,
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

  useEffect(() => {
    if (!selectedSessionId) {
      return
    }

    let cancelled = false
    listSessionMessages(backendUrl, selectedSessionId)
      .then((nextMessages) => {
        if (!cancelled) {
          setMessages(nextMessages)
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
    getSessionArtifactWorkbench(backendUrl, selectedSessionId)
      .then((workbench) => {
        if (!cancelled) {
          setWorkbenchArtifacts(workbench.artifacts)
          setSyncError(null)
        }
      })
      .catch((error) => {
        if (!cancelled) {
          reportSyncError("无法加载产物工作台", error)
        }
      })

    return () => {
      cancelled = true
    }
  }, [artifactRefreshVersion, backendUrl, reportSyncError, selectedSessionId])

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
            setEvidenceArtifactItems([])
            setWorkbenchArtifacts([])
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
        })
        .catch((error) => reportSyncError("无法刷新任务时间线", error))
    }
    source.onerror = () => {
      source.close()
    }

    return () => {
      source.close()
    }
  }, [backendUrl, lastEventSequence, reportSyncError, selectedSessionId])

  function selectSession(sessionId: string) {
    setSyncError(null)
    setEvidenceArtifactItems([])
    setWorkbenchArtifacts([])
    setSelectedArtifactId(null)
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
      setSyncError(null)
      if (nextTasks.length === 0) {
        setEvidenceArtifactItems([])
        setWorkbenchArtifacts([])
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

  function handleApprovePlan(taskId: string) {
    runClientAction(async () => {
      await decideTaskPlan(
        backendUrl,
        taskId,
        "approve",
        "用户已在 AgentHub 界面批准 PMO 计划。",
      )
      await refreshSelectedTasks()
    }, "无法批准 PMO 计划")
  }

  function handleRejectPlan(taskId: string) {
    runClientAction(async () => {
      await decideTaskPlan(
        backendUrl,
        taskId,
        "reject",
        "用户已在 AgentHub 界面拒绝 PMO 计划。",
      )
      await refreshSelectedTasks()
    }, "无法拒绝 PMO 计划")
  }

  function handleRequestPlanClarification(taskId: string) {
    runClientAction(async () => {
      await decideTaskPlan(
        backendUrl,
        taskId,
        "clarification",
        "用户要求 Main Agent 先澄清计划。",
      )
      await refreshSelectedTasks()
    }, "无法请求 PMO 澄清")
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
      refreshArtifacts()
      setSyncError(null)
    }, "无法刷新预览")
  }

  function handleStartPreview(taskRunId: string) {
    runClientAction(async () => {
      const preview = await startTaskRunPreview(backendUrl, taskRunId)
      setSelectedArtifactId(`preview:${preview.id}`)
      setPreviewFrameKey((current) => current + 1)
      refreshArtifacts()
      setSyncError(null)
    }, "无法启动预览")
  }

  function handleCreateReview(taskRunId: string) {
    runClientAction(async () => {
      const review = await createTaskRunReview(backendUrl, taskRunId)
      setSelectedArtifactId(`review:${review.id}`)
      refreshArtifacts()
      setSyncError(null)
    }, "无法创建评审产物")
  }

  function handleCreateDeployment(previewId: string) {
    runClientAction(async () => {
      const deployment = await createPreviewDeployment(backendUrl, previewId)
      setSelectedArtifactId(`deployment:${deployment.id}`)
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

  function handleSaveArtifactEdit(artifactId: string, contentMd: string, summary: string) {
    runClientAction(async () => {
      await saveArtifactWorkbenchEdit(backendUrl, artifactId, {
        contentMd,
        summary,
      })
      refreshArtifacts()
      setSelectedArtifactId(`workbench:${artifactId}`)
      setSyncError(null)
    }, "无法保存产物版本")
  }

  const handleArtifactsChange = useCallback((artifacts: ArtifactPanelItem[]) => {
    setEvidenceArtifactItems(artifacts)
    setSelectedArtifactId((current) => {
      if (current && artifacts.some((artifact) => artifact.id === current)) {
        return current
      }

      return artifacts[artifacts.length - 1]?.id ?? null
    })
    setContextItems((current) =>
      current.filter(
        (item) => !item.artifact || artifacts.some((artifact) => artifact.id === item.id),
      ),
    )
  }, [])

  function handleUseArtifactContext(
    artifact: ArtifactPanelItem,
    intent?: ArtifactContextIntent,
  ) {
    setContextItems((current) => appendContextItem(current, contextItemFromArtifact(artifact)))
    setSelectedArtifactId(artifact.id)
    if (intent) {
      setDraft(contextIntentDraft(intent))
    }
  }

  function handleQuoteMessage(message: ChatMessage) {
    setContextItems((current) => appendContextItem(current, contextItemFromMessage(message)))
  }

  function handleSendMessage(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!selectedSessionId || draft.trim().length === 0) {
      return
    }

    const content = draft.trim()
    setDraft("")
    runClientAction(async () => {
      const created = await createSessionMessage(
        backendUrl,
        selectedSessionId,
        content,
        fetch,
        buildComposerMessageContext(contextItems),
      )
      const [nextMessages, nextTasks] = await Promise.all([
        listSessionMessages(backendUrl, selectedSessionId),
        listSessionTasks(backendUrl, selectedSessionId),
      ])
      setMessages((current) =>
        nextMessages.length > 0 ? nextMessages : [...current, created],
      )
      setTasks(nextTasks)
      setSessions((current) =>
        current.map((session) =>
          session.id === selectedSessionId
            ? { ...session, lastMessageAt: created.createdAt }
            : session,
        ),
      )
      setContextItems([])
      setSyncError(null)
    }, "无法发送消息")
  }

  if (!workspace) {
    return (
      <section className="m-4 rounded-lg border border-[var(--border)] bg-[var(--surface)] p-5 shadow-sm">
        <h2 className="text-lg font-semibold">工作区不可用</h2>
        <p className="mt-3 text-sm leading-6 text-[var(--muted-foreground)]">
          请先启动 API 并初始化 SQLite 数据库，然后刷新 AgentHub。
        </p>
      </section>
    )
  }

  return (
    <section
      className="h-screen overflow-hidden bg-[var(--background)] p-3 sm:p-4 lg:p-6"
      data-region="app-shell"
    >
      <div className="grid h-full min-h-0 overflow-hidden rounded-[28px] bg-white shadow-[0_28px_80px_rgba(15,23,42,0.18)] ring-1 ring-white/70 lg:grid-cols-[310px_minmax(0,1fr)_420px]">
        <SessionSidebar
          agents={initialAgents}
          isPending={isPending}
          onCreateSession={handleCreateSession}
          onSelectSession={selectSession}
          selectedSessionId={selectedSessionId}
          sessions={sessions}
          taskCount={tasks.length}
          workspace={workspace}
        />

        <main className="flex min-h-0 flex-col overflow-hidden bg-[#fbfcfc]">
          <header
            className="shrink-0 border-b border-[var(--border)] bg-white/95 px-5 py-4"
            data-region="top-header"
          >
            <div className="rounded-lg border border-[var(--border)] bg-white px-4 py-3 shadow-sm">
              <div className="flex items-center justify-between gap-3">
                <div className="flex min-w-0 flex-wrap items-center gap-2 text-sm">
                  <span className="font-semibold text-[var(--text-muted)]">
                    AgentHub
                  </span>
                  <span className="text-slate-300">›</span>
                  <span className="inline-flex shrink-0 items-center gap-1.5 font-semibold text-slate-950">
                    <Radio aria-hidden="true" size={15} />
                    当前会话
                  </span>
                </div>
                <div className="hidden shrink-0 sm:flex">{healthSlot}</div>
              </div>

              <div className="mt-5 flex flex-col gap-4">
                <div className="min-w-0">
                  <h2 className="text-xl font-semibold leading-tight text-slate-950 xl:text-2xl">
                    {selectedSession?.title ?? "未选择会话"}
                  </h2>
                  <p className="mt-2 truncate text-sm text-[var(--muted-foreground)]">
                    {tasks.length} 个任务 · {hasCompletedRun ? "已有执行证据" : "等待运行"}
                  </p>
                </div>

                <ConversationModeSwitch
                  mode={conversationMode}
                  onModeChange={setConversationMode}
                />

                <DemoPipeline
                  hasCompletedRun={hasCompletedRun}
                  hasRecoveredRun={hasRecoveredRun}
                  hasRequirement={hasRequirement}
                  hasRunningTask={hasRunningTask}
                  hasTasks={tasks.length > 0}
                />
                <div className="sm:hidden">{healthSlot}</div>
              </div>
            </div>
          </header>

          <div className="flex min-h-0 flex-1 flex-col gap-4 overflow-hidden bg-[#fbfcfc] p-5">
            {syncError ? (
              <div
                className="mx-auto w-full max-w-4xl rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-900 shadow-sm"
                role="alert"
              >
                {syncError}
              </div>
            ) : null}

            <ChatThread
              messages={visibleMessages}
              onQuoteMessage={handleQuoteMessage}
              selectedSession={selectedSession}
              taskCount={tasks.length}
              taskListSlot={
                selectedSession && tasks.length > 0 ? (
                  <section className="py-2">
                    <div className="mb-4 flex items-center justify-between gap-3">
                      <div>
                        <p className="text-[11px] font-bold uppercase tracking-normal text-[var(--text-muted)]">
                          Agent 任务时间线
                        </p>
                        <h3 className="mt-1 text-base font-semibold text-slate-950">
                          执行计划与操作
                        </h3>
                      </div>
                      <span className="rounded-full border border-[var(--border)] bg-white px-3 py-1 text-xs font-semibold text-[var(--muted-foreground)] shadow-sm">
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
                      onApprovePlan={handleApprovePlan}
                      onRejectPlan={handleRejectPlan}
                      onRequestClarification={handleRequestPlanClarification}
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
                contextItems={contextItems}
                draft={draft}
                isPending={isPending}
                onClearContext={() => setContextItems([])}
                onDraftChange={setDraft}
                onMoveContextItem={(itemId, direction) =>
                  setContextItems((current) => moveContextItem(current, itemId, direction))
                }
                onRemoveContextItem={(itemId) =>
                  setContextItems((current) => removeContextItem(current, itemId))
                }
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
          onSaveArtifactEdit={handleSaveArtifactEdit}
          onSelectArtifact={setSelectedArtifactId}
          onStopPreview={handleStopPreview}
          selectedArtifactId={selectedArtifactId}
        />
      </div>
    </section>
  )
}

function ConversationModeSwitch({
  mode,
  onModeChange,
}: {
  mode: "direct" | "group"
  onModeChange: (mode: "direct" | "group") => void
}) {
  return (
    <section className="flex justify-end rounded-lg border border-[var(--border)] bg-[var(--surface-muted)] px-3 py-2">
      <div className="grid grid-cols-2 rounded-full bg-white p-1 shadow-sm">
        <button
          aria-pressed={mode === "direct"}
          className={cn(
            "inline-flex min-h-8 items-center justify-center gap-1.5 rounded-full px-3 text-xs font-semibold transition",
            mode === "direct"
              ? "bg-slate-950 text-white"
              : "text-slate-600 hover:bg-slate-100",
          )}
          onClick={() => onModeChange("direct")}
          type="button"
        >
          <UserRound aria-hidden="true" size={14} />
          单聊
        </button>
        <button
          aria-pressed={mode === "group"}
          className={cn(
            "inline-flex min-h-8 items-center justify-center gap-1.5 rounded-full px-3 text-xs font-semibold transition",
            mode === "group"
              ? "bg-slate-950 text-white"
              : "text-slate-600 hover:bg-slate-100",
          )}
          onClick={() => onModeChange("group")}
          type="button"
        >
          <Users aria-hidden="true" size={14} />
          群聊
        </button>
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
    <div className="flex max-w-full flex-col items-start gap-2">
      <ol className="flex max-w-full items-center gap-2 overflow-x-auto pb-1 text-xs font-semibold [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
        {stages.map((stage, index) => (
          <li className="flex shrink-0 items-center gap-2" key={stage.label}>
            <span
              className={cn(
                "inline-flex min-h-9 items-center gap-1.5 rounded-full border px-3",
                (stage.state === "complete" || stage.state === "ready") &&
                  "border-black bg-black text-white",
                stage.state === "running" && "border-blue-200 bg-blue-50 text-blue-700",
                stage.state === "recovered" &&
                  "border-emerald-200 bg-emerald-50 text-emerald-700",
                stage.state === "pending" &&
                  "border-transparent bg-[var(--surface-muted)] text-slate-500",
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
                /
              </span>
            ) : null}
          </li>
        ))}
      </ol>
    </div>
  )
}

function mergeArtifactPanelItems(
  evidenceItems: ArtifactPanelItem[],
  workbenchArtifacts: ArtifactWorkbenchArtifact[],
): ArtifactPanelItem[] {
  const coveredArtifactIds = new Set(
    evidenceItems.map((item) => item.artifact.artifactId),
  )
  const workbenchItems = workbenchArtifacts
    .filter((artifact) => !coveredArtifactIds.has(artifact.artifactId))
    .map(
      (artifact): ArtifactPanelItem => ({
        artifact,
        id: `workbench:${artifact.artifactId}`,
        kind: "workbench",
        taskRunId: artifact.taskRunId,
        taskTitle: artifact.title,
      }),
    )

  return [...evidenceItems, ...workbenchItems]
}

function appendContextItem(
  items: ComposerContextItem[],
  nextItem: ComposerContextItem,
) {
  const withoutDuplicate = items.filter((item) => item.id !== nextItem.id)
  return [...withoutDuplicate, nextItem]
}

function removeContextItem(
  items: ComposerContextItem[],
  itemId: string,
) {
  return items.filter((item) => item.id !== itemId)
}

function moveContextItem(
  items: ComposerContextItem[],
  itemId: string,
  direction: "up" | "down",
) {
  const index = items.findIndex((item) => item.id === itemId)
  if (index < 0) {
    return items
  }
  const targetIndex = direction === "up" ? index - 1 : index + 1
  if (targetIndex < 0 || targetIndex >= items.length) {
    return items
  }
  const next = [...items]
  const [item] = next.splice(index, 1)
  next.splice(targetIndex, 0, item)
  return next
}

function contextIntentDraft(intent: ArtifactContextIntent) {
  const drafts: Record<ArtifactContextIntent, string> = {
    ask: "请解释这个上下文的关键内容、当前状态和下一步建议。",
    revise: "请基于这个上下文继续修改，并说明需要执行的任务。",
    send_to_agent: "@orchestrator 请基于这个上下文安排后续处理。",
  }
  return drafts[intent]
}
