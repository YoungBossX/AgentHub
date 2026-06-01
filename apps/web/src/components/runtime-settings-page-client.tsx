"use client"

import { useEffect, useState } from "react"

import { AgentRuntimeSettings } from "@/components/agent-runtime-settings"
import {
  getAgentRuntimeConfig,
  updateAgentRuntimeConfig,
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
  const [isSaving, setIsSaving] = useState(false)
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

  async function handleSave() {
    if (!workspace || !config) {
      setStatusMessage("无法保存：未找到可配置的工作区。")
      return
    }

    setIsSaving(true)
    setStatusMessage(null)
    try {
      const updated = await updateAgentRuntimeConfig(
        backendUrl,
        workspace.id,
        draftRoles,
      )
      setConfig(updated)
      setDraftRoles(updated.roles)
      setStatusMessage("运行设置已保存。")
    } catch {
      setStatusMessage("运行设置保存失败，请检查配置后重试。")
    } finally {
      setIsSaving(false)
    }
  }

  return (
    <AgentRuntimeSettings
      busy={isSaving}
      config={config}
      draftRoles={draftRoles}
      onRoleChange={handleRoleChange}
      onSave={handleSave}
      statusMessage={effectiveStatusMessage}
    />
  )
}
