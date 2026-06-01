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

const PLANNER_PROVIDER_PRESETS = [
  {
    baseUrl: "https://api.openai.com/v1",
    id: "openai_api",
    label: "OpenAI API",
    model: "gpt-4.1-mini",
    protocol: "openai_responses",
    apiKeyEnv: "OPENAI_API_KEY",
  },
  {
    baseUrl: "https://api.deepseek.com",
    id: "deepseek_api",
    label: "DeepSeek API",
    model: "deepseek-chat",
    protocol: "openai_compatible_chat",
    apiKeyEnv: "DEEPSEEK_API_KEY",
  },
  {
    baseUrl: "https://api.xiaomimimo.com/v1",
    id: "mimo_api",
    label: "MiMo API",
    model: "mimo-v2.5-pro",
    protocol: "openai_compatible_chat",
    apiKeyEnv: "MIMO_API_KEY",
  },
  {
    baseUrl: "https://api.anthropic.com",
    id: "anthropic_api",
    label: "Anthropic API",
    model: "claude-sonnet-4-5",
    protocol: "anthropic_messages",
    apiKeyEnv: "ANTHROPIC_API_KEY",
  },
  {
    baseUrl: "",
    id: "custom_openai_compatible",
    label: "Custom OpenAI-compatible",
    model: "",
    protocol: "openai_compatible_chat",
    apiKeyEnv: "CUSTOM_OPENAI_COMPATIBLE_API_KEY",
  },
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
      apiKeyEnv: draftRole.apiKeyEnv ?? null,
      availability: draftRole.availability ?? null,
      baseUrl: draftRole.baseUrl ?? null,
      enabled: draftRole.enabled,
      fallbackPolicy: draftRole.fallbackPolicy ?? "environment_default",
      mode: draftRole.mode ?? mode,
      model: draftRole.model ?? null,
      protocol: draftRole.protocol ?? null,
      providerId: draftRole.providerId ?? null,
      providerPresetId: draftRole.providerPresetId ?? null,
      timeoutSeconds: draftRole.timeoutSeconds ?? null,
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

      {role === "planner" ? (
        <PlannerProviderControls draftRole={draftRole} onChange={patchRole} />
      ) : null}

      <div className="mt-2 flex flex-wrap gap-1">
        <RuntimePill label={draftRole.adapterType ?? "adapter unset"} tone="provider" />
        <RuntimePill label={mode} tone="mode" />
        {role === "planner" && draftRole.providerPresetId ? (
          <RuntimePill label={draftRole.providerPresetId} tone="provider" />
        ) : null}
        {role === "planner" && draftRole.availability ? (
          <RuntimePill
            label={draftRole.availability}
            tone={draftRole.availability === "configured" ? "ok" : "danger"}
          />
        ) : null}
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

function PlannerProviderControls({
  draftRole,
  onChange,
}: {
  draftRole: RuntimeRoleConfigInput
  onChange: (nextRole: Partial<RuntimeRoleConfigInput>) => void
}) {
  return (
    <div className="mt-2 grid gap-2">
      <label className="block text-[11px] font-bold uppercase tracking-normal text-[var(--text-muted)]">
        Planner API
        <select
          className="mt-1 w-full rounded border border-[var(--border)] bg-white px-2 py-1.5 text-xs font-medium text-slate-900"
          onChange={(event) => {
            const preset = PLANNER_PROVIDER_PRESETS.find(
              (item) => item.id === event.target.value,
            )
            onChange({
              adapterType: preset?.protocol ?? null,
              apiKeyEnv: preset?.apiKeyEnv ?? null,
              availability: null,
              baseUrl: preset?.baseUrl ?? null,
              enabled: Boolean(preset),
              mode: "read_only",
              model: preset?.model ?? null,
              protocol: preset?.protocol ?? null,
              providerPresetId: preset?.id ?? null,
            })
          }}
          value={draftRole.providerPresetId ?? ""}
        >
          <option value="">Select planner API preset</option>
          {PLANNER_PROVIDER_PRESETS.map((preset) => (
            <option key={preset.id} value={preset.id}>
              {preset.label}
            </option>
          ))}
        </select>
      </label>

      <div className="grid gap-2 sm:grid-cols-2">
        <RuntimeTextInput
          label="Model"
          onChange={(value) => onChange({ model: value || null })}
          value={draftRole.model ?? ""}
        />
        <RuntimeTextInput
          label="apiKeyEnv"
          onChange={(value) => onChange({ apiKeyEnv: value || null })}
          value={draftRole.apiKeyEnv ?? ""}
        />
      </div>

      <RuntimeTextInput
        label="Base URL"
        onChange={(value) => onChange({ baseUrl: value || null })}
        value={draftRole.baseUrl ?? ""}
      />
    </div>
  )
}

function RuntimeTextInput({
  label,
  onChange,
  value,
}: {
  label: string
  onChange: (value: string) => void
  value: string
}) {
  return (
    <label className="block text-[11px] font-bold uppercase tracking-normal text-[var(--text-muted)]">
      {label}
      <input
        className="mt-1 w-full rounded border border-[var(--border)] bg-white px-2 py-1.5 text-xs font-medium text-slate-900"
        onChange={(event) => onChange(event.target.value)}
        value={value}
      />
    </label>
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
