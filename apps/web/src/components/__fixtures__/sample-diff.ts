import type { DiffArtifact } from "@/lib/api"

export const sampleDiffArtifact: DiffArtifact = {
  id: "diff-1",
  artifactId: "artifact-1",
  taskRunId: "run-1",
  artifactType: "diff",
  title: "Git diff",
  status: "ready",
  baseRef: "abc123",
  headRef: "def456+worktree",
  patchText: `diff --git a/apps/demo/src/App.tsx b/apps/demo/src/App.tsx
index 21bd2ac..f2c2e9a 100644
--- a/apps/demo/src/App.tsx
+++ b/apps/demo/src/App.tsx
@@ -1,5 +1,6 @@
 export default function App() {
   return (
     <main>
-      <button>Continue</button>
+      <h1>Welcome back</h1>
+      <button>Let's get started</button>
     </main>
   )
 }
`,
  changedFiles: ["apps/demo/src/App.tsx"],
  stats: {
    filesChanged: 1,
    additions: 2,
    deletions: 1,
    files: [
      {
        path: "apps/demo/src/App.tsx",
        additions: 2,
        deletions: 1,
      },
    ],
  },
}
