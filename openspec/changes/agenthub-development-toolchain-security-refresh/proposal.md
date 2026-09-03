## Why

The production dependency audit is clean, but the complete pnpm audit still
reports 19 development and test-tool advisories: 14 high, 4 moderate, and 1
low. The affected paths are owned by the Demo Vite server or the Web
Vitest/jsdom/ESLint toolchain and include Windows-local development-server file
read and credential-disclosure risks.

The host's first `pnpm` command is also an obsolete Corepack 0.29.4 shim whose
registry-signing keys cannot verify the pinned pnpm 10.33.4 release. This does
not alter the repository lockfile, but it prevents the documented project
commands from running normally on this workstation.

## What changes

- Raise the Demo Vite 7 floor to the patched 7.3.6 release without migrating
  the Demo application to Vite 8.
- Refresh only the vulnerable development/test dependency subtrees so Vitest,
  esbuild, PostCSS, nanoid, js-yaml, brace-expansion, and ws resolve patched
  versions.
- Preserve the existing production dependency overrides and prove both the
  complete and production audits are clean.
- Declare the shared Node engine intersection required by Vite, jsdom, and
  Vitest so unsupported Node 22.11 is not mistaken for a validated runtime.
- Repair the workstation's Corepack shim with a signed-key-aware release that
  remains compatible with the installed Node 22.11 runtime; do not disable
  Corepack integrity verification.

## Out of scope

- Application features, runtime behavior changes, or UI redesign.
- Vite 8, ESLint 10, jsdom 30, TypeScript 7, or other unrelated dependency
  majors.
- Changing the committed pnpm version or weakening registry signature checks.
