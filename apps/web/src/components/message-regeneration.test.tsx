import { act, cleanup, fireEvent, render, screen } from "@testing-library/react"
import { afterEach, expect, it, vi } from "vitest"
import type { ChatMessage } from "@/lib/api"
import { MessageRegeneration, RegenerationLineage } from "./message-regeneration"

afterEach(cleanup)
const message: ChatMessage = { id: "reply", sessionId: "s", senderType: "orchestrator", senderId: "a", contentMd: "Reply", messageKind: "chat", parentMessageId: "request", streamState: "complete", createdAt: "2026-10-09T00:00:00Z", regenerationAction: { kind: "request", available: true, reason: null } }

it("requires explicit confirmation, explains current execution and allows cancellation", async () => {
  const run = vi.fn().mockResolvedValue(undefined)
  render(<MessageRegeneration message={message} onRun={run} />)
  fireEvent.click(screen.getByRole("button", { name: "重新生成" }))
  expect(screen.getByText(/可能创建并执行新的代码任务/)).toBeTruthy()
  expect(run).not.toHaveBeenCalled()
  fireEvent.click(screen.getByRole("button", { name: "取消" }))
  expect(screen.queryByRole("group")).toBeNull()
  fireEvent.click(screen.getByRole("button", { name: "重新生成" }))
  await act(async () => { fireEvent.click(screen.getByRole("button", { name: "确认重新生成" })) })
  expect(run).toHaveBeenCalledExactlyOnceWith(message)
})

it("keeps an uncertain request visible and prevents double clicks", async () => {
  let reject!: (error: Error) => void
  const run = vi.fn(() => new Promise<void>((_, fail) => { reject = fail }))
  render(<MessageRegeneration message={message} onRun={run} />)
  fireEvent.click(screen.getByRole("button", { name: "重新生成" }))
  fireEvent.click(screen.getByRole("button", { name: "确认重新生成" }))
  fireEvent.click(screen.getByRole("button", { name: "正在处理…" }))
  expect(run).toHaveBeenCalledTimes(1)
  await act(async () => reject(new Error("网络结果尚未确认")))
  expect(screen.getByRole("alert").textContent).toContain("网络结果尚未确认")
})

it("uses a distinct summary confirmation and honours backend eligibility", () => {
  const { rerender } = render(<MessageRegeneration message={{ ...message, regenerationAction: { kind: "summary", available: true, reason: null } }} onRun={vi.fn()} />)
  fireEvent.click(screen.getByRole("button", { name: "重新汇总" }))
  expect(screen.getByText(/任务不会重新执行/)).toBeTruthy()
  rerender(<MessageRegeneration message={{ ...message, regenerationAction: { kind: "summary", available: false, reason: "仅最新结果" } }} onRun={vi.fn()} />)
  expect(screen.getByRole("button", { name: "重新汇总" }).hasAttribute("disabled")).toBe(true)
})

it("shows a persisted source and honest interrupted status", () => {
  render(<RegenerationLineage message={{ ...message, regeneration: { sourceMessageId: "old", requestMessageId: "request", operationId: "op", state: "failed", kind: "request", errorCode: "REGENERATION_PREPARATION_INTERRUPTED" } }} />)
  expect(screen.getByRole("link", { name: "查看原消息" }).getAttribute("href")).toBe("#message-old")
  expect(screen.getByText(/未自动重发/)).toBeTruthy()
})
