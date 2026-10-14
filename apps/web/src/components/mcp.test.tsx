import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { McpSettings } from "./mcp-settings"
import { McpEvidence } from "./mcp-evidence"

const api = vi.hoisted(() => ({ getMcpConnection: vi.fn(), saveMcpConnection: vi.fn(), probeMcpConnection: vi.fn(), getMcpRunEvidence: vi.fn() }))
vi.mock("@/lib/mcp-api", () => api)
const config = { serverId: "agenthub_docs", enabled: false, tools: ["list_documents", "read_document"], defaultAgents: [], revision: 0 }
beforeEach(() => { vi.clearAllMocks(); api.getMcpConnection.mockResolvedValue(config); api.saveMcpConnection.mockResolvedValue({ ...config, enabled: true, revision: 1 }) })
afterEach(cleanup)

describe("MCP integration", () => {
  it("saves an explicit connection and Agent scope, without arbitrary server inputs", async () => {
    render(<McpSettings backendUrl="local" workspaceId="w" agents={[]} />)
    await screen.findByLabelText("启用项目文档 MCP")
    fireEvent.click(screen.getByLabelText("启用项目文档 MCP"))
    fireEvent.click(screen.getByLabelText("前端默认 Agent"))
    fireEvent.click(screen.getByRole("button", { name: "保存工具连接" }))
    await waitFor(() => expect(api.saveMcpConnection).toHaveBeenCalledWith("local", "w", expect.objectContaining({ enabled: true, defaultAgents: ["frontend"], revision: 0 })))
    expect(screen.queryByLabelText("Server URL")).toBeNull()
  })
  it("distinguishes a successful handshake from actual tool usage", async () => {
    api.probeMcpConnection.mockResolvedValue({ status: "ready", tools: config.tools })
    render(<McpSettings backendUrl="local" workspaceId="w" agents={[]} />)
    fireEvent.click(await screen.findByRole("button", { name: "测试连接" }))
    await screen.findByText(/MCP 握手成功/)
    expect(screen.getByText(/实际使用记录见任务执行过程/)).toBeTruthy()
  })
  it("shows connection failure without claiming a successful probe", async () => {
    api.probeMcpConnection.mockResolvedValue({ status: "unavailable", reason: "Gateway unavailable" })
    render(<McpSettings backendUrl="local" workspaceId="w" agents={[]} />)
    fireEvent.click(await screen.findByRole("button", { name: "测试连接" }))
    await screen.findByText("Gateway unavailable")
    expect(screen.queryByText(/MCP 握手成功/)).toBeNull()
  })
  it("retains drafts on configuration conflicts", async () => {
    api.saveMcpConnection.mockRejectedValue(new Error("Connection changed"))
    render(<McpSettings backendUrl="local" workspaceId="w" agents={[]} />)
    fireEvent.click(await screen.findByRole("button", { name: "保存工具连接" }))
    await screen.findByText("Connection changed")
    expect(screen.getByLabelText("启用项目文档 MCP")).toBeTruthy()
  })
  it("shows configured or connected runs with zero calls conservatively", async () => {
    api.getMcpRunEvidence.mockResolvedValue({ connection: { status: "configured" }, events: [{ id: "1", type: "mcp.connected", payload: {} }] })
    render(<McpEvidence backendUrl="local" runId="r" refreshKey={0} />)
    await screen.findByText("已建立 MCP 连接，尚无工具调用记录。")
    expect(screen.getByText("MCP 工具调用 · 0 次")).toBeTruthy()
  })
  it("renders actual failed/successful call receipts and bounded returned data", async () => {
    api.getMcpRunEvidence.mockResolvedValue({ connection: { status: "configured" }, events: [
      { id: "1", type: "mcp.tool.completed", payload: { tool: "read_document", status: "passed", durationMs: 2, arguments: { documentId: "doc" }, result: { sha256: "hash", text: "API docs" } } },
      { id: "2", type: "mcp.tool.completed", payload: { tool: "read_document", status: "failed", durationMs: 1, result: { error: "Missing document" } } },
    ] })
    render(<McpEvidence backendUrl="local" runId="r" refreshKey={0} />)
    await screen.findByText(/read_document · 成功/)
    expect(screen.getByText(/read_document · 失败/)).toBeTruthy()
    expect(screen.getByText(/API docs/)).toBeTruthy()
  })
  it("explicitly displays unsupported adapters", async () => {
    api.getMcpRunEvidence.mockResolvedValue({ connection: { status: "unsupported_adapter" }, events: [] })
    render(<McpEvidence backendUrl="local" runId="r" refreshKey={0} />)
    await screen.findByText("当前 Adapter 不支持此连接。")
  })
})
