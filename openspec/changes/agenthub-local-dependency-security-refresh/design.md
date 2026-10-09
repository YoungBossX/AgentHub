# Design

Use maintainer security advisories and npm package metadata to confirm patched
ranges, not historical release assumptions. Upgrade Next/eslint-config-next to
16.3.8, DOMPurify to 3.4.16, sharp to 0.35.5, source-map-js to 1.2.2 and
baseline-browser-mapping to 2.11.0, subject to verified dependency constraints.
Preserve earlier Babel/nanoid/PostCSS floors. Update both installed
brace-expansion 1.x and 5.x families to compatible patched versions. Avoid a
broad latest-version upgrade or disabling existing security gates.

Runtime source inspection found that the React Monaco loader defaults to CDN
Monaco 0.55.1, while installed Monaco 0.56.0 embeds DOMPurify 3.4.8 in its ESM
source. A lockfile override alone therefore does not update the browser's
sanitizer. Load the installed editor lazily in the browser, provide its local
worker, and patch the ESM sanitizer import to use the audited DOMPurify package.
Verify actual editor models and worker requests with external network blocked.
Keep patch rendering available if the local editor cannot load. This is runtime
dependency binding within this security task, not a new editing feature.

The full audit also reports an unfixed braces recursion issue. Determine its
actual importer paths and available maintainer fix before choosing a bounded
package patch, compatible owner upgrade or documented reachability limitation.
Do not fabricate a fixed version or mute the raw audit to claim zero findings.

Preserve the installed Next.js documentation guidance in apps/web/AGENTS.md.
Read version-matched upgrade/runtime guides before code changes. Stop only the
verified owned Web process before dependency replacement, then restore the same
localhost port and API binding. Keep API/session data and other processes intact.

Verify production and full audit reports, dependency resolution and package
patches, Web lint/types/tests, production build, local launcher checks and actual
workspace/Monaco Diff/Markdown/preview behavior after restart. Record both a
raw advisory result and independently verified mitigation evidence when an
unreleased fix makes those differ. Retain full original goal requirements and
advance subsequent feature gaps only after closing this focused task.
