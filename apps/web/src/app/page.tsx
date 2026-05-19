import { HealthCard } from "@/components/health-card"
import { WorkspaceShell } from "@/components/workspace-shell"
import { getBackendHealth, getDemoWorkspace, listWorkspaceSessions } from "@/lib/api"

export default async function Home() {
  const backendUrl = process.env.BACKEND_URL ?? "http://127.0.0.1:8000"
  const health = await getBackendHealth(backendUrl)
  const workspace = await getDemoWorkspace(backendUrl)
  const sessions = workspace
    ? await listWorkspaceSessions(backendUrl, workspace.id)
    : []

  return (
    <main className="h-screen overflow-hidden bg-[var(--background)]">
      <WorkspaceShell
        backendUrl={backendUrl}
        healthSlot={<HealthCard health={health} backendUrl={backendUrl} />}
        initialSessions={sessions}
        workspace={workspace}
      />
    </main>
  )
}
