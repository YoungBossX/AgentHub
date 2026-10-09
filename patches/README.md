# Local dependency patches

`monaco-editor@0.56.0.patch` changes the ESM sanitizer import from its embedded
DOMPurify 3.4.8 copy to the declared `dompurify` dependency, resolved by our
override to 3.4.16. The Web Diff component lazily supplies this local ESM editor
and its workers to the React loader; its default CDN and AMD bundles are not
used. This patch alone does not change Monaco's unused AMD/prebundled copies.
Keep the runtime import and browser-network verification when upgrading Monaco.

`braces@3.0.3.patch` bounds recursive AST traversal for
[GHSA-vfj7-8cjw-p6xm](https://github.com/advisories/GHSA-vfj7-8cjw-p6xm).
The published package had no patched release when checked on 2026-10-08.
This is a local mitigation, not an upstream security release.

The parser allows at most 127 simultaneous brace/parenthesis containers,
leaving room for their leaf nodes in a maximum AST depth of 128. The three
walkers also bound caller-supplied ASTs. Excess input throws a controlled
`RangeError`; callers still need to handle invalid glob patterns. Ordinary
glob semantics and the existing character/range limits are retained. This
patch does not claim to solve arbitrary expansion-size or cyclic parent-link
problems outside the reported deeply nested pattern issue.

pnpm records the patch and its hash in the manifest and lockfile. Use
`pnpm install --frozen-lockfile --ignore-scripts` and `pnpm test:local` to
verify installation and behavior through the actual ESLint importer chain.
Raw full-tree audits still report the vulnerable published version; no
advisory is suppressed. Production dependencies do not import this package.

Recheck the upstream advisory before removing the patch. Once a compatible
fixed release exists, upgrade it, remove the patch registration and file,
and retain equivalent regression coverage adapted to the upstream contract.
