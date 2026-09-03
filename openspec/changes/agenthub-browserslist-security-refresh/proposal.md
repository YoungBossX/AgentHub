## Why

A fresh final-candidate `pnpm audit` reports two high-severity advisories in
`browserslist <=4.28.6`. The repository resolves one vulnerable Browserslist
snapshot through the Babel toolchain shared by the Demo React plugin and Web
lint configuration. The previously clean audit is therefore no longer current,
and the candidate must not be published until the dependency graph is refreshed
and reverified.

## What changes

- Attempt a compatible transitive lock refresh, then use the repository's root
  pnpm override boundary only if pnpm retains the vulnerable snapshot.
- Redirect only the audited vulnerable Browserslist range to the first patched
  release after the compatible refresh proves insufficient.
- Narrow the existing Vite 8 security override to the two Vitest owners that
  require it, because fresh resolution proves the global selector rewrites the
  Demo React plugin's compatible Vite 7 peer range into an invalid Vite 8 peer.
- Regenerate the lockfile without upgrading the owning Vite, React, Babel,
  Next.js, or ESLint package families.
- Re-run complete and production dependency audits plus the repository's build,
  check, test, documentation, and OpenSpec gates on a supported Node runtime.

## Out of scope

- Migrating the Demo from Vite 7 to Vite 8.
- A direct Browserslist dependency or an unconditional override of already safe
  future releases.
- Upgrading Babel, React, Next.js, ESLint, or unrelated dependency subtrees.
- Claiming that a clean package-manager audit proves the absence of all source
  or runtime vulnerabilities.
- Application behavior or API changes.
