import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react"
import { createElement } from "react"
import { renderToString } from "react-dom/server"
import { afterEach, describe, expect, it, vi } from "vitest"

import { ChatMarkdown } from "./chat-markdown"
import { CopyTextButton } from "./copy-text-button"

afterEach(() => { cleanup(); vi.unstubAllGlobals() })

function show(content: string, messageId = "message-one") {
  return render(createElement(ChatMarkdown, { content, messageId }))
}

describe("ChatMarkdown", () => {
  it("renders headings, nested lists, emphasis, inline code, tables and task lists", () => {
    const { container } = show("## 执行结果\n\n**完成** `build()`\n\n1. 第一项\n   - 子任务\n\n- [x] 已验证\n- [ ] 待确认\n\n| 文件 | 结果 |\n| --- | --- |\n| App.tsx | 通过 |\n\n> 参考说明")
    expect(screen.getByRole("heading", { name: "执行结果", level: 2 })).toBeTruthy()
    expect(container.querySelector("strong")?.textContent).toBe("完成")
    expect(container.querySelector("code")?.textContent).toBe("build()")
    expect(container.querySelector("ol li ul li")?.textContent).toBe("子任务")
    expect(screen.getByRole("cell", { name: "App.tsx" })).toBeTruthy()
    expect((screen.getByRole("checkbox", { name: "已完成" }) as HTMLInputElement).disabled).toBe(true)
    expect(container.querySelector("blockquote")?.textContent).toContain("参考说明")
  })

  it("copies literal fenced code including whitespace, without UI labels or fences", async () => {
    const writeText = vi.fn().mockResolvedValue(undefined)
    vi.stubGlobal("navigator", { clipboard: { writeText } })
    const { container } = show('示例：\n\n```tsx\n  const value = "<img>&amp; 中文"\n\n  run(value)\n```')
    const text = '  const value = "<img>&amp; 中文"\n\n  run(value)\n'
    expect(container.querySelector("pre code")?.textContent).toBe(text)
    expect(container.querySelector("img")).toBeNull()
    fireEvent.click(screen.getByRole("button", { name: "复制代码" }))
    await waitFor(() => expect(screen.getByRole("status").textContent).toBe("已复制"))
    expect(writeText).toHaveBeenCalledWith(text)
  })

  it("supports unlabelled, indented and unfinished streaming code, then updates content", async () => {
    const writeText = vi.fn().mockResolvedValue(undefined)
    vi.stubGlobal("navigator", { clipboard: { writeText } })
    const view = show("```\nfirst")
    expect(screen.getByLabelText("代码块").textContent).toBe("first\n")
    view.rerender(createElement(ChatMarkdown, { content: "```\nsecond\n```\n\n    third", messageId: "message-one" }))
    expect(screen.getAllByRole("button", { name: "复制代码" })).toHaveLength(2)
    fireEvent.click(screen.getAllByRole("button", { name: "复制代码" })[1])
    await waitFor(() => expect(writeText).toHaveBeenCalledWith("third\n"))
  })

  it.each(["javascript:alert%281%29", "data:text/html;base64,PHNjcmlwdD4=", "file:///C:/private", "//example.test/pixel", "https://user:pass@example.test/", "https://example.test/\\private", "javascript&#x3a;alert%281%29"])("blocks unsafe navigation %s", (url) => {
    const { container } = show(`[unsafe](${url})`)
    expect(container.querySelector("a[href]")).toBeNull()
    expect(container.textContent).toContain("unsafe")
  })

  it("renders safe external links with opener/referrer isolation and unique footnotes", () => {
    const { container } = show("[文档](https://example.test/docs) 与备注[^note]\n\n[^note]: 说明", "one")
    const link = screen.getByRole("link", { name: "文档" })
    expect(link.getAttribute("rel")).toBe("noopener noreferrer")
    expect(link.getAttribute("target")).toBe("_blank")
    const ids = [...container.querySelectorAll("[id]")].map((element) => element.id)
    const other = show("备注[^note]\n\n[^note]: 说明", "two")
    const otherIds = [...other.container.querySelectorAll("[id]")].map((element) => element.id)
    expect(ids.filter((id) => otherIds.includes(id))).toEqual([])
    for (const anchor of container.querySelectorAll('a[href^="#"]')) {
      expect(container.querySelector(anchor.getAttribute("href")!)).toBeTruthy()
      const description = anchor.getAttribute("aria-describedby")
      if (description) expect(container.querySelector(`#${description}`)).toBeTruthy()
    }
  })

  it("keeps raw HTML inert and does not eagerly load Markdown images", () => {
    const { container } = show('<script>window.bad=true</script>\n\n<img src="https://example.test/track" onerror="alert(1)">\n\n![架构图](https://example.test/diagram.png)')
    expect(container.querySelector("script, iframe, img")).toBeNull()
    expect(container.textContent).toContain("<script>")
    fireEvent.click(screen.getByRole("button", { name: /加载图片：架构图/ }))
    const image = screen.getByRole("img", { name: "架构图" })
    expect(image.getAttribute("referrerpolicy")).toBe("no-referrer")
    fireEvent.error(image)
    expect(screen.getByRole("status").textContent).toContain("图片加载失败")
  })

  it("blocks unsafe images and resets image loading state for updated messages", () => {
    const view = show("![坏图](data:image/svg+xml,test)")
    expect(screen.queryByRole("img")).toBeNull()
    expect(screen.queryByRole("button")).toBeNull()
    view.rerender(createElement(ChatMarkdown, { content: "![图](https://example.test/one.png)", messageId: "message-one" }))
    fireEvent.click(screen.getByRole("button", { name: /加载图片/ }))
    fireEvent.load(screen.getByRole("img"))
    view.rerender(createElement(ChatMarkdown, { content: "![图](https://example.test/two.png)", messageId: "message-one" }))
    expect(screen.queryByRole("img")).toBeNull()
    expect(screen.getByRole("button", { name: /加载图片/ })).toBeTruthy()
  })

  it("retains all oversized content in a labelled plain-text fallback", () => {
    const text = "# " + "全文".repeat(50_001)
    const { container } = show(text)
    expect(screen.getByText("消息较长，以下按原文显示。")).toBeTruthy()
    expect(container.querySelector("pre")?.textContent).toBe(text)
    expect(container.querySelector("h1")).toBeNull()
  })

  it("can render on the server without reading browser APIs", () => {
    const html = renderToString(createElement(ChatMarkdown, { content: "## 标题\n\n```js\nconst n = 1\n```", messageId: "server" }))
    expect(html).toContain("标题")
    expect(html).toContain("复制代码")
  })
})

describe("CopyTextButton", () => {
  it.each(["missing", "denied"])("reports clipboard %s without an unhandled rejection", async (kind) => {
    vi.stubGlobal("navigator", kind === "missing" ? {} : { clipboard: { writeText: vi.fn().mockRejectedValue(new Error("denied")) } })
    render(createElement(CopyTextButton, { text: "source", label: "复制代码" }))
    fireEvent.click(screen.getByRole("button", { name: "复制代码" }))
    await waitFor(() => expect(screen.getByRole("status").textContent).toContain("复制失败"))
  })

  it("does not show an old successful copy as success for changed content", async () => {
    let finish: () => void = () => {}
    vi.stubGlobal("navigator", { clipboard: { writeText: vi.fn(() => new Promise<void>((resolve) => { finish = resolve })) } })
    const view = render(createElement(CopyTextButton, { text: "old", label: "复制代码" }))
    fireEvent.click(screen.getByRole("button", { name: "复制代码" }))
    view.rerender(createElement(CopyTextButton, { text: "new", label: "复制代码" }))
    finish()
    await waitFor(() => expect(screen.getByRole("status").textContent).toBe(""))
  })
})
