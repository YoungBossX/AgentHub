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
}: ContactSettingsPageClientProps) {
  const [mode, setMode] = useState<"direct" | "group">("group")
  const [selectedAgentId, setSelectedAgentId] = useState<string | null>(
    agents[0]?.id ?? null,
  )

  return (
    <section className="grid gap-4">
      <div className="rounded-lg border border-[var(--border)] bg-[linear-gradient(150deg,#f2faf8_0%,#f8fbfb_52%,#ffffff_100%)] p-4 shadow-sm">
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
