import { MemorySettingsPageClient } from "@/components/memory-settings-page-client"

export default async function MemorySettingsPage({
  searchParams,
}: {
  searchParams: Promise<{ session?: string | string[] }>
}) {
  const backendUrl = process.env.BACKEND_URL ?? "http://127.0.0.1:8000"
  const params = await searchParams
  const initialSessionId = typeof params.session === "string" ? params.session : null

  return (
    <main className="h-screen overflow-y-auto bg-[var(--background)] px-5 py-6">
      <div className="mx-auto grid max-w-5xl gap-6">
        <header className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <p className="text-[11px] font-bold tracking-normal text-[var(--text-muted)]">
              AgentHub 设置
            </p>
            <h1 className="mt-1 text-2xl font-semibold text-slate-950">
              记忆设置
            </h1>
          </div>
        </header>

        <MemorySettingsPageClient backendUrl={backendUrl} initialSessionId={initialSessionId} key={initialSessionId} />
      </div>
    </main>
  )
}
