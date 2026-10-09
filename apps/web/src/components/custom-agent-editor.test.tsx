import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react"
import { afterEach, expect, it, vi } from "vitest"
import { CustomAgentEditor } from "./custom-agent-editor"
import type { AgentDirectoryEntry, TargetProject } from "@/lib/api"

const mocks = vi.hoisted(() => ({ save: vi.fn() }))
vi.mock("@/lib/api", async (original) => ({ ...await original<typeof import("@/lib/api")>(), saveCustomAgent: mocks.save }))
afterEach(() => { cleanup(); vi.clearAllMocks() })
const target = { targetId: "demo-frontend", name: "演示前端", requiresPlatformMode: false, allowedAgents: ["frontend", "qa", "review"] } as TargetProject

it("saves an actual custom profile and preserves edits until save succeeds", async () => {
  const saved = vi.fn().mockResolvedValue(undefined)
  mocks.save.mockResolvedValue({ id: "custom" })
  render(<CustomAgentEditor backendUrl="http://api" workspaceId="workspace" targets={[target]} editing={null} onSaved={saved} onCancel={vi.fn()} />)
  fireEvent.change(screen.getByLabelText("自定义名称"), { target: { value: "界面工程师" } })
  fireEvent.change(screen.getByLabelText("@ 别名"), { target: { value: "UI-Designer" } })
  fireEvent.change(screen.getByLabelText("自定义 System Prompt", { exact: false }), { target: { value: "请使用中文" } })
  fireEvent.click(screen.getByText("保存自定义 Agent"))
  await waitFor(() => expect(saved).toHaveBeenCalledOnce())
  expect(mocks.save).toHaveBeenCalledWith("http://api", "workspace", expect.objectContaining({ displayName: "界面工程师", mentionAlias: "ui-designer", toolPolicy: "codex_coding", systemPrompt: "请使用中文", supportedTargets: ["demo-frontend"] }), undefined)
})

it("loads the existing prompt, disables with the same identity, and restricts review tools", async () => {
  mocks.save.mockResolvedValue({ id: "same-id" })
  const editing = { id: "same-id", displayName: "审查助手", role: "review", mentionAlias: "read-review", providerId: "local-claude-code-cli", toolPolicy: "claude_read_only", supportedTargets: ["demo-frontend"], capabilityTags: ["code_review"], systemPrompt: "Read only", status: "available" } as AgentDirectoryEntry
  render(<CustomAgentEditor backendUrl="http://api" workspaceId="workspace" targets={[target]} editing={editing} onSaved={vi.fn()} onCancel={vi.fn()} />)
  expect((screen.getByLabelText("自定义 System Prompt", { exact: false }) as HTMLTextAreaElement).value).toBe("Read only")
  expect(screen.queryByText("Codex · 原生编码工具")).toBeNull()
  fireEvent.click(screen.getByLabelText("启用自定义 Agent"))
  fireEvent.click(screen.getByText("保存自定义 Agent"))
  await waitFor(() => expect(mocks.save).toHaveBeenCalledWith("http://api", "workspace", expect.objectContaining({ enabled: false, toolPolicy: "claude_read_only" }), "same-id"))
})

it("cancels without mutation and shows server rejection without reporting success", async () => {
  mocks.save.mockRejectedValue(new Error("Duplicate alias"))
  const cancel = vi.fn(), saved = vi.fn()
  render(<CustomAgentEditor backendUrl="http://api" workspaceId="workspace" targets={[target]} editing={null} onSaved={saved} onCancel={cancel} />)
  fireEvent.click(screen.getByText("取消自定义编辑"))
  expect(cancel).toHaveBeenCalledOnce(); expect(mocks.save).not.toHaveBeenCalled()
  fireEvent.change(screen.getByLabelText("自定义名称"), { target: { value: "My agent" } })
  fireEvent.change(screen.getByLabelText("@ 别名"), { target: { value: "my-agent" } })
  fireEvent.click(screen.getByText("保存自定义 Agent"))
  expect(await screen.findByRole("alert")).toHaveProperty("textContent", "Duplicate alias")
  expect(saved).not.toHaveBeenCalled()
  expect((screen.getByLabelText("自定义名称") as HTMLInputElement).value).toBe("My agent")
})
