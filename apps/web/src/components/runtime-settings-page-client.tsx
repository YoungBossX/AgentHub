"use client"

import { useEffect, useState, useTransition } from "react"

import { AgentRuntimeSettings } from "@/components/agent-runtime-settings"
import {
  getAgentRuntimeConfig,
  type AgentRuntimeConfig,
  type RuntimeRoleConfigInput,
  type Workspace,
} from "@/lib/api"

type RuntimeSettingsPageClientProps = {
  backendUrl: string
  workspace: Workspace | null
}

export function RuntimeSettingsPageClient({
  backendUrl,
  workspace,
}: RuntimeSettingsPageClientProps) {
  const [isPending] = useTransition()
  const [config, setConfig] = useState<AgentRuntimeConfig | null>(null)
  const [draftRoles, setDraftRoles] = useState<Record<string, RuntimeRoleConfigInput>>({})
  const [statusMessage, setStatusMessage] = useState<string | null>(null)
  const hasUnsavedChanges = config
    ? JSON.stringify(draftRoles) !== JSON.stringify(config.roles)
    : false
  const effectiveStatusMessage =
    statusMessage ??
    (workspace
      ? hasUnsavedChanges
        ? "有未保存更改，点击保存后才会生效。"
        : null
      : "未找到可配置的工作区。")

  useEffect(() => {
    if (!workspace) {
      return
    }

    let cancelled = false
    getAgentRuntimeConfig(backendUrl, workspace.id)
      .then((nextConfig) => {
        if (!cancelled) {
          setConfig(nextConfig)
          setDraftRoles(nextConfig?.roles ?? {})
          setStatusMessage(null)
        }
      })
      .catch(() => {
        if (!cancelled) {
          setStatusMessage("无法加载运行设置，请确认后端服务可访问。")
        }
      })

    return () => {
      cancelled = true
    }
  }, [backendUrl, workspace])

  function handleRoleChange(role: string, nextRole: RuntimeRoleConfigInput) {
    setStatusMessage(null)
    setDraftRoles((current) => ({
      ...current,
      [role]: nextRole,
    }))
  }

  return (
    <AgentRuntimeSettings
      busy={isPending}
      config={config}
      draftRoles={draftRoles}
      onRoleChange={handleRoleChange}
      onSave={() => setStatusMessage("保存操作将在 P17c-3 接入。")}
      statusMessage={effectiveStatusMessage}
    />
  )
}
