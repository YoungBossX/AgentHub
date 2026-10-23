type Node = {
  type: string; value?: string; tagName?: string; properties?: Record<string, unknown>
  children?: Node[]; position?: { start: { offset?: number }; end: { offset?: number } }
}

// Wrapping prose in the existing sanitized HAST preserves Markdown, links and
// copied source. Never split grapheme clusters or execute output as HTML.
export function revealAppendedText({ source, from }: { source: string; from: number }) {
  return (tree: Node) => {
    let count = 0
    const segmenter = new Intl.Segmenter(undefined, { granularity: "grapheme" })
    function walk(parent: Node) {
      if (!parent.children || ["code", "pre", "a"].includes(parent.tagName ?? "")) return
      parent.children = parent.children.flatMap((child): Node[] => {
        if (child.type !== "text") { walk(child); return [child] }
        const start = child.position?.start.offset
        const end = child.position?.end.offset
        if (start === undefined || end === undefined || end <= from || count >= 32 || source.slice(start, end) !== child.value) return [child]
        const text = child.value ?? ""
        const nodes: Node[] = []
        let settled = ""
        for (const { segment, index } of segmenter.segment(text)) {
          if (start + index < from || count >= 32 || !segment.trim()) { settled += segment; continue }
          if (settled) { nodes.push({ type: "text", value: settled }); settled = "" }
          nodes.push({ type: "element", tagName: "span", properties: { className: ["stream-reveal-char"], dataRevealId: start + index, style: `--reveal-delay:${count++ * 30}ms` }, children: [{ type: "text", value: segment }] })
        }
        if (settled) nodes.push({ type: "text", value: settled })
        return nodes
      })
    }
    walk(tree)
  }
}
