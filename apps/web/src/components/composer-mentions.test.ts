import { describe, expect, it } from "vitest"
import { selectComposerMention } from "./composer-mentions"

describe("contact mention selection", () => {
  it("keeps the request and selected participants in group mode", () => {
    const draft = selectComposerMention("更新 demo 按钮", "frontend", "group")
    expect(selectComposerMention(draft, "qa", "group")).toBe("@frontend @qa 更新 demo 按钮")
    expect(selectComposerMention("@QA @ui-designer 更新 demo 按钮", "qa", "group")).toBe("@QA @ui-designer 更新 demo 按钮")
    expect(selectComposerMention("@ui-designer-other update", "ui-designer", "group")).toBe("@ui-designer-other @ui-designer update")
  })
  it("replaces the entire leading participant prefix in direct mode", () => {
    expect(selectComposerMention("@qa @ui-designer 更新 demo 按钮", "backend", "direct")).toBe("@backend 更新 demo 按钮")
    expect(selectComposerMention("@frontend", "qa", "direct")).toBe("@qa ")
    expect(selectComposerMention("询问 @frontend 的结果", "qa", "direct")).toBe("@qa 询问 @frontend 的结果")
  })
})
