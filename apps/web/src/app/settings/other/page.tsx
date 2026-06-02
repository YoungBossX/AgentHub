import Link from "next/link"
import { ArrowLeft, MoreHorizontal } from "lucide-react"

export default function OtherSettingsPage() {
  return (
    <main className="h-screen overflow-y-auto bg-[var(--background)] px-5 py-6">
      <div className="mx-auto grid max-w-5xl gap-6">
        <header className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <p className="text-[11px] font-bold tracking-normal text-[var(--text-muted)]">
              AgentHub 设置
            </p>
            <h1 className="mt-1 text-2xl font-semibold text-slate-950">
              其他设置
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

        <section className="rounded-lg border border-dashed border-[var(--border)] bg-white p-8 text-center shadow-sm">
          <span className="mx-auto flex h-11 w-11 items-center justify-center rounded-lg bg-[var(--surface-muted)] text-slate-700">
            <MoreHorizontal aria-hidden="true" size={20} />
          </span>
          <h2 className="mt-4 text-base font-semibold text-slate-950">
            功能暂未开放
          </h2>
          <p className="mx-auto mt-2 max-w-md text-sm leading-6 text-[var(--muted-foreground)]">
            其他设置入口已保留，后续可以继续扩展为更多本地偏好或工作台配置。
          </p>
        </section>
      </div>
    </main>
  )
}
