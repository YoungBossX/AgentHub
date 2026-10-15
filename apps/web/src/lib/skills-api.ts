import { controlledRequest, apiUrl, responseErrorMessage } from "./api-core"

export type WorkspaceSkill = {
  name: string; description: string; markdown: string; references: Record<string, string>
  roles: string[]; defaultAgents: string[]; enabled: boolean; revision: number; source: string
}
export type SkillReceipt = { source: string; sha256: string; skills: {
  name: string; description: string; revision: number; source: string; sha256: string; resources: string[]; status: string
}[] }

export async function listSkills(backendUrl: string, workspaceId: string): Promise<WorkspaceSkill[]> {
  const response = await controlledRequest(fetch, apiUrl(backendUrl, `/workspaces/${workspaceId}/skills`))
  if (!response.ok) throw new Error(await responseErrorMessage(response, "无法加载技能库"))
  return response.json()
}

export async function saveSkill(backendUrl: string, workspaceId: string, value: WorkspaceSkill): Promise<WorkspaceSkill> {
  const response = await controlledRequest(fetch, apiUrl(backendUrl, `/workspaces/${workspaceId}/skills`), {
    method: "PUT", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ markdown: value.markdown, references: value.references, roles: value.roles,
      defaultAgents: value.defaultAgents, enabled: value.enabled, expectedRevision: value.revision }),
  })
  if (!response.ok) throw new Error(await responseErrorMessage(response, "无法保存技能"))
  return response.json()
}
