import { cleanup, render, screen } from "@testing-library/react"
import { afterEach, describe, expect, it } from "vitest"
import { DagSummary, overlappingRuns } from "./dag-summary"
import type { SessionTask, TaskRun } from "@/lib/api"

afterEach(cleanup)

function task(id: string, dependencies: string[] = []): SessionTask {
  return { id, sessionId: "session", title: id, createdByMessageId: null,
    intentType: "frontend_change", status: "pending", priority: 0,
    planJson: {}, dependsOnTaskIds: dependencies, assignedAgentId: null,
    assignedAgentRole: null, taskRuns: [], createdAt: "", updatedAt: "" }
}

function run(taskId: string, start: string | null, end: string | null): TaskRun {
  return { id: `run-${taskId}`, taskId, sessionId: "session", agentId: "agent",
    adapterType: "scripted_mock", adapterRunId: null, state: "completed",
    startedAt: start, endedAt: end, worktreePath: "", baseRef: null, headRef: null,
    errorCode: null, errorMessage: null, metricsJson: {}, createdAt: "", updatedAt: "" }
}

describe("DAG summary", () => {
  it("keeps ordinary dependency chains serial", () => {
    render(<DagSummary tasks={[task("a"), task("b", ["a"])]} />)
    expect(screen.getByText("任务依赖图 · 串行依赖链")).toBeTruthy()
    expect(screen.getByText(/尚无完整时间区间/)).toBeTruthy()
  })

  it("renders fork, join and group as hints without inventing execution", () => {
    const backend = task("backend", ["plan"])
    backend.planJson = { parallelGroup: "implementation", executionMode: "isolated_write" }
    render(<DagSummary tasks={[task("plan"), backend, task("frontend", ["plan"]), task("qa", ["backend", "frontend"])]} />)
    expect(screen.getByText(/Fork 分叉 → backend \/ frontend/)).toBeTruthy()
    expect(screen.getByText("Join 汇合：backend + frontend → 本任务")).toBeTruthy()
    expect(screen.getByText("并行组（提示）：implementation")).toBeTruthy()
    expect(screen.getByText("请求隔离写 · 尚未分配")).toBeTruthy()
    expect(screen.queryByText(/已记录 TaskRun 生命周期重叠/)).toBeNull()
  })

  it("shows queue, isolation fallback, and provider failure reasons", () => {
    const node = task("backend")
    node.planJson = { scheduler: { runnable: false, reason: "Waiting for target lock" } }
    const attempt = run(node.id, null, null)
    attempt.state = "queued"
    attempt.sessionQueue = { waitReason: "Earlier shared writer" }
    attempt.metricsJson = { executionIsolationFallback: { reason: "dirty baseline" } }
    attempt.errorCode = "PROVIDER_CAPACITY_EXHAUSTED"
    attempt.errorMessage = "Capacity exhausted"
    node.taskRuns = [attempt]
    render(<DagSummary tasks={[node]} />)
    expect(screen.getByText("安全门禁：Waiting for target lock")).toBeTruthy()
    expect(screen.getByText("队列：Earlier shared writer")).toBeTruthy()
    expect(screen.getByText("隔离回退原因：dirty baseline")).toBeTruthy()
    expect(screen.getByText(/PROVIDER_CAPACITY_EXHAUSTED/)).toBeTruthy()
  })

  it("separates verified integration, historical records, prepared and conflicts", () => {
    const join = task("join", ["a", "b"])
    join.integrationArtifacts = [
      { artifactId: "verified", artifactType: "integration", status: "ready", verified: true, createdAt: "", mergeCommit: "abc123", sourceRunIds: ["run-a", "run-b"] },
      { artifactId: "historical", artifactType: "integration", status: "ready", verified: false, createdAt: "" },
      { artifactId: "prepared", artifactType: "integration", status: "prepared", verified: false, createdAt: "" },
      { artifactId: "conflict", artifactType: "conflict", status: "blocked", verified: false, createdAt: "", reason: "Patch conflict", conflictingFiles: ["apps/demo/src/App.tsx"] },
    ]
    render(<DagSummary tasks={[join]} />)
    expect(screen.getByText(/已验证集成 · verified/)).toBeTruthy()
    expect(screen.getByText(/历史或未验证集成/)).toBeTruthy()
    expect(screen.getByText(/集成已准备/)).toBeTruthy()
    expect(screen.getByText(/合并冲突记录/)).toBeTruthy()
    expect(screen.getByText("来源 Run：run-a, run-b")).toBeTruthy()
    expect(screen.getByText("合并 commit：abc123")).toBeTruthy()
  })

  it("uses strict complete UTC intervals and ignores queued, invalid and touching intervals", () => {
    const a = task("a"), b = task("b")
    a.taskRuns = [run("a", "2026-09-04T00:00:00", "2026-09-04T00:00:02")]
    b.taskRuns = [run("b", "2026-09-04T00:00:01Z", "2026-09-04T00:00:03Z")]
    expect(overlappingRuns([a, b])).toHaveLength(1)
    b.taskRuns[0].startedAt = "2026-09-04T00:00:02Z"
    expect(overlappingRuns([a, b])).toHaveLength(0)
    b.taskRuns[0].startedAt = "invalid"
    expect(overlappingRuns([a, b])).toHaveLength(0)
    b.taskRuns[0].startedAt = null
    expect(overlappingRuns([a, b])).toHaveLength(0)
  })

  it("does not trust plan integration flags or merged run flags", () => {
    const node = task("a")
    node.planJson = { integration: { status: "ready", mergeCommit: "fake" } }
    const attempt = run("a", null, null)
    attempt.metricsJson = { executionWorktree: { mode: "isolated_write", branch: "branch", integrationStatus: "merged" } }
    node.taskRuns = [attempt]
    render(<DagSummary tasks={[node]} />)
    expect(screen.queryByText(/已验证集成/)).toBeNull()
  })
})
