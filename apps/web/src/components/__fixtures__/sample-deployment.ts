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
  providerType: "mock",
  targetId: "demo-frontend",
  sourcePreviewId: "preview-1",
  sourceDiffArtifactId: "artifact-diff-1",
  sourceReviewArtifactId: "artifact-review-1",
  logs: ["Mock deploy accepted healthy preview preview-1."],
  statusHistory: [
    { status: "queued", message: "Deploy request queued." },
    { status: "ready", message: "Mock deployment is ready." },
  ],
  createdAt: "2026-05-15T10:30:00Z",
  updatedAt: "2026-05-15T10:30:00Z",
}
