"use client"
import type { ReactNode } from "react"
import { Menu, PanelRight, Check, Circle, CircleDot } from "lucide-react"
import { cn } from "@/lib/utils"
import type { WorkbenchStage, WorkspaceView } from "./session-workbench-state"
import { ThemeToggle } from "./theme-toggle"
export function WorkspaceHeader({ conversationMode, healthSlot, onModeChange, selectedSessionTitle, taskCount, stages, view, onViewChange, artifactCount, onToggleSidebar, onToggleInspector }: {
  conversationMode: "direct" | "group"; healthSlot?: ReactNode; onModeChange: (mode: "direct" | "group") => void
  selectedSessionTitle: string; taskCount: number; stages: WorkbenchStage[]; view: WorkspaceView
  onViewChange: (view: WorkspaceView) => void; artifactCount: number; onToggleSidebar: () => void; onToggleInspector: () => void
}) {
  return <header
    className="shrink-0 border-b border-[var(--border)] bg-white px-5 pt-4"
    data-region="top-header"
  >
    <div className="flex items-center justify-between gap-3">
      <div className="flex min-w-0 items-center gap-2">
        <button
          aria-label="切换会话列表"
          className="rounded-lg p-2 lg:hidden"
          onClick={onToggleSidebar}
        >
          <Menu size={18} />
        </button>
        <div className="min-w-0">
          <p className="text-[10px] font-semibold tracking-wide text-slate-400">AgentHub / 工作台</p>
          <h2 className="mt-1 truncate text-lg font-semibold text-slate-900">{selectedSessionTitle}</h2>
        </div>
      </div>
      <div className="flex shrink-0 items-center gap-2">
        <div className="hidden xl:block">{healthSlot}</div>
        <ThemeToggle />
        <ConversationModeSwitch
          mode={conversationMode}
          onModeChange={onModeChange}
        />
        <button
          aria-label="切换成果面板"
          className="rounded-lg p-2 text-slate-500 hover:bg-slate-100"
          onClick={onToggleInspector}
        >
          <PanelRight size={17} />
        </button>
      </div>
    </div>
    <ol
      aria-label="交付进度"
      className="mt-4 flex gap-3 overflow-x-auto pb-2 text-[11px]"
    >
      {stages.map((stage) => <li
        key={stage.label}
        title={stage.detail}
        className={cn("flex shrink-0 items-center gap-1.5", stage.state === "ready" ? "text-emerald-700" : stage.state === "active" ? "text-blue-600" : stage.state === "failed" ? "text-red-600" : "text-slate-400")}
      >
        {stage.state === "ready" ? <Check size={12} /> : stage.state === "active" ? <CircleDot size={12} /> : <Circle size={12} />}
        {stage.label}
        <span className="sr-only">
          ：
          {stage.detail}
        </span>
      </li>)}
    </ol>
    <nav
      aria-label="工作台视图"
      className="mt-2 flex gap-6"
    >
      {([{ id: "conversation", label: "对话", count: null }, { id: "process", label: "执行过程", count: taskCount }, { id: "results", label: "成果", count: artifactCount }] as const).map((tab) => <button
        key={tab.id}
        aria-pressed={view === tab.id}
        onClick={() => onViewChange(tab.id)}
        className={cn("border-b-2 py-3 text-xs font-medium", view === tab.id ? "border-[var(--primary)] text-[var(--primary)]" : "border-transparent text-slate-500 hover:text-slate-900")}
      >
        {tab.label}
        {tab.count !== null ? <span className="ml-1.5 rounded bg-slate-100 px-1.5 text-[10px] text-slate-500">{tab.count}</span> : null}
      </button>)}
    </nav>
  </header>
}
export function ConversationModeSwitch({ mode, onModeChange }: { mode: "direct" | "group"; onModeChange: (mode: "direct" | "group") => void }) {
  return <div className="flex rounded-lg bg-slate-100 p-0.5">
    {([{ id: "direct", label: "单聊" }, { id: "group", label: "群聊" }] as const).map((item) => <button
      key={item.id}
      aria-pressed={mode === item.id}
      onClick={() => onModeChange(item.id)}
      className={cn("rounded-md px-2.5 py-1.5 text-[11px]", mode === item.id ? "bg-white font-semibold text-slate-800 shadow-sm" : "text-slate-500")}
    >
      {item.label}
    </button>)}
  </div>
}
