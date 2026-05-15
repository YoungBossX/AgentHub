import type { DeploymentArtifact } from "@/lib/api"

export const sampleDeploymentArtifact: DeploymentArtifact = {
  id: "deployment-1",
  artifactId: "artifact-deploy-1",
  taskRunId: "run-1",
  artifactType: "deployment",
  title: "Mock deploy",
  status: "ready",
  provider: "mock",
  environment: "preview",
  commitSha: "def456+worktree",
  url: "https://mock.agenthub.local/deployments/deployment-1",
  deployLogUri: "mock://deployments/deployment-1/logs",
  createdAt: "2026-05-15T10:30:00Z",
  updatedAt: "2026-05-15T10:30:00Z",
}
