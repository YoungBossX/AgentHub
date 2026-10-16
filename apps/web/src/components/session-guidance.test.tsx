import { cleanup, fireEvent, render, screen } from "@testing-library/react"
import { afterEach, expect, it, vi } from "vitest"
import type { ChatMessage, SessionTask, TaskRun } from "@/lib/api"
import { SessionGuidance, sessionGuidance } from "./session-guidance"
import { sampleReviewArtifact } from "./__fixtures__/sample-review"

afterEach(cleanup)
const message = { id: "m", senderType: "user" } as ChatMessage
const task = (state: string, planJson = {}): SessionTask => ({ id: "t", createdByMessageId: "m", title: "修复表单", createdAt: "2026-10-15T00:00:00Z", status: state, planJson, taskRuns: [], dependsOnTaskIds: [] } as unknown as SessionTask)
it.each(["queued", "pending", "waiting_approval", "blocked", "failed", "interrupted", "collecting_diff", "streaming"])("routes %s to existing task controls without executing", state => {
  const onNavigate = vi.fn()
  const current = { ...task(state), taskRuns: [{ id: "r", state, errorMessage: "需要处理的实际原因" } as TaskRun] }
  render(<SessionGuidance tasks={[current]} artifacts={[]} messages={[message]} onNavigate={onNavigate} />)
  expect(onNavigate).not.toHaveBeenCalled()
  fireEvent.click(screen.getByRole("button"))
  expect(onNavigate).toHaveBeenCalledWith("process", "t")
  if (state === "queued") expect(screen.getByText(/排队中/)).toBeTruthy()
  if (state === "waiting_approval") expect(screen.getByText(/等待确认/)).toBeTruthy()
})
it("separates execution completion from acceptance and ignores historical report success", () => {
  const current = { ...task("completed"), taskRuns: [{ id: "new", state: "completed" } as TaskRun] }
  const guide = sessionGuidance([current], [{ kind: "review", id: "review:old", artifact: sampleReviewArtifact, taskRunId: "old", taskTitle: "old" }], [message])
  expect(guide.phase).toContain("待核对结果")
  expect(guide.detail).toContain("不等于功能验收通过")
})
it("shows actual dependency blocking and focuses the current message group", () => {
  const old = { ...task("failed"), id: "old", createdByMessageId: "old-message" }
  const current = task("waiting_dependency", { scheduler: { state: "waiting_dependency", reason: "等待后端接口完成" } })
  const guide = sessionGuidance([old, current], [], [message])
  expect(guide.phase).toBe("等待前置任务")
  expect(guide.detail).toBe("等待后端接口完成")
})
it("explains a rejected planning budget without claiming a plan or execution", () => {
  const guide = sessionGuidance([], [], [message, { id: "reply", senderType: "orchestrator", contextBudget: { status: "rejected" } } as ChatMessage])
  expect(guide.phase).toBe("上下文超限")
  expect(guide.view).toBe("conversation")
})
