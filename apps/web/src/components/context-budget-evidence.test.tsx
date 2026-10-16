import { cleanup, render, screen } from "@testing-library/react"
import { afterEach, expect, it } from "vitest"
import { ContextBudgetEvidence } from "./context-budget-evidence"

afterEach(cleanup)
it.each(["within_limit", "rejected"])("shows honest budget units and source omissions: %s", status => {
  render(<ContextBudgetEvidence receipt={{ schemaVersion: "agenthub.context_budget.v1", status, textCharacters: 12345, textUtf8Bytes: 23000,
    managedBytes: 24000, imageCount: 0, imageBytes: 0, textSha256: "a".repeat(64), limits: { textCharacters: 200000, managedBytes: 50331648 },
    sources: [{ source: "projectRules", status: "included", sourceSerializedCharacters: 100, omissionReason: null, upstreamSelection: {} },
      { source: "pinnedMessages", status: "metadata_only", sourceSerializedCharacters: 30, omissionReason: "source_selection_limit_or_integrity_policy", upstreamSelection: { omitted: 2 } }] }} />)
  expect(screen.getByLabelText("最终上下文预算")).toBeTruthy()
  expect(screen.getByText(/字符不是模型 Token/)).toBeTruthy()
  expect(screen.getByText(/不能相加代替最终总量/)).toBeTruthy()
  expect(screen.getByText(/项目规则 · 已选入/)).toBeTruthy()
  expect(screen.getByText(/置顶消息 · 仅选择记录/)).toBeTruthy()
  expect(screen.getByText(/部分由来源限额或完整性策略省略/)).toBeTruthy()
  if (status === "rejected") expect(screen.getByText(/超限，未调用/)).toBeTruthy()
})
