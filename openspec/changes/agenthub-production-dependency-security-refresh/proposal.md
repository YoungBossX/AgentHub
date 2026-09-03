## Why

The delivered local baseline passes its functional gates, but a fresh
`pnpm audit --prod` reports 34 production advisories: 9 high, 21 moderate,
and 4 low. The affected dependency paths are owned by the Web package and run
through Next.js or Monaco Editor. A focused dependency refresh is required
before treating the baseline as security-current.

## What changes

- Upgrade Next.js and its aligned ESLint configuration to a release that owns
  patched PostCSS, nanoid, and sharp dependency ranges.
- Upgrade Monaco Editor and enforce the patched DOMPurify floor required by
  the remaining transitive sanitizer advisories.
- Enforce the patched Babel 7 floor required by the source-map file-read
  advisory exposed by the refreshed Next.js dependency tree.
- Regenerate the pnpm lockfile and verify the production audit, Web build, and
  complete repository gates.

## Out of scope

- Application feature changes or UI redesign.
- Broad upgrades unrelated to the production audit paths.
- UTC migration, source modularization, production deployment, or platform
  scope expansion.
