"use client"

import { type ReactNode } from "react"
import { UserRound, Users } from "lucide-react"

import type { AgentContact } from "@/lib/api"
import { cn } from "@/lib/utils"

type AgentContactListProps = {
  agents: AgentContact[]
  mode: "direct" | "group"
  onModeChange: (mode: "direct" | "group") => void
  onSelectAgent: (agentId: string) => void
  selectedAgentId: string | null
}

export function AgentContactList({
  agents,
  mode,
  onModeChange,
  onSelectAgent,
  selectedAgentId,
}: AgentContactListProps) {
  return (
    <section className="mt-4 rounded-lg border border-[var(--border)] bg-white p-3">
      <div className="flex items-center justify-between gap-3">
        <div>
          <p className="text-[11px] font-bold uppercase tracking-normal text-[var(--text-muted)]">
            Agent 联系人
          </p>
          <p className="mt-1 text-xs text-[var(--muted-foreground)]">
            {agents.length} 个内置联系人
          </p>
        </div>
        <Users aria-hidden="true" className="text-[var(--primary)]" size={16} />
      </div>

      <div
        aria-label="Agent visual mode"
        className="mt-3 grid grid-cols-2 rounded-md bg-[var(--surface-muted)] p-1"
        role="group"
      >
        <AgentModeButton
          active={mode === "direct"}
          icon={<UserRound aria-hidden="true" size={13} />}
          label="Direct chat"
          onClick={() => onModeChange("direct")}
        />
        <AgentModeButton
          active={mode === "group"}
          icon={<Users aria-hidden="true" size={13} />}
          label="Group workflow"
          onClick={() => onModeChange("group")}
        />
      </div>

      <div className="mt-3 grid max-h-[310px] gap-2 overflow-y-auto pr-1">
        {agents.map((agent) => {
          const selected = agent.id === selectedAgentId
          return (
            <button
              className={cn(
                "grid gap-2 rounded-md border p-2.5 text-left transition",
                selected
                  ? "border-[var(--primary-border)] bg-[var(--primary-soft)]"
                  : "border-[var(--border)] bg-white hover:bg-[var(--surface-muted)]",
              )}
              key={agent.id}
              onClick={() => onSelectAgent(agent.id)}
              type="button"
            >
              <span className="flex items-start gap-2">
                <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md bg-slate-950 text-[11px] font-bold text-white">
                  {agent.avatarInitials}
                </span>
                <span className="min-w-0 flex-1">
                  <span className="flex items-start justify-between gap-2">
                    <span className="truncate text-sm font-semibold text-slate-950">
                      {agent.displayName}
                    </span>
                    <AgentStatus status={agent.status} />
                  </span>
                  <span className="mt-0.5 block truncate font-mono text-[11px] text-[var(--muted-foreground)]">
                    @{agent.role} · {agent.adapterType}
                  </span>
                </span>
              </span>
              <span className="flex flex-wrap gap-1">
                {agent.capabilityTags.slice(0, 3).map((tag) => (
                  <span
                    className="rounded border border-[var(--border)] bg-white px-1.5 py-0.5 text-[10px] font-medium text-slate-600"
                    key={tag}
                  >
                    {tag}
                  </span>
                ))}
              </span>
            </button>
          )
        })}
      </div>
    </section>
  )
}

function AgentModeButton({
  active,
  icon,
  label,
  onClick,
}: {
  active: boolean
  icon: ReactNode
  label: string
  onClick: () => void
}) {
  return (
    <button
      className={cn(
        "inline-flex min-h-8 items-center justify-center gap-1 rounded px-2 text-[11px] font-semibold transition",
        active
          ? "bg-white text-slate-950 shadow-sm"
          : "text-[var(--muted-foreground)] hover:text-slate-900",
      )}
      onClick={onClick}
      type="button"
    >
      {icon}
      {label}
    </button>
  )
}

function AgentStatus({ status }: { status: string }) {
  const label = status === "planned" ? "计划中" : status === "available" ? "在线" : status
  return (
    <span
      className={cn(
        "shrink-0 rounded-full border px-1.5 py-0.5 text-[10px] font-semibold",
        status === "planned"
          ? "border-amber-200 bg-amber-50 text-amber-700"
          : "border-emerald-200 bg-emerald-50 text-emerald-700",
      )}
    >
      {label}
    </span>
  )
}
