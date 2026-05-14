import { HealthCard } from "@/components/health-card"
import { WorkspaceShell } from "@/components/workspace-shell"
import { Button } from "@/components/ui/button"
import { getBackendHealth, getDemoWorkspace, listWorkspaceSessions } from "@/lib/api"

export default async function Home() {
  const backendUrl = process.env.BACKEND_URL ?? "http://127.0.0.1:8000"
  const health = await getBackendHealth(backendUrl)
  const workspace = await getDemoWorkspace(backendUrl)
  const sessions = workspace
    ? await listWorkspaceSessions(backendUrl, workspace.id)
    : []

  return (
    <main className="min-h-screen px-6 py-8">
      <section className="mx-auto flex w-full max-w-6xl flex-col gap-8">
        <header className="flex flex-col gap-4 border-b border-[var(--border)] pb-6 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <p className="text-sm font-medium uppercase tracking-normal text-[var(--muted-foreground)]">
              AgentHub
            </p>
            <h1 className="mt-2 text-3xl font-semibold tracking-normal text-[var(--foreground)]">
              IM Coding Workspace
            </h1>
          </div>
          <Button disabled>Task 1.6 sessions</Button>
        </header>

        <div className="grid gap-4 md:grid-cols-[1fr_360px]">
          <WorkspaceShell
            backendUrl={backendUrl}
            initialSessions={sessions}
            workspace={workspace}
          />

          <HealthCard health={health} backendUrl={backendUrl} />
        </div>
      </section>
    </main>
  )
}
