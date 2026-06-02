"use client"

import { useState } from "react"

import { AgentContactList } from "@/components/agent-contact-list"
import type { AgentContact, Workspace } from "@/lib/api"

type ContactSettingsPageClientProps = {
  agents: AgentContact[]
  workspace: Workspace | null
}

export function ContactSettingsPageClient({
  agents,
  workspace,
}: ContactSettingsPageClientProps) {
  const [mode, setMode] = useState<"direct" | "group">("group")
  const [selectedAgentId, setSelectedAgentId] = useState<string | null>(
    agents[0]?.id ?? null,
  )

  return (
    <section className="grid gap-4">
      <div className="rounded-lg border border-[var(--border)] bg-white p-5 shadow-sm">
        <p className="text-[11px] font-bold uppercase tracking-normal text-[var(--text-muted)]">
          工作区
        </p>
        <h2 className="mt-1 text-base font-semibold text-slate-950">
          {workspace?.name ?? "未选择工作区"}
        </h2>
        <p className="mt-1 truncate font-mono text-xs text-[var(--muted-foreground)]">
          {workspace?.rootPath ?? "正在加载工作区..."}
        </p>
      </div>

      <div className="rounded-lg border border-[var(--border)] bg-[#f8fbfb] p-4 shadow-sm">
        <AgentContactList
          agents={agents}
          mode={mode}
          onModeChange={setMode}
          onSelectAgent={setSelectedAgentId}
          selectedAgentId={selectedAgentId}
        />
      </div>
    </section>
  )
}
