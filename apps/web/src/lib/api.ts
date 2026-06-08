export type BackendHealth = {
  status: string
  service: string
  database: string
}

export type Workspace = {
  id: string
  name: string
  repoUrl: string
  rootPath: string
  defaultBranch: string
  createdAt: string
}

export type TargetProject = {
  targetId: string
  name: string
  type: "frontend" | "backend" | "platform" | string
  root: string
  allowedPaths: string[]
  deniedPaths: string[]
  devCommand: string | null
  testCommand: string | null
  checkCommand: string | null
  buildCommand: string | null
  previewCommand: string | null
  stagingOutputDir: string | null
  stagingServeCommand: string | null
  deployProviderIds: string[]
  baseUrl: string | null
  packageManager: string | null
  detectedFramework: string | null
  projectType: string | null
  analysisStatus: string | null
  allowedAgents: string[]
  requiresPlatformMode: boolean
  requiresApproval: boolean
  relatedTargetIds: string[]
}

export type ExternalProjectAnalysis = {
  rootPath: string
  projectType: string
  detectedFramework: string
  packageManager: string
  allowedPaths: string[]
  deniedPaths: string[]
  devCommand: string | null
  testCommand: string | null
  checkCommand: string | null
  buildCommand: string | null
  previewCommand: string | null
  analysisStatus: string
  analysisWarnings: string[]
  confidence: string
}

export type ExternalProjectTargetInput = {
  targetId?: string | null
  name: string
  rootPath: string
  projectType: string
  allowedPaths: string[]
  deniedPaths?: string[]
  devCommand?: string | null
  testCommand?: string | null
  checkCommand?: string | null
  buildCommand?: string | null
  previewCommand?: string | null
  stagingOutputDir?: string | null
  stagingServeCommand?: string | null
  deployProviderIds?: string[]
  packageManager?: string | null
  detectedFramework?: string | null
}

export type ExternalProjectTarget = ExternalProjectTargetInput & {
  id: string
  workspaceId: string
  targetId: string
  deniedPaths: string[]
  devCommand: string | null
  testCommand: string | null
  checkCommand: string | null
  buildCommand: string | null
  previewCommand: string | null
  stagingOutputDir: string | null
  stagingServeCommand: string | null
  deployProviderIds: string[]
  packageManager: string | null
  detectedFramework: string | null
  analysisStatus: string
  createdAt: string
  updatedAt: string
}

export type LocalFolderEntry = {
  name: string
  path: string
}

export type LocalFolderStart = {
  label: string
  path: string
}

export type LocalFolderListing = {
  currentPath: string
  parentPath: string | null
  starts: LocalFolderStart[]
  children: LocalFolderEntry[]
}

export type AgentContact = {
  id: string
  displayName: string
  avatarInitials: string
  role: string
  adapterType: string
  providerId: string
  capabilityTags: string[]
  supportedTargets: string[]
  supportedModes: string[]
  status: string
  safeForWrite: boolean
  safeForReview: boolean
  description: string
  contactType: "agent" | "placeholder" | "service" | string
}

export type AgentProfile = {
  id: string
  displayName: string
  avatarInitials: string
  role: string
  adapterType: string
  providerId: string
  capabilityTags: string[]
  supportedRoles: string[]
  supportedTargets: string[]
  supportedModes: string[]
  safeForWrite: boolean
  safeForReview: boolean
  description: string
  status: string
}

export type ProviderConfig = {
  providerId: string
  displayName: string
  adapterType: string
  authStatus: string
  available: boolean
  defaultForRoles: string[]
  supportedModes: string[]
}

export type AgentCompatibility = {
  compatible: boolean
  reasons: string[]
  warnings: string[]
  role: string | null
  targetId: string | null
  mode: string | null
  requiredCapabilities: string[]
}

export type AgentDirectoryEntry = {
  id: string
  entryType: "built_in" | "draft" | string
  displayName: string
  avatarInitials: string
  role: string
  agentProfileId: string
  providerId: string
  adapterType: string
  capabilityTags: string[]
  supportedTargets: string[]
  supportedModes: string[]
  safeForWrite: boolean
  safeForReview: boolean
  status: string
  authStatus: string
  available: boolean
  runtimeSelectedForRoles: string[]
  compatibility: AgentCompatibility
  description: string
}

export type AgentDirectory = {
  workspaceId: string
  entries: AgentDirectoryEntry[]
}

export type RuntimeRoleConfig = {
  role: string
  agentProfileId: string | null
  providerId: string | null
  adapterType: string | null
  mode: string | null
  enabled: boolean
  fallbackPolicy: string | null
  providerPresetId: string | null
  protocol: string | null
  model: string | null
  baseUrl: string | null
  timeoutSeconds: number | null
  apiKeyEnv: string | null
  availability: string | null
}

export type RuntimeConfigValidation = {
  valid: boolean
  errors: string[]
  warnings: string[]
}

export type AgentRuntimeConfig = {
  workspaceId: string | null
  configSource: string
  roles: Record<string, RuntimeRoleConfig>
  availableProfiles: AgentProfile[]
  availableProviders: ProviderConfig[]
  validation: RuntimeConfigValidation
}

export type RuntimeProviderCheck = {
  role: string
  providerId: string | null
  adapterType: string | null
  authStatus: string
  availability: string
  available: boolean
  message: string
}

export type RuntimeRoleConfigInput = {
  agentProfileId?: string | null
  providerId?: string | null
  adapterType?: string | null
  mode?: string | null
  enabled: boolean
  fallbackPolicy?: string | null
  providerPresetId?: string | null
  protocol?: string | null
  model?: string | null
  baseUrl?: string | null
  timeoutSeconds?: number | null
  apiKeyEnv?: string | null
  availability?: string | null
}

export type WorkspaceSession = {
  id: string
  workspaceId: string
  title: string
  sessionType: string
  boundBranch: string
  worktreePath: string
  activeFrontendTargetId?: string | null
  activeBackendTargetId?: string | null
  memorySnapshotId?: string | null
  status: string
  lastMessageAt: string | null
  createdAt: string
  updatedAt: string
}

export type MemoryItem = {
  id: string
  workspaceId: string | null
  scope: string
  memoryType: string
  source: string
  status: string
  trustLevel: string
  title: string
  contentMd: string
  contentHash: string
  version: number
  importance: number
  targetIds: string[]
  agentRoles: string[]
  lastUsedAt: string | null
  supersededBy: string | null
  compiledToAgentsMd: boolean
  compiledToClaudeMd: boolean
  createdAt: string
  updatedAt: string
}

export type ChatMessage = {
  id: string
  sessionId: string
  senderType: "user" | "system" | "orchestrator" | "agent" | string
  senderId: string | null
  contentMd: string
  messageKind: string
  parentMessageId: string | null
  streamState: string
  createdAt: string
}

export type SessionExecutionLedger = {
  id: string
  sessionId: string
  currentGoal: string | null
  activeAgents: string[]
  latestTaskId: string | null
  latestTaskRunId: string | null
  latestDiffArtifactId: string | null
  latestChangedFiles: string[]
  latestPreviewId: string | null
  latestPreviewUrl: string | null
  latestPreviewHealth: string | null
  latestDeploymentId: string | null
  latestDeploymentProvider: string | null
  latestDeploymentStatus: string | null
  lastSuccessfulAdapter: string | null
  summaryMd: string
  updatedAt: string
}

export type SessionTask = {
  id: string
  sessionId: string
  createdByMessageId: string | null
  title: string
  intentType: string
  status: string
  priority: number
  planJson: Record<string, unknown>
  planReviewMetadata?: PlanReviewMetadata
  dependsOnTaskIds: string[]
  assignedAgentId: string | null
  assignedAgentRole: string | null
  taskRuns: TaskRun[]
  createdAt: string
  updatedAt: string
}

export type PMOPlanDecisionAction = "approve" | "reject" | "clarification"

export type PlanReviewMetadata = {
  plannerMode?: string
  rationale?: string
  assignedRole?: string
  targetId?: string
  dependencies?: string[]
  plannedFiles?: string[]
  acceptanceCriteria?: string[]
  validationExpectations?: string[]
  taskBreakdown?: Array<{
    title?: string
    role?: string
    targetId?: string
    dependsOn?: string[]
    plannedFiles?: string[]
  }>
  readOnly?: boolean
  sourceTaskId?: string
}

export type ApprovalRequest = {
  approvalType: "product_confirmation" | "security_approval" | string
  reason: string
  requestedAction: string
  riskLevel: "low" | "medium" | "high" | string
  command: string | null
  path: string | null
  expiresAt: string | null
}

export type TaskRun = {
  id: string
  taskId: string
  sessionId: string
  agentId: string
  adapterType: string
  adapterRunId: string | null
  state: string
  startedAt: string | null
  endedAt: string | null
  worktreePath: string
  baseRef: string | null
  headRef: string | null
  errorCode: string | null
  errorMessage: string | null
  metricsJson: Record<string, unknown>
  approvalRequest?: ApprovalRequest | null
  createdAt: string
  updatedAt: string
}

export type DiffFileStat = {
  path: string
  additions: number
  deletions: number
}

export type DiffStats = {
  filesChanged: number
  additions: number
  deletions: number
  files: DiffFileStat[]
}

export type DiffArtifact = {
  id: string
  artifactId: string
  taskRunId: string
  artifactType: "diff" | string
  title: string
  status: string
  baseRef: string
  headRef: string
  patchText: string
  changedFiles: string[]
  stats: DiffStats
}

export type ReviewArtifact = {
  id: string
  artifactId: string
  taskRunId: string
  reviewedDiffArtifactId: string
  artifactType: "review" | string
  title: string
  status: "passed" | "warning" | "failed" | string
  riskLevel: "low" | "medium" | "high" | string
  summary: string
  filesReviewed: string[]
  findings: Array<Record<string, unknown>>
  suggestedChanges: string[]
  adapterType: string
}

export type PreviewArtifact = {
  id: string
  artifactId: string
  taskRunId: string
  artifactType: "preview" | string
  title: string
  status: string
  port: number
  url: string
  command: string
  processId: number | null
  healthStatus: string
  statusReason: string | null
  expiresAt: string | null
  lastCheckedAt: string | null
}

export type DeploymentArtifact = {
  id: string
  artifactId: string
  taskRunId: string
  artifactType: "deployment" | string
  title: string
  status: string
  provider: string
  providerType: string | null
  environment: string
  commitSha: string | null
  url: string | null
  deployLogUri: string | null
  targetId: string | null
  sourcePreviewId: string | null
  sourceDiffArtifactId: string | null
  sourceReviewArtifactId: string | null
  logs: string[]
  statusHistory: Array<{ status: string; message?: string }>
  createdAt: string
  updatedAt: string
}

type Fetcher = typeof fetch

function apiUrl(backendUrl: string, path: string) {
  return `${backendUrl.replace(/\/$/, "")}${path}`
}

export async function getBackendHealth(
  backendUrl: string,
  fetcher: Fetcher = fetch,
): Promise<BackendHealth> {
  const response = await fetcher(apiUrl(backendUrl, "/health"), {
    cache: "no-store",
  })

  if (!response.ok) {
    return {
      status: "unreachable",
      service: "agenthub-api",
      database: "unknown",
    }
  }

  return (await response.json()) as BackendHealth
}

export async function getDemoWorkspace(
  backendUrl: string,
  fetcher: Fetcher = fetch,
): Promise<Workspace | null> {
  const response = await fetcher(apiUrl(backendUrl, "/workspaces/demo"), {
    cache: "no-store",
  })

  if (!response.ok) {
    return null
  }

  return (await response.json()) as Workspace
}

export async function listWorkspaceSessions(
  backendUrl: string,
  workspaceId: string,
  fetcher: Fetcher = fetch,
): Promise<WorkspaceSession[]> {
  const response = await fetcher(
    apiUrl(backendUrl, `/workspaces/${workspaceId}/sessions`),
    {
      cache: "no-store",
    },
  )

  if (!response.ok) {
    return []
  }

  return (await response.json()) as WorkspaceSession[]
}

export async function listWorkspaceTargets(
  backendUrl: string,
  workspaceId: string,
  fetcher: Fetcher = fetch,
): Promise<TargetProject[]> {
  const response = await fetcher(
    apiUrl(backendUrl, `/workspaces/${workspaceId}/targets`),
    {
      cache: "no-store",
    },
  )

  if (!response.ok) {
    return []
  }

  return (await response.json()) as TargetProject[]
}

export async function analyzeExternalProject(
  backendUrl: string,
  workspaceId: string,
  rootPath: string,
  fetcher: Fetcher = fetch,
): Promise<ExternalProjectAnalysis> {
  const response = await fetcher(
    apiUrl(backendUrl, `/workspaces/${workspaceId}/external-targets/analyze`),
    {
      body: JSON.stringify({ rootPath }),
      headers: { "Content-Type": "application/json" },
      method: "POST",
    },
  )

  if (!response.ok) {
    throw new Error("Could not analyze external project")
  }

  return (await response.json()) as ExternalProjectAnalysis
}

export async function createExternalProjectTarget(
  backendUrl: string,
  workspaceId: string,
  input: ExternalProjectTargetInput,
  fetcher: Fetcher = fetch,
): Promise<ExternalProjectTarget> {
  const response = await fetcher(
    apiUrl(backendUrl, `/workspaces/${workspaceId}/external-targets`),
    {
      body: JSON.stringify(input),
      headers: { "Content-Type": "application/json" },
      method: "POST",
    },
  )

  if (!response.ok) {
    throw new Error("Could not register external project")
  }

  return (await response.json()) as ExternalProjectTarget
}

export async function listExternalTargetFolders(
  backendUrl: string,
  workspaceId: string,
  path?: string,
  fetcher: Fetcher = fetch,
): Promise<LocalFolderListing> {
  const params = new URLSearchParams()
  if (path) {
    params.set("path", path)
  }
  const query = params.toString()
  const response = await fetcher(
    apiUrl(
      backendUrl,
      `/workspaces/${workspaceId}/external-targets/folders${query ? `?${query}` : ""}`,
    ),
    {
      cache: "no-store",
    },
  )

  if (!response.ok) {
    return {
      children: [],
      currentPath: path ?? "",
      parentPath: null,
      starts: [],
    }
  }

  return (await response.json()) as LocalFolderListing
}

export async function updateSessionTargetSelection(
  backendUrl: string,
  sessionId: string,
  selection: {
    frontendTargetId?: string | null
    backendTargetId?: string | null
  },
  fetcher: Fetcher = fetch,
): Promise<WorkspaceSession> {
  const response = await fetcher(
    apiUrl(backendUrl, `/sessions/${sessionId}/target-selection`),
    {
      body: JSON.stringify(selection),
      headers: { "Content-Type": "application/json" },
      method: "PATCH",
    },
  )

  if (!response.ok) {
    throw new Error("Could not update session target selection")
  }

  return (await response.json()) as WorkspaceSession
}

export async function listWorkspaceAgents(
  backendUrl: string,
  workspaceId: string,
  fetcher: Fetcher = fetch,
): Promise<AgentContact[]> {
  const response = await fetcher(
    apiUrl(backendUrl, `/workspaces/${workspaceId}/agents`),
    {
      cache: "no-store",
    },
  )

  if (!response.ok) {
    return []
  }

  return (await response.json()) as AgentContact[]
}

export async function listWorkspaceAgentProfiles(
  backendUrl: string,
  workspaceId: string,
  fetcher: Fetcher = fetch,
): Promise<AgentProfile[]> {
  const response = await fetcher(
    apiUrl(backendUrl, `/workspaces/${workspaceId}/agent-profiles`),
    {
      cache: "no-store",
    },
  )

  if (!response.ok) {
    return []
  }

  return (await response.json()) as AgentProfile[]
}

export async function listProviderConfigs(
  backendUrl: string,
  fetcher: Fetcher = fetch,
): Promise<ProviderConfig[]> {
  const response = await fetcher(apiUrl(backendUrl, "/provider-configs"), {
    cache: "no-store",
  })

  if (!response.ok) {
    return []
  }

  return (await response.json()) as ProviderConfig[]
}

export async function getWorkspaceAgentDirectory(
  backendUrl: string,
  workspaceId: string,
  fetcher: Fetcher = fetch,
): Promise<AgentDirectory | null> {
  const response = await fetcher(
    apiUrl(backendUrl, `/workspaces/${workspaceId}/agent-directory`),
    {
      cache: "no-store",
    },
  )

  if (!response.ok) {
    return null
  }

  return (await response.json()) as AgentDirectory
}

export async function getAgentRuntimeConfig(
  backendUrl: string,
  workspaceId: string,
  fetcher: Fetcher = fetch,
): Promise<AgentRuntimeConfig | null> {
  const response = await fetcher(
    apiUrl(backendUrl, `/workspaces/${workspaceId}/runtime-config`),
    {
      cache: "no-store",
    },
  )

  if (!response.ok) {
    return null
  }

  return (await response.json()) as AgentRuntimeConfig
}

export async function updateAgentRuntimeConfig(
  backendUrl: string,
  workspaceId: string,
  roles: Record<string, RuntimeRoleConfigInput>,
  fetcher: Fetcher = fetch,
): Promise<AgentRuntimeConfig> {
  const response = await fetcher(
    apiUrl(backendUrl, `/workspaces/${workspaceId}/runtime-config`),
    {
      body: JSON.stringify({ roles }),
      headers: { "Content-Type": "application/json" },
      method: "PUT",
    },
  )

  if (!response.ok) {
    throw new Error("Could not update runtime config")
  }

  return (await response.json()) as AgentRuntimeConfig
}

export async function checkAgentRuntimeProvider(
  backendUrl: string,
  workspaceId: string,
  role: string,
  roleConfig: RuntimeRoleConfigInput,
  fetcher: Fetcher = fetch,
): Promise<RuntimeProviderCheck> {
  const response = await fetcher(
    apiUrl(backendUrl, `/workspaces/${workspaceId}/runtime-config/check-provider`),
    {
      body: JSON.stringify({ role, roleConfig }),
      headers: { "Content-Type": "application/json" },
      method: "POST",
    },
  )

  if (!response.ok) {
    throw new Error("Could not check runtime provider")
  }

  return (await response.json()) as RuntimeProviderCheck
}

export async function listWorkspaceMemory(
  backendUrl: string,
  workspaceId: string,
  status: string | null = null,
  fetcher: Fetcher = fetch,
): Promise<MemoryItem[]> {
  const suffix = status ? `?status=${encodeURIComponent(status)}` : ""
  const response = await fetcher(
    apiUrl(backendUrl, `/workspaces/${workspaceId}/memory${suffix}`),
    {
      cache: "no-store",
    },
  )

  if (!response.ok) {
    return []
  }

  return (await response.json()) as MemoryItem[]
}

export async function updateMemoryItemStatus(
  backendUrl: string,
  memoryItemId: string,
  status: string,
  fetcher: Fetcher = fetch,
): Promise<MemoryItem> {
  const response = await fetcher(
    apiUrl(backendUrl, `/memory/${memoryItemId}/status`),
    {
      body: JSON.stringify({ status }),
      headers: { "Content-Type": "application/json" },
      method: "PATCH",
    },
  )

  if (!response.ok) {
    throw new Error("Could not update memory status")
  }

  return (await response.json()) as MemoryItem
}

export async function createWorkspaceSession(
  backendUrl: string,
  workspaceId: string,
  title: string,
  fetcher: Fetcher = fetch,
): Promise<WorkspaceSession> {
  const response = await fetcher(
    apiUrl(backendUrl, `/workspaces/${workspaceId}/sessions`),
    {
      body: JSON.stringify({ title }),
      headers: { "Content-Type": "application/json" },
      method: "POST",
    },
  )

  if (!response.ok) {
    throw new Error("Could not create session")
  }

  return (await response.json()) as WorkspaceSession
}

export async function listSessionMessages(
  backendUrl: string,
  sessionId: string,
  fetcher: Fetcher = fetch,
): Promise<ChatMessage[]> {
  const response = await fetcher(apiUrl(backendUrl, `/sessions/${sessionId}/messages`), {
    cache: "no-store",
  })

  if (!response.ok) {
    return []
  }

  return (await response.json()) as ChatMessage[]
}

export async function getSessionLedger(
  backendUrl: string,
  sessionId: string,
  fetcher: Fetcher = fetch,
): Promise<SessionExecutionLedger | null> {
  const response = await fetcher(apiUrl(backendUrl, `/sessions/${sessionId}/ledger`), {
    cache: "no-store",
  })

  if (!response.ok) {
    return null
  }

  return (await response.json()) as SessionExecutionLedger
}

export async function createSessionMessage(
  backendUrl: string,
  sessionId: string,
  contentMd: string,
  fetcher: Fetcher = fetch,
): Promise<ChatMessage> {
  const response = await fetcher(apiUrl(backendUrl, `/sessions/${sessionId}/messages`), {
    body: JSON.stringify({
      contentMd,
      senderType: "user",
    }),
    headers: { "Content-Type": "application/json" },
    method: "POST",
  })

  if (!response.ok) {
    throw new Error("Could not create message")
  }

  return (await response.json()) as ChatMessage
}

export function sessionEventsUrl(
  backendUrl: string,
  sessionId: string,
  afterSequence = 0,
) {
  const params = new URLSearchParams({
    after: String(afterSequence),
    stream: "true",
  })
  return apiUrl(backendUrl, `/sessions/${sessionId}/events?${params.toString()}`)
}

export async function listSessionTasks(
  backendUrl: string,
  sessionId: string,
  fetcher: Fetcher = fetch,
): Promise<SessionTask[]> {
  const response = await fetcher(apiUrl(backendUrl, `/sessions/${sessionId}/tasks`), {
    cache: "no-store",
  })

  if (!response.ok) {
    return []
  }

  return (await response.json()) as SessionTask[]
}

export async function createTaskRun(
  backendUrl: string,
  taskId: string,
  fetcher: Fetcher = fetch,
): Promise<TaskRun> {
  return mutateTaskRun(apiUrl(backendUrl, `/tasks/${taskId}/runs`), fetcher)
}

export async function decideTaskPlan(
  backendUrl: string,
  taskId: string,
  action: PMOPlanDecisionAction,
  reason: string,
  fetcher: Fetcher = fetch,
): Promise<SessionTask> {
  const response = await fetcher(apiUrl(backendUrl, `/tasks/${taskId}/plan-decision/${action}`), {
    body: JSON.stringify({ reason }),
    headers: { "Content-Type": "application/json" },
    method: "POST",
  })

  if (!response.ok) {
    throw new Error("Could not update PMO plan decision")
  }

  return (await response.json()) as SessionTask
}

export async function forceCodexFailure(
  backendUrl: string,
  taskId: string,
  fetcher: Fetcher = fetch,
): Promise<TaskRun> {
  return mutateTaskRun(
    apiUrl(backendUrl, `/tasks/${taskId}/runs/force-codex-failure`),
    fetcher,
  )
}

export async function interruptTaskRun(
  backendUrl: string,
  taskRunId: string,
  fetcher: Fetcher = fetch,
): Promise<TaskRun> {
  return mutateTaskRun(apiUrl(backendUrl, `/task-runs/${taskRunId}/interrupt`), fetcher)
}

export async function retryTaskRun(
  backendUrl: string,
  taskRunId: string,
  fetcher: Fetcher = fetch,
): Promise<TaskRun> {
  return mutateTaskRun(apiUrl(backendUrl, `/task-runs/${taskRunId}/retry`), fetcher)
}

export async function retryTaskRunWithFallback(
  backendUrl: string,
  taskRunId: string,
  fetcher: Fetcher = fetch,
): Promise<TaskRun> {
  return mutateTaskRun(
    apiUrl(backendUrl, `/task-runs/${taskRunId}/retry-with-fallback`),
    fetcher,
  )
}

export async function approveTaskRun(
  backendUrl: string,
  taskRunId: string,
  fetcher: Fetcher = fetch,
): Promise<TaskRun> {
  return mutateTaskRun(apiUrl(backendUrl, `/task-runs/${taskRunId}/approve`), fetcher)
}

export async function denyTaskRun(
  backendUrl: string,
  taskRunId: string,
  reason: string,
  fetcher: Fetcher = fetch,
): Promise<TaskRun> {
  const response = await fetcher(apiUrl(backendUrl, `/task-runs/${taskRunId}/deny`), {
    body: JSON.stringify({ reason }),
    headers: { "Content-Type": "application/json" },
    method: "POST",
  })

  if (!response.ok) {
    throw new Error("Could not deny task run")
  }

  return (await response.json()) as TaskRun
}

export async function listTaskRunDiffs(
  backendUrl: string,
  taskRunId: string,
  fetcher: Fetcher = fetch,
): Promise<DiffArtifact[]> {
  const response = await fetcher(apiUrl(backendUrl, `/task-runs/${taskRunId}/diffs`), {
    cache: "no-store",
  })

  if (!response.ok) {
    return []
  }

  return (await response.json()) as DiffArtifact[]
}

export async function createTaskRunReview(
  backendUrl: string,
  taskRunId: string,
  fetcher: Fetcher = fetch,
): Promise<ReviewArtifact> {
  const response = await fetcher(apiUrl(backendUrl, `/task-runs/${taskRunId}/review`), {
    method: "POST",
  })

  if (!response.ok) {
    throw new Error("Could not create review")
  }

  return (await response.json()) as ReviewArtifact
}

export async function listTaskRunReviews(
  backendUrl: string,
  taskRunId: string,
  fetcher: Fetcher = fetch,
): Promise<ReviewArtifact[]> {
  const response = await fetcher(apiUrl(backendUrl, `/task-runs/${taskRunId}/reviews`), {
    cache: "no-store",
  })

  if (!response.ok) {
    return []
  }

  return (await response.json()) as ReviewArtifact[]
}

export async function startTaskRunPreview(
  backendUrl: string,
  taskRunId: string,
  fetcher: Fetcher = fetch,
): Promise<PreviewArtifact> {
  const response = await fetcher(apiUrl(backendUrl, `/task-runs/${taskRunId}/preview`), {
    method: "POST",
  })

  if (!response.ok) {
    throw new Error("Could not start preview")
  }

  return (await response.json()) as PreviewArtifact
}

export async function listTaskRunPreviews(
  backendUrl: string,
  taskRunId: string,
  fetcher: Fetcher = fetch,
): Promise<PreviewArtifact[]> {
  const response = await fetcher(apiUrl(backendUrl, `/task-runs/${taskRunId}/previews`), {
    cache: "no-store",
  })

  if (!response.ok) {
    return []
  }

  return (await response.json()) as PreviewArtifact[]
}

export async function stopPreview(
  backendUrl: string,
  previewId: string,
  fetcher: Fetcher = fetch,
): Promise<PreviewArtifact> {
  const response = await fetcher(apiUrl(backendUrl, `/previews/${previewId}/stop`), {
    method: "POST",
  })

  if (!response.ok) {
    throw new Error("Could not stop preview")
  }

  return (await response.json()) as PreviewArtifact
}

export async function createPreviewDeployment(
  backendUrl: string,
  previewId: string,
  fetcher: Fetcher = fetch,
): Promise<DeploymentArtifact> {
  const response = await fetcher(apiUrl(backendUrl, `/previews/${previewId}/deploy`), {
    method: "POST",
  })

  if (!response.ok) {
    throw new Error("Could not create deployment")
  }

  return (await response.json()) as DeploymentArtifact
}

export async function listTaskRunDeployments(
  backendUrl: string,
  taskRunId: string,
  fetcher: Fetcher = fetch,
): Promise<DeploymentArtifact[]> {
  const response = await fetcher(
    apiUrl(backendUrl, `/task-runs/${taskRunId}/deployments`),
    {
      cache: "no-store",
    },
  )

  if (!response.ok) {
    return []
  }

  return (await response.json()) as DeploymentArtifact[]
}

async function mutateTaskRun(url: string, fetcher: Fetcher): Promise<TaskRun> {
  const response = await fetcher(url, { method: "POST" })

  if (!response.ok) {
    throw new Error("Could not update task run")
  }

  return (await response.json()) as TaskRun
}
