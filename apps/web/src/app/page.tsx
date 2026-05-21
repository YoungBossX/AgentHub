import { HealthCard } from "@/components/health-card"
import { WorkspaceShell } from "@/components/workspace-shell"
import {
  getBackendHealth,
  getDemoWorkspace,
  listWorkspaceAgents,
  listWorkspaceSessions,
} from "@/lib/api"

export default async function Home() {
  const backendUrl = process.env.BACKEND_URL ?? "http://127.0.0.1:8000"
  const health = await getBackendHealth(backendUrl)
  const workspace = await getDemoWorkspace(backendUrl)
  const agents = workspace ? await listWorkspaceAgents(backendUrl, workspace.id) : []
  const sessions = workspace
    ? await listWorkspaceSessions(backendUrl, workspace.id)
    : []

  return (
    <main className="h-screen overflow-hidden bg-[var(--background)]">
      <WorkspaceShell
        backendUrl={backendUrl}
        healthSlot={<HealthCard health={health} backendUrl={backendUrl} />}
        initialAgents={agents}
        initialSessions={sessions}
        workspace={workspace}
      />
    </main>
  )
}
