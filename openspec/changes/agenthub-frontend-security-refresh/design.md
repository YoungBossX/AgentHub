# Design

## Approach
Use compatible targeted security releases rather than a whole-tree latest-major
upgrade or audit suppression. Candidate versions confirmed in registry metadata:
Next/eslint-config-next 16.4.3, Vitest/mocker 4.1.12, Demo Vite 7.3.7, test Vite
8.1.6, DOMPurify 3.4.17 and Zod 4.6.6. Preserve React 19.2, TypeScript 5, ESLint 9,
Monaco 0.56 and existing source patches. Keep a frozen lockfile and verify actual
resolved versions; manifest values alone are insufficient.

Replace obsolete 4.1.11-only Vite override selectors with compatible Vitest 4.x
selectors and keep the Demo's Vite 7 branch separate. Use a conditional Zod 4.x
security floor, without adding a direct application dependency. Verify Monaco's
real patched domSanitize importer resolves the refreshed DOMPurify package.

## Preview boundary
The guard currently checks a filename inferred from pathname. The reserved
editor pathname need not exist to pass that check. Vite later mounts Connect's
editor middleware, allowing a host capability unrelated to previewing content.
Connect accepts case variants and '/' or '.' suffixes, and supports absolute
HTTP request targets. Use the same legacy Node URL parser as Connect/parseurl;
WHATWG normalization can erase the reserved route before dot segments. Preserve
origin-form double-slash semantics and the existing one-decode policy. Deny the
editor route at its route boundary with 403, retaining malformed-encoding 400.
Do not execute the editor to reproduce the issue: memory middleware tests and
real HTTP requests without a file query are sufficient and safe controls.

Keep normal HTML/TSX/CSS, React dependencies, Vite client/HMR and in-scope assets
working. Retain protected paths, realpath/hardlink/CSS guards and loopback binding.
Do not broaden adapter commands or disable browser sandbox, TLS, patch checks or
pnpm strict build permissions.

## Verification and preservation
Capture RED at the real guard and installed importer paths, plus the raw audit.
Then update manifests/lock and explicitly install from an E-drive store/cache.
Use disposable E-drive UI/preview copies, database paths and build outputs; never
reuse or alter historical .next/dev output or measured Session worktrees.
Check product data/configuration and patch hashes before/after. No real model
calls are needed. Run full repository gates and actual browser verification of
local Monaco workers, Diff fallback/retry, preview rendering and serving denials.
Perform one fresh read-only candidate review after focused checks. Leave Python,
CI gate additions and unrelated feature work for separate user-requested tasks.
