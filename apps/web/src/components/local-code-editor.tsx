"use client"

import Editor, { type EditorProps } from "@monaco-editor/react"
import { useEffect, useLayoutEffect, useRef, useState } from "react"
import { loadLocalMonaco } from "@/lib/load-local-monaco"
import { useTheme } from "./theme-toggle"
import { MAX_QUOTED_CODE_CHARS } from "./code-quote-context"

export function LocalCodeEditor({ value, onChange, disabled, path, onQuote }: {
  value: string; onChange: (value: string) => void; disabled: boolean; path: string; onQuote?: (text: string) => void
}) {
  const theme = useTheme()
  const [ready, setReady] = useState(false)
  const [plain, setPlain] = useState(false)
  const [failed, setFailed] = useState(false)
  const [selection, setSelection] = useState<{ text: string; value: string; path: string } | null>(null)
  const current = useRef({ value, path })
  useLayoutEffect(() => { current.current = { value, path } }, [value, path])
  const selectedText = selection?.value === value && selection.path === path ? selection.text : ""
  const selectionLength = Array.from(selectedText).length
  const captureSelection = (text: string) => setSelection({ text, ...current.current })
  const editorRef = useRef<Parameters<NonNullable<EditorProps["onMount"]>>[0] | null>(null)
  const selectionListener = useRef<{ dispose: () => void } | null>(null)
  useEffect(() => {
    let active = true
    loadLocalMonaco().then(() => { if (active) setReady(true) }, () => { if (active) setFailed(true) })
    return () => { active = false }
  }, [])
  useEffect(() => () => {
    selectionListener.current?.dispose()
    selectionListener.current = null
    const editor = editorRef.current
    const model = editor?.getModel()
    editor?.setModel(null)
    model?.dispose()
    editorRef.current = null
  }, [plain])
  const fallback = <textarea aria-label="完整源码" spellCheck={false} disabled={disabled} value={value}
    onSelect={event => captureSelection(event.currentTarget.value.slice(event.currentTarget.selectionStart, event.currentTarget.selectionEnd))}
    onChange={event => onChange(event.target.value)} className="h-80 w-full min-w-0 resize-y rounded border border-[var(--border)] bg-[var(--surface)] p-2 font-mono text-xs" />
  return <div className="min-w-0">
    <div className="mb-2 flex flex-wrap items-center gap-3">
      <button type="button" className="text-xs underline" onClick={() => { setSelection(null); setPlain(current => !current) }}>{plain ? "代码编辑器" : "纯文本模式"}</button>
      {onQuote ? <button type="button" disabled={disabled || !selectedText.trim() || selectionLength > MAX_QUOTED_CODE_CHARS} className="rounded border border-[var(--border)] px-2 py-1 text-xs disabled:opacity-40"
        onClick={() => { onQuote(selectedText); setSelection(null) }}>引用选中代码</button> : null}
    </div>
    {onQuote ? <p role="status" className="mb-2 text-xs text-[var(--muted-foreground)]">{selectionLength > MAX_QUOTED_CODE_CHARS ? "选区超过 2400 字符，请缩小选区后引用。" : "选中代码后添加到消息上下文；保留草稿内容，不自动应用或发送。"}</p> : null}
    {failed ? <p role="status" className="text-xs text-[var(--muted-foreground)]">编辑器加载失败，可以继续使用完整源码文本框。</p> : null}
    {ready && !plain ? <Editor height="320px" value={value} keepCurrentModel
      language={/\.tsx?$/.test(path) ? "typescript" : /\.[cm]?jsx?$/.test(path) ? "javascript" : path.endsWith(".css") ? "css" : "plaintext"}
      theme={theme === "dark" ? "vs-dark" : "vs"} loading={fallback}
      options={{ readOnly: disabled, minimap: { enabled: false }, scrollBeyondLastLine: false, automaticLayout: true, wordWrap: "on", ariaLabel: "完整源码" }}
      onChange={content => { if (!disabled) onChange(content ?? "") }} onMount={editor => {
        editorRef.current = editor
        selectionListener.current = editor.onDidChangeCursorSelection(() => {
          const range = editor.getSelection()
          captureSelection(range ? editor.getModel()?.getValueInRange(range) ?? "" : "")
        })
      }}
      /> : fallback}
  </div>
}
