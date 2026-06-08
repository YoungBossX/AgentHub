"use client"

import {
  Code2,
  ExternalLink,
  FileText,
  Monitor,
  RefreshCw,
  Rocket,
  ShieldCheck,
  Square,
  X,
} from "lucide-react"
import { type ChangeEvent, useState } from "react"

import { DeployCard } from "./deploy-card"
import { DiffCard } from "./diff-card"
import { Button } from "@/components/ui/button"
import type {
  ArtifactWorkbenchArtifact,
  DeploymentArtifact,
  DiffArtifact,
  PreviewArtifact,
  ReviewArtifact,
} from "@/lib/api"
import { formatCompactDateTime } from "@/lib/date-format"
import { cn } from "@/lib/utils"

type PreviewCardProps = {
  busy?: boolean
  onCreateDeploy?: (previewId: string) => void
  onOpen?: (preview: PreviewArtifact) => void
  onRefresh?: (taskRunId: string) => void
  onStop?: (previewId: string) => void
  preview: PreviewArtifact
}

type PreviewPanelProps = {
  artifactItems: ArtifactPanelItem[]
  busy?: boolean
  frameKey: number
  onClose?: () => void
  onCreateDeploy?: (previewId: string) => void
  onOpenPreview?: (preview: PreviewArtifact) => void
  onRefresh?: (taskRunId: string) => void
  onSaveArtifactEdit?: (artifactId: string, contentMd: string, summary: string) => void
  onSelectArtifact?: (artifactId: string) => void
  onStopPreview?: (previewId: string) => void
  selectedArtifactId: string | null
}

export type ArtifactPanelItem =
  | {
      artifact: DiffArtifact
      id: string
      kind: "diff"
      taskRunId: string
      taskTitle: string
    }
  | {
      artifact: PreviewArtifact
      id: string
      kind: "preview"
      taskRunId: string
      taskTitle: string
    }
  | {
      artifact: ReviewArtifact
      id: string
      kind: "review"
      taskRunId: string
      taskTitle: string
    }
  | {
      artifact: DeploymentArtifact
      id: string
      kind: "deployment"
      taskRunId: string
      taskTitle: string
    }
  | {
      artifact: ArtifactWorkbenchArtifact
      id: string
      kind: "workbench"
      taskRunId: string
      taskTitle: string
    }

function formatPreviewTime(value: string | null) {
  if (!value) {
    return "最近检查：等待中"
  }

  return `最近检查：${formatCompactDateTime(value)}`
}

function previewHost(url: string) {
  try {
    return new URL(url).host
  } catch {
    return url
  }
}

function previewTitle(title: string) {
  return title === "Vite React preview" ? "Vite React 预览" : title
}

function statusLabel(status: string) {
  const labels: Record<string, string> = {
    healthy: "健康",
    pending: "等待中",
    ready: "就绪",
    starting: "启动中",
    stopped: "已停止",
    unhealthy: "异常",
  }
  return labels[status] ?? status
}

export function PreviewCard({
  busy = false,
  onCreateDeploy,
  onOpen,
  onRefresh,
  onStop,
  preview,
}: PreviewCardProps) {
  return (
    <article className="rounded-lg border border-[var(--border)] bg-white p-3 shadow-sm">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="flex items-center gap-2 text-xs font-medium uppercase tracking-normal text-[var(--muted-foreground)]">
            <Monitor aria-hidden="true" size={14} />
            预览
          </p>
          <h3 className="mt-1 truncate text-sm font-semibold">
            {previewTitle(preview.title)}
          </h3>
          <p className="mt-1 truncate text-xs text-[var(--muted-foreground)]">
            {preview.url}
          </p>
        </div>
        <span className="rounded-full border border-[var(--border)] px-2.5 py-1 text-xs font-semibold text-[var(--muted-foreground)]">
          {statusLabel(preview.healthStatus)}
        </span>
      </div>

      <dl className="mt-3 grid gap-2 text-xs sm:grid-cols-3">
        <div>
          <dt className="text-[var(--muted-foreground)]">状态</dt>
          <dd className="mt-1 font-medium">{statusLabel(preview.status)}</dd>
        </div>
        <div>
          <dt className="text-[var(--muted-foreground)]">端口</dt>
          <dd className="mt-1 font-medium">{preview.port}</dd>
        </div>
        <div className="min-w-0">
          <dt className="text-[var(--muted-foreground)]">检查时间</dt>
          <dd className="mt-1 truncate font-medium">
            {formatPreviewTime(preview.lastCheckedAt)}
          </dd>
        </div>
      </dl>

      {preview.statusReason ? (
        <p className="mt-3 rounded-md bg-amber-50 p-2 text-xs text-amber-900">
          {preview.statusReason}
        </p>
      ) : null}

      <div className="mt-3 flex flex-wrap gap-2">
        <Button
          className="h-8 px-3 text-xs"
          disabled={busy || !onOpen}
          onClick={() => onOpen?.(preview)}
          type="button"
        >
          <ExternalLink aria-hidden="true" size={14} />
          打开预览
        </Button>
        <Button
          className="h-8 px-3 text-xs"
          disabled={busy || !onRefresh}
          onClick={() => onRefresh?.(preview.taskRunId)}
          type="button"
          variant="secondary"
        >
          <RefreshCw aria-hidden="true" size={14} />
          刷新预览
        </Button>
        <Button
          className="h-8 px-3 text-xs"
          disabled={busy || !onCreateDeploy || preview.healthStatus !== "healthy"}
          onClick={() => onCreateDeploy?.(preview.id)}
          type="button"
          variant="secondary"
        >
          <Rocket aria-hidden="true" size={14} />
          创建部署卡片
        </Button>
        <Button
          className="h-8 px-3 text-xs"
          disabled={busy || !onStop}
          onClick={() => onStop?.(preview.id)}
          type="button"
          variant="secondary"
        >
          <Square aria-hidden="true" size={14} />
          停止预览
        </Button>
      </div>
    </article>
  )
}

export function PreviewPanel({
  artifactItems,
  busy = false,
  frameKey,
  onClose,
  onCreateDeploy,
  onOpenPreview,
  onRefresh,
  onSaveArtifactEdit,
  onSelectArtifact,
  onStopPreview,
  selectedArtifactId,
}: PreviewPanelProps) {
  const selectedItem =
    artifactItems.find((item) => item.id === selectedArtifactId) ?? null
  const selectedPreview =
    selectedItem?.kind === "preview" ? selectedItem.artifact : null
  const latestByKind = (kind: ArtifactPanelItem["kind"]) =>
    [...artifactItems].reverse().find((item) => item.kind === kind) ?? null
  const activeKind = selectedItem?.kind ?? "empty"

  return (
    <aside className="flex min-h-0 flex-col overflow-hidden border-t border-[var(--border)] bg-[#f7f8f8] lg:border-l lg:border-t-0">
      <header className="shrink-0 border-b border-[var(--border)] bg-white/95 px-4 py-4">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <p className="text-[11px] font-bold uppercase tracking-normal text-[var(--text-muted)]">
              产物详情
            </p>
            <h2 className="mt-1 truncate text-base font-semibold text-slate-950">
              {panelTitle(selectedItem)}
            </h2>
            <p className="mt-1 text-xs text-[var(--muted-foreground)]">
              {selectedItem
                ? selectedItem.taskTitle
                : "从任务时间线选择 Diff、评审、预览或部署产物。"}
            </p>
            {selectedItem ? (
              <p className="mt-2 inline-flex rounded-full bg-[var(--surface-muted)] px-2.5 py-1 text-[11px] font-semibold uppercase tracking-normal text-slate-600">
                {artifactKindLabel(selectedItem.kind)}
              </p>
            ) : null}
          </div>
          <div className="flex gap-2 pt-1">
            <Button
              aria-label="刷新面板"
              className="h-8 w-8 rounded-lg p-0"
              disabled={!selectedPreview || !onRefresh}
              onClick={() => selectedPreview && onRefresh?.(selectedPreview.taskRunId)}
              type="button"
              variant="secondary"
            >
              <RefreshCw aria-hidden="true" size={14} />
            </Button>
            <Button
              aria-label="关闭产物"
              className="h-8 w-8 rounded-lg p-0"
              disabled={!selectedItem || !onClose}
              onClick={onClose}
              type="button"
              variant="secondary"
            >
              <X aria-hidden="true" size={14} />
            </Button>
          </div>
        </div>

        <div className="mt-4 grid grid-cols-5 gap-1 rounded-full bg-[var(--surface-muted)] p-1">
          <ArtifactRailItem
            active={activeKind === "diff"}
            count={artifactItems.filter((item) => item.kind === "diff").length}
            label="Diff"
            onSelect={() => {
              const item = latestByKind("diff")
              if (item) {
                onSelectArtifact?.(item.id)
              }
            }}
          />
          <ArtifactRailItem
            active={activeKind === "preview"}
            count={artifactItems.filter((item) => item.kind === "preview").length}
            label="预览"
            onSelect={() => {
              const item = latestByKind("preview")
              if (item) {
                onSelectArtifact?.(item.id)
              }
            }}
          />
          <ArtifactRailItem
            active={activeKind === "review"}
            count={artifactItems.filter((item) => item.kind === "review").length}
            label="评审"
            onSelect={() => {
              const item = latestByKind("review")
              if (item) {
                onSelectArtifact?.(item.id)
              }
            }}
          />
          <ArtifactRailItem
            active={activeKind === "deployment"}
            count={artifactItems.filter((item) => item.kind === "deployment").length}
            label="部署"
            onSelect={() => {
              const item = latestByKind("deployment")
              if (item) {
                onSelectArtifact?.(item.id)
              }
            }}
          />
          <ArtifactRailItem
            active={activeKind === "workbench"}
            count={artifactItems.filter((item) => item.kind === "workbench").length}
            label="文档"
            onSelect={() => {
              const item = latestByKind("workbench")
              if (item) {
                onSelectArtifact?.(item.id)
              }
            }}
          />
        </div>
      </header>

      <div
        className="grid min-h-0 flex-1 grid-rows-[auto_auto_minmax(0,1fr)] gap-3 overflow-y-auto p-4"
        data-region="artifact-scroll"
      >
        {selectedItem ? <ArtifactSummary item={selectedItem} /> : null}

        <section className="rounded-lg border border-[var(--border)] bg-white p-3 shadow-sm">
          <div className="flex items-center justify-between gap-3">
            <p className="text-[11px] font-bold uppercase tracking-normal text-[var(--text-muted)]">
              预览环境
            </p>
            <span className="text-[11px] font-semibold text-[var(--primary)]">
              Vite
            </span>
          </div>
          <div className="mt-3 rounded-lg bg-[var(--surface-muted)] p-2">
            <div className="flex items-center gap-1.5">
              <span className="h-2.5 w-2.5 rounded-full bg-red-400" />
              <span className="h-2.5 w-2.5 rounded-full bg-amber-400" />
              <span className="h-2.5 w-2.5 rounded-full bg-green-400" />
              <span className="ml-2 min-w-0 flex-1 truncate rounded bg-white px-2 py-1 text-center text-xs text-[var(--muted-foreground)]">
                {selectedPreview?.url ?? "预览尚未启动"}
              </span>
            </div>
          </div>
        </section>

        {selectedItem ? (
          <ArtifactDetail
            busy={busy}
            frameKey={frameKey}
            item={selectedItem}
            onCreateDeploy={onCreateDeploy}
            onOpenPreview={onOpenPreview}
            onRefresh={onRefresh}
            onSaveArtifactEdit={onSaveArtifactEdit}
            onStopPreview={onStopPreview}
          />
        ) : (
          <div className="flex min-h-[360px] w-full items-start justify-center rounded-lg border border-dashed border-[var(--border)] bg-white/60 p-8 pt-20 text-center text-sm text-[var(--muted-foreground)]">
            <div className="w-full max-w-64 rounded-lg border border-[var(--border)] bg-white px-6 py-7 shadow-sm">
              <span className="mx-auto flex h-10 w-10 items-center justify-center rounded-lg bg-[var(--primary)] text-white">
                <Monitor aria-hidden="true" size={18} />
              </span>
              <p className="mt-4 font-semibold text-slate-900">等待产物</p>
              <p className="mt-1 leading-6">
                任务生成 Diff、评审、预览或部署证据后，可在这里查看详情。
              </p>
            </div>
          </div>
        )}
      </div>
    </aside>
  )
}

function ArtifactSummary({ item }: { item: ArtifactPanelItem }) {
  const rows = summaryRows(item)

  return (
    <section className="rounded-lg border border-[var(--border)] bg-white p-3 shadow-sm">
      <div className="flex items-center justify-between gap-3">
        <div>
          <p className="text-[11px] font-bold uppercase tracking-normal text-[var(--text-muted)]">
            来源任务
          </p>
          <p className="mt-1 line-clamp-2 text-sm font-semibold text-slate-950">
            {item.taskTitle}
          </p>
        </div>
        <span className="rounded-full bg-[var(--surface-muted)] px-2.5 py-1 font-mono text-[11px] font-semibold text-slate-600">
          {item.taskRunId.slice(0, 8)}
        </span>
      </div>

      <dl className="mt-3 grid grid-cols-2 gap-2 text-xs">
        {rows.map((row) => (
          <div className="min-w-0 rounded-lg bg-[var(--surface-muted)] px-2.5 py-2" key={row.label}>
            <dt className="text-[var(--text-muted)]">{row.label}</dt>
            <dd className="mt-1 truncate font-semibold text-slate-800">{row.value}</dd>
          </div>
        ))}
      </dl>
    </section>
  )
}

function ArtifactDetail({
  busy,
  frameKey,
  item,
  onCreateDeploy,
  onOpenPreview,
  onRefresh,
  onSaveArtifactEdit,
  onStopPreview,
}: {
  busy: boolean
  frameKey: number
  item: ArtifactPanelItem
  onCreateDeploy?: (previewId: string) => void
  onOpenPreview?: (preview: PreviewArtifact) => void
  onRefresh?: (taskRunId: string) => void
  onSaveArtifactEdit?: (artifactId: string, contentMd: string, summary: string) => void
  onStopPreview?: (previewId: string) => void
}) {
  if (item.kind === "diff") {
    return <DiffCard diff={item.artifact} />
  }

  if (item.kind === "deployment") {
    return <DeployCard deployment={item.artifact} />
  }

  if (item.kind === "review") {
    return <ReviewCard review={item.artifact} />
  }

  if (item.kind === "workbench") {
    return (
      <WorkbenchArtifactDetail
        artifact={item.artifact}
        busy={busy}
        onSaveArtifactEdit={onSaveArtifactEdit}
      />
    )
  }

  return (
    <div className="grid gap-3">
      <PreviewCard
        busy={busy}
        onCreateDeploy={onCreateDeploy}
        onOpen={onOpenPreview}
        onRefresh={onRefresh}
        onStop={onStopPreview}
        preview={item.artifact}
      />
      <iframe
        className="min-h-[420px] w-full rounded-lg border border-[var(--border)] bg-white shadow-sm"
        key={`${item.artifact.id}-${frameKey}`}
        src={item.artifact.url}
        title="Vite React 预览"
      />
    </div>
  )
}

function ArtifactRailItem({
  active,
  count,
  label,
  onSelect,
}: {
  active: boolean
  count: number
  label: string
  onSelect: () => void
}) {
  return (
    <button
      className={cn(
        "rounded-full px-2 py-2 text-center text-sm font-semibold transition",
        active
          ? "bg-slate-950 text-white shadow-sm"
          : "text-slate-500 hover:bg-white/70",
        count === 0 && "cursor-not-allowed opacity-50 hover:bg-transparent",
      )}
      disabled={count === 0}
      onClick={onSelect}
      type="button"
    >
      {label}
      {count > 0 ? <span className="ml-1 text-xs text-current">{count}</span> : null}
    </button>
  )
}

function panelTitle(item: ArtifactPanelItem | null) {
  if (!item) {
    return "证据工作台"
  }
  if (item.kind === "preview") {
    return previewHost(item.artifact.url)
  }
  if (item.kind === "deployment") {
    return item.artifact.title
  }
  if (item.kind === "review") {
    return item.artifact.title
  }
  if (item.kind === "workbench") {
    return item.artifact.title
  }
  return item.artifact.title
}

function artifactKindLabel(kind: ArtifactPanelItem["kind"]) {
  if (kind === "deployment") {
    return "部署产物"
  }

  if (kind === "preview") {
    return "预览产物"
  }

  if (kind === "workbench") {
    return "工作台产物"
  }

  return kind === "review" ? "评审产物" : "Diff 产物"
}

function summaryRows(item: ArtifactPanelItem) {
  if (item.kind === "diff") {
    return [
      { label: "文件", value: String(item.artifact.stats.filesChanged) },
      {
        label: "变更文件",
        value: item.artifact.changedFiles[0] ?? "暂无文件",
      },
      { label: "新增", value: `+${item.artifact.stats.additions}` },
      { label: "删除", value: `-${item.artifact.stats.deletions}` },
    ]
  }

  if (item.kind === "preview") {
    return [
      { label: "健康", value: statusLabel(item.artifact.healthStatus) },
      { label: "状态", value: statusLabel(item.artifact.status) },
      { label: "端口", value: String(item.artifact.port) },
      { label: "URL", value: previewHost(item.artifact.url) },
    ]
  }

  if (item.kind === "review") {
    return [
      { label: "状态", value: reviewStatusLabel(item.artifact.status) },
      { label: "风险", value: riskLabel(item.artifact.riskLevel) },
      { label: "文件", value: String(item.artifact.filesReviewed.length) },
      { label: "Adapter", value: item.artifact.adapterType },
    ]
  }

  if (item.kind === "workbench") {
    return [
      { label: "渲染", value: rendererKindLabel(item.artifact.rendererKind) },
      { label: "版本", value: `v${item.artifact.version}` },
      { label: "可编辑", value: item.artifact.editable ? "是" : "否" },
      { label: "历史", value: `${item.artifact.versions.length} 个版本` },
    ]
  }

  return [
    { label: "提供方", value: item.artifact.provider },
    { label: "状态", value: statusLabel(item.artifact.status) },
    { label: "环境", value: item.artifact.environment },
    { label: "URL", value: item.artifact.url ?? "mock://pending" },
  ]
}

function WorkbenchArtifactDetail({
  artifact,
  busy,
  onSaveArtifactEdit,
}: {
  artifact: ArtifactWorkbenchArtifact
  busy: boolean
  onSaveArtifactEdit?: (artifactId: string, contentMd: string, summary: string) => void
}) {
  const latestVersion =
    artifact.versions.find((version) => version.version === artifact.version) ??
    artifact.versions[artifact.versions.length - 1] ??
    null
  const hasTextContent = Boolean(latestVersion?.contentMd)
  const safeMeta = JSON.stringify(artifact.safeMeta, null, 2)
  const isCode = artifact.rendererKind === "code_snippet"
  const [isEditing, setIsEditing] = useState(false)
  const [draftContent, setDraftContent] = useState(latestVersion?.contentMd ?? "")
  const [draftSummary, setDraftSummary] = useState("Artifact workbench edit.")

  function startEditing() {
    setDraftContent(latestVersion?.contentMd ?? "")
    setDraftSummary("Artifact workbench edit.")
    setIsEditing(true)
  }

  function cancelEditing() {
    setDraftContent(latestVersion?.contentMd ?? "")
    setDraftSummary("Artifact workbench edit.")
    setIsEditing(false)
  }

  function saveEdit() {
    if (!draftContent.trim()) {
      return
    }
    onSaveArtifactEdit?.(artifact.artifactId, draftContent, draftSummary)
    setIsEditing(false)
  }

  return (
    <article className="grid gap-3 rounded-lg border border-[var(--border)] bg-white p-4 shadow-sm">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="flex items-center gap-2 text-xs font-medium uppercase tracking-normal text-[var(--muted-foreground)]">
            {isCode ? (
              <Code2 aria-hidden="true" size={14} />
            ) : (
              <FileText aria-hidden="true" size={14} />
            )}
            Artifact Workbench
          </p>
          <h3 className="mt-1 truncate text-sm font-semibold">{artifact.title}</h3>
          <p className="mt-1 text-xs text-[var(--muted-foreground)]">
            {rendererKindLabel(artifact.rendererKind)} · {artifact.artifactType}
          </p>
        </div>
        <span className="rounded-sm border border-[var(--border)] px-2 py-0.5 text-xs text-[var(--muted-foreground)]">
          {artifact.editable ? "可编辑" : "只读"}
        </span>
      </div>

      {artifact.editable ? (
        <div className="flex flex-wrap gap-2">
          <Button
            className="h-8 px-3 text-xs"
            disabled={busy || !onSaveArtifactEdit || isEditing}
            onClick={startEditing}
            type="button"
            variant="secondary"
          >
            编辑版本
          </Button>
          {isEditing ? (
            <Button
              className="h-8 px-3 text-xs"
              disabled={busy}
              onClick={cancelEditing}
              type="button"
              variant="secondary"
            >
              取消
            </Button>
          ) : null}
        </div>
      ) : null}

      <dl className="grid gap-2 text-xs sm:grid-cols-3">
        <div>
          <dt className="text-[var(--muted-foreground)]">版本</dt>
          <dd className="mt-1 font-medium">v{artifact.version}</dd>
        </div>
        <div>
          <dt className="text-[var(--muted-foreground)]">状态</dt>
          <dd className="mt-1 font-medium">{statusLabel(artifact.status)}</dd>
        </div>
        <div className="min-w-0">
          <dt className="text-[var(--muted-foreground)]">内容哈希</dt>
          <dd className="mt-1 truncate font-mono font-medium">
            {(latestVersion?.contentHash ?? artifact.contentHash).slice(0, 20)}
          </dd>
        </div>
      </dl>

      {isEditing ? (
        <section className="grid gap-2 rounded-lg border border-[var(--border)] bg-[var(--surface-muted)] p-3">
          <label className="grid gap-1 text-xs font-semibold text-slate-700">
            编辑内容
            <textarea
              className="min-h-48 resize-y rounded-lg border border-[var(--border)] bg-white p-3 font-mono text-xs leading-6 outline-none focus:border-slate-400"
              onChange={(event: ChangeEvent<HTMLTextAreaElement>) =>
                setDraftContent(event.target.value)
              }
              value={draftContent}
            />
          </label>
          <label className="grid gap-1 text-xs font-semibold text-slate-700">
            版本摘要
            <input
              className="rounded-lg border border-[var(--border)] bg-white px-3 py-2 text-xs outline-none focus:border-slate-400"
              onChange={(event: ChangeEvent<HTMLInputElement>) =>
                setDraftSummary(event.target.value)
              }
              value={draftSummary}
            />
          </label>
          <div className="flex justify-end gap-2">
            <Button
              className="h-8 px-3 text-xs"
              disabled={busy}
              onClick={cancelEditing}
              type="button"
              variant="secondary"
            >
              取消
            </Button>
            <Button
              className="h-8 px-3 text-xs"
              disabled={busy || !draftContent.trim()}
              onClick={saveEdit}
              type="button"
            >
              保存版本
            </Button>
          </div>
        </section>
      ) : hasTextContent ? (
        <pre className="max-h-[420px] overflow-auto rounded-lg bg-slate-950 p-3 text-xs leading-6 text-slate-50">
          <code>{latestVersion?.contentMd}</code>
        </pre>
      ) : (
        <pre className="max-h-[320px] overflow-auto rounded-lg bg-[var(--surface-muted)] p-3 text-xs leading-6 text-slate-700">
          <code>{safeMeta === "{}" ? "暂无可渲染正文，显示安全元数据 fallback。" : safeMeta}</code>
        </pre>
      )}

      <section className="rounded-lg border border-[var(--border)] bg-[var(--surface-muted)] p-3">
        <div className="flex items-center justify-between gap-3">
          <p className="text-[11px] font-bold uppercase tracking-normal text-[var(--text-muted)]">
            版本历史
          </p>
          <span className="rounded-full bg-white px-2 py-0.5 text-[11px] font-semibold text-slate-500">
            {artifact.versions.length} 个版本
          </span>
        </div>
        <ol className="mt-2 grid gap-1.5 text-xs">
          {artifact.versions.length > 0 ? (
            artifact.versions.map((version) => (
              <li
                className="grid gap-1 rounded-md bg-white px-2.5 py-2 text-slate-700"
                key={version.id}
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="font-semibold">v{version.version}</span>
                  <span className="font-mono text-[11px] text-slate-500">
                    {version.contentHash.slice(0, 18)}
                  </span>
                </div>
                <p className="line-clamp-2 text-slate-500">
                  {version.summary || "Artifact workbench version"}
                </p>
              </li>
            ))
          ) : (
            <li className="rounded-md bg-white px-2.5 py-2 text-slate-500">
              尚无版本记录
            </li>
          )}
        </ol>
      </section>
    </article>
  )
}

function ReviewCard({ review }: { review: ReviewArtifact }) {
  return (
    <article className="rounded-xl border border-[var(--border)] bg-white p-4 shadow-sm">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="flex items-center gap-2 text-xs font-medium uppercase tracking-normal text-[var(--muted-foreground)]">
            <ShieldCheck aria-hidden="true" size={14} />
            Review Agent
          </p>
          <h3 className="mt-1 truncate text-sm font-semibold">{review.title}</h3>
          <p className="mt-1 text-xs text-[var(--muted-foreground)]">
            Advisory only · {review.adapterType}
          </p>
        </div>
        <span className="rounded-sm border border-[var(--border)] px-2 py-0.5 text-xs text-[var(--muted-foreground)]">
          {reviewStatusLabel(review.status)}
        </span>
      </div>

      <p className="mt-3 rounded-md bg-slate-50 p-3 text-sm leading-6 text-slate-800">
        {review.summary}
      </p>

      <dl className="mt-3 grid gap-2 text-xs sm:grid-cols-3">
        <div>
          <dt className="text-[var(--muted-foreground)]">风险</dt>
          <dd className="mt-1 font-medium">{riskLabel(review.riskLevel)}</dd>
        </div>
        <div>
          <dt className="text-[var(--muted-foreground)]">文件</dt>
          <dd className="mt-1 font-medium">{review.filesReviewed.length}</dd>
        </div>
        <div className="min-w-0">
          <dt className="text-[var(--muted-foreground)]">Diff</dt>
          <dd className="mt-1 truncate font-mono font-medium">
            {review.reviewedDiffArtifactId.slice(0, 8)}
          </dd>
        </div>
      </dl>

      {review.findings.length > 0 ? (
        <div className="mt-3 grid gap-2">
          {review.findings.map((finding, index) => (
            <div
              className="rounded-md border border-amber-200 bg-amber-50 p-2 text-xs text-amber-950"
              key={`${String(finding.message)}-${index}`}
            >
              <p className="font-semibold">
                {String(finding.severity ?? "warning")}
                {finding.file ? ` · ${String(finding.file)}` : ""}
              </p>
              <p className="mt-1 leading-5">{String(finding.message ?? "")}</p>
            </div>
          ))}
        </div>
      ) : null}

      {review.suggestedChanges.length > 0 ? (
        <ul className="mt-3 grid gap-1 text-xs text-slate-700">
          {review.suggestedChanges.map((change) => (
            <li className="rounded bg-slate-50 px-2 py-1" key={change}>
              {change}
            </li>
          ))}
        </ul>
      ) : null}
    </article>
  )
}

function reviewStatusLabel(status: string) {
  const labels: Record<string, string> = {
    failed: "未通过",
    passed: "通过",
    warning: "警告",
  }
  return labels[status] ?? status
}

function riskLabel(riskLevel: string) {
  const labels: Record<string, string> = {
    high: "高",
    low: "低",
    medium: "中",
  }
  return labels[riskLevel] ?? riskLevel
}

function rendererKindLabel(rendererKind: string) {
  const labels: Record<string, string> = {
    code_snippet: "代码片段",
    deployment: "部署证据",
    diff: "Diff 证据",
    markdown_document: "Markdown 文档",
    review: "评审证据",
    text_document: "文本",
    unknown: "未知类型",
    web_preview: "网页预览",
  }
  return labels[rendererKind] ?? rendererKind
}
