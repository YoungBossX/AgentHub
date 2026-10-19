import { createElement } from "react"
import { cleanup, render, screen } from "@testing-library/react"
import { afterEach, describe, expect, it } from "vitest"
import type { QaAssessment } from "@/lib/api"
import { PreviewPanel } from "./preview-card"
import { QaEvidence, qaLabel } from "./qa-evidence"
import { sampleReviewArtifact } from "./__fixtures__/sample-review"

afterEach(cleanup)

function snapshot(): QaAssessment {
  return {
    schemaVersion: "agenthub.qa.v1", taskRunId: "run-1", diffArtifactId: "diff-1",
    patchSha256: "a".repeat(64), inputFingerprint: null, acceptance: "not_established",
    status: "incomplete", rules: { status: "passed", violations: [], findings: [] },
    model: { status: "not_run", source: "none" },
    commands: ["check", "test", "build"].map((kind) => ({
      kind: kind as "check" | "test" | "build", status: "not_run", configured: true,
      versionBound: false, evidence: [],
    })),
  }
}

describe("layered QA evidence", () => {
  it.each([
    ["native", "native", "原生固定验证"],
    ["docker", "docker", "Docker 固定验证"],
    ["docker", "not_run", "请求 Docker · 未运行/环境不可用"],
  ] as const)("distinguishes requested and executed environment: %s/%s", (backend, commandsBackend, text) => {
    const qa = snapshot()
    qa.validation = { eventId: "validation-1", status: commandsBackend === "not_run" ? "unavailable" : "passed",
      profile: "vite-build-smoke-v1", execution: { backend, commandsBackend, operationId: "operation-1",
        generationFingerprint: "f".repeat(64), runtimePolicyId: "container-validation-v1" } }
    qa.functional = { status: "unavailable", contract: { schemaVersion: "v1", target: "login_page" }, checks: [],
      execution: { backend: "native", inputArtifactFingerprint: "a".repeat(64) } }
    render(createElement(QaEvidence, { review: { ...sampleReviewArtifact, qaAssessment: qa } }))
    expect(screen.getByText(text)).toBeTruthy()
    expect(screen.getByText("原生浏览器检查")).toBeTruthy()
    expect(screen.getByText("QA 待验证")).toBeTruthy()
    if (commandsBackend === "not_run") expect(screen.queryByText("Docker 固定验证")).toBeNull()
  })

  it("shows missing legacy execution without inventing an environment", () => {
    const qa = snapshot()
    qa.validation = { eventId: "legacy", status: "passed", profile: "vite-build-smoke-v1" }
    render(createElement(QaEvidence, { review: { ...sampleReviewArtifact, qaAssessment: qa } }))
    expect(screen.getByText("历史验证（环境未记录）")).toBeTruthy()
    expect(screen.queryByText("原生固定验证")).toBeNull()
    expect(screen.queryByText("Docker 固定验证")).toBeNull()
  })
  it.each(["passed", "expired"] as const)("shows the backend scope without inventing a build: %s", (status) => {
    const qa = snapshot()
    qa.status = status
    qa.currentness = status === "passed" ? "current" : "expired"
    qa.validation = { eventId: "backend-validation", status: "passed", profile: "fastapi-contract-v1", sourceFingerprint: "backend1234567890" }
    qa.commands = qa.commands.map(item => item.kind === "build"
      ? { ...item, status: "not_applicable", configured: false }
      : { ...item, status, versionBound: status === "passed" })
    qa.functional = { status: "not_configured", contract: null, checks: [] }
    render(createElement(QaEvidence, { review: { ...sampleReviewArtifact, qaAssessment: qa } }))
    expect(screen.getByText(/Python 语法、FastAPI/)).toBeTruthy()
    expect(screen.getByText("此验证配置不需要")).toBeTruthy()
    expect(screen.getByText(/不包含新增接口、真实数据库或完整前后端联调/)).toBeTruthy()
    expect(screen.queryByText(/类型检查、构建、构建产物/)).toBeNull()
    expect(screen.queryByText(/请检查已安装的浏览器/)).toBeNull()
    expect(screen.queryByText(/需求交互验收/)).toBeNull()
    if (status === "expired") expect(screen.getByText("QA 证据已过期")).toBeTruthy()
  })
  it.each(["passed", "failed", "expired", "unavailable", "not_configured"] as const)("shows bounded requirement coverage: %s", (status) => {
    const qa = snapshot()
    qa.status = status === "passed" ? "passed" : status === "failed" ? "blocked" : status === "expired" ? "expired" : "incomplete"
    qa.acceptance = status === "passed" ? "requirement_checks_passed" : "not_established"
    qa.functional = { status, contract: status === "not_configured" ? null : { schemaVersion: "v1", target: "login_page" },
      checks: status === "unavailable" || status === "not_configured" ? [] : [{ id: "desktop.empty", status: status === "failed" ? "failed" : "passed" }] }
    render(createElement(QaEvidence, { review: { ...sampleReviewArtifact, qaAssessment: qa } }))
    expect(screen.getByText(/需求交互验收/)).toBeTruthy()
    expect(screen.getByText(/不包含真实账号认证/)).toBeTruthy()
    if (status === "passed") expect(screen.getByText("本版本指定需求验收通过")).toBeTruthy()
    if (status === "expired") expect(screen.getByText("QA 证据已过期")).toBeTruthy()
    if (status === "unavailable") expect(screen.getByText(/请检查已安装的浏览器/)).toBeTruthy()
    if (status === "not_configured") expect(screen.getByText(/当前结构化任务未配置/)).toBeTruthy()
  })
  it.each(["passed", "expired"] as const)("shows version-bound results and freshness: %s", (status) => {
    const qa = snapshot()
    qa.status = status
    qa.currentness = status === "passed" ? "current" : "expired"
    qa.validation = { eventId: "validation-1", status: "passed", profile: "vite-build-smoke-v1", sourceFingerprint: "abcdef1234567890" }
    qa.commands = qa.commands.map((item) => ({ ...item, status, versionBound: status === "passed", evidence: [
      { eventId: "validation-1", taskRunId: "run-1", command: `fixed ${item.kind}`, exitCode: 0, log: `${item.kind} log` },
    ] }))
    render(createElement(QaEvidence, { review: { ...sampleReviewArtifact, qaAssessment: qa } }))
    expect(screen.getByText(status === "passed" ? "本版本已配置验证通过" : "QA 证据已过期")).toBeTruthy()
    expect(screen.getByText(/不代表完整业务功能验收/)).toBeTruthy()
    expect(screen.getByText("abcdef123456")).toBeTruthy()
    expect(screen.getByText("test log")).toBeTruthy()
    expect(screen.queryByText(/命令记录未绑定源码版本/)).toBeNull()
  })
  it("never calls a scripted pass full QA acceptance", () => {
    const review = { ...sampleReviewArtifact, qaAssessment: snapshot() }
    render(createElement(QaEvidence, { review }))
    expect(screen.getByText("QA 待验证")).toBeTruthy()
    expect(screen.getByText(/此报告仅完成规则审查/)).toBeTruthy()
    expect(screen.getAllByText("未运行")).toHaveLength(4)
    expect(qaLabel(review)).toBe("QA 待验证")
  })

  it("shows rule failure independently from a passed model", () => {
    const qa = snapshot()
    qa.status = "blocked"
    qa.model = { status: "passed", source: "native" }
    qa.rules = { status: "failed", violations: [".env"], findings: [] }
    render(createElement(QaEvidence, { review: { ...sampleReviewArtifact, qaAssessment: qa } }))
    expect(screen.getByText("QA 有阻塞问题")).toBeTruthy()
    expect(screen.getByText("未通过")).toBeTruthy()
    expect(screen.getByText("通过")).toBeTruthy()
    expect(screen.getByText("范围违规：.env")).toBeTruthy()
  })

  it("renders separate command results and provenance without claiming current tests passed", () => {
    const qa = snapshot()
    qa.commands[1] = { ...qa.commands[1], status: "recorded_failed", evidence: [
      { artifactId: "receipt-1", taskRunId: "run-1", command: "pnpm test", exitCode: 1 },
    ] }
    qa.commands[2].status = "recorded_passed"
    qa.status = "blocked"
    render(createElement(QaEvidence, { review: { ...sampleReviewArtifact, qaAssessment: qa } }))
    expect(screen.getByText("记录失败")).toBeTruthy()
    expect(screen.getByText("记录通过")).toBeTruthy()
    expect(screen.getByText("pnpm test")).toBeTruthy()
    expect(screen.getByText(/运行 run-1 · 证据 receipt-/)).toBeTruthy()
    expect(screen.getByText(/命令记录未绑定源码版本/)).toBeTruthy()
  })

  it("keeps legacy evidence unknown", () => {
    render(createElement(QaEvidence, { review: sampleReviewArtifact }))
    expect(screen.getByText(/历史报告缺少分项 QA 证据/)).toBeTruthy()
    expect(screen.queryByText("QA 待验证")).toBeNull()
  })

  it("keeps the snapshot visible after the artifact panel is reloaded", () => {
    const props = {
      artifactItems: [{ artifact: { ...sampleReviewArtifact, qaAssessment: snapshot() },
        id: "qa-report", kind: "review" as const, taskRunId: "run-1", taskTitle: "Review" }],
      frameKey: 1, selectedArtifactId: "qa-report",
    }
    const view = render(createElement(PreviewPanel, props))
    view.rerender(createElement(PreviewPanel, { ...props, frameKey: 2 }))
    expect(screen.getByRole("region", { name: "QA 分项证据" })).toBeTruthy()
    expect(screen.getByText("QA 待验证")).toBeTruthy()
    expect(screen.getByText(/证据截至本报告生成时/)).toBeTruthy()
  })
})
