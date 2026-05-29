"use client"

import { Bot, Save, ShieldCheck } from "lucide-react"

import { Button } from "@/components/ui/button"
import type {
  AgentProfile,
  AgentRuntimeConfig,
  RuntimeRoleConfigInput,
} from "@/lib/api"
import { cn } from "@/lib/utils"

const CONFIGURABLE_ROLES = [
  { label: "Planner Agent", role: "planner", mode: "read_only" },
  { label: "Frontend Agent", role: "frontend", mode: "frontend" },
  { label: "Backend Agent", role: "backend", mode: "backend" },
] as const

type AgentRuntimeSettingsProps = {
  busy: boolean
  config: AgentRuntimeConfig | null
  draftRoles: Record<string, RuntimeRoleConfigInput>
  onRoleChange: (role: string, nextRole: RuntimeRoleConfigInput) => void
  onSave: () => void
  statusMessage: string | null
}

export function AgentRuntimeSettings({
  busy,
  config,
  draftRoles,
  onRoleChange,
  onSave,
  statusMessage,
}: AgentRuntimeSettingsProps) {
  if (!config) {
    return (
      <section className="mt-4 rounded-lg border border-[var(--border)] bg-white p-3">
        <div className="flex items-center gap-2">
          <Bot aria-hidden="true" className="text-[var(--primary)]" size={16} />
          <p className="text-sm font-semibold text-slate-950">
            Agent Runtime Settings
          </p>
        </div>
        <p className="mt-2 text-xs text-[var(--muted-foreground)]">
          Runtime config loading
        </p>
      </section>
    )
  }

  return (
    <section className="mt-4 rounded-lg border border-[var(--border)] bg-white p-3">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-[11px] font-bold uppercase tracking-normal text-[var(--text-muted)]">
            Agent Runtime Settings
          </p>
          <p className="mt-1 text-xs text-[var(--muted-foreground)]">
            Source: {config.configSource}
          </p>
        </div>
        <ShieldCheck aria-hidden="true" className="text-emerald-600" size={16} />
      </div>

      <div className="mt-3 grid gap-3">
        {CONFIGURABLE_ROLES.map(({ label, mode, role }) => (
          <RuntimeRoleSelector
            config={config}
            draftRole={draftRoles[role] ?? config.roles[role]}
            key={role}
            label={label}
            mode={mode}
            onChange={(nextRole) => onRoleChange(role, nextRole)}
            role={role}
          />
        ))}
      </div>

      {config.validation.errors.length > 0 ? (
        <div className="mt-3 rounded border border-red-200 bg-red-50 p-2 text-xs text-red-800">
          {config.validation.errors[0]}
        </div>
      ) : null}
      {config.validation.warnings.length > 0 ? (
        <div className="mt-3 rounded border border-amber-200 bg-amber-50 p-2 text-xs text-amber-800">
          {config.validation.warnings[0]}
        </div>
      ) : null}
      {statusMessage ? (
        <div className="mt-3 rounded border border-blue-200 bg-blue-50 p-2 text-xs text-blue-800">
          {statusMessage}
        </div>
      ) : null}

      <Button
        className="mt-3 w-full"
        disabled={busy}
        onClick={onSave}
        type="button"
      >
        <Save aria-hidden="true" size={15} />
        Save runtime config
      </Button>
    </section>
  )
}

function RuntimeRoleSelector({
  config,
  draftRole,
  label,
  mode,
  onChange,
  role,
}: {
  config: AgentRuntimeConfig
  draftRole: RuntimeRoleConfigInput
  label: string
  mode: string
  onChange: (nextRole: RuntimeRoleConfigInput) => void
  role: string
}) {
  const profileOptions = config.availableProfiles.filter((profile) =>
    profileSupportsRole(profile, role),
  )
  const providerOptions = config.availableProviders.filter((provider) =>
    provider.supportedModes.includes(mode),
  )
  const selectedProfile = config.availableProfiles.find(
    (profile) => profile.id === draftRole.agentProfileId,
  )
  const selectedProvider = config.availableProviders.find(
    (provider) => provider.providerId === draftRole.providerId,
  )

  function patchRole(next: Partial<RuntimeRoleConfigInput>) {
    onChange({
      agentProfileId: draftRole.agentProfileId ?? null,
      adapterType: draftRole.adapterType ?? null,
      enabled: draftRole.enabled,
      fallbackPolicy: draftRole.fallbackPolicy ?? "environment_default",
      mode: draftRole.mode ?? mode,
      providerId: draftRole.providerId ?? null,
      ...next,
    })
  }

  return (
    <div className="rounded-md border border-[var(--border)] bg-[var(--surface-muted)] p-2">
      <div className="flex items-center justify-between gap-2">
        <p className="text-sm font-semibold text-slate-950">{label}</p>
        <label className="inline-flex items-center gap-1.5 text-xs font-medium text-[var(--muted-foreground)]">
          <input
            checked={draftRole.enabled}
            className="h-3.5 w-3.5"
            onChange={(event) => patchRole({ enabled: event.target.checked })}
            type="checkbox"
          />
          Enabled
        </label>
      </div>

      <label className="mt-2 block text-[11px] font-bold uppercase tracking-normal text-[var(--text-muted)]">
        Profile
        <select
          className="mt-1 w-full rounded border border-[var(--border)] bg-white px-2 py-1.5 text-xs font-medium text-slate-900"
          onChange={(event) => {
            const profile = config.availableProfiles.find(
              (item) => item.id === event.target.value,
            )
            patchRole({
              agentProfileId: profile?.id ?? null,
              enabled: true,
            })
          }}
          value={draftRole.agentProfileId ?? ""}
        >
          <option value="">Select profile</option>
          {profileOptions.map((profile) => (
            <option disabled={profile.status !== "available"} key={profile.id} value={profile.id}>
              {profile.displayName} · {profile.status}
            </option>
          ))}
        </select>
      </label>

      <label className="mt-2 block text-[11px] font-bold uppercase tracking-normal text-[var(--text-muted)]">
        Provider
        <select
          className="mt-1 w-full rounded border border-[var(--border)] bg-white px-2 py-1.5 text-xs font-medium text-slate-900"
          onChange={(event) => {
            const provider = config.availableProviders.find(
              (item) => item.providerId === event.target.value,
            )
            patchRole({
              adapterType: provider?.adapterType ?? null,
              enabled: true,
              mode,
              providerId: provider?.providerId ?? null,
            })
          }}
          value={draftRole.providerId ?? ""}
        >
          <option value="">Select provider</option>
          {providerOptions.map((provider) => (
            <option disabled={!provider.available} key={provider.providerId} value={provider.providerId}>
              {provider.displayName} · {provider.authStatus}
            </option>
          ))}
        </select>
      </label>

      <div className="mt-2 flex flex-wrap gap-1">
        <RuntimePill label={draftRole.adapterType ?? "adapter unset"} tone="provider" />
        <RuntimePill label={mode} tone="mode" />
        {selectedProvider ? (
          <RuntimePill
            label={selectedProvider.available ? "available" : "unavailable"}
            tone={selectedProvider.available ? "ok" : "danger"}
          />
        ) : null}
      </div>
      {selectedProfile ? (
        <div className="mt-2 flex flex-wrap gap-1">
          {selectedProfile.capabilityTags.slice(0, 3).map((tag) => (
            <RuntimePill key={tag} label={tag} tone="capability" />
          ))}
          {selectedProfile.supportedTargets.slice(0, 2).map((target) => (
            <RuntimePill key={target} label={target} tone="target" />
          ))}
        </div>
      ) : null}
    </div>
  )
}

function RuntimePill({
  label,
  tone,
}: {
  label: string
  tone: "provider" | "mode" | "capability" | "target" | "ok" | "danger"
}) {
  return (
    <span
      className={cn(
        "max-w-full truncate rounded border px-1.5 py-0.5 text-[10px] font-medium",
        tone === "provider"
          ? "border-blue-200 bg-blue-50 text-blue-700"
          : tone === "ok"
            ? "border-emerald-200 bg-emerald-50 text-emerald-700"
            : tone === "danger"
              ? "border-rose-200 bg-rose-50 text-rose-700"
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

function profileSupportsRole(profile: AgentProfile, role: string) {
  const roleAliases =
    role === "planner"
      ? ["planner", "orchestrator", "manager"]
      : role === "review"
        ? ["review", "qa"]
        : [role]
  return roleAliases.some((candidate) => profile.supportedRoles.includes(candidate))
}
