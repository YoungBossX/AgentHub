import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react"
import { afterEach, describe, expect, it, vi } from "vitest"
import { ReviewRepair, ReviewRepairContext } from "./review-repair"
import type { RepairState } from "@/lib/review-repair-api"

afterEach(() => { cleanup(); vi.unstubAllGlobals() })
const issue = { id: "finding:one", message: "人工核对接口说明", file: "apps/demo-api/app/main.py", line: 2, autoVerifiable: false }
const state: RepairState = { issues: [issue], history: [], canPrepare: true, reason: null, sourceFingerprint: "a".repeat(64) }
const context = { backendUrl: "http://127.0.0.1:8000", sessionId: "session-1", revision: 0, onDraft: vi.fn(), onOpenArtifact: vi.fn() }

describe("review repair controls", () => {
  it("prepares a selected draft without sending, modifying files or confirming", async () => {
    const draft = { contentMd: "@backend @qa 修复接口", selection: { reviewArtifactId: "review-1", issueIds: [issue.id], expectedFingerprint: "b".repeat(64) } }
    const fetcher = vi.fn().mockResolvedValueOnce(Response.json(state)).mockResolvedValueOnce(Response.json(draft))
    vi.stubGlobal("fetch", fetcher)
    const onDraft = vi.fn()
    render(<ReviewRepairContext.Provider value={{ ...context, onDraft }}><ReviewRepair artifactId="review-1" /></ReviewRepairContext.Provider>)
    const box = await screen.findByRole("checkbox")
    expect(onDraft).not.toHaveBeenCalled()
    fireEvent.click(box); fireEvent.click(screen.getByRole("button", { name: /准备修复草稿/ }))
    await waitFor(() => expect(onDraft).toHaveBeenCalledWith("session-1", draft))
    expect(fetcher).toHaveBeenCalledTimes(2)
    const [url, init] = fetcher.mock.calls[1]
    expect(url).toContain("/reviews/review-1/repair/prepare")
    expect(init.headers["x-agenthub-control"]).toBe("local-workspace")
    expect(JSON.parse(init.body)).toEqual({ issueIds: [issue.id] })
  })

  it("shows stale source and prevents preparing a detached repair", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(Response.json({ ...state, canPrepare: false, reason: "评审源码已变化" })))
    render(<ReviewRepairContext.Provider value={context}><ReviewRepair artifactId="review-1" /></ReviewRepairContext.Provider>)
    expect(await screen.findByText("评审源码已变化")).toBeTruthy()
    expect((screen.getByRole("checkbox") as HTMLInputElement).disabled).toBe(true)
    expect((screen.getByRole("button", { name: /准备修复草稿/ }) as HTMLButtonElement).disabled).toBe(true)
  })

  it("keeps model suggestions unverified, records explicit versioned user confirmation and opens new artifacts", async () => {
    const entry = { messageId: "message-1", taskIds: ["task-1"], runs: [{ id: "run-1", state: "completed", errorCode: null }], artifactIds: ["new-diff"],
      issues: [{ ...issue, outcome: "unverified" }], confirmations: [], revision: "c".repeat(64), sourceFingerprint: "d".repeat(64),
      state: "completed", checksCurrent: true, sourceChanged: true, canConfirm: true }
    const next = { ...state, history: [{ ...entry, issues: [{ ...issue, outcome: "user_confirmed" }], confirmations: [{ issueId: issue.id, sourceFingerprint: entry.sourceFingerprint, confirmedAt: "2026-10-15T00:00:00" }] }] }
    const fetcher = vi.fn().mockResolvedValueOnce(Response.json({ ...state, history: [entry] })).mockResolvedValueOnce(Response.json(next))
    vi.stubGlobal("fetch", fetcher)
    const onOpenArtifact = vi.fn()
    render(<ReviewRepairContext.Provider value={{ ...context, onOpenArtifact }}><ReviewRepair artifactId="review-1" /></ReviewRepairContext.Provider>)
    expect(await screen.findByText(/仍待核验/)).toBeTruthy()
    fireEvent.click(screen.getByRole("button", { name: /我已核验此问题/ }))
    expect(await screen.findByText(/用户已确认当前版本/)).toBeTruthy()
    expect(JSON.parse(fetcher.mock.calls[1][1].body)).toEqual({ messageId: entry.messageId, issueId: issue.id, sourceFingerprint: entry.sourceFingerprint, revision: entry.revision })
    fireEvent.click(screen.getByRole("button", { name: /查看产物/ }))
    expect(onOpenArtifact).toHaveBeenCalledWith("new-diff")
    expect(screen.queryByText(/匹配检查已恢复通过/)).toBeNull()
  })
})
