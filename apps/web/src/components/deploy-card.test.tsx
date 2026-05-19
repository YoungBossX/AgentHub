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
    expect(screen.getByText("preview")).toBeTruthy()
    expect(screen.getByText("就绪")).toBeTruthy()
    expect(screen.getByText("def456+worktree")).toBeTruthy()
    expect(
      screen.getByText("https://mock.agenthub.local/deployments/deployment-1"),
    ).toBeTruthy()
    expect(screen.getByText("mock://deployments/deployment-1/logs")).toBeTruthy()
  })
})
