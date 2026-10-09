export function selectComposerMention(draft: string, alias: string, mode: "direct" | "group"): string {
  const mention = `@${alias}`
  if (mode === "group") {
    const aliases = Array.from(draft.matchAll(/@([A-Za-z][A-Za-z0-9_-]*)/g), (match) => match[1].toLowerCase())
    if (aliases.includes(alias.toLowerCase())) return draft
    const prefix = draft.match(/^(?:@[A-Za-z][A-Za-z0-9_-]*(?:\s+|$))+/)?.[0] ?? ""
    return `${prefix}${prefix && !/\s$/.test(prefix) ? " " : ""}${mention} ${draft.slice(prefix.length)}`
  }
  return `${mention} ${draft.replace(/^(?:@[A-Za-z][A-Za-z0-9_-]*(?:\s+|$))+/, "")}`
}
