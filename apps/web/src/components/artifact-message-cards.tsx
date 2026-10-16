import { FileDiff, FileText, Monitor, Rocket, SearchCheck } from "lucide-react"
import type { ArtifactPanelItem } from "./preview-card"
import type { DeploymentArtifact, PreviewArtifact, ReviewArtifact } from "../lib/api"
import { healthLabel, statusLabel } from "./task-card"
import { qaLabel } from "./qa-evidence"
import { Button } from "./ui/button"
import { cn } from "@/lib/utils"

export type ArtifactContextIntent = "ask" | "revise" | "send_to_agent"

export function ArtifactMessageCards({
  deployments,
  onCreateDeploy,
  onCreateReview,
  onOpenPreview,
  onSelectArtifact,
  onUseArtifactContext,
  reviews,
  selectedArtifactId,
  taskArtifactItems,
}: {
  deployments: DeploymentArtifact[]
  onCreateDeploy?: (previewId: string) => void
  onCreateReview?: (taskRunId: string) => void
  onOpenPreview?: (preview: PreviewArtifact) => void
  onSelectArtifact?: (artifactId: string) => void
  onUseArtifactContext?: (
    artifact: ArtifactPanelItem,
    intent?: ArtifactContextIntent,
  ) => void
  reviews: ReviewArtifact[]
  selectedArtifactId: string | null
  taskArtifactItems: ArtifactPanelItem[]
}) {
  if (taskArtifactItems.length === 0) {
    return null
  }

  return (
    <section
      aria-label="Artifact message cards"
      className="mt-3 grid gap-2 rounded-lg border border-[var(--border)] bg-[var(--surface-muted)]/80 p-3"
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-[11px] font-bold uppercase tracking-normal text-[var(--text-muted)]">
          证据卡片
        </p>
        <span className="rounded-full bg-white px-2.5 py-1 text-[11px] font-semibold text-slate-500 shadow-sm">
          {taskArtifactItems.length} 个会话产物
        </span>
      </div>

      <div className="grid gap-2">
        {[...taskArtifactItems].sort(compareArtifactCards).map((item) => (
          <ArtifactMessageCard
            deployments={deployments}
            item={item}
            key={`${item.id}:${item.taskRunId}`}
            onCreateDeploy={onCreateDeploy}
            onCreateReview={onCreateReview}
            onOpenPreview={onOpenPreview}
            onSelectArtifact={onSelectArtifact}
            onUseArtifactContext={onUseArtifactContext}
            reviews={reviews}
            selected={selectedArtifactId === item.id}
          />
        ))}
      </div>
    </section>
  )
}

function ArtifactMessageCard({
  deployments,
  item,
  onCreateDeploy,
  onCreateReview,
  onOpenPreview,
  onSelectArtifact,
  onUseArtifactContext,
  reviews,
  selected,
}: {
  deployments: DeploymentArtifact[]
  item: ArtifactPanelItem
  onCreateDeploy?: (previewId: string) => void
  onCreateReview?: (taskRunId: string) => void
  onOpenPreview?: (preview: PreviewArtifact) => void
  onSelectArtifact?: (artifactId: string) => void
  onUseArtifactContext?: (
    artifact: ArtifactPanelItem,
    intent?: ArtifactContextIntent,
  ) => void
  reviews: ReviewArtifact[]
  selected: boolean
}) {
  const meta = artifactCardMeta(item)
  const reviewed = item.kind === "diff" && reviews.some(
    (review) =>
      review.reviewedDiffArtifactId === item.artifact.artifactId ||
      review.taskRunId === item.taskRunId,
  )
  const deployed = item.kind === "preview" && deployments.some(
    (deployment) => deployment.taskRunId === item.taskRunId,
  )

  return (
    <article
      className={cn(
        "rounded-lg border bg-white p-3 shadow-sm",
        artifactCardBorder(item.kind),
        selected && "ring-2 ring-[var(--primary-border)]",
      )}
    >
      <div className="flex items-start gap-3">
        <span
          className={cn(
            "flex h-9 w-9 shrink-0 items-center justify-center rounded-lg",
            artifactCardIconClass(item.kind),
          )}
        >
          <ArtifactKindIcon kind={item.kind} />
        </span>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[11px] font-bold uppercase tracking-normal text-slate-600">
              {artifactCardKindLabel(item.kind)}
            </span>
            <span className="rounded-full bg-white px-2 py-0.5 font-mono text-[11px] font-semibold text-slate-500 ring-1 ring-slate-200">
              run {item.taskRunId.slice(0, 8)}
            </span>
            <span className="rounded-full bg-slate-50 px-2 py-0.5 text-[11px] font-semibold text-slate-600">
              {meta.status}
            </span>
          </div>
          <h4 className="mt-2 line-clamp-1 text-sm font-semibold text-slate-950">
            {meta.title}
          </h4>
          <p className="mt-1 line-clamp-2 text-xs leading-5 text-slate-600">
            {meta.summary}
          </p>
          <dl className="mt-2 grid gap-2 text-[11px] sm:grid-cols-3">
            {meta.rows.map((row) => (
              <div className="min-w-0 rounded-md bg-slate-50 px-2 py-1.5" key={row.label}>
                <dt className="text-slate-500">{row.label}</dt>
                <dd className="mt-0.5 truncate font-semibold text-slate-800">
                  {row.value}
                </dd>
              </div>
            ))}
          </dl>
          <p className="mt-2 line-clamp-1 text-[11px] text-slate-500">
            Source task: {item.taskTitle}
          </p>
        </div>
      </div>

      <div className="mt-3 flex flex-wrap gap-2">
        <Button
          className="h-8 px-3 text-xs"
          disabled={!onSelectArtifact}
          onClick={() => onSelectArtifact?.(item.id)}
          type="button"
          variant="secondary"
        >
          {artifactInspectLabel(item.kind)}
        </Button>
        {item.kind === "diff" ? (
          <>
            <ContextActionButtons item={item} onUseArtifactContext={onUseArtifactContext} />
            <Button
              className="h-8 px-3 text-xs"
              disabled={!onCreateReview || reviewed}
              onClick={() => onCreateReview?.(item.taskRunId)}
              type="button"
              variant="secondary"
            >
              {reviewed ? "评审已就绪" : "评审 Diff"}
            </Button>
          </>
        ) : null}
        {item.kind === "review" ? (
          <ContextActionButtons item={item} onUseArtifactContext={onUseArtifactContext} />
        ) : null}
        {item.kind === "preview" ? (
          <>
            <Button
              className="h-8 px-3 text-xs"
              disabled={!onOpenPreview}
              onClick={() => onOpenPreview?.(item.artifact)}
              type="button"
              variant="secondary"
            >
              打开预览
            </Button>
            <Button
              className="h-8 px-3 text-xs"
              disabled={
                !onCreateDeploy || deployed || item.artifact.healthStatus !== "healthy"
              }
              onClick={() => onCreateDeploy?.(item.artifact.id)}
              type="button"
              variant="secondary"
            >
              {deployed ? "部署卡已就绪" : "创建部署卡"}
            </Button>
          </>
        ) : null}
        {item.kind === "deployment" ? (
          <ContextActionButtons item={item} onUseArtifactContext={onUseArtifactContext} />
        ) : null}
      </div>
    </article>
  )
}

function ContextActionButtons({
  item,
  onUseArtifactContext,
}: {
  item: ArtifactPanelItem
  onUseArtifactContext?: (
    artifact: ArtifactPanelItem,
    intent?: ArtifactContextIntent,
  ) => void
}) {
  const disabled = !onUseArtifactContext
  return (
    <>
      <Button
        className="h-8 px-3 text-xs"
        disabled={disabled}
        onClick={() => onUseArtifactContext?.(item)}
        type="button"
        variant="secondary"
      >
        作为上下文
      </Button>
      <Button
        className="h-8 px-3 text-xs"
        disabled={disabled}
        onClick={() => onUseArtifactContext?.(item, "ask")}
        type="button"
        variant="secondary"
      >
        询问此项
      </Button>
      <Button
        className="h-8 px-3 text-xs"
        disabled={disabled}
        onClick={() => onUseArtifactContext?.(item, "revise")}
        type="button"
        variant="secondary"
      >
        基于此修改
      </Button>
      <Button
        className="h-8 px-3 text-xs"
        disabled={disabled}
        onClick={() => onUseArtifactContext?.(item, "send_to_agent")}
        type="button"
        variant="secondary"
      >
        交给 Agent
      </Button>
    </>
  )
}

function compareArtifactCards(a: ArtifactPanelItem, b: ArtifactPanelItem) {
  const order: Record<ArtifactPanelItem["kind"], number> = {
    deployment: 3,
    diff: 0,
    preview: 2,
    review: 1,
    workbench: 4,
  }
  return order[a.kind] - order[b.kind]
}

function artifactCardMeta(item: ArtifactPanelItem) {
  if (item.kind === "diff") {
    return {
      rows: [
        { label: "文件", value: String(item.artifact.stats.filesChanged) },
        { label: "新增", value: `+${item.artifact.stats.additions}` },
        { label: "删除", value: `-${item.artifact.stats.deletions}` },
      ],
      status: statusLabel(item.artifact.status),
      summary: item.artifact.changedFiles[0] ?? "本次运行已捕获 Git Diff。",
      title: item.artifact.title,
    }
  }

  if (item.kind === "review") {
    return {
      rows: [
        { label: "风险", value: item.artifact.riskLevel },
        { label: "文件", value: String(item.artifact.filesReviewed.length) },
        { label: "来源", value: item.artifact.nativeReceipt ? "模型评审 · 未运行测试" : item.artifact.adapterType },
      ],
      status: qaLabel(item.artifact),
      summary: item.artifact.summary,
      title: item.artifact.title,
    }
  }

  if (item.kind === "preview") {
    return {
      rows: [
        { label: "健康", value: healthLabel(item.artifact.healthStatus) },
        { label: "状态", value: statusLabel(item.artifact.status) },
        { label: "端口", value: String(item.artifact.port) },
      ],
      status: healthLabel(item.artifact.healthStatus),
      summary: item.artifact.url,
      title: item.artifact.title,
    }
  }

  if (item.kind === "workbench") {
    const latestVersion =
      item.artifact.versions.find((version) => version.version === item.artifact.version) ??
      item.artifact.versions[item.artifact.versions.length - 1] ??
      null
    return {
      rows: [
        { label: "版本", value: `v${item.artifact.version}` },
        { label: "渲染", value: item.artifact.rendererKind },
        { label: "编辑", value: item.artifact.editable ? "可编辑" : "只读" },
      ],
      status: statusLabel(item.artifact.status),
      summary: latestVersion?.summary || "Artifact Workbench 元数据产物。",
      title: item.artifact.title,
    }
  }

  return {
    rows: [
      { label: "提供方", value: item.artifact.provider },
      { label: "环境", value: item.artifact.environment },
      { label: "URL", value: item.artifact.url ?? "未生成 URL" },
    ],
    status: statusLabel(item.artifact.status),
    summary: "本地部署证据卡片，不代表生产发布。",
    title: item.artifact.title,
  }
}

function artifactCardKindLabel(kind: ArtifactPanelItem["kind"]) {
  const labels: Record<ArtifactPanelItem["kind"], string> = {
    deployment: "部署",
    diff: "Diff",
    preview: "预览",
    review: "评审",
    workbench: "文档",
  }
  return labels[kind]
}

function artifactInspectLabel(kind: ArtifactPanelItem["kind"]) {
  const labels: Record<ArtifactPanelItem["kind"], string> = {
    deployment: "查看部署",
    diff: "查看 Diff",
    preview: "查看预览",
    review: "查看评审",
    workbench: "查看文档",
  }
  return labels[kind]
}

function ArtifactKindIcon({ kind }: { kind: ArtifactPanelItem["kind"] }) {
  if (kind === "deployment") {
    return <Rocket aria-hidden="true" size={17} />
  }
  if (kind === "preview") {
    return <Monitor aria-hidden="true" size={17} />
  }
  if (kind === "review") {
    return <SearchCheck aria-hidden="true" size={17} />
  }
  if (kind === "workbench") {
    return <FileText aria-hidden="true" size={17} />
  }
  return <FileDiff aria-hidden="true" size={17} />
}

function artifactCardIconClass(kind: ArtifactPanelItem["kind"]) {
  const classes: Record<ArtifactPanelItem["kind"], string> = {
    deployment: "bg-violet-50 text-violet-700",
    diff: "bg-cyan-50 text-cyan-700",
    preview: "bg-green-50 text-green-700",
    review: "bg-amber-50 text-amber-700",
    workbench: "bg-slate-100 text-slate-700",
  }
  return classes[kind]
}

function artifactCardBorder(kind: ArtifactPanelItem["kind"]) {
  const classes: Record<ArtifactPanelItem["kind"], string> = {
    deployment: "border-violet-200",
    diff: "border-cyan-200",
    preview: "border-green-200",
    review: "border-amber-200",
    workbench: "border-slate-200",
  }
  return classes[kind]
}
