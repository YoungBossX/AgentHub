"use client"

import { Bot, RotateCcw, Save, ShieldCheck } from "lucide-react"

import { Button } from "@/components/ui/button"
import type {
  AgentProfile,
  AgentRuntimeConfig,
  RuntimeRoleConfigInput,
} from "@/lib/api"
import { cn } from "@/lib/utils"

const CONFIGURABLE_ROLES = [
  {
    label: "规划模型",
    role: "planner",
    mode: "read_only",
  },
  {
    label: "前端 Agent",
    role: "frontend",
    mode: "frontend",
  },
  {
    label: "后端 Agent",
    role: "backend",
    mode: "backend",
  },
  {
    label: "评审 Agent",
    role: "review",
    mode: "read_only",
  },
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
    label: "自定义 OpenAI 兼容 API",
    model: "",
    protocol: "openai_compatible_chat",
    apiKeyEnv: "CUSTOM_OPENAI_COMPATIBLE_API_KEY",
  },
] as const

type AgentRuntimeSettingsProps = {
  busy: boolean
  checkingRole: string | null
  config: AgentRuntimeConfig | null
  draftRoles: Record<string, RuntimeRoleConfigInput>
  onRoleChange: (role: string, nextRole: RuntimeRoleConfigInput) => void
  onCancel: () => void
  onCheckProvider: (role: string, roleConfig: RuntimeRoleConfigInput) => void
  onSave: () => void
  statusMessage: string | null
}

export function AgentRuntimeSettings({
  busy,
  checkingRole,
  config,
  draftRoles,
  onRoleChange,
  onCancel,
  onCheckProvider,
  onSave,
  statusMessage,
}: AgentRuntimeSettingsProps) {
  if (!config) {
    return (
      <section className="mt-4 rounded-lg border border-[var(--border)] bg-white p-3">
        <div className="flex items-center gap-2">
          <Bot aria-hidden="true" className="text-[var(--primary)]" size={16} />
          <p className="text-sm font-semibold text-slate-950">
            运行设置
          </p>
        </div>
        <p className="mt-2 text-xs text-[var(--muted-foreground)]">
          正在加载运行设置...
        </p>
      </section>
    )
  }

  return (
    <section className="rounded-lg border border-[var(--border)] bg-white p-5">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-[11px] font-bold tracking-normal text-[var(--text-muted)]">
            运行设置
          </p>
          <p className="mt-1 text-xs text-[var(--muted-foreground)]">
            来源：{formatConfigSourceLabel(config.configSource)}
          </p>
        </div>
        <ShieldCheck aria-hidden="true" className="text-emerald-600" size={16} />
      </div>

      <div className="mt-5 grid gap-4 lg:grid-cols-2">
        {CONFIGURABLE_ROLES.map(({ label, mode, role }) => (
          <RuntimeRoleSelector
            config={config}
            checking={checkingRole === role}
            draftRole={draftRoles[role] ?? config.roles[role]}
            key={role}
            label={label}
            mode={mode}
            onCheckProvider={() =>
              onCheckProvider(role, draftRoles[role] ?? config.roles[role])
            }
            onChange={(nextRole) => onRoleChange(role, nextRole)}
            role={role}
          />
        ))}
      </div>

      {config.validation.errors.length > 0 ? (
        <div className="mt-3 rounded border border-red-200 bg-red-50 p-2 text-xs text-red-800">
          {formatValidationMessage(config.validation.errors[0])}
        </div>
      ) : null}
      {config.validation.warnings.length > 0 ? (
        <div className="mt-3 rounded border border-amber-200 bg-amber-50 p-2 text-xs text-amber-800">
          {formatValidationMessage(config.validation.warnings[0])}
        </div>
      ) : null}
      {statusMessage ? (
        <div className="mt-3 rounded border border-blue-200 bg-blue-50 p-2 text-xs text-blue-800">
          {statusMessage}
        </div>
      ) : null}

      <div className="mt-4 flex flex-wrap justify-end gap-2">
        <Button
          className="bg-white text-slate-700 hover:bg-slate-50"
          disabled={busy}
          onClick={onCancel}
          type="button"
          variant="secondary"
        >
          <RotateCcw aria-hidden="true" size={15} />
          取消
        </Button>
        <Button disabled={busy} onClick={onSave} type="button">
          <Save aria-hidden="true" size={15} />
          保存
        </Button>
      </div>
    </section>
  )
}

function RuntimeRoleSelector({
  checking,
  config,
  draftRole,
  label,
  mode,
  onCheckProvider,
  onChange,
  role,
}: {
  config: AgentRuntimeConfig
  checking: boolean
  draftRole: RuntimeRoleConfigInput
  label: string
  mode: string
  onCheckProvider: () => void
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
  const canCheckProvider =
    role === "planner"
      ? Boolean(draftRole.providerPresetId || draftRole.providerId)
      : Boolean(draftRole.providerId)

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
    <div className="rounded-md border border-[var(--border)] bg-[var(--surface-muted)] p-3">
      <div className="flex items-center justify-between gap-2">
        <p className="text-sm font-semibold text-slate-950">{label}</p>
        <div className="flex items-center gap-2">
          <Button
            className="h-7 bg-white px-2 text-xs text-slate-700 hover:bg-slate-50"
            disabled={!canCheckProvider || checking}
            onClick={onCheckProvider}
            type="button"
            variant="secondary"
          >
            {checking ? "检测中..." : "检测"}
          </Button>
          <label className="inline-flex items-center gap-1.5 text-xs font-medium text-[var(--muted-foreground)]">
            <input
              checked={draftRole.enabled}
              className="h-3.5 w-3.5"
              onChange={(event) => patchRole({ enabled: event.target.checked })}
              type="checkbox"
            />
            启用
          </label>
        </div>
      </div>

      <label className="mt-2 block text-[11px] font-bold tracking-normal text-[var(--text-muted)]">
        Agent 档案
        <select
          className="mt-1 w-full rounded border border-[var(--border)] bg-white px-2 py-1.5 text-xs font-medium text-slate-900"
          onChange={(event) => {
            const profile = config.availableProfiles.find(
              (item) => item.id === event.target.value,
            )
            const defaultProvider = config.availableProviders.find(
              (item) => item.providerId === profile?.providerId,
            )
            patchRole({
              adapterType: defaultProvider?.adapterType ?? profile?.adapterType ?? null,
              agentProfileId: profile?.id ?? null,
              availability: null,
              enabled: Boolean(profile),
              mode,
              providerId: defaultProvider?.providerId ?? profile?.providerId ?? null,
            })
          }}
          value={draftRole.agentProfileId ?? ""}
        >
          <option value="">选择档案</option>
          {profileOptions.map((profile) => (
            <option disabled={profile.status !== "available"} key={profile.id} value={profile.id}>
              {profile.displayName} · {formatAvailabilityLabel(profile.status)}
            </option>
          ))}
        </select>
      </label>

      <label className="mt-2 block text-[11px] font-bold tracking-normal text-[var(--text-muted)]">
        提供方
        <select
          className="mt-1 w-full rounded border border-[var(--border)] bg-white px-2 py-1.5 text-xs font-medium text-slate-900"
          onChange={(event) => {
            const provider = config.availableProviders.find(
              (item) => item.providerId === event.target.value,
            )
            patchRole({
              adapterType: provider?.adapterType ?? null,
              availability: null,
              enabled: true,
              mode,
              providerId: provider?.providerId ?? null,
            })
          }}
          value={draftRole.providerId ?? ""}
        >
          <option value="">选择提供方</option>
          {providerOptions.map((provider) => (
            <option disabled={!provider.available} key={provider.providerId} value={provider.providerId}>
              {provider.displayName} · {formatAuthStatusLabel(provider.authStatus)}
            </option>
          ))}
        </select>
      </label>

      {role === "planner" ? (
        <PlannerProviderControls draftRole={draftRole} onChange={patchRole} />
      ) : null}

      <div className="mt-2 flex flex-wrap gap-1">
        <RuntimePill label={draftRole.adapterType ?? "未设置适配器"} tone="provider" />
        <RuntimePill label={formatModeLabel(mode)} tone="mode" />
        {role === "planner" && draftRole.providerPresetId ? (
          <RuntimePill label={draftRole.providerPresetId} tone="provider" />
        ) : null}
        {draftRole.availability ? (
          <RuntimePill
            label={formatAvailabilityLabel(draftRole.availability)}
            tone={isPositiveAvailability(draftRole.availability) ? "ok" : "danger"}
          />
        ) : null}
      </div>
      {selectedProfile ? (
        <div className="mt-2 flex flex-wrap gap-1">
          <RuntimePill label={formatAvailabilityLabel(selectedProfile.status)} tone="ok" />
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
      <label className="block text-[11px] font-bold tracking-normal text-[var(--text-muted)]">
        规划 API
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
          <option value="">选择规划 API 预设</option>
          {PLANNER_PROVIDER_PRESETS.map((preset) => (
            <option key={preset.id} value={preset.id}>
              {preset.label}
            </option>
          ))}
        </select>
      </label>

      <div className="grid gap-2 sm:grid-cols-2">
        <RuntimeTextInput
          label="模型"
          onChange={(value) => onChange({ model: value || null })}
          value={draftRole.model ?? ""}
        />
        <RuntimeTextInput
          label="密钥环境变量"
          onChange={(value) => onChange({ apiKeyEnv: value || null })}
          value={draftRole.apiKeyEnv ?? ""}
        />
      </div>

      <RuntimeTextInput
        label="接口地址"
        onChange={(value) => onChange({ baseUrl: value || null })}
        value={draftRole.baseUrl ?? ""}
      />

      {draftRole.availability === "missing_key" ? (
        <p className="rounded border border-amber-200 bg-amber-50 px-2 py-1.5 text-xs text-amber-800">
          缺少环境变量 {draftRole.apiKeyEnv ?? "API_KEY"}
        </p>
      ) : null}
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
    <label className="block text-[11px] font-bold tracking-normal text-[var(--text-muted)]">
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

function formatConfigSourceLabel(source: string) {
  switch (source) {
    case "default":
      return "默认"
    case "workspace":
      return "工作区"
    default:
      return source
  }
}

function formatModeLabel(mode: string) {
  switch (mode) {
    case "read_only":
      return "只读"
    case "frontend":
      return "前端"
    case "backend":
      return "后端"
    case "review":
      return "评审"
    case "qa":
      return "质检"
    case "debug":
      return "调试"
    case "platform_maintenance":
      return "平台维护"
    default:
      return mode
  }
}

function formatAuthStatusLabel(status: string) {
  switch (status) {
    case "available":
      return "可用"
    case "unchecked":
      return "未检测"
    case "configured":
      return "已配置"
    case "missing_key":
      return "缺少密钥环境变量"
    case "not_required":
      return "无需认证"
    case "unavailable":
      return "不可用"
    default:
      return status
  }
}

function formatAvailabilityLabel(status: string) {
  switch (status) {
    case "available":
      return "可用"
    case "configured":
      return "已配置"
    case "missing_key":
      return "缺少密钥环境变量"
    case "not_required":
      return "无需认证"
    case "unchecked":
      return "未检测"
    case "unavailable":
      return "不可用"
    default:
      return status
  }
}

function isPositiveAvailability(status: string) {
  return ["available", "configured", "not_required"].includes(status)
}

function formatValidationMessage(message: string) {
  if (message.toLowerCase().includes("required")) {
    return `必填配置缺失：${message}`
  }

  return message
}
