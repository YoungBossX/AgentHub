import { cleanup, fireEvent, render, screen } from "@testing-library/react"
import { afterEach, describe, expect, it, vi } from "vitest"
import type { GroupSummary } from "@/lib/api"
import { GroupSummaryCard } from "./group-summary-card"

afterEach(cleanup)
const receipt: GroupSummary = {
  groupId: "group-1", state: "completed", current: true, source: "native_model", coordinatorName: "My Manager",
  interpretation: { summary: "Actual model interpretation", nextSteps: ["Inspect the diff"] },
  evidence: { outcome: "completed", inputFingerprint: "fingerprint", tasks: [{
    taskId: "task-1", title: "Review", displayName: "Reviewer", runId: "run-1", state: "completed",
    attemptCount: 2, adapterType: "claude_code", missingEvidence: [], errorCode: null,
    artifacts: [{ artifactId: "diff-1", type: "diff", version: 1, contentHash: "hash", readOnlySnapshot: true }],
    reviews: [{ artifactId: "review-1", status: "passed", source: "native_model", summary: "Static judgment" }],
  }] },
}

describe("group summary receipts", () => {
  it("shows interpretation, actual lineage, read-only and test boundaries", () => {
    render(<GroupSummaryCard summary={receipt} />)
    expect(screen.getByText("原生协调模型")).toBeTruthy()
    expect(screen.getByText("Actual model interpretation")).toBeTruthy()
    expect(screen.getByText("Inspect the diff")).toBeTruthy()
    expect(screen.getByText(/2 次运行 · claude_code/)).toBeTruthy()
    expect(screen.getByText(/只读 Diff 快照（非评审修改）/)).toBeTruthy()
    expect(screen.getByText(/本次汇总未运行测试/)).toBeTruthy()
  })
  it("discloses deterministic source and scripted review", () => {
    render(<GroupSummaryCard summary={{ ...receipt, source: "deterministic", interpretation: null, evidence: { ...receipt.evidence!, tasks: [{ ...receipt.evidence!.tasks[0], reviews: [{ artifactId: "review-1", status: "warning", source: "scripted_advisory", summary: "Advisory" }] }] } }} />)
    expect(screen.getByText("确定性执行记录")).toBeTruthy()
    expect(screen.getByText(/未配置原生协调模型/)).toBeTruthy()
    expect(screen.getByText(/脚本参考评审/)).toBeTruthy()
  })
  it("retries only current failures and labels history", () => {
    const retry = vi.fn()
    const { rerender } = render(<GroupSummaryCard summary={{ ...receipt, state: "failed", interpretation: null, errorCode: "GROUP_SUMMARY_OUTPUT_INVALID" }} onRetry={retry} />)
    fireEvent.click(screen.getByRole("button", { name: "重试汇总" }))
    expect(retry).toHaveBeenCalledWith("group-1")
    rerender(<GroupSummaryCard summary={{ ...receipt, state: "failed", current: false, interpretation: null }} onRetry={retry} />)
    expect(screen.queryByRole("button", { name: "重试汇总" })).toBeNull()
    expect(screen.getByText(/历史汇总/)).toBeTruthy()
  })
  it("shows pending, partial failure, blockers and obsolete states", () => {
    const { rerender } = render(<GroupSummaryCard summary={{ ...receipt, state: "calling", interpretation: null }} />)
    expect(screen.getByRole("status").textContent).toContain("正在")
    rerender(<GroupSummaryCard summary={{ ...receipt, state: "superseded", current: false, interpretation: null, evidence: { ...receipt.evidence!, outcome: "partial_failure", tasks: [{ ...receipt.evidence!.tasks[0], state: "failed", missingEvidence: ["review"], errorCode: "CONTROLLED" }] } }} />)
    expect(screen.getByText("任务组部分失败")).toBeTruthy()
    expect(screen.getByText(/输入已过期/)).toBeTruthy()
    expect(screen.getByText(/缺少完成证据：review/)).toBeTruthy()
  })
})
