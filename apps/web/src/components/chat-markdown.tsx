"use client"

import { memo, useState } from "react"
import Markdown, { type Components } from "react-markdown"
import remarkGfm from "remark-gfm"

import { CopyTextButton } from "./copy-text-button"
import styles from "./chat-markdown.module.css"

const MARKDOWN_CHARACTER_LIMIT = 100_000

type MarkdownNode = { properties?: Record<string, unknown>; children?: MarkdownNode[] }

function uniqueFootnoteLabel({ prefix }: { prefix: string }) {
  return (tree: MarkdownNode) => {
    const pending = [tree]
    while (pending.length) {
      const node = pending.pop()!
      if (node.properties?.id === "footnote-label") node.properties.id = `${prefix}footnote-label`
      if (Array.isArray(node.properties?.ariaDescribedBy)) {
        node.properties.ariaDescribedBy = node.properties.ariaDescribedBy.map((id) => id === "footnote-label" ? `${prefix}footnote-label` : id)
      }
      pending.push(...(node.children || []))
    }
  }
}

function safeUrl(value: string, image = false): string | undefined {
  if (/[\u0000-\u0020\u007f\\]/u.test(value)) return undefined
  if (/%(?:0[0-9a-f]|1[0-9a-f]|5c|7f)/iu.test(value)) return undefined
  if (!image && /^#[\w-]+$/u.test(value)) return value
  try {
    const url = new URL(value)
    const allowed = image ? ["https:", "http:"] : ["https:", "http:", "mailto:"]
    if (!allowed.includes(url.protocol) || url.username || url.password) return undefined
    return url.href
  } catch {
    return undefined
  }
}

function MessageImage({ src, alt }: { src?: string; alt?: string }) {
  const [state, setState] = useState<"idle" | "loading" | "loaded" | "failed">("idle")
  const description = alt || "消息图片"
  if (!src) return <span className={styles.imagePlaceholder}>图片：{description}（链接不可用）</span>
  return <span className={styles.imagePreview}>
    {state === "idle" ? <button type="button" onClick={() => setState("loading")} className={styles.imageButton}>
      加载图片：{description} <span>来源：{new URL(src).host}</span>
    </button> : state === "failed" ? <span role="status">图片加载失败：{description}</span> : <>
      {state === "loading" ? <span role="status">正在加载图片…</span> : null}
      {/* User-initiated remote image; no server optimizer or automatic fetch. */}
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img src={src} alt={description} referrerPolicy="no-referrer" crossOrigin="anonymous" onLoad={() => setState("loaded")} onError={() => setState("failed")} />
    </>}
    <a href={src} target="_blank" rel="noopener noreferrer" referrerPolicy="no-referrer">打开图片链接</a>
  </span>
}

const components: Components = {
  a({ href, children, title, id, "aria-describedby": describedBy }) {
    if (!href) return <span>{children}</span>
    return <a id={id} aria-describedby={describedBy} href={href} title={title} target={href.startsWith("#") ? undefined : "_blank"} rel="noopener noreferrer" referrerPolicy="no-referrer">{children}</a>
  },
  img({ src, alt }) {
    return <MessageImage key={`${src}:${alt}`} src={typeof src === "string" ? src : undefined} alt={alt} />
  },
  pre({ node, children }) {
    const code = node?.children.find((child) => child.type === "element" && child.tagName === "code")
    const text = code?.type === "element" ? code.children.map((child) => child.type === "text" ? child.value : "").join("") : ""
    const classes = code?.type === "element" ? code.properties.className : []
    const language = Array.isArray(classes) ? classes.find((value) => typeof value === "string" && value.startsWith("language-"))?.toString().slice(9, 49) : undefined
    return <div className={styles.codeBlock}>
      <div className={styles.codeHeader}><span>{language || "代码"}</span><CopyTextButton text={text} label="复制代码" /></div>
      <pre tabIndex={0} aria-label={language ? `${language} 代码` : "代码块"}>{children}</pre>
    </div>
  },
  table({ children }) {
    return <div className={styles.tableScroll} tabIndex={0} role="region" aria-label="消息表格"><table>{children}</table></div>
  },
  input({ checked }) {
    return <input type="checkbox" checked={!!checked} disabled aria-label={checked ? "已完成" : "未完成"} />
  },
}

export const ChatMarkdown = memo(function ChatMarkdown({ content, messageId }: { content: string; messageId: string }) {
  if (content.length > MARKDOWN_CHARACTER_LIMIT) {
    return <div className={styles.markdown}><p className={styles.longNotice}>消息较长，以下按原文显示。</p><pre className={styles.plainText}>{content}</pre></div>
  }
  const prefix = `message-${encodeURIComponent(messageId)}-`
  return <div className={styles.markdown}>
    <Markdown components={components} remarkPlugins={[remarkGfm]}
      rehypePlugins={[[uniqueFootnoteLabel, { prefix }]]}
      remarkRehypeOptions={{ clobberPrefix: prefix, footnoteLabel: "注释" }}
      urlTransform={(url, _key, node) => safeUrl(url, node.tagName === "img")}>
      {content}
    </Markdown>
  </div>
})
