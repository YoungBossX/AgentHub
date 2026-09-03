## Finding boundary

The final-candidate audit resolves `browserslist@4.28.2`. Its concrete paths are
the Demo's `@vitejs/plugin-react -> @babel/core ->
@babel/helper-compilation-targets` chain and the Web lint tree's
`eslint-config-next -> eslint-plugin-react-hooks -> @babel/core` chain. Both
share the same Browserslist snapshot. Versions through 4.28.6 are reported by
the registry audit as vulnerable to unbounded query-cache growth and malformed
custom-stat handling; 4.28.7 is the first patched release.

The invariant is that the committed lockfile resolves no Browserslist release in
the audited vulnerable range. Demo Vite 7, Babel 7, React 19, the Web lint/build
toolchain, application behavior, and the repository's supported Node engine
contract must remain unchanged.

## Patch strategy

First request a targeted lock-only refresh to 4.28.7 within
`@babel/helper-compilation-targets`' existing `^4.24.0` range. pnpm 10.33.4
completes that command without changing manifests but retains 4.28.2, proving
that ordinary compatible resolution does not refresh this pinned transitive
snapshot. Therefore use the existing root override boundary to map only
`browserslist@<=4.28.6` to exactly 4.28.7. This is narrower than upgrading
`@vitejs/plugin-react` to a new major that requires Vite 8 and does not constrain
later already-safe releases.

Regenerate only the lockfile state required by the conditional override.
Expected changes are override metadata, the Browserslist package/snapshot, its
current data packages, and the `update-browserslist-db` peer-context key.
Workspace importers and direct dependency manifests must not otherwise change.

## Validation

Use the original complete `pnpm audit` as the security trigger. Verify that
`pnpm why browserslist --recursive` resolves one patched version, then run the
complete and production audits, frozen installation, Demo and Web checks/builds,
root checks/tests, strict OpenSpec validation, candidate whitespace/link/UTF-8
checks, temporary-artifact cleanup, and one independent read-only patch review.
Run Node-dependent gates through the conda `Agent` environment because the
shell's Node 22.11.0 is below the repository's declared 22.12.0 floor.
