"use client"

import { useRef, useState } from "react"
import { Check, Copy } from "lucide-react"

export function CopyTextButton({ text, label, ariaLabel = label, compact = false }: {
  text: string
  label: string
  ariaLabel?: string
  compact?: boolean
}) {
  const requestId = useRef(0)
  const [result, setResult] = useState<{ text: string; status: "copying" | "copied" | "failed" } | null>(null)
  const status = result?.text === text ? result.status : null

  async function copy() {
    const id = ++requestId.current
    setResult({ text, status: "copying" })
    try {
      if (!navigator.clipboard?.writeText) throw new Error("Clipboard unavailable")
      await navigator.clipboard.writeText(text)
      if (id === requestId.current) setResult({ text, status: "copied" })
    } catch {
      if (id === requestId.current) setResult({ text, status: "failed" })
    }
  }

  return (
    <span className="inline-flex max-w-full flex-wrap items-center gap-2">
      <button aria-label={ariaLabel} title={label} type="button" onClick={() => void copy()} disabled={status === "copying"}
        className="inline-flex min-h-7 shrink-0 items-center gap-1.5 rounded-md px-2 text-xs text-[var(--muted-foreground)] hover:bg-[var(--muted)] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--primary)] disabled:opacity-50">
        {status === "copied" ? <Check aria-hidden="true" size={13} /> : <Copy aria-hidden="true" size={13} />}
        {!compact ? (status === "copied" ? "已复制" : status === "copying" ? "复制中…" : label) : null}
      </button>
      <span role="status" className={status === "failed" || (compact && status === "copied") ? "text-xs text-[var(--muted-foreground)]" : "sr-only"}>
        {status === "failed" ? "复制失败，请手动选择文本复制。" : status === "copied" ? "已复制" : ""}
      </span>
    </span>
  )
}
