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
