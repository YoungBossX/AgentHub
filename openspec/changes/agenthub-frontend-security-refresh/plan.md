# Frontend Security Refresh Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Resolve the audited frontend dependency families and remove the preview host-editor capability while preserving current local workflows.

**Architecture:** Targeted manifest/lock refresh with real-importer security checks. The existing server-owned request guard denies the editor before Vite; all builds/runtime evidence use new E-drive fixtures.

**Tech Stack:** Existing pnpm/Node, Next/React, Vite/Vitest, Playwright and Node tests. Existing Python checks are reused without upgrading Python packages.

**Spec:** [design.md](design.md), [frontend-security/spec.md](specs/frontend-security/spec.md).

## Global Constraints
- Keep three Adapters, product SQLite/configuration and all historical evidence.
- Keep Demo Vite 7 separate from test Vite 8, React 19.2/TypeScript 5/ESLint 9 and existing patch bytes.
- Work in the current clean dev checkout; no commit/push, branch creation or historical worktree writes.
- Use explicit E-drive store/cache/temp/build/database/evidence locations; preserve browser sandbox and pnpm strict build permissions.
- The milestones below belong to the single OpenSpec task 1.1; do not begin Python or CI redesign tasks.

## Review Focus
1. A manifest upgrade can leave Monaco using its embedded sanitizer: assert the real patched importer and browser bundle/worker.
2. Old Vitest override selectors can stop matching: assert both actual test Vite consumers and the separate Demo branch.
3. Connect case/dot/slash/absolute request aliases can bypass equality checks: pin all at the actual guard, without executing an editor.
4. Scope hardening can reject legitimate assets/HMR: retain controls for in-scope files, public assets, CSS and Vite client plus outside/protected denials.
5. Dependency installation/build can overwrite historical output or caches: hash data/config/patches and use disposable E fixtures.

## Task 1: One independently verifiable maintenance change

**Files:** Modify package.json, apps/web/package.json, apps/demo/package.json and pnpm-lock.yaml; scripts/dependency-security.test.mjs, scripts/preview-serving-paths.{mjs,test.mjs}, scripts/preview-vite.config.mjs; patches/README.md and current docs only where versions/verification need updating. No patch-byte changes are planned.

- [x] Capture clean base, product/config/patch hashes and raw full/prod audit; record current importer versions.
- [x] Add real-importer security floors and guard regression cases. Run focused Node tests; expect old floors and editor-route aliases to fail while ordinary controls pass.
- [x] Apply minimal preview pathname extraction/route rejection. Pin compatible package floors and refresh only affected lockfile subtrees; install explicitly from the E store and verify patch/importer bindings.
- [x] Run syntax/local/Web/Demo checks/tests and full/prod audits. Investigate failures before proceeding; preserve raw outputs and do not mute findings.
- [x] Build Web in a new E runtime copy; test actual local Monaco/worker/Diff fallback and preview HTTP/render/HMR/scope denials using safe endpoint requests without a file query.
- [x] Run relevant full API/backend gates with isolated E databases; review candidate once, address confirmed issues and rerun affected checks. Initial sweep/replay distinction is retained in verification.md.
- [x] Record exact source/version-bound results and data preservation; update changelog/project-state, then tick OpenSpec 1.1 only after verification. Do not commit/push.
