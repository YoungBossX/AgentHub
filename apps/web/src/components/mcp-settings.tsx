"use client"

import { useEffect, useState } from "react"
import type { AgentDirectoryEntry } from "@/lib/api"
import { getMcpConnection, saveMcpConnection, probeMcpConnection, type McpConnection } from "@/lib/mcp-api"

const field = "rounded-md border border-[var(--border)] bg-[var(--surface)] px-3 py-2 text-xs"
export function McpSettings({ backendUrl, workspaceId, agents }: { backendUrl: string; workspaceId?: string; agents: AgentDirectoryEntry[] }) {
  const [config, setConfig] = useState<McpConnection | null>(null)
  const [busy, setBusy] = useState(false)
  const [notice, setNotice] = useState("")
  const [reload, setReload] = useState(0)
  useEffect(() => { let current = true
    if (workspaceId) getMcpConnection(backendUrl, workspaceId).then(value => { if (current) { setConfig(value); setNotice("") } })
      .catch(error => { if (current) setNotice(error instanceof Error ? error.message : "连接配置加载失败") })
    return () => { current = false }
  }, [backendUrl, workspaceId, reload])
  const identities = [{ key: "frontend", label: "前端默认 Agent" }, { key: "backend", label: "后端默认 Agent" },
    ...agents.filter(a => a.toolPolicy && a.adapterType === "codex" && ["frontend", "backend"].includes(a.role)).map(a => ({ key: a.agentProfileId, label: a.displayName }))]
  return <section aria-label="MCP 工具连接" className="grid gap-3 rounded-xl border border-[var(--border)] bg-[var(--surface)] p-4">
    <div className="flex flex-wrap items-center justify-between gap-2"><div><h2 className="font-semibold">MCP · 工具连接</h2>
      <p className="mt-1 text-xs text-[var(--muted-foreground)]">本地项目文档 · 只读 · 支持 Codex。读取当前目标及同工作树内关联演示后端的 README/docs。</p></div>
      <button className={field} type="button" disabled={busy} onClick={() => setReload(v => v + 1)}>刷新连接</button></div>
    {notice ? <p role="status" className="text-xs text-[var(--muted-foreground)]">{notice}</p> : null}
    {config ? <form className="grid gap-3" onSubmit={async event => { event.preventDefault(); if (!workspaceId || busy) return
      setBusy(true); setNotice("")
      try { setConfig(await saveMcpConnection(backendUrl, workspaceId, config)); setNotice("工具连接已保存。新运行使用新配置，关闭连接会拒绝后续工具调用。") }
      catch (error) { setNotice(error instanceof Error ? error.message : "保存失败") } finally { setBusy(false) }
    }}>
      <label className="text-xs"><input type="checkbox" disabled={busy} checked={config.enabled} onChange={event => setConfig({ ...config, enabled: event.target.checked })} /> 启用项目文档 MCP</label>
      <fieldset className="flex flex-wrap gap-3" disabled={busy}><legend className="mb-2 text-xs">允许的工具</legend>
        {[{ name: "list_documents", label: "列出文档" }, { name: "read_document", label: "读取文档" }].map(tool => <label className="text-xs" key={tool.name}>
          <input type="checkbox" checked={config.tools.includes(tool.name)} onChange={event => setConfig({ ...config,
            tools: event.target.checked ? [...config.tools, tool.name] : config.tools.filter(t => t !== tool.name) })} /> {tool.label}</label>)}
      </fieldset>
      <fieldset className="flex flex-wrap gap-3" disabled={busy}><legend className="mb-2 text-xs">默认绑定 Agent</legend>{identities.map(agent => <label className="text-xs" key={agent.key}>
        <input type="checkbox" checked={config.defaultAgents.includes(agent.key)} onChange={event => setConfig({ ...config,
          defaultAgents: event.target.checked ? [...config.defaultAgents, agent.key] : config.defaultAgents.filter(k => k !== agent.key) })} /> {agent.label}</label>)}</fieldset>
      <p className="text-xs text-[var(--muted-foreground)]">Claude / ScriptedMock 当前会明确显示不支持；连接测试只检查握手和工具列表，实际使用记录见任务执行过程。</p>
      <div className="flex flex-wrap gap-2"><button type="submit" className={field} disabled={busy}>{busy ? "处理中…" : "保存工具连接"}</button>
        <button type="button" className={field} disabled={busy || !workspaceId} onClick={async () => { if (!workspaceId) return; setBusy(true); setNotice("")
          try { const result = await probeMcpConnection(backendUrl, workspaceId); setNotice(result.status === "ready" ? `MCP 握手成功 · ${result.tools?.length ?? 0} 个工具（已保存配置）` : result.reason ?? "MCP 不可用") }
          catch (error) { setNotice(error instanceof Error ? error.message : "连接测试失败") } finally { setBusy(false) }
        }}>测试连接</button></div>
    </form> : null}
  </section>
}
