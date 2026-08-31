"use client"

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
import { WorkspaceHeader } from "@/components/workspace-shell-header"
import {
  appendContextItem,
  contextIntentDraft,
  mergeArtifactPanelItems,
  moveContextItem,
  removeContextItem,
} from "@/components/workspace-shell-state"
import { useSessionEventRefresh } from "@/components/use-session-event-refresh"
import { useTaskArtifactActions } from "@/components/use-task-artifact-actions"
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
  createSessionMessage,
  createWorkspaceSession,
  getSessionArtifactWorkbench,
  listSessionMessages,
  listSessionTasks,
  ApiRequestError,
  type ArtifactWorkbenchArtifact,
  type AgentContact,
  type ChatMessage,
  type SessionTask,
  type Workspace,
  type WorkspaceSession,
} from "@/lib/api"
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

  useSessionEventRefresh({
    backendUrl,
    reportSyncError,
    selectedSessionId,
    setArtifactRefreshVersion,
    setSyncError,
    setTasks,
  })

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

  const {
    handleCreateTaskRun,
    handleForceCodexFailure,
    handleInterruptTaskRun,
    handleRetryTaskRun,
    handleRetryTaskRunWithFallback,
    handleApproveTaskRun,
    handleApprovePlan,
    handleRejectPlan,
    handleRequestPlanClarification,
    handleDenyTaskRun,
    handleOpenPreview,
    handleRefreshPreviews,
    handleStartPreview,
    handleCreateReview,
    handleCreateDeployment,
    handleStopPreview,
    handleSaveArtifactEdit,
  } = useTaskArtifactActions({
    backendUrl,
    refreshArtifacts,
    refreshSelectedTasks,
    runClientAction,
    selectedPreview,
    setPreviewFrameKey,
    setSelectedArtifactId,
    setSyncError,
  })

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
          <WorkspaceHeader
            conversationMode={conversationMode}
            hasCompletedRun={hasCompletedRun}
            hasRecoveredRun={hasRecoveredRun}
            hasRequirement={hasRequirement}
            hasRunningTask={hasRunningTask}
            healthSlot={healthSlot}
            onModeChange={setConversationMode}
            selectedSessionTitle={selectedSession?.title ?? "未选择会话"}
            taskCount={tasks.length}
          />

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
                      artifactRefreshKey={artifactRefreshVersion}
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
