import type { PreviewArtifact } from "@/lib/api"

export const samplePreviewArtifact: PreviewArtifact = {
  id: "preview-1",
  artifactId: "artifact-preview-1",
  taskRunId: "run-1",
  artifactType: "preview",
  title: "Vite React preview",
  status: "ready",
  port: 5173,
  url: "http://127.0.0.1:5173",
  command: "pnpm dev --host 127.0.0.1 --port 5173",
  processId: 4242,
  healthStatus: "healthy",
  statusReason: null,
  expiresAt: "2026-05-15T12:00:00Z",
  lastCheckedAt: "2026-05-15T10:30:00Z",
}
