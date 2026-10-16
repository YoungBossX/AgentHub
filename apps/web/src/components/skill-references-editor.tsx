"use client"

export type ReferenceDraft = { id: string; path: string; content: string }
const bytes = (text: string) => new TextEncoder().encode(text).length
const field = "w-full min-w-0 rounded-md border border-[var(--border)] bg-[var(--surface)] p-2 text-xs"

export function referenceRows(references: Record<string, string>): ReferenceDraft[] {
  return Object.entries(references).map(([path, content]) => ({ id: crypto.randomUUID(), path, content }))
}

export function validateReferenceRows(rows: ReferenceDraft[], markdown: string): Record<string, string> {
  if (rows.length > 8) throw new Error("参考资料最多 8 个文件。")
  const result: Record<string, string> = Object.create(null)
  let total = bytes(markdown)
  for (const row of rows) {
    const parts = row.path.split("/")
    if (row.path.length > 160 || /[\\\0]/.test(row.path) || !["references", "assets"].includes(parts[0]) || parts.length < 2
      || parts.some(part => !part || part.startsWith(".")) || !/\.(md|txt|json|ya?ml)$/i.test(row.path))
      throw new Error("参考路径须为 references/ 或 assets/ 下的相对文本路径，不能使用隐藏目录、上级目录或脚本。")
    if (Object.hasOwn(result, row.path)) throw new Error(`参考路径重复：${row.path}`)
    if (bytes(row.content) > 12000 || row.content.includes("\0")) throw new Error(`文件 ${row.path} 超过 12 KB 或包含非文本内容。`)
    result[row.path] = row.content
    total += bytes(row.content)
  }
  if (total > 48000) throw new Error("技能正文与参考资料合计最多 48 KB。")
  return result
}

export async function readSkillText(file: File, limit: number): Promise<string> {
  if (file.size > limit) throw new Error(`文件最多 ${limit / 1000} KB。`)
  const value = new TextDecoder("utf-8", { fatal: true }).decode(await file.arrayBuffer())
  if (value.includes("\0")) throw new Error("仅支持 UTF-8 文本，不能导入二进制文件。")
  return value
}

export function SkillReferencesEditor({ rows, markdown, busy, onChange, onBusyChange, onNotice }: {
  rows: ReferenceDraft[]; markdown: string; busy: boolean; onChange: (rows: ReferenceDraft[]) => void; onBusyChange: (busy: boolean) => void; onNotice: (notice: string) => void
}) {
  async function importFiles(files: File[]) {
    if (!files.length) return
    if (files.length + rows.length > 8) { onNotice("参考资料最多 8 个文件，请先移除不需要的条目。"); return }
    onBusyChange(true); onNotice("")
    try {
      const incoming = await Promise.all(files.map(async file => ({ id: crypto.randomUUID(), path: `references/${file.name}`, content: await readSkillText(file, 12000) })))
      const next = [...rows, ...incoming]
      validateReferenceRows(next, markdown)
      onChange(next)
    } catch (error) { onNotice(error instanceof TypeError ? "无法解码文件，请选择 UTF-8 文本。" : error instanceof Error ? error.message : "导入失败") }
    finally { onBusyChange(false) }
  }
  return <fieldset className="grid min-w-0 gap-2 rounded-lg border border-[var(--border)] bg-[var(--surface-muted)] p-3" disabled={busy}>
    <legend className="px-1 text-xs font-medium">参考资料 · {rows.length}/8</legend>
    <p className="text-xs text-[var(--muted-foreground)]">每个文件最多 12 KB，整个技能最多 48 KB。使用 references/ 或 assets/ 相对路径，在正文中引用；文件仅作为文本资料，不执行脚本。</p>
    {rows.map((row, index) => <div key={row.id} className="grid min-w-0 gap-2 rounded border border-[var(--border)] bg-[var(--surface)] p-2">
      <div className="flex min-w-0 items-end gap-2"><label className="grid min-w-0 flex-1 gap-1 text-xs">文件路径
        <input aria-label={`参考路径 ${index + 1}`} className={`${field} font-mono`} value={row.path} maxLength={160} onChange={event => onChange(rows.map(item => item.id === row.id ? { ...item, path: event.target.value } : item))} />
      </label><button type="button" aria-label={`移除参考文件 ${index + 1}`} className="shrink-0 rounded border border-[var(--border)] px-2 py-2 text-xs" onClick={() => onChange(rows.filter(item => item.id !== row.id))}>移除</button></div>
      <label className="grid min-w-0 gap-1 text-xs">文件内容<textarea aria-label={`参考内容 ${index + 1}`} className={`${field} min-h-28 font-mono`} value={row.content} onChange={event => onChange(rows.map(item => item.id === row.id ? { ...item, content: event.target.value } : item))} /></label>
      <p className="text-[10px] text-[var(--muted-foreground)]">UTF-8 {bytes(row.content).toLocaleString()} / 12,000 字节</p>
    </div>)}
    <div className="flex flex-wrap items-center gap-3 text-xs"><button type="button" disabled={rows.length >= 8} className="rounded border border-[var(--border)] bg-[var(--surface)] px-2 py-1.5" onClick={() => {
      let index = 1
      while (rows.some(row => row.path === `references/resource-${index}.md`)) index++
      onChange([...rows, { id: crypto.randomUUID(), path: `references/resource-${index}.md`, content: "" }])
    }}>添加参考文件</button><label className="min-w-0">导入文本文件<input aria-label="导入参考文件" type="file" multiple accept=".md,.txt,.json,.yaml,.yml" className="mt-1 block max-w-full text-xs" onChange={event => { const files = Array.from(event.currentTarget.files ?? []); event.currentTarget.value = ""; void importFiles(files) }} /></label></div>
  </fieldset>
}
