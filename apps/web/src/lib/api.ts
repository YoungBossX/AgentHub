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

export type WorkspaceSession = {
  id: string
  workspaceId: string
  title: string
  sessionType: string
  boundBranch: string
  worktreePath: string
  status: string
  lastMessageAt: string | null
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

export type SessionTask = {
  id: string
  sessionId: string
  createdByMessageId: string | null
  title: string
  intentType: string
  status: string
  priority: number
  planJson: Record<string, unknown>
  dependsOnTaskIds: string[]
  assignedAgentId: string | null
  assignedAgentRole: string | null
  taskRuns: TaskRun[]
  createdAt: string
  updatedAt: string
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
  environment: string
  commitSha: string | null
  url: string | null
  deployLogUri: string | null
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
