import type { ReviewArtifact } from "@/lib/api"

export const sampleReviewArtifact: ReviewArtifact = {
  adapterType: "scripted_mock",
  artifactId: "artifact-review-1",
  artifactType: "review",
  filesReviewed: ["apps/demo/src/App.tsx"],
  findings: [],
  id: "review-1",
  reviewedDiffArtifactId: "artifact-diff-1",
  riskLevel: "low",
  status: "passed",
  suggestedChanges: [],
  summary: "Scripted Review Agent passed 1 changed file with low risk.",
  taskRunId: "run-1",
  title: "Review Agent report",
}
