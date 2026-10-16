import { apiUrl, controlledRequest, responseErrorMessage } from "./api-core"

export type RepairSelection = { reviewArtifactId: string; issueIds: string[]; expectedFingerprint: string }
export type RepairDraft = { contentMd: string; selection: RepairSelection }
export type RepairIssue = { id: string; message: string; file: string | null; line: number | null; autoVerifiable: boolean; outcome?: string }
export type RepairHistory = {
  messageId: string; taskIds: string[]; runs: { id: string; state: string; errorCode: string | null }[]
  artifactIds: string[]; issues: RepairIssue[]; confirmations: { issueId: string; sourceFingerprint: string; confirmedAt: string }[]
  revision: string; sourceFingerprint: string | null; state: string; checksCurrent: boolean; sourceChanged: boolean; canConfirm: boolean
}
export type RepairState = { issues: RepairIssue[]; history: RepairHistory[]; canPrepare: boolean; reason: string | null; sourceFingerprint: string | null }

export async function reviewRepairRequest<T>(backendUrl: string, sessionId: string, artifactId: string, action = "", body?: unknown): Promise<T> {
  const response = await controlledRequest(fetch, apiUrl(backendUrl, `/sessions/${encodeURIComponent(sessionId)}/reviews/${encodeURIComponent(artifactId)}/repair${action}`), body === undefined ? {} : {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
  })
  if (!response.ok) throw new Error(await responseErrorMessage(response, "无法读取评审修复记录"))
  return await response.json() as T
}
