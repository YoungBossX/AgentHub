import { cleanup, render, screen } from "@testing-library/react"
import { createElement } from "react"
import { afterEach, describe, expect, it } from "vitest"

import { sampleDeploymentArtifact } from "./__fixtures__/sample-deployment"
import { DeployCard } from "./deploy-card"

afterEach(() => cleanup())

describe("DeployCard", () => {
  it("shows persisted mock deployment details", () => {
    render(createElement(DeployCard, { deployment: sampleDeploymentArtifact }))

    expect(screen.getByText("模拟部署")).toBeTruthy()
    expect(screen.getByText("mock")).toBeTruthy()
    expect(screen.getByText("模拟 · mock")).toBeTruthy()
    expect(screen.getByText("preview")).toBeTruthy()
    expect(screen.getByText("就绪")).toBeTruthy()
    expect(screen.getByRole("link", { name: "打开 URL" })).toBeTruthy()
    expect(screen.getByText("def456+worktree")).toBeTruthy()
    expect(screen.getByText("demo-frontend")).toBeTruthy()
    expect(screen.getByText("artifact-diff-1")).toBeTruthy()
    expect(screen.getByText("artifact-review-1")).toBeTruthy()
    expect(screen.getByText("ready")).toBeTruthy()
    expect(screen.getByText("Mock deploy accepted healthy preview preview-1.")).toBeTruthy()
    expect(
      screen.getByText("https://mock.agenthub.local/deployments/deployment-1"),
    ).toBeTruthy()
    expect(screen.getByText("mock://deployments/deployment-1/logs")).toBeTruthy()
  })

  it("shows blocked external deployment cards without success wording", () => {
    render(
      createElement(DeployCard, {
        deployment: {
          ...sampleDeploymentArtifact,
          deployLogUri: "vercel://deployments/deployment-2/logs",
          environment: "external",
          id: "deployment-2",
          logs: [
            "Vercel deploy request was blocked.",
            "Vercel provider execution is not configured in P24.",
            "AgentHub did not execute a third-party production deploy.",
          ],
          provider: "vercel",
          providerType: "external_static",
          status: "blocked",
          statusHistory: [
            { status: "queued", message: "Vercel deploy requested." },
            {
              status: "blocked",
              message: "Vercel provider execution is not configured in P24.",
            },
          ],
          title: "Blocked deployment request",
          url: null,
        },
      }),
    )

    expect(screen.getByText("已阻止")).toBeTruthy()
    expect(screen.getByText("第三方静态托管 · vercel")).toBeTruthy()
    expect(screen.getByText("未生成 URL")).toBeTruthy()
    expect(screen.queryByRole("link", { name: "打开 URL" })).toBeNull()
    expect(
      screen.getByText(/AgentHub did not execute a third-party production deploy/),
    ).toBeTruthy()
  })

  it("shows manual handoff deployment cards explicitly", () => {
    render(
      createElement(DeployCard, {
        deployment: {
          ...sampleDeploymentArtifact,
          deployLogUri: "manual_external://deployments/deployment-3/logs",
          environment: "external",
          id: "deployment-3",
          logs: ["No third-party deploy was executed by AgentHub."],
          provider: "manual_external",
          providerType: "manual_handoff",
          status: "handoff",
          statusHistory: [
            { status: "queued", message: "Manual external deploy handoff requested." },
            { status: "handoff", message: "Manual handoff card is ready." },
          ],
          title: "Manual deploy handoff",
          url: null,
        },
      }),
    )

    expect(screen.getByText("待人工处理")).toBeTruthy()
    expect(screen.getByText("人工交接 · manual_external")).toBeTruthy()
    expect(screen.getByText("No third-party deploy was executed by AgentHub.")).toBeTruthy()
  })
})
