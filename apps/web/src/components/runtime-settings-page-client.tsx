"use client"

import { useCallback, useEffect, useState } from "react"

import { AgentRuntimeSettings } from "@/components/agent-runtime-settings"
import { WorkspaceTargetSettings } from "@/components/workspace-target-settings"
import {
  ApiRequestError,
  applyProjectProvisioning,
  checkAgentRuntimeProvider,
  createExternalProjectTarget,
  getDemoWorkspace,
  getAgentRuntimeConfig,
  listWorkspaceSessions,
  listExternalTargetFolders,
  listWorkspaceTargets,
  updateAgentRuntimeConfig,
  updateSessionTargetSelection,
  type AgentRuntimeConfig,
  type LocalFolderListing,
  type ProjectProvisioningSetupStep,
  type RuntimeProviderCheck,
  type RuntimeRoleConfigInput,
  type TargetProject,
  type Workspace,
  type WorkspaceSession,
} from "@/lib/api"

type RuntimeSettingsPageClientProps = {
  backendUrl: string
  workspace?: Workspace | null
}

export function RuntimeSettingsPageClient({
  backendUrl,
  workspace: initialWorkspace = null,
}: RuntimeSettingsPageClientProps) {
  const [isSaving, setIsSaving] = useState(false)
  const [workspace, setWorkspace] = useState<Workspace | null>(initialWorkspace)
  const [config, setConfig] = useState<AgentRuntimeConfig | null>(null)
  const [draftRoles, setDraftRoles] = useState<Record<string, RuntimeRoleConfigInput>>({})
  const [targets, setTargets] = useState<TargetProject[]>([])
  const [sessions, setSessions] = useState<WorkspaceSession[]>([])
  const [selectedSessionId, setSelectedSessionId] = useState("")
  const [frontendTargetId, setFrontendTargetId] = useState("")
  const [backendTargetId, setBackendTargetId] = useState("")
  const [externalRootPath, setExternalRootPath] = useState("")
  const [statusMessage, setStatusMessage] = useState<string | null>(null)
  const [workspaceStatusMessage, setWorkspaceStatusMessage] = useState<string | null>(null)
  const [projectSetupSteps, setProjectSetupSteps] = useState<ProjectProvisioningSetupStep[]>([])
  const [isLoadingConfig, setIsLoadingConfig] = useState(true)
  const [checkingRole, setCheckingRole] = useState<string | null>(null)
  const [isRegisteringExternal, setIsRegisteringExternal] = useState(false)
  const [isProvisioningProject, setIsProvisioningProject] = useState(false)
  const [isSavingTargets, setIsSavingTargets] = useState(false)
  const [folderListing, setFolderListing] = useState<LocalFolderListing | null>(null)
  const [isFolderPickerOpen, setIsFolderPickerOpen] = useState(false)
  const [isLoadingFolders, setIsLoadingFolders] = useState(false)
  const [externalTargetKind, setExternalTargetKind] = useState<"frontend" | "backend">("frontend")
  const hasUnsavedChanges = config
    ? JSON.stringify(draftRoles) !== JSON.stringify(config.roles)
    : false
  const effectiveStatusMessage =
    statusMessage ??
    (isLoadingConfig
      ? "正在加载运行设置..."
      : workspace
        ? hasUnsavedChanges
          ? "有未保存更改，点击保存后才会生效。"
          : null
        : "未找到可配置的工作区。")

  const applyTargetSelection = useCallback(
    (session: WorkspaceSession | undefined, nextTargets: TargetProject[]) => {
      setFrontendTargetId(
        session?.activeFrontendTargetId ??
          nextTargets.find((target) => target.type === "frontend")?.targetId ??
          "",
      )
      setBackendTargetId(
        session?.activeBackendTargetId ??
          nextTargets.find((target) => target.type === "backend")?.targetId ??
          "",
      )
    },
    [],
  )

  const applyInitialTargetSelection = useCallback(
    (nextSessions: WorkspaceSession[], nextTargets: TargetProject[]) => {
      const nextSession = nextSessions[0]
      setSelectedSessionId(nextSession?.id ?? "")
      applyTargetSelection(nextSession, nextTargets)
    },
    [applyTargetSelection],
  )

  useEffect(() => {
    let cancelled = false

    async function loadRuntimeConfig() {
      try {
        const nextWorkspace = initialWorkspace ?? await getDemoWorkspace(backendUrl)
        if (cancelled) {
          return
        }
        setWorkspace(nextWorkspace)

        if (!nextWorkspace) {
          setConfig(null)
          setDraftRoles({})
          setStatusMessage(null)
          return
        }

        const [nextConfig, nextSessions, nextTargets] = await Promise.all([
          getAgentRuntimeConfig(backendUrl, nextWorkspace.id),
          listWorkspaceSessions(backendUrl, nextWorkspace.id),
          listWorkspaceTargets(backendUrl, nextWorkspace.id),
        ])
        if (!cancelled) {
          setConfig(nextConfig)
          setDraftRoles(nextConfig?.roles ?? {})
          setSessions(nextSessions)
          setTargets(nextTargets)
          applyInitialTargetSelection(nextSessions, nextTargets)
          setStatusMessage(null)
          setWorkspaceStatusMessage(null)
          setProjectSetupSteps([])
        }
      } catch {
        if (!cancelled) {
          setStatusMessage("无法加载运行设置，请确认后端服务可访问。")
        }
      } finally {
        if (!cancelled) {
          setIsLoadingConfig(false)
        }
      }
    }

    void loadRuntimeConfig()

    return () => {
      cancelled = true
    }
  }, [applyInitialTargetSelection, backendUrl, initialWorkspace])

  async function refreshWorkspaceTargets() {
    if (!workspace) {
      return
    }

    try {
      const [nextSessions, nextTargets] = await Promise.all([
        listWorkspaceSessions(backendUrl, workspace.id),
        listWorkspaceTargets(backendUrl, workspace.id),
      ])
      setSessions(nextSessions)
      setTargets(nextTargets)
      const selectedSession = nextSessions.find(
        (session) => session.id === selectedSessionId,
      ) ?? nextSessions[0]
      applyTargetSelection(selectedSession, nextTargets)
      setWorkspaceStatusMessage("工作区目标已刷新。")
    } catch (error) {
      setWorkspaceStatusMessage(
        workspaceSettingsErrorMessage(error, "刷新工作区目标失败，请确认后端服务可访问。"),
      )
    }
  }

  function handleRoleChange(role: string, nextRole: RuntimeRoleConfigInput) {
    setStatusMessage(null)
    setDraftRoles((current) => ({
      ...current,
      [role]: nextRole,
    }))
  }

  function handleSessionChange(sessionId: string) {
    setSelectedSessionId(sessionId)
    applyTargetSelection(
      sessions.find((session) => session.id === sessionId),
      targets,
    )
    setWorkspaceStatusMessage(null)
  }

  async function handleRegisterExternalProject() {
    if (!workspace) {
      setWorkspaceStatusMessage("无法注册：未找到可配置的工作区。")
      return
    }

    if (!externalRootPath.trim()) {
      setWorkspaceStatusMessage("请先输入外部项目路径。")
      return
    }

    setIsRegisteringExternal(true)
    setWorkspaceStatusMessage(null)
    try {
      const registered = await createExternalProjectTarget(
        backendUrl,
        workspace.id,
        {
          allowedPaths: ["*"],
          buildCommand: null,
          checkCommand: null,
          deniedPaths: [],
          devCommand: null,
          name: externalTargetNameFor(externalRootPath, externalTargetKind),
          previewCommand: null,
          projectType: externalProjectTypeFor(externalTargetKind),
          rootPath: externalRootPath,
          targetId: externalTargetIdFor(externalRootPath, externalTargetKind),
          testCommand: null,
        },
      )
      await refreshWorkspaceTargets()
      setWorkspaceStatusMessage(`外部项目已注册：${registered.name}`)
    } catch (error) {
      setWorkspaceStatusMessage(
        workspaceSettingsErrorMessage(
          error,
          "外部项目注册失败，可能 targetId 已存在或路径不符合安全规则。",
        ),
      )
    } finally {
      setIsRegisteringExternal(false)
    }
  }

  async function handleProvisionNewProject() {
    if (!workspace) {
      setWorkspaceStatusMessage("无法新建项目：未找到可配置的工作区。")
      return
    }

    if (!selectedSessionId) {
      setWorkspaceStatusMessage("无法新建项目：请选择一个会话。")
      return
    }

    const selectedRootPath = externalRootPath.trim()
    if (!selectedRootPath) {
      setWorkspaceStatusMessage("请先选择一个空文件夹。")
      return
    }

    setIsProvisioningProject(true)
    setWorkspaceStatusMessage(null)
    setProjectSetupSteps([])
    try {
      const provisioned = await applyProjectProvisioning(
        backendUrl,
        workspace.id,
        {
          preferredSlug: preferredProjectSlugFor(selectedRootPath),
          selectedRootPath,
          sessionId: selectedSessionId,
          userRequest: "新建全栈项目",
        },
      )
      const provisionedFrontendTargetId =
        provisioned.session.activeFrontendTargetId ??
        provisioned.registeredTargets.find((target) => target.targetId.includes("-frontend-"))
          ?.targetId ??
        null
      const provisionedBackendTargetId =
        provisioned.session.activeBackendTargetId ??
        provisioned.registeredTargets.find((target) => target.targetId.includes("-backend-"))
          ?.targetId ??
        null
      const [nextSessions, nextTargets] = await Promise.all([
        listWorkspaceSessions(backendUrl, workspace.id),
        listWorkspaceTargets(backendUrl, workspace.id),
      ])
      const selectedSession =
        provisioned.session ?? nextSessions.find((session) => session.id === selectedSessionId)
      const mergedSessions = mergeSession(nextSessions, selectedSession)

      setSessions(mergedSessions)
      setTargets(nextTargets)
      setFrontendTargetId(
        selectedSession?.activeFrontendTargetId ??
          provisionedFrontendTargetId ??
          nextTargets.find((target) => target.type === "frontend")?.targetId ??
          "",
      )
      setBackendTargetId(
        selectedSession?.activeBackendTargetId ??
          provisionedBackendTargetId ??
          nextTargets.find((target) => target.type === "backend")?.targetId ??
          "",
      )
      setProjectSetupSteps(provisioned.plan.setupSteps)
      setWorkspaceStatusMessage("新项目已创建并绑定到当前会话。")
    } catch (error) {
      setWorkspaceStatusMessage(
        workspaceSettingsErrorMessage(error, "新项目创建失败，请确认文件夹为空且可写。"),
      )
    } finally {
      setIsProvisioningProject(false)
    }
  }

  async function openFolderPicker() {
    if (!workspace) {
      setWorkspaceStatusMessage("无法选择文件夹：未找到可配置的工作区。")
      return
    }

    setIsFolderPickerOpen(true)
    await browseFolder(undefined)
  }

  async function browseFolder(path: string | undefined) {
    if (!workspace) {
      return
    }

    setIsLoadingFolders(true)
    setWorkspaceStatusMessage(null)
    try {
      const listing = await listExternalTargetFolders(
        backendUrl,
        workspace.id,
        path,
      )
      setFolderListing(listing)
    } catch (error) {
      setWorkspaceStatusMessage(
        workspaceSettingsErrorMessage(error, "无法读取本地文件夹，请选择其他目录。"),
      )
    } finally {
      setIsLoadingFolders(false)
    }
  }

  function selectCurrentFolder() {
    if (!folderListing) {
      return
    }

    setExternalRootPath(folderListing.currentPath)
    setWorkspaceStatusMessage(null)
    setIsFolderPickerOpen(false)
  }

  async function handleSaveTargets() {
    if (!selectedSessionId) {
      setWorkspaceStatusMessage("无法保存目标：请选择一个会话。")
      return
    }

    setIsSavingTargets(true)
    setWorkspaceStatusMessage(null)
    try {
      const updated = await updateSessionTargetSelection(
        backendUrl,
        selectedSessionId,
        {
          backendTargetId: backendTargetId || undefined,
          frontendTargetId: frontendTargetId || undefined,
        },
      )
      setSessions((current) =>
        current.map((session) => session.id === updated.id ? updated : session),
      )
      setWorkspaceStatusMessage("会话目标已保存。")
    } catch (error) {
      setWorkspaceStatusMessage(
        workspaceSettingsErrorMessage(error, "会话目标保存失败，请确认目标类型匹配。"),
      )
    } finally {
      setIsSavingTargets(false)
    }
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

  function handleCancel() {
    if (!config) {
      setStatusMessage("没有可恢复的已保存配置。")
      return
    }

    setDraftRoles(config.roles)
    setStatusMessage("已取消未保存更改。")
  }

  async function handleCheckProvider(
    role: string,
    roleConfig: RuntimeRoleConfigInput,
  ) {
    if (!workspace) {
      setStatusMessage("无法检测：未找到可配置的工作区。")
      return
    }

    setCheckingRole(role)
    setStatusMessage(null)
    try {
      const result = await checkAgentRuntimeProvider(
        backendUrl,
        workspace.id,
        role,
        roleConfig,
      )
      applyProviderCheckResult(role, result)
      setStatusMessage(result.message)
    } catch {
      setStatusMessage("检测失败，请确认后端服务可访问。")
    } finally {
      setCheckingRole(null)
    }
  }

  function applyProviderCheckResult(role: string, result: RuntimeProviderCheck) {
    setDraftRoles((current) => ({
      ...current,
      [role]: {
        ...(current[role] ?? config?.roles[role]),
        availability: result.availability,
      },
    }))
    setConfig((current) => {
      if (!current) {
        return current
      }

      return {
        ...current,
        availableProviders: current.availableProviders.map((provider) =>
          provider.providerId === result.providerId
            ? {
                ...provider,
                authStatus: result.authStatus,
                available: result.available,
              }
            : provider,
        ),
        roles: {
          ...current.roles,
          [role]: {
            ...current.roles[role],
            availability: result.availability,
          },
        },
      }
    })
  }

  return (
    <div className="grid gap-5">
      <WorkspaceTargetSettings
        backendTargetId={backendTargetId}
        busy={isLoadingConfig}
        frontendTargetId={frontendTargetId}
        folderListing={folderListing}
        externalTargetKind={externalTargetKind}
        isFolderPickerOpen={isFolderPickerOpen}
        isLoadingFolders={isLoadingFolders}
        isProvisioning={isProvisioningProject}
        isRegistering={isRegisteringExternal}
        isSavingTargets={isSavingTargets}
        onBackendTargetChange={(targetId) => {
          setBackendTargetId(targetId)
          setWorkspaceStatusMessage(null)
        }}
        onBrowseFolder={(path) => {
          void browseFolder(path)
        }}
        onCloseFolderPicker={() => setIsFolderPickerOpen(false)}
        onExternalTargetKindChange={(kind) => {
          setExternalTargetKind(kind)
          setWorkspaceStatusMessage(null)
        }}
        onFrontendTargetChange={(targetId) => {
          setFrontendTargetId(targetId)
          setWorkspaceStatusMessage(null)
        }}
        onOpenFolderPicker={() => {
          void openFolderPicker()
        }}
        onProvisionNewProject={() => {
          void handleProvisionNewProject()
        }}
        onRefresh={refreshWorkspaceTargets}
        onRegister={handleRegisterExternalProject}
        onRootPathChange={(rootPath) => {
          setExternalRootPath(rootPath)
          setWorkspaceStatusMessage(null)
          setProjectSetupSteps([])
        }}
        onSaveTargets={handleSaveTargets}
        onSelectCurrentFolder={selectCurrentFolder}
        onSessionChange={handleSessionChange}
        setupSteps={projectSetupSteps}
        rootPath={externalRootPath}
        selectedSessionId={selectedSessionId}
        sessions={sessions}
        statusMessage={workspaceStatusMessage}
        targets={targets}
        workspace={workspace}
      />

      <AgentRuntimeSettings
        busy={isSaving}
        checkingRole={checkingRole}
        config={config}
        draftRoles={draftRoles}
        onCancel={handleCancel}
        onCheckProvider={handleCheckProvider}
        onRoleChange={handleRoleChange}
        onSave={handleSave}
        statusMessage={effectiveStatusMessage}
      />
    </div>
  )
}

function externalProjectTypeFor(kind: "frontend" | "backend") {
  return kind === "backend" ? "external-backend" : "external-frontend"
}

function externalTargetNameFor(rootPath: string, kind: "frontend" | "backend") {
  const lastSegment = rootPath.replace(/\/+$/, "").split("/").filter(Boolean).at(-1)
  const prefix = kind === "backend" ? "后端外部项目" : "前端外部项目"
  return lastSegment ? `${prefix} ${lastSegment}` : prefix
}

function externalTargetIdFor(rootPath: string, kind: "frontend" | "backend") {
  const lastSegment = rootPath.replace(/\/+$/, "").split("/").filter(Boolean).at(-1)
  const slug = (lastSegment || "project")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 48)
  return `external-${kind}-${slug || "project"}`
}

function preferredProjectSlugFor(rootPath: string) {
  const lastSegment = rootPath.replace(/\/+$/, "").split("/").filter(Boolean).at(-1)
  return (lastSegment || "project")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 48) || "project"
}

function mergeSession(
  sessions: WorkspaceSession[],
  session: WorkspaceSession | null | undefined,
) {
  if (!session) {
    return sessions
  }

  if (sessions.some((current) => current.id === session.id)) {
    return sessions.map((current) => current.id === session.id ? session : current)
  }

  return [session, ...sessions]
}

function workspaceSettingsErrorMessage(error: unknown, fallback: string) {
  return error instanceof ApiRequestError && error.message.trim().length > 0
    ? error.message
    : fallback
}
