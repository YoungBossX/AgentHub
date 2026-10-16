"use client"

import { useState } from "react"
import type { ChatMessage } from "@/lib/api"
import { getMessageContent, type MessageContentPage } from "@/lib/message-history-api"
import { CopyTextButton } from "./copy-text-button"

export function LongMessageContent({ backendUrl, message }: { backendUrl: string; message: ChatMessage }) {
  const [page, setPage] = useState<MessageContentPage | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  if (!message.contentTruncated) return null
  async function load(offset: number) {
    setBusy(true); setError(null)
    try { setPage(await getMessageContent(backendUrl, message.sessionId, message.id, offset)) }
    catch (error) { setError(error instanceof Error ? error.message : "读取失败") }
    finally { setBusy(false) }
  }
  return <details className="mt-2 min-w-0 rounded border border-[var(--border)] bg-[var(--surface)] p-2 text-xs" onToggle={event => { if (event.currentTarget.open && !page && !busy) void load(0) }}>
    <summary className="cursor-pointer">长消息仅展示预览 · 查看全文（分段）</summary>
    <p className="mt-2 text-[var(--muted-foreground)]">原消息完整保留。每次读取最多 12,000 个 Unicode 字符；下方为正文文本，不执行其中代码。</p>
    {error ? <p role="alert" className="mt-2">{error}<button className="ml-2 underline" type="button" onClick={() => void load(page?.offset ?? 0)}>重试读取</button></p> : null}
    {page ? <><p className="my-2">第 {page.offset + 1}–{page.offset + Array.from(page.text).length} / {page.totalCharacters} 字符</p>
      <pre className="max-h-72 overflow-auto whitespace-pre-wrap break-words rounded bg-[var(--surface-muted)] p-2 font-mono">{page.text}</pre>
      <div className="mt-2 flex flex-wrap items-center gap-2"><button type="button" disabled={busy || page.previousOffset === null} className="rounded border border-[var(--border)] px-2 py-1 disabled:opacity-40" onClick={() => void load(page.previousOffset!)}>上一段</button>
        <button type="button" disabled={busy || page.nextOffset === null} className="rounded border border-[var(--border)] px-2 py-1 disabled:opacity-40" onClick={() => void load(page.nextOffset!)}>下一段</button><CopyTextButton text={page.text} label="复制当前段" ariaLabel="Copy current segment" compact /></div>
    </> : null}
    {busy ? <p className="mt-2" role="status">正在读取正文片段…</p> : null}
  </details>
}
