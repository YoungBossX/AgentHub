## Finding boundary

The complete audit identifies only development and test paths:

- `apps/demo -> vite@7.3.3 -> esbuild@0.27.7` and
  `postcss@8.5.14 -> nanoid@3.3.12`;
- `apps/web -> vitest@4.1.6 -> vite@8.0.12`;
- `apps/web -> eslint@9.39.4 -> js-yaml@4.1.1` and two vulnerable
  brace-expansion major lines;
- `apps/web -> jsdom@27.4.0 -> ws@8.20.1`.

The security invariant is that the committed lockfile must not resolve a
version reported by the complete audit as vulnerable. The legitimate behavior
to preserve is the Vite React Demo development/build path, the Web Vitest jsdom
environment, Next-aligned ESLint checks, and all existing repository commands.

## Patch strategy

Vite 7.3.6 fixes the direct Vite advisories and declares esbuild
`^0.27.0 || ^0.28.0`, so the lockfile can select patched esbuild 0.28.x without
a Vite major upgrade or an out-of-range override. Raise only the Demo manifest
floor and refresh the explicitly affected lockfile subtrees within their
existing compatible ranges. Add an override only if a vulnerable transitive
cannot otherwise be resolved to its patched version.

The repository already pins `pnpm@10.33.4`, and CI installs that version
directly. The Corepack failure is therefore repaired on the workstation, not
papered over in project code. Corepack 0.34.5 supports Node 22.11 and contains
the current registry signing keys. Install that release and regenerate the
first-on-PATH shims; never set `COREPACK_INTEGRITY_KEYS=0`.

The first-on-PATH host Node remains 22.11, while Vite and jsdom require at least
22.12 on the Node 22 line. Declare the compatible shared engine range
`^20.19.0 || ^22.12.0 || >=24.0.0` and run compatibility gates in the existing
conda `agent` environment. This makes the previously implicit runtime boundary
visible without changing CI's current Node 22-latest behavior.

## Validation

Run the ordinary `pnpm` command after the Corepack repair, perform a frozen
install under the supported conda `agent` runtime, and require both
`pnpm audit --prod` and the complete `pnpm audit` to exit successfully. Then
run Demo type/build checks, Web lint/type/Vitest/build checks, full repository
checks and tests, strict OpenSpec validation, and a bounded Demo server smoke on
127.0.0.1. Audit the final candidate set and remove reproducible temporary
artifacts.
