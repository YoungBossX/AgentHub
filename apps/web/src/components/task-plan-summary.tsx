import { ContextBudgetEvidence } from "./context-budget-evidence"
import { Button } from "./ui/button"
import type { PlanReviewMetadata } from "../lib/api"
import type { PlannerEvidenceSummary, PMODecisionSummaryData } from "./task-card-data"

export function PlanReviewSummary({
  metadata,
  plannerEvidence,
}: {
  metadata: PlanReviewMetadata | null
  plannerEvidence: PlannerEvidenceSummary | null
}) {
  if (!metadata && !plannerEvidence) {
    return null
  }
  const plannedFiles = metadata?.plannedFiles ?? []
  const acceptanceCriteria = metadata?.acceptanceCriteria ?? []
  const validationExpectations = metadata?.validationExpectations ?? []
  const taskBreakdown = metadata?.taskBreakdown ?? []
  const hasContent = Boolean(
    metadata?.plannerMode ||
      metadata?.rationale ||
      metadata?.targetId ||
      plannedFiles.length ||
      acceptanceCriteria.length ||
      validationExpectations.length ||
      taskBreakdown.length ||
      plannerEvidence,
  )
  if (!hasContent) {
    return null
  }

  return (
    <section className="mt-3 rounded-lg border border-[var(--border)] bg-white p-3 text-xs">
      <div className="flex flex-wrap items-center gap-2">
        <span className="font-bold text-slate-700">计划审阅</span>
        {metadata?.plannerMode ? (
          <span className="rounded-full bg-slate-100 px-2 py-0.5 font-mono text-[11px] font-semibold text-slate-600">
            {metadata.plannerMode}
          </span>
        ) : null}
        {metadata?.targetId ? (
          <span className="rounded-full bg-white px-2 py-0.5 font-mono text-[11px] font-semibold text-slate-500 ring-1 ring-slate-200">
            {metadata.targetId}
          </span>
        ) : null}
        {metadata?.readOnly ? (
          <span className="rounded-full bg-slate-50 px-2 py-0.5 text-[11px] font-semibold text-slate-500">
            read-only
          </span>
        ) : null}
        {plannerEvidence?.plannerSource ? (
          <span className="rounded-full bg-purple-50 px-2 py-0.5 text-[11px] font-semibold text-purple-700">
            {plannerEvidence.plannerSource}
          </span>
        ) : null}
      </div>
      {metadata?.rationale ? (
        <p className="mt-2 line-clamp-2 text-slate-600">{metadata.rationale}</p>
      ) : null}
      {plannerEvidence ? (
        <div className="mt-2 grid gap-1.5 rounded-md bg-purple-50 px-2.5 py-2 text-[11px] text-purple-900">
          <p className="font-semibold">规划证据</p>
          <div className="flex flex-wrap gap-1.5">
            {plannerEvidence.providerId ? (
              <span className="rounded bg-white/70 px-2 py-0.5 font-mono">
                {plannerEvidence.providerId}
              </span>
            ) : null}
            {plannerEvidence.validationResult ? (
              <span className="rounded bg-white/70 px-2 py-0.5">
                validation {plannerEvidence.validationResult}
              </span>
            ) : null}
            {plannerEvidence.fallbackReason ? (
              <span className="rounded bg-white/70 px-2 py-0.5">
                fallback {plannerEvidence.fallbackReason}
              </span>
            ) : null}
            {plannerEvidence.errorCode ? (
              <span className="rounded bg-white/70 px-2 py-0.5">
                {plannerEvidence.errorCode}
              </span>
            ) : null}
          </div>
          {plannerEvidence.errorSummary ? (
            <p className="line-clamp-2">{plannerEvidence.errorSummary}</p>
          ) : null}
          <ContextBudgetEvidence receipt={plannerEvidence.contextBudget} />
        </div>
      ) : null}
      <div className="mt-2 flex flex-wrap gap-1.5 text-[11px] font-medium text-slate-500">
        {metadata?.assignedRole ? (
          <span className="rounded bg-slate-50 px-2 py-0.5">@{metadata.assignedRole}</span>
        ) : null}
        {taskBreakdown.length > 0 ? (
          <span className="rounded bg-slate-50 px-2 py-0.5">
            task graph {taskBreakdown.length}
          </span>
        ) : null}
        {plannedFiles.slice(0, 3).map((file) => (
          <span className="rounded bg-slate-50 px-2 py-0.5 font-mono" key={file}>
            {file}
          </span>
        ))}
        {plannedFiles.length > 3 ? (
          <span className="rounded bg-slate-50 px-2 py-0.5">
            +{plannedFiles.length - 3} files
          </span>
        ) : null}
        {acceptanceCriteria.length > 0 ? (
          <span className="rounded bg-green-50 px-2 py-0.5 text-green-700">
            acceptance {acceptanceCriteria.length}
          </span>
        ) : null}
        {validationExpectations.length > 0 ? (
          <span className="rounded bg-blue-50 px-2 py-0.5 text-blue-700">
            validation {validationExpectations.length}
          </span>
        ) : null}
      </div>
    </section>
  )
}

export function PMODecisionSummary({
  decision,
  onApprove,
  onReject,
  onRequestClarification,
}: {
  decision: PMODecisionSummaryData | null
  onApprove?: () => void
  onReject?: () => void
  onRequestClarification?: () => void
}) {
  if (!decision?.state) {
    return null
  }
  const pending = decision.state === "pending_review"
  return (
    <section className="mt-3 rounded-lg border border-amber-200 bg-amber-50/70 p-3 text-xs">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex flex-wrap items-center gap-2">
          <span className="font-bold text-amber-950">PMO 决策</span>
          <span className="rounded-full bg-white px-2 py-0.5 font-semibold text-amber-800 ring-1 ring-amber-200">
            {pmoDecisionLabel(decision.state)}
          </span>
          {decision.actor ? (
            <span className="rounded-full bg-white/80 px-2 py-0.5 font-mono text-[11px] text-amber-800">
              {decision.actor}
            </span>
          ) : null}
        </div>
        {pending ? (
          <div className="flex flex-wrap gap-1.5">
            <Button
              className="h-8 px-2.5 text-xs"
              disabled={!onApprove}
              onClick={onApprove}
              type="button"
            >
              批准计划
            </Button>
            <Button
              className="h-8 px-2.5 text-xs"
              disabled={!onRequestClarification}
              onClick={onRequestClarification}
              type="button"
              variant="secondary"
            >
              要求澄清
            </Button>
            <Button
              className="h-8 px-2.5 text-xs"
              disabled={!onReject}
              onClick={onReject}
              type="button"
              variant="secondary"
            >
              拒绝计划
            </Button>
          </div>
        ) : null}
      </div>
      {decision.reason ? (
        <p className="mt-2 line-clamp-2 text-amber-900">{decision.reason}</p>
      ) : null}
      {decision.nextActionSummary ? (
        <p className="mt-1 line-clamp-2 text-[11px] text-amber-800">
          {decision.nextActionSummary}
        </p>
      ) : null}
    </section>
  )
}

function pmoDecisionLabel(state: string) {
  if (state === "pending_review") {
    return "待审阅"
  }
  if (state === "approved") {
    return "已批准"
  }
  if (state === "rejected") {
    return "已拒绝"
  }
  if (state === "clarification_needed") {
    return "需澄清"
  }
  return state
}
