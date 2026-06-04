import Link from "next/link"
import { ArrowLeft } from "lucide-react"

import { MemorySettingsPageClient } from "@/components/memory-settings-page-client"

export default function MemorySettingsPage() {
  const backendUrl = process.env.BACKEND_URL ?? "http://127.0.0.1:8000"

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
          <Link
            className="inline-flex items-center gap-2 rounded-md border border-[var(--border)] bg-white px-3 py-2 text-sm font-semibold text-slate-700 transition hover:border-[var(--primary-border)] hover:text-[var(--primary)]"
            href="/"
          >
            <ArrowLeft aria-hidden="true" size={16} />
            返回聊天
          </Link>
        </header>

        <MemorySettingsPageClient backendUrl={backendUrl} />
      </div>
    </main>
  )
}
