import { cleanup, fireEvent, render, screen } from "@testing-library/react"
import { afterEach, describe, expect, it, vi } from "vitest"
import type { SessionTask, TaskRun } from "@/lib/api"
import { dependencyLayout, sessionStages } from "./session-workbench-state"
import { visualEvent, SessionEventTimeline } from "./session-event-timeline"
import { SessionResults } from "./session-overview"
import { TaskDependencyGraph } from "./task-dependency-graph"
import { sampleDiffArtifact } from "./__fixtures__/sample-diff"
import { samplePreviewArtifact } from "./__fixtures__/sample-preview"
import type { ArtifactPanelItem } from "./preview-card"

afterEach(cleanup)
const run = (id: string, state: string): TaskRun => ({ id, state, taskId: "a", sessionId: "s", agentId: "agent", adapterType: "codex", adapterRunId: null, startedAt: null, endedAt: null, worktreePath: "/assigned", baseRef: null, headRef: null, errorCode: null, errorMessage: null, metricsJson: {}, createdAt: "2026-10-07T00:00:00Z", updatedAt: "2026-10-07T00:00:00Z" })
const task = (id: string, dependencies: string[] = [], runs: TaskRun[] = []): SessionTask => ({ id, sessionId: "s", createdByMessageId: "m", title: `任务 ${id}`, intentType: "frontend_change", status: "pending", priority: 1, planJson: {}, dependsOnTaskIds: dependencies, assignedAgentId: "agent", assignedAgentRole: "frontend", taskRuns: runs, createdAt: "2026-10-07T00:00:00Z", updatedAt: "2026-10-07T00:00:00Z" })
const diff: ArtifactPanelItem = { id: "diff:1", kind: "diff", artifact: sampleDiffArtifact, taskRunId: "run-1", taskTitle: "登录页" }
const preview: ArtifactPanelItem = { id: "preview:1", kind: "preview", artifact: samplePreviewArtifact, taskRunId: "run-1", taskTitle: "登录页" }
const stage = (tasks: SessionTask[], artifacts: ArtifactPanelItem[], label: string) => sessionStages(tasks, artifacts, true).find((item) => item.label === label)!

describe("evidence-backed workbench", () => {
  it("does not infer diff or preview from a completed run", () => {
    const tasks = [task("a", [], [run("run-1", "completed")])]
    expect(stage(tasks, [], "执行").state).toBe("ready")
    expect(stage(tasks, [], "Diff").state).toBe("pending")
    expect(stage(tasks, [], "预览").state).toBe("pending")
  })
  it("keeps a failed retry visible without using previous successful evidence", () => {
    const tasks = [task("a", [], [run("run-1", "completed"), run("run-2", "failed")])]
    expect(stage(tasks, [diff, preview], "执行").state).toBe("failed")
    expect(stage(tasks, [diff, preview], "Diff").state).toBe("pending")
    expect(stage(tasks, [diff, preview], "预览").state).toBe("pending")
  })
  it("requires an actual nonempty diff", () => {
    const tasks = [task("a", [], [run("run-1", "completed")])]
    expect(stage(tasks, [diff], "Diff").state).toBe("ready")
    expect(stage(tasks, [{ ...diff, artifact: { ...sampleDiffArtifact, patchText: "" } }], "Diff").state).toBe("pending")
  })
  it.each(["stopped", "failed"])("does not mark %s preview ready", (status) => {
    const item: ArtifactPanelItem = { ...preview, artifact: { ...samplePreviewArtifact, status } }
    expect(stage([task("a", [], [run("run-1", "completed")])], [item], "预览").state).toBe("pending")
  })
  it("requires preview health in addition to readiness", () => {
    const tasks = [task("a", [], [run("run-1", "completed")])]
    expect(stage(tasks, [preview], "预览").state).toBe("ready")
    expect(stage(tasks, [{ ...preview, artifact: { ...samplePreviewArtifact, healthStatus: "unhealthy" } }], "预览").state).toBe("pending")
  })
  it("lays out unordered fork and join dependencies with actual edges", () => {
    const tasks = [task("join", ["b", "c"]), task("c", ["a"]), task("a"), task("b", ["a"])]
    const nodes = new Map(dependencyLayout(tasks).nodes.map((node) => [node.task.id, node]))
    expect(nodes.get("join")!.x).toBeGreaterThan(nodes.get("b")!.x)
    expect(nodes.get("b")!.x).toBe(nodes.get("c")!.x)
    expect(nodes.get("b")!.y).not.toBe(nodes.get("c")!.y)
    const { container } = render(<TaskDependencyGraph tasks={tasks} />)
    expect(container.querySelectorAll("[data-dependency]")).toHaveLength(4)
    expect(screen.getByRole("img", { name: "任务依赖关系图" })).toBeTruthy()
  })
  it("terminates on cycles and warns about incomplete dependency records", () => {
    expect(dependencyLayout([task("a", ["b"]), task("b", ["a"])]).cyclic).toBe(true)
    expect(dependencyLayout([task("a", ["missing"])]).missing).toBe(true)
  })
  it("whitelists event fields rather than exposing provider payloads", () => {
    const parsed = visualEvent({ id: "event", taskRunId: "run-1", eventType: "task.state", createdAt: "2026-10-07T00:00:00Z", payload: { state: "failed", secret: "provider private payload", chainOfThought: "hidden" } }, "s")!
    expect(parsed.state).toBe("failed")
    expect(JSON.stringify(parsed)).not.toContain("private")
    render(<SessionEventTimeline events={[parsed]} tasks={[task("a", [], [run("run-1", "failed")])]} />)
    expect(screen.getByText("运行状态更新 · 失败")).toBeTruthy()
    expect(screen.queryByText("hidden")).toBeNull()
    expect(visualEvent({ id: "bad" }, "s")).toBeNull()
  })
  it("preserves exact event timestamps for inspection and rejects calendar rollovers", () => {
    const event = { id: "time", taskRunId: "run-1", eventType: "task.state", createdAt: "2026-10-08T05:25:18.739767", payload: {} }
    const parsed = visualEvent(event, "s")!
    expect(parsed.createdAt).toBe(event.createdAt)
    expect(visualEvent({ ...event, createdAt: "2026-02-30T00:00:00Z" }, "s")).toBeNull()
    const { container } = render(<SessionEventTimeline events={[parsed]} tasks={[]} />)
    expect(container.querySelector("time")?.dateTime).toBe("2026-10-08T05:25:18.739Z")
    expect(container.querySelector("time")?.title).toContain(event.createdAt)
  })

  it("marks historical artifacts and opens the selected concrete artifact", () => {
    const onSelect = vi.fn()
    render(<SessionResults artifacts={[diff]} tasks={[task("a", [], [run("run-2", "failed")])]} onSelect={onSelect} />)
    fireEvent.click(screen.getByRole("button", { name: /代码变更/ }))
    expect(onSelect).toHaveBeenCalledWith("diff:1")
    expect(screen.getByText(/历史成果/)).toBeTruthy()
  })
})
