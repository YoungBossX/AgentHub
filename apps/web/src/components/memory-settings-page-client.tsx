"use client"

import Link from "next/link"
import { useEffect, useRef, useState, type ReactNode } from "react"
import { Archive, ArrowLeft, Check, RefreshCw, Trash2, X } from "lucide-react"

import {
  getDemoWorkspace,
  listWorkspaceMemory,
  listWorkspaceSessions,
  refreshSessionMemorySnapshot,
  updateMemoryItemStatus,
  type MemoryItem,
  type Workspace,
  type WorkspaceSession,
} from "@/lib/api"
import { cn } from "@/lib/utils"

const STATUS_FILTERS = [
  "active",
  "pending_review",
  "warm",
  "archived",
  "rejected",
  "deleted",
]

type MemorySettingsPageClientProps = {
  backendUrl: string
  initialSessionId?: string | null
}

export function MemorySettingsPageClient({
  backendUrl,
  initialSessionId,
}: MemorySettingsPageClientProps) {
  const [workspace, setWorkspace] = useState<Workspace | null>(null)
  const [sessions, setSessions] = useState<WorkspaceSession[]>([])
  const [items, setItems] = useState<MemoryItem[]>([])
  const [statusFilter, setStatusFilter] = useState<string>("active")
  const [message, setMessage] = useState<string | null>(null)
  const [isPending, setIsPending] = useState(false)
  const [isLoading, setIsLoading] = useState(true)
  const [isRefreshing, setIsRefreshing] = useState(false)
  const [selectedSessionId, setSelectedSessionId] = useState(initialSessionId ?? "")
  const generation = useRef(0)
  const operationPending = useRef(false)

  useEffect(() => {
    const currentGeneration = ++generation.current
    const isCurrent = () => generation.current === currentGeneration
    async function load() {
      setIsLoading(true)
      setIsPending(false)
      setIsRefreshing(false)
      operationPending.current = false
      setMessage(null)
      setWorkspace(null)
      setSessions([])
      setItems([])
      const loadedWorkspace = await getDemoWorkspace(backendUrl)
      if (!isCurrent()) {
        return
      }
      setWorkspace(loadedWorkspace)
      if (!loadedWorkspace) {
        setSessions([])
        setItems([])
        setMessage("当前工作区不可用，请检查后端连接。")
        return
      }
      const [loadedSessions, loadedMemory] = await Promise.all([
        listWorkspaceSessions(backendUrl, loadedWorkspace.id),
        listWorkspaceMemory(backendUrl, loadedWorkspace.id, statusFilter),
      ])
      if (!isCurrent()) {
        return
      }
      setSessions(loadedSessions.filter((session) => session.workspaceId === loadedWorkspace.id))
      setItems(loadedMemory)
    }
    load()
      .catch(() => {
        if (isCurrent()) setMessage("加载记忆失败")
      })
      .finally(() => {
        if (isCurrent()) setIsLoading(false)
      })
    return () => {
      generation.current += 1
    }
  }, [backendUrl, statusFilter])

  const selectedSession = sessions.find((session) => session.id === selectedSessionId) ?? null
  const currentSnapshotId = selectedSession?.memorySnapshotId ?? null
  const busy = isPending || isLoading

  function beginOperation() {
    if (busy || operationPending.current) return false
    operationPending.current = true
    setIsPending(true)
    setMessage(null)
    return true
  }

  function finishOperation(currentGeneration: number) {
    if (generation.current !== currentGeneration) return
    operationPending.current = false
    setIsPending(false)
    setIsRefreshing(false)
  }

  async function refreshSnapshot() {
    if (!workspace || !selectedSession || !beginOperation()) return
    const currentGeneration = generation.current
    setIsRefreshing(true)
    try {
      const updated = await refreshSessionMemorySnapshot(backendUrl, selectedSession.id)
      if (generation.current !== currentGeneration) return
      if (
        updated.id !== selectedSession.id ||
        updated.workspaceId !== workspace.id ||
        !updated.memorySnapshotId
      ) {
        throw new Error("返回的会话快照与当前会话不匹配，请重新加载页面后重试。")
      }
      setSessions((current) =>
        current.map((session) => session.id === updated.id ? updated : session),
      )
      setMessage("会话快照已刷新，后续请求将采用新快照；历史任务的记忆绑定保持不变。")
    } catch (error) {
      if (generation.current === currentGeneration) {
        setMessage(`刷新失败：${error instanceof Error ? error.message : "请检查后端连接后重试。"}`)
      }
    } finally {
      finishOperation(currentGeneration)
    }
  }

  function reload() {
    if (!workspace || !beginOperation()) {
      return
    }
    const currentGeneration = generation.current
    listWorkspaceMemory(backendUrl, workspace.id, statusFilter)
      .then((loadedMemory) => {
        if (generation.current !== currentGeneration) return
        setItems(loadedMemory)
        setMessage("列表已重新加载，会话快照保持不变。")
      })
      .catch(() => {
        if (generation.current === currentGeneration) setMessage("重新加载记忆列表失败，请重试。")
      })
      .finally(() => {
        finishOperation(currentGeneration)
      })
  }

  function updateStatus(item: MemoryItem, status: string) {
    if (!beginOperation()) return
    const currentGeneration = generation.current
    updateMemoryItemStatus(backendUrl, item.id, status)
      .then((updated) => {
        if (generation.current !== currentGeneration) return
        setItems((current) =>
          current
            .map((entry) => (entry.id === updated.id ? updated : entry))
            .filter((entry) => entry.status === statusFilter),
        )
        setMessage(`已更新：${statusLabel(status)}。如需当前会话采用变更，请刷新会话快照。`)
      })
      .catch(() => {
        if (generation.current === currentGeneration) setMessage("更新记忆状态失败")
      })
      .finally(() => {
        finishOperation(currentGeneration)
      })
  }

  return (
    <section className="grid gap-4">
      <div className="rounded-lg border border-[var(--border)] bg-white p-5 shadow-sm">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="grid min-w-0 flex-1 gap-3">
            <p className="text-sm font-semibold text-slate-950">会话记忆快照</p>
            <label className="grid gap-1 text-sm text-slate-700">
              会话
              <select
                aria-label="会话"
                className="w-full rounded-md border border-[var(--border)] bg-white px-3 py-2 disabled:opacity-60"
                disabled={busy || !sessions.length}
                onChange={(event) => {
                  setSelectedSessionId(event.target.value)
                  setMessage(null)
                }}
                value={selectedSession?.id ?? ""}
              >
                <option value="">请选择会话</option>
                {sessions.map((session) => (
                  <option key={session.id} value={session.id}>{session.title}</option>
                ))}
              </select>
            </label>
            <p className="max-w-xl break-all font-mono text-xs text-[var(--muted-foreground)]">
              {currentSnapshotId
                ? `快照：${currentSnapshotId}`
                : selectedSession ? "尚未绑定记忆快照" : "选择会话后查看和刷新快照"}
            </p>
            <p className="max-w-xl text-xs leading-5 text-slate-500">
              记忆变更不会自动替换会话快照。刷新后，后续请求采用新快照，历史任务保留原有记忆绑定。任务执行中请等待结束后再刷新。
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <Link
              className="inline-flex items-center gap-2 rounded-md border border-[var(--border)] px-3 py-2 text-sm font-semibold text-slate-700"
              href={selectedSession ? `/?session=${encodeURIComponent(selectedSession.id)}` : "/"}
            >
              <ArrowLeft aria-hidden="true" size={16} />
              返回聊天
            </Link>
            <button
              className="inline-flex items-center gap-2 rounded-md border border-[var(--border)] bg-white px-3 py-2 text-sm font-semibold text-slate-700 transition hover:border-[var(--primary-border)] hover:text-[var(--primary)] disabled:opacity-60"
              disabled={busy || !selectedSession || !workspace}
              onClick={refreshSnapshot}
              type="button"
            >
              <RefreshCw aria-hidden="true" size={16} />
              {isRefreshing ? "刷新中…" : "刷新会话快照"}
            </button>
          </div>
        </div>
      </div>

      <div className="rounded-lg border border-[var(--border)] bg-white p-4 shadow-sm">
        <div className="flex flex-wrap gap-2">
          <button
            className="rounded-md border border-[var(--border)] px-3 py-1.5 text-xs font-semibold text-slate-700 disabled:opacity-60"
            disabled={busy || !workspace}
            onClick={reload}
            type="button"
          >
            重新加载列表
          </button>
          {STATUS_FILTERS.map((status) => (
            <button
              className={cn(
                "rounded-full border px-3 py-1.5 text-xs font-semibold transition",
                statusFilter === status
                  ? "border-slate-950 bg-slate-950 text-white"
                  : "border-[var(--border)] bg-white text-slate-600 hover:border-slate-400",
              )}
              key={status}
              disabled={busy}
              onClick={() => setStatusFilter(status)}
              type="button"
            >
              {statusLabel(status)}
            </button>
          ))}
        </div>
      </div>

      {message ? (
        <div role="status" className="rounded-md border border-[var(--border)] bg-white px-4 py-3 text-sm text-slate-700">
          {message}
        </div>
      ) : null}

      <div className="grid gap-3">
        {items.length ? (
          items.map((item) => (
            <MemoryCard
              disabled={busy}
              item={item}
              key={item.id}
              onUpdateStatus={updateStatus}
            />
          ))
        ) : (
          <div className="rounded-lg border border-dashed border-[var(--border)] bg-white p-6 text-sm text-[var(--text-muted)]">
            当前状态下没有记忆项
          </div>
        )}
      </div>
    </section>
  )
}

type MemoryCardProps = {
  disabled: boolean
  item: MemoryItem
  onUpdateStatus: (item: MemoryItem, status: string) => void
}

function MemoryCard({ disabled, item, onUpdateStatus }: MemoryCardProps) {
  return (
    <article className="rounded-lg border border-[var(--border)] bg-white p-4 shadow-sm">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="text-sm font-semibold text-slate-950">{item.title}</h3>
            <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[11px] font-semibold text-slate-600">
              {statusLabel(item.status)}
            </span>
            <span className="rounded-full bg-teal-50 px-2 py-0.5 text-[11px] font-semibold text-teal-700">
              {memoryTypeLabel(item.memoryType)}
            </span>
          </div>
          <p className="mt-2 whitespace-pre-wrap text-sm leading-6 text-slate-700">
            {item.contentMd}
          </p>
        </div>
        <div className="flex shrink-0 flex-wrap gap-2">
          <IconAction
            disabled={disabled || item.status === "active"}
            icon={<Check aria-hidden="true" size={15} />}
            label="确认"
            onClick={() => onUpdateStatus(item, "active")}
          />
          <IconAction
            disabled={disabled || item.status === "rejected"}
            icon={<X aria-hidden="true" size={15} />}
            label="拒绝"
            onClick={() => onUpdateStatus(item, "rejected")}
          />
          <IconAction
            disabled={disabled || item.status === "archived"}
            icon={<Archive aria-hidden="true" size={15} />}
            label="归档"
            onClick={() => onUpdateStatus(item, "archived")}
          />
          <IconAction
            disabled={disabled || item.status === "deleted"}
            icon={<Trash2 aria-hidden="true" size={15} />}
            label="删除"
            onClick={() => onUpdateStatus(item, "deleted")}
          />
        </div>
      </div>
      <dl className="mt-4 grid gap-2 border-t border-slate-100 pt-3 text-xs text-[var(--muted-foreground)] sm:grid-cols-2">
        <MetaRow label="来源" value={item.source} />
        <MetaRow label="范围" value={item.scope} />
        <MetaRow label="目标" value={item.targetIds.join(", ") || "通用"} />
        <MetaRow label="角色" value={item.agentRoles.join(", ") || "通用"} />
        <MetaRow label="AGENTS.md" value={item.compiledToAgentsMd ? "已编译" : "未编译"} />
        <MetaRow label="CLAUDE.md" value={item.compiledToClaudeMd ? "已编译" : "未编译"} />
      </dl>
    </article>
  )
}

function IconAction({
  disabled,
  icon,
  label,
  onClick,
}: {
  disabled: boolean
  icon: ReactNode
  label: string
  onClick: () => void
}) {
  return (
    <button
      aria-label={label}
      className="inline-flex h-8 w-8 items-center justify-center rounded-md border border-[var(--border)] bg-white text-slate-600 transition hover:border-slate-400 hover:text-slate-950 disabled:opacity-40"
      disabled={disabled}
      onClick={onClick}
      title={label}
      type="button"
    >
      {icon}
    </button>
  )
}

function MetaRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="min-w-0">
      <dt className="font-semibold text-slate-500">{label}</dt>
      <dd className="mt-0.5 truncate font-mono text-[11px]">{value}</dd>
    </div>
  )
}

function statusLabel(status: string) {
  const labels: Record<string, string> = {
    active: "已启用",
    pending_review: "待确认",
    warm: "温记忆",
    archived: "已归档",
    rejected: "已拒绝",
    deleted: "已删除",
  }
  return labels[status] ?? status
}

function memoryTypeLabel(type: string) {
  const labels: Record<string, string> = {
    project_rule: "项目规则",
    user_preference: "用户偏好",
    decision: "架构决策",
    pattern: "经验模式",
    feedback: "用户反馈",
    session_summary: "会话摘要",
    external_suggestion: "外部建议",
  }
  return labels[type] ?? type
}
