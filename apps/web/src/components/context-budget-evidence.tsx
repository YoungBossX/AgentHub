"use client"

type Receipt = { schemaVersion: string; status: string; textCharacters: number; textUtf8Bytes: number; managedBytes: number; imageCount: number; imageBytes: number; textSha256: string;
  limits: { textCharacters: number; managedBytes: number }; sources: { source: string; status: string; sourceSerializedCharacters: number; omissionReason: string | null; omissionReasons?: Record<string, number>; upstreamSelection: Record<string, number> }[] }
const names: Record<string, string> = { systemPrompt: "角色指令", skills: "Skills", projectRules: "项目规则", otherMemory: "其他记忆", currentRequest: "当前需求", recentMessages: "近期消息", pinnedMessages: "置顶消息", attachments: "附件", references: "引用与产物", guardrails: "权限与边界", memorySelection: "记忆选择记录", nativeReviewContract: "原生评审契约", mcpInstruction: "MCP 工具提示" }
const reasons: Record<string, string> = { image_budget: "图片限额", text_budget: "文本限额", no_text: "未提取到文本", attachment_selection_limit: "附件选择限额", pinned_selection_limit: "置顶选择限额", omittedByBudget: "记忆预算", omittedByExperienceLimit: "经验数量限额", source_text_truncated: "文本截断", protected_content_redacted: "保护内容已脱敏" }

export function ContextBudgetEvidence({ receipt }: { receipt?: unknown }) {
  if (!receipt || typeof receipt !== "object" || !("schemaVersion" in receipt) || receipt.schemaVersion !== "agenthub.context_budget.v1") return null
  const value = receipt as Receipt
  if (!value.limits || !Array.isArray(value.sources) || typeof value.textSha256 !== "string"
    || ![value.textCharacters, value.textUtf8Bytes, value.managedBytes, value.imageCount, value.imageBytes, value.limits.textCharacters].every(Number.isFinite)
    || value.sources.some(source => !source || typeof source.source !== "string" || !Number.isFinite(source.sourceSerializedCharacters))) return null
  return <details className="mt-2 min-w-0 rounded-lg border border-[var(--border)] bg-[var(--surface)] p-2 text-xs" aria-label="最终上下文预算">
    <summary className="cursor-pointer break-words">上下文预算 · {value.textCharacters.toLocaleString()} / {value.limits.textCharacters.toLocaleString()} 字符 · {value.status === "rejected" ? "超限，未调用" : "已记录"}</summary>
    <p className="mt-2 leading-5 text-[var(--muted-foreground)]">应用拼装的输入计量，包含最终格式与重复内容。字符不是模型 Token；不含 CLI 自行发现的上下文、模型回答或后续工具输出。超限时保留必要规则并拒绝调用。</p>
    <p className="mt-2 break-words">文本 UTF-8 {value.textUtf8Bytes.toLocaleString()} 字节 · 托管输入 {value.managedBytes.toLocaleString()} 字节 · 图片 {value.imageCount} 张 / {value.imageBytes.toLocaleString()} 字节</p>
    <p className="mt-1 break-all font-mono text-[var(--muted-foreground)]">文本指纹 {value.textSha256.slice(0, 16)}</p>
    <p className="mt-2 text-[var(--muted-foreground)]">各来源为序列化诊断大小，可能重叠，不能相加代替最终总量：</p>
    <ul className="mt-1 space-y-1">{value.sources.map(source => <li key={source.source} className="flex flex-wrap justify-between gap-1 border-t border-[var(--border)] py-1">
      <span>{names[source.source] ?? source.source} · {source.status === "included" ? "已选入" : source.status === "metadata_only" ? "仅选择记录" : "无内容或未选入"}</span>
      <span>{source.sourceSerializedCharacters.toLocaleString()} 字符{source.omissionReason ? " · 部分由来源限额或完整性策略省略" : ""}</span>
      {source.omissionReasons ? <span className="w-full text-[var(--muted-foreground)]">{Object.entries(source.omissionReasons).map(([reason, count]) => `${reasons[reason] ?? reason} ${count}`).join(" · ")}</span> : null}
    </li>)}</ul>
  </details>
}
