import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { SkillSettings } from "./skill-settings"
import { SkillSelector } from "./skill-selector"
import { SkillEvidence } from "./skill-evidence"
import { readSkillText, validateReferenceRows } from "./skill-references-editor"
import type { WorkspaceSkill } from "@/lib/skills-api"

const api = vi.hoisted(() => ({ listSkills: vi.fn(), saveSkill: vi.fn() }))
vi.mock("@/lib/skills-api", () => api)
const skill: WorkspaceSkill = { name: "react-form", description: "React 表单开发", markdown: "---\nname: react-form\ndescription: 表单\n---\n步骤",
  references: {}, roles: ["frontend"], defaultAgents: [], enabled: true, revision: 0, source: "builtin" }
beforeEach(() => { vi.clearAllMocks(); api.listSkills.mockResolvedValue([skill]); api.saveSkill.mockResolvedValue({ ...skill, revision: 1 }) })
afterEach(cleanup)

describe("Skills", () => {
  it("supports explicit overrides, an empty selection and return to defaults", async () => {
    const change = vi.fn()
    const { rerender } = render(<SkillSelector backendUrl="local" workspaceId="w" selected={null} onChange={change} disabled={false} />)
    await screen.findByLabelText(/react-form/)
    fireEvent.click(screen.getByLabelText(/react-form/)); expect(change).toHaveBeenLastCalledWith(["react-form"])
    rerender(<SkillSelector backendUrl="local" workspaceId="w" selected={["react-form"]} onChange={change} disabled={false} />)
    fireEvent.click(screen.getByRole("button", { name: "全部取消" })); expect(change).toHaveBeenLastCalledWith([])
    fireEvent.click(screen.getByRole("button", { name: "使用默认" })); expect(change).toHaveBeenLastCalledWith(null)
  })
  it("caps selection and disables changes while sending", async () => {
    render(<SkillSelector backendUrl="local" workspaceId="w" selected={["a", "b", "c"]} onChange={vi.fn()} disabled={true} />)
    await screen.findByLabelText(/react-form/)
    expect(screen.getByLabelText(/react-form/).hasAttribute("disabled")).toBe(true)
    expect(screen.getByRole("button", { name: "使用默认" }).hasAttribute("disabled")).toBe(true)
  })
  it("edits a skill and saves Agent defaults with its expected revision", async () => {
    render(<SkillSettings backendUrl="local" workspaceId="w" agents={[]} />)
    fireEvent.click(await screen.findByRole("button", { name: /react-form/ }))
    fireEvent.click(screen.getByLabelText("前端默认 Agent"))
    fireEvent.change(screen.getByLabelText("SKILL.md"), { target: { value: skill.markdown + "\n检查输入" } })
    fireEvent.click(screen.getByRole("button", { name: "保存技能" }))
    await waitFor(() => expect(api.saveSkill).toHaveBeenCalledWith("local", "w", expect.objectContaining({ revision: 0, defaultAgents: ["frontend"] })))
    await screen.findByText("技能已保存，新运行将使用新版本。")
  })
  it("retains the draft on revision conflicts", async () => {
    api.saveSkill.mockRejectedValue(new Error("Skill changed; reload"))
    render(<SkillSettings backendUrl="local" workspaceId="w" agents={[]} />)
    fireEvent.click(await screen.findByRole("button", { name: /react-form/ }))
    fireEvent.click(screen.getByRole("button", { name: "保存技能" }))
    await screen.findByText("Skill changed; reload")
    expect(screen.getByLabelText("SKILL.md")).toBeTruthy()
  })
  it("edits bounded path/content resources with revision-checked save instead of JSON", async () => {
    render(<SkillSettings backendUrl="local" workspaceId="w" agents={[]} />)
    fireEvent.click(await screen.findByRole("button", { name: /react-form/ }))
    fireEvent.click(screen.getByRole("button", { name: "添加参考文件" }))
    fireEvent.change(screen.getByLabelText("参考路径 1"), { target: { value: "references/checklist.md" } })
    fireEvent.change(screen.getByLabelText("参考内容 1"), { target: { value: "核对输入与错误提示" } })
    fireEvent.click(screen.getByRole("button", { name: "保存技能" }))
    await waitFor(() => expect(api.saveSkill).toHaveBeenCalledWith("local", "w", expect.objectContaining({ revision: 0, references: { "references/checklist.md": "核对输入与错误提示" } })))
    expect(screen.queryByLabelText("技能参考资料")).toBeNull()
  })
  it("retains invalid resource drafts and does not call save", async () => {
    render(<SkillSettings backendUrl="local" workspaceId="w" agents={[]} />)
    fireEvent.click(await screen.findByRole("button", { name: /react-form/ }))
    fireEvent.click(screen.getByRole("button", { name: "添加参考文件" }))
    fireEvent.change(screen.getByLabelText("参考路径 1"), { target: { value: "references/../secret.md" } })
    fireEvent.change(screen.getByLabelText("参考内容 1"), { target: { value: "保留草稿" } })
    fireEvent.click(screen.getByRole("button", { name: "保存技能" }))
    expect(await screen.findByText(/参考路径须为/)).toBeTruthy()
    expect(api.saveSkill).not.toHaveBeenCalled()
    expect((screen.getByLabelText("参考内容 1") as HTMLTextAreaElement).value).toBe("保留草稿")
  })
  it("checks duplicate paths, UTF-8 bytes and strict text imports", async () => {
    const row = { id: "r", path: "references/a.md", content: "中文" }
    expect(() => validateReferenceRows([row, { ...row, id: "other" }], "body")).toThrow(/重复/)
    expect(() => validateReferenceRows([{ ...row, content: "中".repeat(4001) }], "body")).toThrow(/12 KB/)
    const file = (raw: Uint8Array) => ({ size: raw.length, arrayBuffer: async () => raw.buffer } as File)
    expect(await readSkillText(file(new TextEncoder().encode("导入文本")), 12000)).toBe("导入文本")
    await expect(readSkillText(file(new Uint8Array([0xff])), 12000)).rejects.toThrow()
    await expect(readSkillText(file(new Uint8Array([0])), 12000)).rejects.toThrow(/UTF-8/)
  })
  it("displays actual loading and scripted compatibility separately", () => {
    render(<SkillEvidence value={{ source: "message", sha256: "s", skills: [
      { name: "react-form", description: "form", revision: 1, source: "workspace", sha256: "hash", resources: [], status: "loaded" },
      { name: "review", description: "review", revision: 0, source: "builtin", sha256: "hash2", resources: [], status: "unsupported_adapter" },
    ] }} />)
    expect(screen.getByText(/已载入调用指令/)).toBeTruthy()
    expect(screen.getByText(/脚本模式不执行技能/)).toBeTruthy()
    expect(screen.getByText(/执行结果仍以 Diff 和 QA 为准/)).toBeTruthy()
  })
})
