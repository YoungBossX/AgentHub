"use client"

import { FolderGit2, FolderPlus, RefreshCw, Save } from "lucide-react"

import { Button } from "@/components/ui/button"
import type {
  ExternalProjectAnalysis,
  TargetProject,
  Workspace,
  WorkspaceSession,
} from "@/lib/api"
import { cn } from "@/lib/utils"

type WorkspaceTargetSettingsProps = {
  analysis: ExternalProjectAnalysis | null
  backendTargetId: string
  busy: boolean
  frontendTargetId: string
  isAnalyzing: boolean
  isRegistering: boolean
  isSavingTargets: boolean
  onAnalyze: () => void
  onBackendTargetChange: (targetId: string) => void
  onFrontendTargetChange: (targetId: string) => void
  onRefresh: () => void
  onRegister: () => void
  onRootPathChange: (rootPath: string) => void
  onSaveTargets: () => void
  onSessionChange: (sessionId: string) => void
  rootPath: string
  selectedSessionId: string
  sessions: WorkspaceSession[]
  statusMessage: string | null
  targets: TargetProject[]
  workspace: Workspace | null
}

export function WorkspaceTargetSettings({
  analysis,
  backendTargetId,
  busy,
  frontendTargetId,
  isAnalyzing,
  isRegistering,
  isSavingTargets,
  onAnalyze,
  onBackendTargetChange,
  onFrontendTargetChange,
  onRefresh,
  onRegister,
  onRootPathChange,
  onSaveTargets,
  onSessionChange,
  rootPath,
  selectedSessionId,
  sessions,
  statusMessage,
  targets,
  workspace,
}: WorkspaceTargetSettingsProps) {
  const frontendTargets = targets.filter((target) => target.type === "frontend")
  const backendTargets = targets.filter((target) => target.type === "backend")
  const canRegister = Boolean(analysis && analysis.allowedPaths.length > 0)

  return (
    <section className="rounded-lg border border-[var(--border)] bg-white p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-[11px] font-bold tracking-normal text-[var(--text-muted)]">
            工作区设置
          </p>
          <p className="mt-1 text-sm font-semibold text-slate-950">
            {workspace?.name ?? "未选择工作区"}
          </p>
          <p className="mt-1 max-w-2xl truncate text-xs text-[var(--muted-foreground)]">
            {workspace?.rootPath ?? "正在加载工作区..."}
          </p>
        </div>
        <Button
          className="bg-white text-slate-700 hover:bg-slate-50"
          disabled={busy}
          onClick={onRefresh}
          type="button"
          variant="secondary"
        >
          <RefreshCw aria-hidden="true" size={15} />
          刷新
        </Button>
      </div>

      <div className="mt-5 grid gap-4 lg:grid-cols-[1.1fr_0.9fr]">
        <div className="rounded-md border border-[var(--border)] bg-[var(--surface-muted)] p-3">
          <div className="flex items-center gap-2">
            <FolderGit2 aria-hidden="true" className="text-[var(--primary)]" size={16} />
            <p className="text-sm font-semibold text-slate-950">
              当前会话目标
            </p>
          </div>

          <label className="mt-3 block text-[11px] font-bold tracking-normal text-[var(--text-muted)]">
            会话
            <select
              className="mt-1 w-full rounded border border-[var(--border)] bg-white px-2 py-1.5 text-xs font-medium text-slate-900"
              disabled={sessions.length === 0}
              onChange={(event) => onSessionChange(event.target.value)}
              value={selectedSessionId}
            >
              {sessions.length === 0 ? (
                <option value="">暂无会话</option>
              ) : null}
              {sessions.map((session) => (
                <option key={session.id} value={session.id}>
                  {session.title}
                </option>
              ))}
            </select>
          </label>

          <div className="mt-3 grid gap-2 sm:grid-cols-2">
            <TargetSelect
              label="前端目标"
              onChange={onFrontendTargetChange}
              targets={frontendTargets}
              value={frontendTargetId}
            />
            <TargetSelect
              label="后端目标"
              onChange={onBackendTargetChange}
              targets={backendTargets}
              value={backendTargetId}
            />
          </div>

          <div className="mt-3 flex justify-end">
            <Button
              disabled={!selectedSessionId || isSavingTargets || busy}
              onClick={onSaveTargets}
              type="button"
            >
              <Save aria-hidden="true" size={15} />
              保存目标
            </Button>
          </div>
        </div>

        <div className="rounded-md border border-[var(--border)] bg-[var(--surface-muted)] p-3">
          <div className="flex items-center gap-2">
            <FolderPlus aria-hidden="true" className="text-[var(--primary)]" size={16} />
            <p className="text-sm font-semibold text-slate-950">
              注册外部项目
            </p>
          </div>

          <label className="mt-3 block text-[11px] font-bold tracking-normal text-[var(--text-muted)]">
            本地项目路径
            <input
              className="mt-1 w-full rounded border border-[var(--border)] bg-white px-2 py-1.5 text-xs font-medium text-slate-900"
              onChange={(event) => onRootPathChange(event.target.value)}
              placeholder="/Users/you/Desktop/my-app"
              value={rootPath}
            />
          </label>

          <div className="mt-3 flex flex-wrap gap-2">
            <Button
              className="bg-white text-slate-700 hover:bg-slate-50"
              disabled={!rootPath.trim() || isAnalyzing || busy}
              onClick={onAnalyze}
              type="button"
              variant="secondary"
            >
              {isAnalyzing ? "分析中..." : "分析"}
            </Button>
            <Button
              disabled={!canRegister || isRegistering || busy}
              onClick={onRegister}
              type="button"
            >
              {isRegistering ? "注册中..." : "注册到工作区"}
            </Button>
          </div>

          {analysis ? (
            <AnalysisSummary analysis={analysis} />
          ) : null}
        </div>
      </div>

      {targets.length > 0 ? (
        <div className="mt-4 flex flex-wrap gap-2">
          {targets.map((target) => (
            <TargetPill key={target.targetId} target={target} />
          ))}
        </div>
      ) : null}

      {statusMessage ? (
        <div className="mt-3 rounded border border-blue-200 bg-blue-50 p-2 text-xs text-blue-800">
          {statusMessage}
        </div>
      ) : null}
    </section>
  )
}

function TargetSelect({
  label,
  onChange,
  targets,
  value,
}: {
  label: string
  onChange: (targetId: string) => void
  targets: TargetProject[]
  value: string
}) {
  return (
    <label className="block text-[11px] font-bold tracking-normal text-[var(--text-muted)]">
      {label}
      <select
        className="mt-1 w-full rounded border border-[var(--border)] bg-white px-2 py-1.5 text-xs font-medium text-slate-900"
        onChange={(event) => onChange(event.target.value)}
        value={value}
      >
        {targets.length === 0 ? <option value="">暂无可选目标</option> : null}
        {targets.map((target) => (
          <option key={target.targetId} value={target.targetId}>
            {target.name}
          </option>
        ))}
      </select>
    </label>
  )
}

function AnalysisSummary({ analysis }: { analysis: ExternalProjectAnalysis }) {
  return (
    <div className="mt-3 rounded border border-[var(--border)] bg-white p-2 text-xs text-slate-700">
      <div className="flex flex-wrap gap-1">
        <MiniPill label={formatProjectType(analysis.projectType)} tone="type" />
        <MiniPill label={analysis.packageManager} tone="neutral" />
        <MiniPill label={formatAnalysisStatus(analysis.analysisStatus)} tone="status" />
        <MiniPill label={`置信度 ${formatConfidence(analysis.confidence)}`} tone="neutral" />
      </div>
      <p className="mt-2 truncate text-[11px] text-[var(--muted-foreground)]">
        可写路径：{analysis.allowedPaths.join(", ") || "无"}
      </p>
      {analysis.devCommand ? (
        <p className="mt-1 truncate text-[11px] text-[var(--muted-foreground)]">
          dev：{analysis.devCommand}
        </p>
      ) : null}
      {analysis.analysisWarnings.length > 0 ? (
        <p className="mt-2 text-[11px] text-amber-700">
          {analysis.analysisWarnings[0]}
        </p>
      ) : null}
    </div>
  )
}

function TargetPill({ target }: { target: TargetProject }) {
  return (
    <span
      className={cn(
        "inline-flex max-w-full items-center gap-1 rounded border px-2 py-1 text-[11px] font-medium",
        target.type === "frontend"
          ? "border-blue-200 bg-blue-50 text-blue-700"
          : target.type === "backend"
            ? "border-emerald-200 bg-emerald-50 text-emerald-700"
            : "border-slate-200 bg-slate-50 text-slate-600",
      )}
      title={`${target.targetId} · ${target.root}`}
    >
      <span>{formatTargetType(target.type)}</span>
      <span className="truncate">{target.name}</span>
    </span>
  )
}

function MiniPill({
  label,
  tone,
}: {
  label: string
  tone: "type" | "status" | "neutral"
}) {
  return (
    <span
      className={cn(
        "rounded border px-1.5 py-0.5 text-[10px] font-medium",
        tone === "type"
          ? "border-blue-200 bg-blue-50 text-blue-700"
          : tone === "status"
            ? "border-emerald-200 bg-emerald-50 text-emerald-700"
            : "border-slate-200 bg-slate-50 text-slate-600",
      )}
    >
      {label}
    </span>
  )
}

function formatTargetType(type: string) {
  switch (type) {
    case "frontend":
      return "前端"
    case "backend":
      return "后端"
    case "platform":
      return "平台"
    default:
      return type
  }
}

function formatProjectType(type: string) {
  switch (type) {
    case "vite-react":
      return "Vite React"
    case "nextjs":
      return "Next.js"
    case "fastapi":
      return "FastAPI"
    case "node-api":
      return "Node API"
    case "python-package":
      return "Python"
    default:
      return "未知项目"
  }
}

function formatAnalysisStatus(status: string) {
  switch (status) {
    case "ready":
      return "可注册"
    case "needs_confirmation":
      return "需确认"
    default:
      return status
  }
}

function formatConfidence(confidence: string) {
  switch (confidence) {
    case "high":
      return "高"
    case "low":
      return "低"
    default:
      return confidence
  }
}
