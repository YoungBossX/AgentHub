# Brand icon verification

2026-10-23, uncommitted `dev` checkout, retaining prior uncommitted reading UI
changes. No commit or push performed.

## Implementation

- Exact uploaded source copied to `apps/web/public/brand/agenthub.png`.
- Shared percentage frame crops presentation padding only; source pixels are not
  modified. Sidebar `BrandMark` is decorative beside the unchanged workspace name.
- Next Image optimizes the sidebar source. Existing Next ImageResponse generates
  force-static 64px `/icon` and 180px `/apple-icon`; no new dependency, remote fetch
  or user-controlled path. The generated images stay in ignored `.next` output.

## Fresh verification

- Existing sidebar/shell/page tests: **3 files, 24 passed**, `tests.log`.
- `pnpm check:web`: ESLint and TypeScript passed, `check.log`.
- Production build passed, `build.log`; both icon routes appear as static output.
- Actual installed Edge: **6 checks**, `browser-result.json`, no page/hydration
  errors or mutation requests. Verified 40x40 frame, square loaded art, no theme
  filter, light/dark desktop and 390px drawer without document overflow.
- Actual metadata links return PNG: 64x64 **11841 bytes**, 180x180 **72404 bytes**.
  Optimized sidebar transfer **3525 bytes** in the tested 1x desktop viewport.
- Source SHA256 compared against original attachment and matches. File identity
  and strict OpenSpec/whitespace verification recorded under the evidence root.

## Evidence and limits

`E:\Docker\AgentHub\brand-icon-20261023-01` contains source-hash audit, tests,
check/build/browser logs, `desktop-light.png`, `desktop-dark.png`,
`mobile-sidebar-dark.png`, and actual 64px/180px PNG responses. The database is an
independent backup copy of the previous isolated UI fixture. API requests are
read-only; no product data changes, Provider calls or clipboard writes occurred.
PNG metadata/links were inspected; adding an actual device home-screen shortcut
was not tested. These are UI checks, not real-task or resume performance metrics.
