## 1. Refresh the vulnerable Browserslist snapshot

- [x] 1.1 Attempt a compatible lock refresh, enforce the patched Browserslist
  boundary only when pnpm retains the vulnerable snapshot, regenerate only the
  required lockfile subtree, prove the complete and production audits are clean
  on a supported Node runtime, scope the existing Vite override to its intended
  Vitest owners when peer resolution exposes the global-selector defect, run
  the compatibility and repository gates, update project documentation, obtain
  one independent read-only review, and clean reproducible artifacts.
