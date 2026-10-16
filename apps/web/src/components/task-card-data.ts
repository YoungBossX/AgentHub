import type { PlanReviewMetadata, SessionTask } from "../lib/api"

export type PlannerEvidenceSummary = {
  contextBudget?: unknown
  errorCode?: string
  errorSummary?: string
  fallbackReason?: string
  plannerSource?: string
  providerId?: string
  validationResult?: string
}

export type PMODecisionSummaryData = {
  actor?: string
  nextActionSummary?: string
  reason?: string
  state?: string
}

export type SchedulerMeta = {
  state?: string
  runnable?: boolean
  reason?: string
  dependencyIds?: string[]
  blockingDependencyIds?: string[]
  targetId?: string | null
  writeLockRequired?: boolean
  lockHolderTaskRunIds?: string[]
  retryable?: boolean
  fallbackAvailable?: boolean
}

export function plannerEvidenceFromPlan(task: SessionTask): PlannerEvidenceSummary | null {
  const plan = task.planJson
  const evidence = objectValue(plan.plannerEvidence)
  const fallback = objectValue(plan.plannerFallback)
  const source = Object.keys(evidence).length > 0 ? evidence : fallback
  if (Object.keys(source).length === 0) {
    return null
  }

  return {
    contextBudget: source.contextBudget,
    errorCode: stringValue(source.errorCode),
    errorSummary: stringValue(source.errorSummary),
    fallbackReason: stringValue(source.fallbackReason) || stringValue(source.reason),
    plannerSource: stringValue(source.plannerSource),
    providerId: stringValue(source.providerId),
    validationResult: stringValue(source.validationResult),
  }
}

export function pmoDecisionFromPlan(task: SessionTask): PMODecisionSummaryData | null {
  const decision = objectValue(task.planJson.pmoDecision)
  const state = stringValue(decision.state)
  if (!state) {
    return null
  }
  return {
    actor: stringValue(decision.actor),
    nextActionSummary: stringValue(decision.nextActionSummary),
    reason: stringValue(decision.reason),
    state,
  }
}

export function planReviewMetadataFromPlan(task: SessionTask): PlanReviewMetadata | null {
  const plan = task.planJson
  const planDraft = objectValue(plan.planDraft)
  const taskGraph = objectValue(plan.taskGraph)
  return {
    plannerMode: stringValue(plan.plannerMode) || stringValue(plan.planner) || stringValue(planDraft.plannerMode),
    rationale: stringValue(plan.rationale) || stringValue(planDraft.rationale),
    assignedRole: stringValue(plan.assignedRole) || task.assignedAgentRole || undefined,
    targetId:
      stringValue(plan.targetId) ||
      stringValue(plan.frontendTargetId) ||
      stringValue(plan.backendTargetId),
    dependencies: task.dependsOnTaskIds,
    plannedFiles:
      stringList(plan.plannedFiles) ||
      stringList(plan.files) ||
      stringList(planDraft.plannedFiles),
    acceptanceCriteria:
      stringList(plan.acceptanceCriteria) || stringList(planDraft.acceptanceCriteria),
    validationExpectations:
      stringList(plan.validationExpectations) || stringList(planDraft.validationExpectations),
    taskBreakdown: taskBreakdownFromPlan(taskGraph.tasks),
    readOnly: true,
    sourceTaskId: task.id,
  }
}

export function taskSupportsPreview(task: SessionTask) {
  const targetId = previewTargetIdForTask(task)
  if (targetId) {
    return targetId === "demo-frontend" || targetId.includes("frontend")
  }
  return task.assignedAgentRole === "frontend" || task.intentType.includes("frontend")
}

export function previewTargetIdForTask(task: SessionTask) {
  const plan = task.planJson
  const metadata = task.planReviewMetadata
  return (
    stringValue(plan.targetId) ||
    stringValue(plan.frontendTargetId) ||
    metadata?.targetId ||
    undefined
  )
}

function taskBreakdownFromPlan(value: unknown): PlanReviewMetadata["taskBreakdown"] {
  if (!Array.isArray(value)) {
    return []
  }
  return value
    .filter((item): item is Record<string, unknown> => Boolean(item && typeof item === "object" && !Array.isArray(item)))
    .map((item) => ({
      title: stringValue(item.title) || stringValue(item.name),
      role: stringValue(item.role) || stringValue(item.assignedRole),
      targetId: stringValue(item.targetId),
      dependsOn: stringList(item.dependsOn) ?? [],
      plannedFiles: stringList(item.plannedFiles) || stringList(item.files) || [],
    }))
}

function objectValue(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : {}
}

function stringValue(value: unknown): string | undefined {
  return typeof value === "string" && value.trim() ? value.trim() : undefined
}

function stringList(value: unknown): string[] | undefined {
  if (!Array.isArray(value)) {
    return undefined
  }
  const values = value.filter((item): item is string => typeof item === "string" && item.length > 0)
  return values.length > 0 ? values : undefined
}

export function schedulerMeta(task: SessionTask): SchedulerMeta | null {
  const scheduler = task.planJson.scheduler
  if (!scheduler || typeof scheduler !== "object" || Array.isArray(scheduler)) {
    return null
  }
  return scheduler as SchedulerMeta
}

export function shortId(value: string) {
  return value.slice(0, 8)
}
