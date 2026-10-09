"use client"

import { DiffEditor, type DiffEditorProps } from "@monaco-editor/react"
import { useEffect, useRef, useState } from "react"
import { loadLocalMonaco } from "@/lib/load-local-monaco"

type LocalDiffEditorProps = Omit<DiffEditorProps,
  "originalModelPath" | "modifiedModelPath" | "keepCurrentOriginalModel" | "keepCurrentModifiedModel">

export function LocalDiffEditor(props: LocalDiffEditorProps) {
  const [status, setStatus] = useState<"loading" | "ready" | "failed">("loading")
  const [attempt, setAttempt] = useState(0)
  const editorRef = useRef<Parameters<NonNullable<DiffEditorProps["onMount"]>>[0] | null>(null)

  useEffect(() => () => {
    const editor = editorRef.current
    const models = editor?.getModel()
    // Monaco 0.56 requires detaching models before disposing them. The React
    // wrapper disposes models first by default, so own these anonymous models.
    editor?.setModel(null)
    models?.original.dispose()
    models?.modified.dispose()
    editorRef.current = null
  }, [])

  useEffect(() => {
    let active = true
    loadLocalMonaco().then(
      () => { if (active) setStatus("ready") },
      () => { if (active) setStatus("failed") },
    )
    return () => { active = false }
  }, [attempt])

  if (status === "ready") return <DiffEditor {...props}
    keepCurrentOriginalModel
    keepCurrentModifiedModel
    onMount={(editor, monaco) => {
      editorRef.current = editor
      props.onMount?.(editor, monaco)
    }}
  />
  return <>
    {props.loading}
    {status === "failed" ? <div role="status" className="px-3 py-2 text-xs text-[var(--muted-foreground)]">
      对比编辑器加载失败，仍可查看上方代码补丁。
      <button className="ml-2 underline" type="button" onClick={() => {
        setStatus("loading")
        setAttempt(value => value + 1)
      }}>重试加载</button>
    </div> : null}
  </>
}
