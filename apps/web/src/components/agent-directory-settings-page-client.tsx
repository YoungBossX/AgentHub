"use client"

import { useMemo, useState } from "react"
import { Search, ShieldCheck, Users } from "lucide-react"

import type { AgentDirectory, AgentDirectoryEntry, Workspace } from "@/lib/api"
import { cn } from "@/lib/utils"

type AgentDirectorySettingsPageClientProps = {
  directory: AgentDirectory | null
  workspace: Workspace | null
}

type FilterKey = "role" | "provider" | "capability" | "target" | "status"

const FILTERS: Array<{ key: FilterKey; label: string }> = [
  { key: "role", label: "角色筛选" },
  { key: "provider", label: "Provider 筛选" },
  { key: "capability", label: "能力筛选" },
  { key: "target", label: "目标筛选" },
  { key: "status", label: "状态筛选" },
]

export function AgentDirectorySettingsPageClient({
  directory,
  workspace,
}: AgentDirectorySettingsPageClientProps) {
  const entries = useMemo(() => directory?.entries ?? [], [directory])
  const [query, setQuery] = useState("")
  const [filters, setFilters] = useState<Record<FilterKey, string>>({
    capability: "all",
    provider: "all",
    role: "all",
    status: "all",
    target: "all",
  })
  const options = useMemo(() => buildFilterOptions(entries), [entries])
  const filteredEntries = entries.filter((entry) =>
    matchesEntry(entry, filters, query),
  )

  return (
    <section className="grid gap-4">
      <div className="rounded-lg border border-[var(--border)] bg-white p-5 shadow-sm">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <p className="text-[11px] font-bold uppercase tracking-normal text-[var(--text-muted)]">
              工作区
            </p>
            <h2 className="mt-1 text-base font-semibold text-slate-950">
              {workspace?.name ?? "未选择工作区"}
            </h2>
            <p className="mt-1 truncate font-mono text-xs text-[var(--muted-foreground)]">
              {workspace?.rootPath ?? "正在加载工作区..."}
            </p>
          </div>
          <span className="inline-flex items-center gap-2 rounded-md border border-emerald-200 bg-emerald-50 px-2.5 py-1.5 text-xs font-semibold text-emerald-700">
            <Users aria-hidden="true" size={14} />
            {entries.length} 个 Agent
          </span>
        </div>
      </div>

      <div className="grid gap-3 rounded-lg border border-[var(--border)] bg-white p-4 shadow-sm">
        <label className="grid gap-1 text-xs font-semibold text-slate-700">
          搜索 Agent
          <span className="relative">
            <Search
              aria-hidden="true"
              className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-[var(--text-muted)]"
              size={15}
            />
            <input
              className="min-h-10 w-full rounded-md border border-[var(--border)] bg-white pl-9 pr-3 text-sm text-slate-900 outline-none transition focus:border-[var(--primary-border)]"
              onChange={(event) => setQuery(event.target.value)}
              placeholder="按名称、角色、Provider 搜索"
              value={query}
            />
          </span>
        </label>

        <div className="grid gap-2 md:grid-cols-5">
          {FILTERS.map((filter) => (
            <label
              className="grid gap-1 text-xs font-semibold text-slate-700"
              key={filter.key}
            >
              {filter.label}
              <select
                aria-label={filter.label}
                className="min-h-10 rounded-md border border-[var(--border)] bg-white px-2 text-sm text-slate-900 outline-none transition focus:border-[var(--primary-border)]"
                onChange={(event) =>
                  setFilters((current) => ({
                    ...current,
                    [filter.key]: event.target.value,
                  }))
                }
                value={filters[filter.key]}
              >
                <option value="all">全部</option>
                {options[filter.key].map((option) => (
                  <option key={option} value={option}>
                    {option}
                  </option>
                ))}
              </select>
            </label>
          ))}
        </div>
      </div>

      <div className="grid gap-3 lg:grid-cols-2">
        {filteredEntries.map((entry) => (
          <AgentDirectoryCard entry={entry} key={entry.id} />
        ))}
      </div>

      {filteredEntries.length === 0 ? (
        <div className="rounded-lg border border-dashed border-[var(--border)] bg-white p-8 text-center text-sm text-[var(--muted-foreground)]">
          没有匹配的 Agent。
        </div>
      ) : null}
    </section>
  )
}

function AgentDirectoryCard({ entry }: { entry: AgentDirectoryEntry }) {
  return (
    <article className="grid gap-3 rounded-lg border border-[var(--border)] bg-white p-4 shadow-sm">
      <div className="flex min-w-0 items-start gap-3">
        <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-slate-950 text-xs font-bold text-white">
          {entry.avatarInitials}
        </span>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="truncate text-base font-semibold text-slate-950">
              {entry.displayName}
            </h3>
            <DirectoryPill label={statusLabel(entry.status)} tone="status" />
            <DirectoryPill
              label={entry.compatibility.compatible ? "兼容" : "不兼容"}
              tone={entry.compatibility.compatible ? "ok" : "danger"}
            />
          </div>
          <p className="mt-1 font-mono text-xs text-[var(--muted-foreground)]">
            @{entry.role} · {entry.adapterType}
          </p>
        </div>
      </div>

      <p className="text-sm leading-6 text-slate-600">{entry.description}</p>

      <div className="flex flex-wrap gap-1.5">
        <DirectoryPill label={entry.providerId} tone="provider" />
        <DirectoryPill label={entry.authStatus} tone="status" />
        <DirectoryPill label={entry.available ? "可用" : "不可用"} tone={entry.available ? "ok" : "danger"} />
        {entry.runtimeSelectedForRoles.map((role) => (
          <DirectoryPill key={role} label={`已选：${role}`} tone="selected" />
        ))}
      </div>

      <div className="grid gap-2 text-xs text-slate-600">
        <MetaRow label="能力" values={entry.capabilityTags} />
        <MetaRow label="目标" values={entry.supportedTargets} />
        <MetaRow label="模式" values={entry.supportedModes} />
      </div>

      <div className="flex flex-wrap gap-1.5">
        <DirectoryPill label={entry.safeForWrite ? "可写" : "只读"} tone={entry.safeForWrite ? "ok" : "status"} />
        <DirectoryPill label={entry.safeForReview ? "可评审" : "不可评审"} tone={entry.safeForReview ? "ok" : "status"} />
        <DirectoryPill label={entry.entryType === "draft" ? "草稿" : "内置"} tone="status" />
      </div>

      {entry.compatibility.reasons.length > 0 || entry.compatibility.warnings.length > 0 ? (
        <div className="grid gap-1 rounded-md border border-amber-200 bg-amber-50 p-3 text-xs text-amber-800">
          <span className="inline-flex items-center gap-1 font-semibold">
            <ShieldCheck aria-hidden="true" size={13} />
            兼容性说明
          </span>
          {[...entry.compatibility.reasons, ...entry.compatibility.warnings].map(
            (reason) => (
              <p key={reason}>{reason}</p>
            ),
          )}
        </div>
      ) : null}
    </article>
  )
}

function MetaRow({ label, values }: { label: string; values: string[] }) {
  return (
    <div className="flex min-w-0 flex-wrap items-center gap-1.5">
      <span className="font-semibold text-slate-700">{label}</span>
      {values.length === 0 ? (
        <span className="text-[var(--muted-foreground)]">未声明</span>
      ) : (
        values.map((value) => <DirectoryPill key={value} label={value} tone="meta" />)
      )}
    </div>
  )
}

function DirectoryPill({
  label,
  tone,
}: {
  label: string
  tone: "provider" | "meta" | "status" | "ok" | "danger" | "selected"
}) {
  return (
    <span
      className={cn(
        "max-w-full rounded-md border px-2 py-1 text-xs font-semibold",
        tone === "provider"
          ? "border-blue-200 bg-blue-50 text-blue-700"
          : tone === "ok"
            ? "border-emerald-200 bg-emerald-50 text-emerald-700"
            : tone === "danger"
              ? "border-rose-200 bg-rose-50 text-rose-700"
              : tone === "selected"
                ? "border-violet-200 bg-violet-50 text-violet-700"
                : tone === "meta"
                  ? "border-slate-200 bg-slate-50 text-slate-600"
                  : "border-[var(--border)] bg-white text-slate-600",
      )}
      title={label}
    >
      {label}
    </span>
  )
}

function buildFilterOptions(entries: AgentDirectoryEntry[]) {
  return {
    capability: sortedUnique(entries.flatMap((entry) => entry.capabilityTags)),
    provider: sortedUnique(entries.map((entry) => entry.providerId)),
    role: sortedUnique(entries.map((entry) => entry.role)),
    status: sortedUnique(entries.map((entry) => entry.status)),
    target: sortedUnique(entries.flatMap((entry) => entry.supportedTargets)),
  }
}

function matchesEntry(
  entry: AgentDirectoryEntry,
  filters: Record<FilterKey, string>,
  query: string,
) {
  const normalizedQuery = query.trim().toLowerCase()
  const queryMatch =
    !normalizedQuery ||
    [entry.displayName, entry.role, entry.providerId, entry.adapterType]
      .join(" ")
      .toLowerCase()
      .includes(normalizedQuery)
  return (
    queryMatch &&
    matchesScalar(entry.role, filters.role) &&
    matchesScalar(entry.providerId, filters.provider) &&
    matchesScalar(entry.status, filters.status) &&
    matchesList(entry.capabilityTags, filters.capability) &&
    matchesList(entry.supportedTargets, filters.target)
  )
}

function matchesScalar(value: string, filter: string) {
  return filter === "all" || value === filter
}

function matchesList(values: string[], filter: string) {
  return filter === "all" || values.includes(filter)
}

function sortedUnique(values: string[]) {
  return Array.from(new Set(values.filter(Boolean))).sort((a, b) =>
    a.localeCompare(b),
  )
}

function statusLabel(status: string) {
  return {
    available: "可用",
    disabled: "停用",
    draft_only: "草稿",
    planned: "计划中",
    unavailable: "不可用",
  }[status] ?? status
}
