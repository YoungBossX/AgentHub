import Link from "next/link"
import { ArrowLeft, Settings } from "lucide-react"

import { RuntimeSettingsPageClient } from "@/components/runtime-settings-page-client"
import { getDemoWorkspace } from "@/lib/api"

export default async function RuntimeSettingsPage() {
  const backendUrl = process.env.BACKEND_URL ?? "http://127.0.0.1:8000"
  const workspace = await getDemoWorkspace(backendUrl)

  return (
    <main className="min-h-screen overflow-y-auto bg-[var(--background)] px-5 py-6">
      <div className="mx-auto grid max-w-5xl gap-6">
        <header className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <p className="text-[11px] font-bold uppercase tracking-normal text-[var(--text-muted)]">
              AgentHub Settings
            </p>
            <h1 className="mt-1 text-2xl font-semibold text-slate-950">
              运行设置
            </h1>
            <p className="mt-2 max-w-2xl text-sm text-[var(--muted-foreground)]">
              配置 Planner、Frontend、Backend 和 Review Agent 的运行时提供方。
            </p>
          </div>
          <Link
            className="inline-flex items-center gap-2 rounded-md border border-[var(--border)] bg-white px-3 py-2 text-sm font-semibold text-slate-700 transition hover:border-[var(--primary-border)] hover:text-[var(--primary)]"
            href="/"
          >
            <ArrowLeft aria-hidden="true" size={16} />
            返回聊天
          </Link>
        </header>

        <section className="rounded-lg border border-[var(--border)] bg-white p-5">
          <div className="flex items-center gap-3">
            <span className="inline-flex h-9 w-9 items-center justify-center rounded-md bg-[var(--primary-soft)] text-[var(--primary)]">
              <Settings aria-hidden="true" size={18} />
            </span>
            <div>
              <h2 className="text-base font-semibold text-slate-950">
                Agent Runtime Settings
              </h2>
              <p className="mt-1 text-sm text-[var(--muted-foreground)]">
                详细配置表单将在此页面加载，不再占用聊天会话侧栏。
              </p>
            </div>
          </div>
        </section>

        <RuntimeSettingsPageClient
          backendUrl={backendUrl}
          workspace={workspace}
        />
      </div>
    </main>
  )
}
