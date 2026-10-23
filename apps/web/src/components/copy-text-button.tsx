"use client"

import { useEffect, useRef, useState } from "react"
import { Check, Copy } from "lucide-react"

export function CopyTextButton({ text, label, ariaLabel = label, compact = false }: {
  text: string
  label: string
  ariaLabel?: string
  compact?: boolean
}) {
  const requestId = useRef(0)
  const [input, setInput] = useState(text)
  const [result, setResult] = useState<{ text: string; status: "copying" | "copied" | "failed" } | null>(null)
  // Clear on a content transition, including A -> B -> A. Masking only by
  // equality would resurrect a successful or invalidated pending operation.
  if (input !== text) { setInput(text); setResult(null) }
  const status = result?.text === text ? result.status : null

  useEffect(() => () => { requestId.current += 1 }, [text])
  useEffect(() => {
    if (status !== "copied") return
    const timer = window.setTimeout(() => setResult(null), 2500)
    return () => window.clearTimeout(timer)
  }, [result, status])

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
        className="copy-button inline-flex min-h-7 shrink-0 items-center gap-1.5 rounded-md px-2 text-xs text-[var(--muted-foreground)] hover:bg-[var(--muted)] disabled:opacity-50" data-copied={status === "copied"}>
        <span className="copy-icons" aria-hidden="true"><Copy size={13} className="copy-icon" /><Check size={13} className="copy-check" /></span>
        {!compact ? (status === "copied" ? "已复制" : status === "copying" ? "复制中…" : label) : null}
      </button>
      <span role="status" className={status === "failed" || (compact && status === "copied") ? "text-xs text-[var(--muted-foreground)]" : "sr-only"}>
        {status === "failed" ? "复制失败，请手动选择文本复制。" : status === "copied" ? "已复制" : ""}
      </span>
    </span>
  )
}
