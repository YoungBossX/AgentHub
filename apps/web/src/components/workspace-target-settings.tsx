"use client"

import { ArrowUp, Folder, FolderGit2, FolderOpen, FolderPlus, RefreshCw, Save, Terminal, X } from "lucide-react"

import { Button } from "@/components/ui/button"
import type {
  LocalFolderListing,
  ProjectProvisioningSetupStep,
  TargetProject,
  Workspace,
  WorkspaceSession,
} from "@/lib/api"
import { cn } from "@/lib/utils"

type WorkspaceTargetSettingsProps = {
  backendTargetId: string
  busy: boolean
  frontendTargetId: string
  folderListing: LocalFolderListing | null
  isRegistering: boolean
  isSavingTargets: boolean
  isFolderPickerOpen: boolean
  isLoadingFolders: boolean
  isProvisioning: boolean
  setupSteps: ProjectProvisioningSetupStep[]
  externalTargetKind: "frontend" | "backend"
  onBackendTargetChange: (targetId: string) => void
  onBrowseFolder: (path: string) => void
  onCloseFolderPicker: () => void
  onExternalTargetKindChange: (kind: "frontend" | "backend") => void
  onFrontendTargetChange: (targetId: string) => void
  onOpenFolderPicker: () => void
  onProvisionNewProject: () => void
  onRefresh: () => void
  onRegister: () => void
  onRootPathChange: (rootPath: string) => void
  onSaveTargets: () => void
  onSelectCurrentFolder: () => void
  onSessionChange: (sessionId: string) => void
  rootPath: string
  selectedSessionId: string
  sessions: WorkspaceSession[]
  statusMessage: string | null
  targets: TargetProject[]
  workspace: Workspace | null
}

export function WorkspaceTargetSettings({
  backendTargetId,
  busy,
  frontendTargetId,
  folderListing,
  isRegistering,
  isFolderPickerOpen,
  isLoadingFolders,
  isProvisioning,
  isSavingTargets,
  setupSteps,
  externalTargetKind,
  onBackendTargetChange,
  onBrowseFolder,
  onCloseFolderPicker,
  onExternalTargetKindChange,
  onFrontendTargetChange,
  onOpenFolderPicker,
  onProvisionNewProject,
  onRefresh,
  onRegister,
  onRootPathChange,
  onSaveTargets,
  onSelectCurrentFolder,
  onSessionChange,
  rootPath,
  selectedSessionId,
  sessions,
  statusMessage,
  targets,
}: WorkspaceTargetSettingsProps) {
  const frontendTargets = targets.filter((target) => target.type === "frontend")
  const backendTargets = targets.filter((target) => target.type === "backend")

  return (
    <section className="rounded-lg border border-[var(--border)] bg-white p-5">
      <div className="flex flex-wrap justify-end gap-3">
        <Button
          className="bg-white text-slate-700 hover:bg-slate-50"
          disabled={busy}
          onClick={onRefresh}
          type="button"
          variant="secondary"
        >
          <RefreshCw aria-hidden="true" size={15} />
          刷新
        </Button>
      </div>

      <div className="mt-5 grid gap-4 lg:grid-cols-[1.1fr_0.9fr]">
        <div className="rounded-md border border-[var(--border)] bg-[var(--surface-muted)] p-3">
          <div className="flex items-center gap-2">
            <FolderGit2 aria-hidden="true" className="text-[var(--primary)]" size={16} />
            <p className="text-sm font-semibold text-slate-950">
              当前会话目标
            </p>
          </div>

          <label className="mt-3 block text-[11px] font-bold tracking-normal text-[var(--text-muted)]">
            会话
            <select
              className="mt-1 w-full rounded border border-[var(--border)] bg-white px-2 py-1.5 text-xs font-medium text-slate-900"
              disabled={sessions.length === 0}
              onChange={(event) => onSessionChange(event.target.value)}
              value={selectedSessionId}
            >
              {sessions.length === 0 ? (
                <option value="">暂无会话</option>
              ) : null}
              {sessions.map((session) => (
                <option key={session.id} value={session.id}>
                  {session.title}
                </option>
              ))}
            </select>
          </label>

          <div className="mt-3 grid gap-2 sm:grid-cols-2">
            <TargetSelect
              label="前端目标"
              onChange={onFrontendTargetChange}
              targets={frontendTargets}
              value={frontendTargetId}
            />
            <TargetSelect
              label="后端目标"
              onChange={onBackendTargetChange}
              targets={backendTargets}
              value={backendTargetId}
            />
          </div>

          <div className="mt-3 flex justify-end">
            <Button
              disabled={!selectedSessionId || isSavingTargets || busy}
              onClick={onSaveTargets}
              type="button"
            >
              <Save aria-hidden="true" size={15} />
              保存目标
            </Button>
          </div>
        </div>

        <div className="rounded-md border border-[var(--border)] bg-[var(--surface-muted)] p-3">
          <div className="flex items-center gap-2">
            <FolderPlus aria-hidden="true" className="text-[var(--primary)]" size={16} />
            <p className="text-sm font-semibold text-slate-950">
              空文件夹与外部项目
            </p>
          </div>

          <p className="mt-2 text-[11px] text-[var(--muted-foreground)]">
            选择或填写一个文件夹，可新建全栈项目，也可注册为单一目标。
          </p>

          <label className="mt-3 block text-[11px] font-bold tracking-normal text-[var(--text-muted)]">
            目标类型
            <select
              className="mt-1 w-full rounded border border-[var(--border)] bg-white px-2 py-1.5 text-xs font-medium text-slate-900"
              onChange={(event) =>
                onExternalTargetKindChange(event.target.value as "frontend" | "backend")
              }
              value={externalTargetKind}
            >
              <option value="frontend">前端目标</option>
              <option value="backend">后端目标</option>
            </select>
          </label>

          <label className="mt-3 block text-[11px] font-bold tracking-normal text-[var(--text-muted)]">
            项目路径
            <div className="mt-1 flex gap-2">
              <input
                className="min-w-0 flex-1 rounded border border-[var(--border)] bg-white px-2 py-1.5 text-xs font-medium text-slate-900"
                onChange={(event) => onRootPathChange(event.target.value)}
                placeholder="/Users/you/Desktop/my-app"
                value={rootPath}
              />
              <Button
                className="h-8 shrink-0 bg-white px-3 text-xs text-slate-700 hover:bg-slate-50"
                disabled={busy || isLoadingFolders}
                onClick={onOpenFolderPicker}
                type="button"
                variant="secondary"
              >
                <FolderOpen aria-hidden="true" size={14} />
                选择文件夹
              </Button>
            </div>
          </label>

          <p className="mt-2 rounded border border-slate-200 bg-white px-2 py-1.5 text-[11px] text-slate-600">
            写入范围：当前文件夹下所有路径，受保护路径仍会被拒绝。
          </p>

          <div className="mt-3 flex flex-wrap gap-2">
            <Button
              disabled={!rootPath.trim() || !selectedSessionId || isProvisioning || busy}
              onClick={onProvisionNewProject}
              type="button"
            >
              {isProvisioning ? "新建中..." : "新建全栈项目"}
            </Button>
            <Button
              className="bg-white text-slate-700 hover:bg-slate-50"
              disabled={!rootPath.trim() || isRegistering || busy}
              onClick={onRegister}
              type="button"
              variant="secondary"
            >
              {isRegistering ? "注册中..." : "注册"}
            </Button>
          </div>
        </div>
      </div>

      {isFolderPickerOpen ? (
        <FolderPickerDialog
          isLoading={isLoadingFolders}
          listing={folderListing}
          onBrowseFolder={onBrowseFolder}
          onClose={onCloseFolderPicker}
          onSelectCurrentFolder={onSelectCurrentFolder}
        />
      ) : null}

      {targets.length > 0 ? (
        <div className="mt-4 flex flex-wrap gap-2">
          {targets.map((target) => (
            <TargetPill key={target.targetId} target={target} />
          ))}
        </div>
      ) : null}

      {setupSteps.length > 0 ? (
        <div className="mt-4 rounded-md border border-amber-200 bg-amber-50 p-3">
          <div className="flex items-center gap-2 text-amber-900">
            <Terminal aria-hidden="true" size={15} />
            <p className="text-xs font-semibold">依赖准备命令</p>
          </div>
          <div className="mt-2 grid gap-2">
            {setupSteps.map((step) => (
              <div
                className="rounded border border-amber-200 bg-white px-2 py-2 text-[11px] text-slate-700"
                key={`${step.role}:${step.cwd}:${step.command}`}
              >
                <div className="flex flex-wrap items-center gap-2">
                  <span className="rounded bg-amber-100 px-1.5 py-0.5 font-semibold text-amber-900">
                    {formatTargetType(step.role)}
                  </span>
                  <code className="rounded bg-slate-950 px-1.5 py-0.5 font-mono text-[11px] text-white">
                    {step.command}
                  </code>
                </div>
                <p className="mt-1 break-all font-mono text-[11px] text-slate-800">
                  {step.cwd}
                </p>
                <p className="mt-1 text-[11px] text-slate-600">{step.reason}</p>
              </div>
            ))}
          </div>
        </div>
      ) : null}

      {statusMessage ? (
        <div className="mt-3 rounded border border-blue-200 bg-blue-50 p-2 text-xs text-blue-800">
          {statusMessage}
        </div>
      ) : null}
    </section>
  )
}

function FolderPickerDialog({
  isLoading,
  listing,
  onBrowseFolder,
  onClose,
  onSelectCurrentFolder,
}: {
  isLoading: boolean
  listing: LocalFolderListing | null
  onBrowseFolder: (path: string) => void
  onClose: () => void
  onSelectCurrentFolder: () => void
}) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/35 p-4">
      <div className="w-full max-w-2xl rounded-lg border border-[var(--border)] bg-white p-4 shadow-xl">
        <div className="flex items-start justify-between gap-3">
          <div>
            <p className="text-sm font-semibold text-slate-950">选择文件夹</p>
            <p className="mt-1 max-w-xl truncate text-xs text-[var(--muted-foreground)]">
              {listing?.currentPath ?? "正在加载本地目录..."}
            </p>
          </div>
          <Button
            aria-label="关闭"
            className="h-8 w-8 bg-white p-0 text-slate-700 hover:bg-slate-50"
            onClick={onClose}
            type="button"
            variant="secondary"
          >
            <X aria-hidden="true" size={15} />
          </Button>
        </div>

        {listing?.starts.length ? (
          <div className="mt-3 flex flex-wrap gap-2">
            {listing.starts.map((start) => (
              <Button
                key={start.path}
                className="h-8 bg-white px-3 text-xs text-slate-700 hover:bg-slate-50"
                disabled={isLoading}
                onClick={() => onBrowseFolder(start.path)}
                type="button"
                variant="secondary"
              >
                {start.label}
              </Button>
            ))}
          </div>
        ) : null}

        <div className="mt-3 flex items-center justify-between gap-2">
          <Button
            className="h-8 bg-white px-3 text-xs text-slate-700 hover:bg-slate-50"
            disabled={!listing?.parentPath || isLoading}
            onClick={() => {
              if (listing?.parentPath) {
                onBrowseFolder(listing.parentPath)
              }
            }}
            type="button"
            variant="secondary"
          >
            <ArrowUp aria-hidden="true" size={14} />
            上一级
          </Button>
          <Button
            className="h-8 px-3 text-xs"
            disabled={!listing || isLoading}
            onClick={onSelectCurrentFolder}
            type="button"
          >
            <Folder aria-hidden="true" size={14} />
            选择当前文件夹
          </Button>
        </div>

        <div className="mt-3 max-h-72 overflow-y-auto rounded border border-[var(--border)] bg-[var(--surface-muted)] p-2">
          {isLoading ? (
            <p className="px-2 py-6 text-center text-xs text-[var(--muted-foreground)]">
              正在加载...
            </p>
          ) : listing?.children.length ? (
            <div className="grid gap-1">
              {listing.children.map((child) => (
                <button
                  key={child.path}
                  className="flex min-h-9 w-full items-center gap-2 rounded border border-transparent px-2 py-1.5 text-left text-xs font-medium text-slate-800 hover:border-blue-200 hover:bg-blue-50"
                  onClick={() => onBrowseFolder(child.path)}
                  type="button"
                >
                  <Folder aria-hidden="true" className="shrink-0 text-[var(--primary)]" size={15} />
                  <span className="truncate">{child.name}</span>
                </button>
              ))}
            </div>
          ) : (
            <p className="px-2 py-6 text-center text-xs text-[var(--muted-foreground)]">
              没有可浏览的子文件夹
            </p>
          )}
        </div>
      </div>
    </div>
  )
}

function TargetSelect({
  label,
  onChange,
  targets,
  value,
}: {
  label: string
  onChange: (targetId: string) => void
  targets: TargetProject[]
  value: string
}) {
  return (
    <label className="block text-[11px] font-bold tracking-normal text-[var(--text-muted)]">
      {label}
      <select
        className="mt-1 w-full rounded border border-[var(--border)] bg-white px-2 py-1.5 text-xs font-medium text-slate-900"
        onChange={(event) => onChange(event.target.value)}
        value={value}
      >
        {targets.length === 0 ? <option value="">暂无可选目标</option> : null}
        {targets.map((target) => (
          <option key={target.targetId} value={target.targetId}>
            {target.name}
          </option>
        ))}
      </select>
    </label>
  )
}

function TargetPill({ target }: { target: TargetProject }) {
  return (
    <span
      className={cn(
        "inline-flex max-w-full items-center gap-1 rounded border px-2 py-1 text-[11px] font-medium",
        target.type === "frontend"
          ? "border-blue-200 bg-blue-50 text-blue-700"
          : target.type === "backend"
            ? "border-emerald-200 bg-emerald-50 text-emerald-700"
            : "border-slate-200 bg-slate-50 text-slate-600",
      )}
      title={`${target.targetId} · ${target.root}`}
    >
      <span>{formatTargetType(target.type)}</span>
      <span className="truncate">{target.name}</span>
    </span>
  )
}

function formatTargetType(type: string) {
  switch (type) {
    case "frontend":
      return "前端"
    case "backend":
      return "后端"
    case "platform":
      return "平台"
    default:
      return type
  }
}
