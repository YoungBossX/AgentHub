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
    <section className="grid gap-3">
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
        className="grid grid-cols-2 rounded-full bg-white/70 p-1 shadow-sm ring-1 ring-white/80"
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

      <div className="grid gap-1.5 overflow-x-hidden">
        {agents.map((agent) => {
          const selected = agent.id === selectedAgentId
          return (
            <button
              className={cn(
                "grid min-w-0 gap-1.5 rounded-lg border p-2.5 text-left transition",
                selected
                  ? "border-white bg-white text-slate-950 shadow-sm"
                  : "border-transparent bg-transparent text-slate-700 hover:bg-white/70",
              )}
              key={agent.id}
              onClick={() => onSelectAgent(agent.id)}
              type="button"
            >
              <span className="flex min-w-0 items-start gap-2">
                <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-slate-950 text-[11px] font-bold text-white">
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
              <span className="flex min-w-0 flex-wrap gap-1 overflow-hidden">
                <AgentMetaPill label={agent.providerId} tone="provider" />
                {agent.supportedTargets.slice(0, 1).map((target) => (
                  <AgentMetaPill key={target} label={target} tone="target" />
                ))}
                {agent.supportedTargets.length > 1 ? (
                  <AgentMetaPill
                    label={`+${agent.supportedTargets.length - 1} targets`}
                    tone="target"
                  />
                ) : null}
              </span>
              <span className="flex min-w-0 flex-wrap gap-1 overflow-hidden">
                {agent.capabilityTags.slice(0, 2).map((tag) => (
                  <AgentMetaPill key={tag} label={tag} tone="capability" />
                ))}
                {agent.capabilityTags.length > 2 ? (
                  <AgentMetaPill
                    label={`+${agent.capabilityTags.length - 2} caps`}
                    tone="capability"
                  />
                ) : null}
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
        "inline-flex min-h-8 items-center justify-center gap-1 rounded-full px-2 text-[11px] font-semibold transition",
        active
          ? "bg-slate-950 text-white shadow-sm"
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

function AgentMetaPill({
  label,
  tone,
}: {
  label: string
  tone: "provider" | "target" | "capability"
}) {
  return (
    <span
      className={cn(
        "max-w-[118px] truncate rounded-full border px-1.5 py-0.5 text-[10px] font-medium",
        tone === "provider"
          ? "border-blue-200 bg-blue-50 text-blue-700"
          : tone === "target"
            ? "border-slate-200 bg-slate-50 text-slate-600"
            : "border-[var(--border)] bg-white text-slate-600",
      )}
      title={label}
    >
      {label}
    </span>
  )
}

function AgentStatus({ status }: { status: string }) {
  const label =
    status === "planned"
      ? "计划中"
      : status === "available"
        ? "在线"
        : status === "auth_blocked"
          ? "需认证"
          : status === "unavailable"
            ? "不可用"
            : status === "draft_only"
              ? "草稿"
              : status === "disabled"
                ? "停用"
                : status
  const unavailable = ["auth_blocked", "unavailable", "disabled", "draft_only"].includes(
    status,
  )
  return (
    <span
      className={cn(
        "shrink-0 rounded-full border px-1.5 py-0.5 text-[10px] font-semibold",
        status === "planned"
          ? "border-amber-200 bg-amber-50 text-amber-700"
          : unavailable
            ? "border-rose-200 bg-rose-50 text-rose-700"
            : "border-emerald-200 bg-emerald-50 text-emerald-700",
      )}
    >
      {label}
    </span>
  )
}
