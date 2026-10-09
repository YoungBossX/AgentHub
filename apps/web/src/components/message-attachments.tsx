"use client"

import { Download, FileText } from "lucide-react"
import { attachmentContentUrl, type MessageAttachment } from "@/lib/api"

export function attachmentReadLabel(item: MessageAttachment) {
  if (item.extractionStatus === "no_text") return "未提取到文字 · 请换用文本 PDF 或文本文件"
  if (item.kind === "image") return "图像输入 · 需要支持图片的原生 Agent"
  return item.textTruncated ? "已提取文字 · 内容过长，截取前段" : "文字已提取 · 按上下文预算供 Agent 参考"
}

export function MessageAttachments({ items, backendUrl }: { items: MessageAttachment[]; backendUrl: string }) {
  return <ul className="mt-3 grid min-w-0 grid-cols-1 gap-2" aria-label="消息附件">
    {items.map((item) => <li key={item.id} className="min-w-0 overflow-hidden rounded-lg border border-[var(--border)] bg-[var(--surface)]">
      {item.kind === "image" ? <a href={attachmentContentUrl(backendUrl, item, true)} target="_blank" rel="noreferrer" aria-label={`预览 ${item.filename}`}>
        {/* Validated local raster endpoint; bypass Next remote image optimization. */}
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src={attachmentContentUrl(backendUrl, item, true)} alt={item.filename} loading="lazy" className="max-h-56 w-full bg-[var(--surface-muted)] object-contain" />
      </a> : null}
      <div className="flex min-w-0 items-start gap-2 p-3">
        <FileText size={16} className="mt-1 shrink-0 text-[var(--primary)]" aria-hidden="true" />
        <div className="min-w-0 flex-1"><p className="break-all text-xs font-semibold">{item.filename}</p>
          <p className="text-[10px] leading-4 text-[var(--muted-foreground)]">{Math.max(1, Math.ceil(item.byteSize / 1024))} KiB · {attachmentReadLabel(item)}</p>
          <details className="text-[10px] text-[var(--muted-foreground)]"><summary>文件来源</summary><p className="break-all">附件 {item.id}<br />SHA-256 {item.sha256}</p></details>
        </div>
        <a href={attachmentContentUrl(backendUrl, item)} download={item.filename} aria-label={`下载 ${item.filename}`} className="rounded p-1.5 hover:bg-[var(--surface-muted)]"><Download size={15} /></a>
      </div>
    </li>)}
  </ul>
}
