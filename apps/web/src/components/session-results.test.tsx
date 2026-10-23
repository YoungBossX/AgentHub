import { cleanup, fireEvent, render, screen, within } from "@testing-library/react"
import { afterEach, expect, it, vi } from "vitest"
import type { SessionTask, TaskRun } from "@/lib/api"
import type { ArtifactPanelItem } from "./preview-card"
import { sampleDiffArtifact } from "./__fixtures__/sample-diff"
import { samplePreviewArtifact } from "./__fixtures__/sample-preview"
import { SessionResults } from "./session-overview"

afterEach(cleanup)
const run = (id: string, state = "completed") => ({ id, state } as TaskRun)
const task = (id: string, runs: TaskRun[]) => ({ id, title: "同名任务", taskRuns: runs } as SessionTask)
const item = (id: string, runId: string): ArtifactPanelItem => ({ id, taskRunId: runId, taskTitle: "同名任务", kind: "diff", artifact: { ...sampleDiffArtifact, artifactId: id, taskRunId: runId } })
it("groups by task/run IDs, keeps failed retry current and older success collapsed", () => {
  const select = vi.fn()
  render(<SessionResults tasks={[task("a", [run("old"), run("new", "failed")]), task("b", [run("b")])]} artifacts={[item("old-diff", "old"), item("b-diff", "b")]} onSelect={select} />)
  const groups = screen.getAllByRole("region", { name: /任务成果/ })
  expect(groups).toHaveLength(2)
  expect(within(groups[0]).getByText(/当前运行尚无成果/)).toBeTruthy()
  expect(within(groups[0]).getByText("失败")).toBeTruthy()
  expect(within(groups[0]).queryByRole("button", { name: /代码变更/ })).toBeNull()
  fireEvent.click(within(groups[0]).getByRole("button", { name: /历史成果/ }))
  fireEvent.click(within(groups[0]).getByRole("button", { name: /代码变更/ }))
  expect(select).toHaveBeenCalledWith("old-diff")
  fireEvent.click(within(groups[1]).getByRole("button", { name: /代码变更/ }))
  expect(select).toHaveBeenLastCalledWith("b-diff")
})
it("keeps unassociated evidence historical and shows actual document versions", () => {
  const doc: ArtifactPanelItem = { id: "doc", taskRunId: "r", taskTitle: "说明", kind: "workbench", artifact: {
    artifactId: "doc", taskRunId: "r", artifactType: "document", title: "交付说明", status: "ready", version: 3, rendererKind: "markdown", editable: true, contentHash: "hash", safeMeta: {}, createdAt: "", updatedAt: "",
    versions: [1, 3].map(version => ({ id: `v${version}`, artifactId: "doc", version, summary: `说明修订 ${version}`, contentMd: "内容", contentHash: "hash", editorSource: "user", createdAt: "", parentVersionId: null, sourceTaskRunId: "r", parentArtifactId: null, gitBaseRef: null, gitHeadRef: null, changedFiles: [] })) } }
  render(<SessionResults tasks={[task("t", [run("r")])]} artifacts={[doc, item("orphan", "unknown")]} onSelect={vi.fn()} />)
  expect(screen.getByText("v3")).toBeTruthy()
  fireEvent.click(screen.getByRole("button", { name: /文档版本/ }))
  expect(screen.getByText(/说明修订 1/)).toBeTruthy()
  expect(screen.getByText(/未关联任务/)).toBeTruthy()
})
it("keeps preview health explicit rather than inferring it from completed tasks", () => {
  const preview: ArtifactPanelItem = { kind: "preview", id: "p", taskRunId: "r", taskTitle: "同名任务", artifact: { ...samplePreviewArtifact, healthStatus: "unhealthy" } }
  render(<SessionResults tasks={[task("t", [run("r")])]} artifacts={[preview]} onSelect={vi.fn()} />)
  expect(screen.getByRole("button", { name: /网页预览/ }).textContent).toContain("异常")
})
it("shows a current run that has not produced any artifacts", () => {
  render(<SessionResults tasks={[task("t", [run("r", "running")])]} artifacts={[]} onSelect={vi.fn()} />)
  expect(screen.getByText(/当前运行尚无成果/)).toBeTruthy()
  expect(screen.getByText("运行中")).toBeTruthy()
})
