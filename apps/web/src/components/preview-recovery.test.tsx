import { cleanup, renderHook } from "@testing-library/react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { useTaskArtifactActions } from "./use-task-artifact-actions"
import { samplePreviewArtifact } from "./__fixtures__/sample-preview"
import { sampleReviewArtifact } from "./__fixtures__/sample-review"
import { artifactSelectionAfterRefresh } from "./workspace-shell-state"
import type { ArtifactPanelItem } from "./preview-card"

const api = vi.hoisted(() => ({ list: vi.fn(), start: vi.fn() }))
vi.mock("@/lib/api", async original => ({ ...await original<typeof import("@/lib/api")>(), listTaskRunPreviews: api.list, startTaskRunPreview: api.start }))
beforeEach(() => vi.resetAllMocks())
afterEach(cleanup)

function actions() {
  const options = { backendUrl: "http://local", selectedPreview: samplePreviewArtifact, refreshArtifacts: vi.fn(), refreshSelectedTasks: vi.fn(), runClientAction: (action: () => Promise<void>) => { pending = action() }, setSelectedArtifactId: vi.fn(), setPreviewFrameKey: vi.fn(), setSyncError: vi.fn() }
  let pending: Promise<void>
  const { result } = renderHook(() => useTaskArtifactActions(options))
  return { options, refresh: async () => { result.current.handleRefreshPreviews(samplePreviewArtifact.taskRunId); await pending } }
}

describe("explicit Preview recovery", () => {
  it("keeps the new Preview selected through partial evidence refresh without overriding a later user choice", () => {
    const review: ArtifactPanelItem = { id: "review:report", kind: "review", artifact: sampleReviewArtifact, taskRunId: samplePreviewArtifact.taskRunId, taskTitle: "Review" }
    const preview: ArtifactPanelItem = { id: "preview:new", kind: "preview", artifact: { ...samplePreviewArtifact, id: "new" }, taskRunId: samplePreviewArtifact.taskRunId, taskTitle: "Coding" }
    let selection: string | null = "preview:new"
    for (const batch of [[], [review], [preview, review]]) {
      selection = artifactSelectionAfterRefresh(selection, batch)
      expect(selection).toBe("preview:new")
    }
    selection = "review:report"
    expect(artifactSelectionAfterRefresh(selection, [preview, review])).toBe("review:report")
    expect(artifactSelectionAfterRefresh(null, [preview])).toBe("preview:new")
  })
  it("restarts once when backend health changed despite a cached healthy selection", async () => {
    api.list.mockResolvedValue([{ ...samplePreviewArtifact, healthStatus: "unhealthy", status: "failed" }])
    api.start.mockResolvedValue({ ...samplePreviewArtifact, id: "new", artifactId: "new-artifact" })
    const { options, refresh } = actions()
    await refresh()
    expect(api.start).toHaveBeenCalledTimes(1)
    expect(api.start).toHaveBeenCalledWith("http://local", samplePreviewArtifact.taskRunId)
    expect(options.setSelectedArtifactId).toHaveBeenCalledWith("preview:new")
  })

  it("reuses a healthy backend Preview without launching another process", async () => {
    api.list.mockResolvedValue([{ ...samplePreviewArtifact, id: "healthy-new" }])
    const { options, refresh } = actions()
    await refresh()
    expect(api.start).not.toHaveBeenCalled()
    expect(options.setSelectedArtifactId).toHaveBeenCalledWith("preview:healthy-new")
  })
})
