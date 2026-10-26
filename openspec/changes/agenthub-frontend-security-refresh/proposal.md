# Frontend and preview security maintenance

## Why
The current dependency graph has 19 audit records across 14 distinct advisories.
Affected versions are not evidence that every exploit is reachable. Independently,
the server-owned preview HTTP guard permits Vite's host-editor route, which is
outside a view-only preview's capabilities.

## What Changes
- Refresh Next/eslint-config-next together within 16.4, DOMPurify within 3.x,
  Demo Vite within 7.x and Vitest/mocker within 4.x with their own Vite 8.x.
  Refresh the affected Zod 4.x subtree; retain Monaco and braces patches.
- Deny the reserved host-editor route before Vite handles it, including actual
  Connect route aliases and absolute-form requests. Preserve file-scope guards.
- Verify real installed importer paths, full/production audits, build/check/test
  gates and browser/HTTP preview compatibility in new external E-drive fixtures.

## Scope
One focused maintenance task. User authorized this next step after the current
health review. Work in the current dev checkout, following the existing native
workflow; no new feature branch, API/model calls, Python dependency changes,
database migration, CI redesign, implicit commit or push. Keep existing product
data, local configuration and historical results; all new evidence/temp/cache
data stays under E:/Docker.
