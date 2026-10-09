"use client"

import { CodeEditProvider } from "./user-code-edit-context"
import { CodeQuoteContext, MAX_QUOTED_CODE_CHARS, type CodeQuote } from "./code-quote-context"

import { selectComposerMention } from "./composer-mentions"
import { useMessageAttachments } from "./use-message-attachments"
import { useMessageRegeneration } from "./use-message-regeneration"

import { usePathname, useRouter, useSearchParams } from "next/navigation"
import {
  type FormEvent,
  type ReactNode,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  useTransition,
} from "react"

import { ArtifactPanel } from "@/components/artifact-panel"
import { SessionProgress, SessionResults } from "./session-overview"
import { sessionStages, type WorkspaceView } from "./session-workbench-state"
import { SessionEventTimeline, type SessionVisualEvent } from "./session-event-timeline"
import { WorkspaceHeader } from "@/components/workspace-shell-header"
import { WorkbenchLayout } from "@/components/workbench-layout"
import {
  artifactSelectionAfterRefresh,
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
  contextItemFromCode,
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
  retryGroupSummary,
  organizeSession,
  pinSessionMessage,
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
  const messageRevisionRef = useRef(0)
  const [tasks, setTasks] = useState<SessionTask[]>([])
  const [draft, setDraft] = useState("")
  const [artifactRefreshVersion, setArtifactRefreshVersion] = useState(0)
  const [evidenceArtifactItems, setEvidenceArtifactItems] = useState<ArtifactPanelItem[]>([])
  const [workbenchArtifacts, setWorkbenchArtifacts] = useState<ArtifactWorkbenchArtifact[]>([])
  const [workbenchSessionId, setWorkbenchSessionId] = useState<string | null>(null)
  const [selectedArtifactId, setSelectedArtifactId] = useState<string | null>(null)
  const composerRef = useRef<HTMLTextAreaElement>(null)
  const [contextSessionId, setContextSessionId] = useState<string | null>(null)
  const [contextItems, setContextItems] = useState<ComposerContextItem[]>([])
  const [conversationMode, setConversationMode] = useState<"direct" | "group">("group")
  const [previewFrameKey, setPreviewFrameKey] = useState(0)
  const [syncError, setSyncError] = useState<string | null>(null)

  const [view, setView] = useState<WorkspaceView>("conversation")
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [inspectorCollapsed, setInspectorCollapsed] = useState(false)
  const [inspectorOpen, setInspectorOpen] = useState(false)
  const [inspectorExpanded, setInspectorExpanded] = useState(false)
  const [eventsBySession, setEventsBySession] = useState<Record<string, SessionVisualEvent[]>>({})
  const onVisualEvent = useCallback((event: SessionVisualEvent) => {
    setEventsBySession((current) => {
      const previous = current[event.sessionId] ?? []
      if (previous.some((item) => item.id === event.id)) return current
      return { ...current, [event.sessionId]: [...previous, event].slice(-60) }
    })
  }, [])

  const selectedSessionId = searchParams.get("session") ?? sessions[0]?.id ?? null
  const attachments = useMessageAttachments(backendUrl, selectedSessionId)
  const selectedSessionIdRef = useRef(selectedSessionId)
  const regeneration = useMessageRegeneration(backendUrl, selectedSessionId, (sessionId, nextMessages, nextTasks, created) => {
    setSessions((current) => current.map((session) => session.id === sessionId ? { ...session, lastMessageAt: created.createdAt } : session))
    if (selectedSessionIdRef.current !== sessionId) return
    messageRevisionRef.current += 1
    setMessages(nextMessages)
    setTasks(nextTasks)
    setSyncError(null)
  })
  useEffect(() => { selectedSessionIdRef.current = selectedSessionId }, [selectedSessionId])
  const selectedSession = useMemo(
    () => sessions.find((session) => session.id === selectedSessionId) ?? null,
    [selectedSessionId, sessions],
  )
  const visibleTasks = useMemo(() => tasks.filter((task) => task.sessionId === selectedSessionId), [tasks, selectedSessionId])
  const artifactItems = useMemo(() => {
    const runIds = new Set(visibleTasks.flatMap((task) => task.taskRuns.map((run) => run.id)))
    return mergeArtifactPanelItems(evidenceArtifactItems.filter((item) => runIds.has(item.taskRunId)), workbenchSessionId === selectedSessionId ? workbenchArtifacts : [])
  }, [evidenceArtifactItems, workbenchArtifacts, visibleTasks, workbenchSessionId, selectedSessionId])
  const activeContextItems = contextSessionId === selectedSessionId ? contextItems : []
  const selectedArtifact = artifactItems.find((artifact) => artifact.id === selectedArtifactId) ?? null
  const selectedPreview = selectedArtifact?.kind === "preview" ? selectedArtifact.artifact : null
  const visibleMessages = messages.filter((message) => message.sessionId === selectedSessionId)
  const stages = sessionStages(visibleTasks, artifactItems, visibleMessages.some((message) => message.senderType === "user"))
  function selectArtifact(id: string) {
    setSelectedArtifactId(id)
    setInspectorOpen(true)
    setInspectorCollapsed(false)
  }
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

  const reportArtifactError = useCallback((error: unknown) => reportSyncError("无法加载执行成果", error), [reportSyncError])

  const runClientAction = useCallback(
    (action: () => Promise<void>, failureMessage: string) => {
      startTransition(async () => {
        try { await action() } catch (error) { reportSyncError(failureMessage, error) }
      })
    },
    [reportSyncError, startTransition],
  )

  useEffect(() => {
    if (!selectedSessionId) {
      return
    }

    let cancelled = false
    const revision = messageRevisionRef.current
    listSessionMessages(backendUrl, selectedSessionId)
      .then((nextMessages) => {
        if (!cancelled && revision === messageRevisionRef.current) {
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
          setWorkbenchSessionId(workbench.sessionId)
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
    setMessages,
    messageRevisionRef,
    onVisualEvent,
    summaryPending: messages.some((message) => message.sessionId === selectedSessionId && (message.regeneration?.state === "preparing" || message.groupSummary?.state === "pending" || message.groupSummary?.state === "calling")),
  })

  function selectSession(sessionId: string) {
    if (sessionId === selectedSessionId) {
      setSidebarOpen(false)
      return
    }
    setContextItems([])
    setSidebarOpen(false)
    setInspectorExpanded(false)
    setSyncError(null)
    setEvidenceArtifactItems([])
    setWorkbenchArtifacts([])
    setSelectedArtifactId(null)
    const params = new URLSearchParams(searchParams.toString())
    params.set("session", sessionId)
    router.replace(`${pathname}?${params.toString()}`)
  }

  function handleOrganizeSession(sessionId: string, changes: { pinned?: boolean; archived?: boolean }) {
    runClientAction(async () => {
      const updated = await organizeSession(backendUrl, sessionId, changes)
      setSessions((current) => current.map((session) => session.id === updated.id ? updated : session))
      setSyncError(null)
    }, "无法整理会话")
  }

  function handlePinMessage(message: ChatMessage, pinned: boolean) {
    runClientAction(async () => {
      const updated = await pinSessionMessage(backendUrl, message.sessionId, message.id, pinned)
      if (selectedSessionIdRef.current === message.sessionId) {
        messageRevisionRef.current += 1
        setMessages((current) => current.map((item) => item.id === updated.id ? { ...item, pinnedAt: updated.pinnedAt } : item))
        setSyncError(null)
      }
    }, "无法置顶消息")
  }

  function handleRetryGroupSummary(groupId: string) {
    if (!selectedSessionId) return
    const sessionId = selectedSessionId
    runClientAction(async () => {
      await retryGroupSummary(backendUrl, sessionId, groupId)
      const nextMessages = await listSessionMessages(backendUrl, sessionId)
      if (selectedSessionIdRef.current === sessionId) setMessages(nextMessages)
    }, "无法重试任务组汇总")
  }

  function handleCreateSession() {
    if (!workspace) {
      return
    }

    const title = `会话 ${sessions.length + 1}`
    runClientAction(async () => {
      const created = await createWorkspaceSession(backendUrl, workspace.id, title)
      setSessions((current) => [created, ...current])
      setSidebarOpen(false)
      setContextItems([])
      setEvidenceArtifactItems([])
      setWorkbenchArtifacts([])
      setSelectedArtifactId(null)
      setView("conversation")
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
    setSelectedArtifactId((current) => artifactSelectionAfterRefresh(current, artifacts))
    setContextItems((current) =>
      current.filter(
        (item) => !item.artifact || item.artifact.kind === "workbench" || artifacts.some((artifact) => artifact.id === item.artifact?.id),
      ),
    )
  }, [])

  function handleUseArtifactContext(
    artifact: ArtifactPanelItem,
    intent?: ArtifactContextIntent,
  ) {
    setContextItems((current) => appendContextItem(contextSessionId === selectedSessionId ? current : [], contextItemFromArtifact(artifact)))
    setContextSessionId(selectedSessionId)
    setSelectedArtifactId(artifact.id)
    if (intent) {
      setDraft(contextIntentDraft(intent))
    }
  }

  function handleQuoteMessage(message: ChatMessage) {
    setContextItems((current) => appendContextItem(contextSessionId === selectedSessionId ? current : [], contextItemFromMessage(message)))
    setContextSessionId(selectedSessionId)
  }

  function handleQuoteCode(quote: CodeQuote) {
    const artifact = artifactItems.find(item => item.artifact.artifactId === quote.artifactId)
    if (!artifact || !quote.text.trim() || Array.from(quote.text).length > MAX_QUOTED_CODE_CHARS) return
    if (activeContextItems.length >= 8) {
      setSyncError("每条消息最多包含 8 项上下文，请先移除不需要的内容再引用。")
      return
    }
    setContextItems(current => appendContextItem(contextSessionId === selectedSessionId ? current : [], contextItemFromCode(artifact, quote.path, quote.text)))
    setContextSessionId(selectedSessionId)
    setView("conversation")
    setInspectorExpanded(false)
    setInspectorOpen(false)
    requestAnimationFrame(() => composerRef.current?.focus())
  }

  function handleSendMessage(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!selectedSessionId || isPending || attachments.blocked || draft.trim().length === 0) {
      return
    }

    const content = draft.trim()
    const sessionId = selectedSessionId
    const attachmentIds = attachments.ids
    runClientAction(async () => {
      let created: ChatMessage
      try { created = await createSessionMessage(
        backendUrl,
        selectedSessionId,
        content,
        fetch,
        buildComposerMessageContext(activeContextItems),
        attachmentIds,
      ) } catch (error) {
        // Planning can fail after persistence; recover the immutable binding.
        if (attachmentIds.length) {
          const saved = await listSessionMessages(backendUrl, sessionId).catch(() => [])
          if (saved.some((message) => message.contentMd === content && attachmentIds.every((id) => message.attachments?.some((item) => item.id === id)))) {
            attachments.sent(sessionId, attachmentIds)
            if (selectedSessionIdRef.current === sessionId) {
              setMessages(saved)
              setDraft((current) => current.trim() === content ? "" : current)
            }
            throw new ApiRequestError(`消息及附件已保存，但规划未完成：${error instanceof Error ? error.message : "请求失败"}`)
          }
        }
        throw error
      }
      attachments.sent(sessionId, attachmentIds)
      if (selectedSessionIdRef.current === sessionId) setDraft((current) => current.trim() === content ? "" : current)
      const [nextMessages, nextTasks] = await Promise.all([
        listSessionMessages(backendUrl, selectedSessionId),
        listSessionTasks(backendUrl, selectedSessionId),
      ])
      if (selectedSessionIdRef.current !== sessionId) return
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
    <CodeEditProvider backendUrl={backendUrl} sessionId={selectedSessionId}>
    <CodeQuoteContext.Provider key={selectedSessionId} value={handleQuoteCode}>
    <section className="h-dvh overflow-hidden bg-white" data-region="app-shell">
      <WorkbenchLayout inspectorCollapsed={inspectorCollapsed} inspectorExpanded={inspectorExpanded} className={`workbench-layout h-full min-h-0 ${inspectorExpanded ? "inspector-expanded" : ""} ${inspectorOpen ? "inspector-open" : ""} ${sidebarOpen ? "sidebar-open" : ""} ${inspectorCollapsed ? "inspector-collapsed" : ""}`}>
        <div className="workbench-sidebar min-h-0" hidden={inspectorExpanded}>
          <SessionSidebar onClose={() => setSidebarOpen(false)} agents={initialAgents} isPending={isPending} onCreateSession={handleCreateSession} onSelectSession={selectSession}
            onOrganizeSession={handleOrganizeSession}
            onMentionAgent={(role) => { setDraft((current) => selectComposerMention(current, role, conversationMode)); setView("conversation"); setSidebarOpen(false); composerRef.current?.focus() }}
            selectedSessionId={selectedSessionId} sessions={sessions} taskCount={visibleTasks.length} workspace={workspace} />
        </div>
        <main className="workbench-main flex min-h-0 min-w-0 flex-col overflow-hidden bg-white" hidden={inspectorExpanded}>
          <WorkspaceHeader conversationMode={conversationMode} healthSlot={healthSlot} onModeChange={setConversationMode}
            selectedSessionTitle={selectedSession?.title ?? "未选择会话"} taskCount={visibleTasks.length} stages={stages}
            view={view} onViewChange={setView} artifactCount={artifactItems.length}
            onToggleSidebar={() => setSidebarOpen((open) => !open)} onToggleInspector={() => { if (window.matchMedia("(min-width: 1200px)").matches) setInspectorCollapsed((value) => !value); else setInspectorOpen((open) => !open) }} />
          {syncError ? <div className="mx-5 mt-3 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-900" role="alert">{syncError}</div> : null}
          <div className="min-h-0 flex-1 overflow-y-auto px-5 py-5" data-region="center-scroll">
            <div className="mx-auto max-w-3xl" hidden={view !== "conversation"}>
              {selectedSession?.archivedAt ? <div className="mb-3 flex items-center justify-between gap-2 rounded-lg border border-[var(--border)] bg-[var(--surface-muted)] p-3 text-xs"><span>会话已归档 · 历史保留，不中断任务</span><button type="button" disabled={isPending} onClick={() => handleOrganizeSession(selectedSession.id, { archived: false })} className="rounded border border-[var(--border)] bg-[var(--surface)] px-2 py-1">恢复会话</button></div> : null}
              <ChatThread backendUrl={backendUrl} agents={initialAgents} messages={visibleMessages} onQuoteMessage={handleQuoteMessage} onRetryGroupSummary={handleRetryGroupSummary} onPinMessage={handlePinMessage} onRegenerateMessage={regeneration.run} actionsPending={isPending || regeneration.pending} selectedSession={selectedSession} taskCount={visibleTasks.length}
                taskListSlot={<><SessionProgress tasks={visibleTasks} agents={initialAgents} onOpenProcess={() => setView("process")} />{artifactItems.length ? <SessionResults compact artifacts={artifactItems} tasks={visibleTasks} onSelect={selectArtifact} /> : null}</>} />
            </div>
            <div className="mx-auto max-w-4xl space-y-5" hidden={view !== "process"}>
              {selectedSession && visibleTasks.length ? (
                <TaskCardList
                      compact
                      agents={initialAgents}
                      key={selectedSessionId}
                      artifactRefreshKey={artifactRefreshVersion}
                      backendUrl={backendUrl}
                      busy={isPending}
                      onApproveRun={handleApproveTaskRun}
                      onArtifactsChange={handleArtifactsChange}
                      onArtifactError={reportArtifactError}
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
                      onSelectArtifact={selectArtifact}
                      onStartPreview={handleStartPreview}
                      onUseArtifactContext={handleUseArtifactContext}
                      selectedArtifactId={selectedArtifactId}
                      tasks={visibleTasks}
                    />
              ) : <div className="rounded-xl border border-dashed border-slate-200 p-10 text-center text-sm text-slate-400">发送需求后，这里会展示任务依赖与执行过程。</div>}
              <SessionEventTimeline events={selectedSessionId ? eventsBySession[selectedSessionId] ?? [] : []} tasks={visibleTasks} />
            </div>
            <div className="mx-auto max-w-3xl" hidden={view !== "results"}><SessionResults artifacts={artifactItems} tasks={visibleTasks} onSelect={selectArtifact} /></div>
          </div>
          {selectedSession ? <div className="shrink-0 px-5 pb-4 pt-2"><MessageComposer
                inputRef={composerRef}
                key={selectedSessionId}
                attachments={attachments.items}
                attachmentsBlocked={attachments.blocked}
                onAttach={attachments.add}
                onRemoveAttachment={attachments.remove}
                contextItems={activeContextItems}
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
              /><p className="mx-auto mt-2 max-w-3xl text-[10px] text-slate-400">@ 选择 Agent · Enter 发送 · Shift + Enter 换行</p></div> : null}
        </main>
        <div className="workbench-inspector flex min-h-0 min-w-0 flex-col">
          <ArtifactPanel artifactItems={artifactItems} busy={isPending} frameKey={previewFrameKey}
            expanded={inspectorExpanded} onToggleExpand={() => { setInspectorExpanded((value) => !value); setInspectorOpen(true); setInspectorCollapsed(false) }}
            onClose={() => { setSelectedArtifactId(null); setInspectorOpen(false); setInspectorExpanded(false); setInspectorCollapsed(true) }}
            onCreateDeploy={handleCreateDeployment} onOpenPreview={handleOpenPreview} onRefresh={handleRefreshPreviews}
            onSaveArtifactEdit={handleSaveArtifactEdit} onSelectArtifact={selectArtifact} onStopPreview={handleStopPreview} selectedArtifactId={selectedArtifactId} />
        </div>
      </WorkbenchLayout>
    </section>
    </CodeQuoteContext.Provider>
    </CodeEditProvider>
  )
}
