"use client"

import { Disclosure } from "./disclosure"

import { useEffect, useState } from "react"
import { getMcpRunEvidence, type McpRunEvidence } from "@/lib/mcp-api"

export function McpEvidence({ backendUrl, runId, refreshKey }: { backendUrl: string; runId: string; refreshKey: number }) {
  const [evidence, setEvidence] = useState<McpRunEvidence | null>(null)
  const [error, setError] = useState("")
  const [reload, setReload] = useState(0)
  useEffect(() => { let current = true
    getMcpRunEvidence(backendUrl, runId).then(value => { if (current) { setEvidence(value); setError("") } })
      .catch(error => { if (current) setError(error instanceof Error ? error.message : "工具记录加载失败") })
    return () => { current = false }
  }, [backendUrl, runId, refreshKey, reload])
  const calls = evidence?.events.filter(e => e.type === "mcp.tool.completed") ?? []
  return <Disclosure className="mt-3 rounded-lg border border-[var(--border)] bg-[var(--surface)] p-3 text-xs" summaryClassName="cursor-pointer font-medium" summary={<>MCP 工具调用 · {calls.length} 次</>}>

    {error ? <p role="status" className="mt-2">{error}</p> : null}
    <button type="button" className="mt-2 text-[var(--primary)]" onClick={() => setReload(v => v + 1)}>刷新工具记录</button>
    <p className="mt-2 text-[var(--muted-foreground)]">{evidence?.connection?.status === "unsupported_adapter" ? "当前 Adapter 不支持此连接。" : calls.length ? "以下记录来自服务端实际工具执行。文档结果作为参考，不能替代 QA 验收。" : evidence?.events.some(e => e.type === "mcp.connected") ? "已建立 MCP 连接，尚无工具调用记录。" : "已配置连接，尚无实际连接或调用证据。"}</p>
    <ul className="mt-2 grid gap-2">{calls.map(call => <li key={call.id} className="rounded bg-[var(--surface-muted)] p-2">
      <p className="font-medium">{call.payload.tool} · {call.payload.status === "passed" ? "成功" : "失败"} · {call.payload.durationMs}ms</p>
      <Disclosure className="mt-1" summaryClassName="cursor-pointer" summary={<>参数与返回结果</>}>
        <pre className="mt-2 max-h-48 overflow-auto whitespace-pre-wrap break-all text-[11px]">{JSON.stringify({ arguments: call.payload.arguments, result: call.payload.result }, null, 2)}</pre></Disclosure>
    </li>)}</ul>
  </Disclosure>
}
