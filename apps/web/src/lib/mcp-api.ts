import { controlledRequest, apiUrl, responseErrorMessage } from "./api-core"

export type McpConnection = { serverId: string; enabled: boolean; tools: string[]; defaultAgents: string[]; revision: number }
export type McpRunEvidence = { connection: { serverId: string; revision: number; tools: string[]; status: string } | null
  events: { id: string; type: string; createdAt: string; payload: { tool?: string; status?: string; durationMs?: number; arguments?: unknown; result?: unknown } }[] }

async function request<T>(base: string, path: string, options?: RequestInit): Promise<T> {
  const response = await controlledRequest(fetch, apiUrl(base, path), options)
  if (!response.ok) throw new Error(await responseErrorMessage(response, "MCP 请求失败"))
  return response.json()
}
export const getMcpConnection = (base: string, workspaceId: string) => request<McpConnection>(base, `/workspaces/${workspaceId}/mcp`)
export const saveMcpConnection = (base: string, workspaceId: string, config: McpConnection) => request<McpConnection>(base, `/workspaces/${workspaceId}/mcp`, {
  method: "PUT", headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ enabled: config.enabled, tools: config.tools, defaultAgents: config.defaultAgents, expectedRevision: config.revision }),
})
export const probeMcpConnection = (base: string, workspaceId: string) => request<{ status: string; reason?: string; tools?: string[] }>(base, `/workspaces/${workspaceId}/mcp/probe`, { method: "POST" })
export const getMcpRunEvidence = (base: string, runId: string) => request<McpRunEvidence>(base, `/task-runs/${runId}/mcp`)
