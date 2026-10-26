# Verification

## Scope and outcome

Base: `ff622d74627dbc8291e6f1f1a63cde634240583c`, native `dev` checkout.
One focused maintenance task; no Python package upgrade, CI redesign, model calls,
database migration or commit/push. Outcome: `fixed` within this focused scope;
the full API first sweep/replay distinction below is retained.

Changes are confined to root/Web/Demo manifests and lockfile, two preview path/
config modules and their regression tests, dependency-security tests, patch
README and this focused specification/current project documentation. The
existing product Diff component and three Adapters are unchanged. Strategy:
compatible dependency subtrees plus one shared pre-Vite request guard; no audit
suppression or broad execution permission change.

External evidence: `E:\Docker\AgentHub\frontend-security-20261026-01`.
New temporary/build/runtime copies: `E:\Docker\fs26`; pnpm store/cache/state and
npm cache are explicitly under `E:\Docker`. Product databases remain in place.

## Dependency and boundary evidence

- Baseline raw full/prod audits were copied from the immediately preceding health
  inspection of the same base. Full audit had 19 records representing 14 distinct
  advisories; these are version matches, not 19 demonstrated exploits.
- Frozen installation completed with strict build permissions and unchanged
  Monaco/braces patch bytes. E-drive contained build fixture installed offline
  from the same lockfile; no dependency install occurs during Agent execution.
- Actual importer checks resolve Next/config 16.4.3, DOMPurify 3.4.17 via Monaco's
  patched ESM importer, Vitest/mocker 4.1.12, test Vite 8.1.6, Demo Vite 7.3.7,
  and ESLint-hooks Zod 4.6.6. React 19.2.6, TypeScript 5.9.3 and ESLint 9.39.5 stay.
- Fresh `pnpm audit --json` and `pnpm audit --prod --json`: exit 0, all severity
  counts zero, no muted advisories. This does not prove absence of unknown flaws.
- Before the fix, the server-owned request guard allowed the reserved editor
  route to reach Vite's Connect middleware. A fresh candidate reviewer also
  demonstrated that WHATWG URL normalization hid absolute-form dot segments.
  The final helper uses Connect's legacy `node:url.parse` pathname semantics,
  then existing one-time decoding and reserved-route denial before `next()`.
- Regression RED logs are retained, including the corrected importer-resolver
  RED and four parser-alias failures. Final route tests cover fifteen aliases,
  ordinary assets/control paths, malformed encodings and dependency realpaths.
  Reviewer verification replaced the editor handler with a 299 sentinel; final
  actual HTTP probes omit the `file` query. No host editor was launched.

## Ordered gates

| Gate | Result | Evidence |
| --- | --- | --- |
| Syntax + whitespace + strict OpenSpec | passed | command output; final closeout repeated for docs |
| Local tool tests, final parser cases | 53 passed | `local-tests-complete.log` |
| Web ESLint + TypeScript | passed | `web-check.log` |
| Web tests, fully contained E fixture | 386 passed / 51 files | `web-tests-contained.log` |
| Default production Web build | Next 16.4.3 Turbopack passed | `web-build-contained.log` |
| Demo TypeScript + production build | Vite 7.3.7 passed | `demo-build.log` |
| API + Demo API compile | passed | `api-compile.log`, `demo-api-compile.log` |
| Demo API regression | 5 passed | `demo-api-tests.log` |
| Actual HTTP/browser compatibility, default loaders | 31 checks passed | `browser-security-default-profile.json`, `preview-profile-hashes.json`, screenshots |
| Frozen contacts feedback regression | 10 passed | `contacts-workflow-frozen.log`, JUnit |
| Full API initial three groups | 2948 passed, 19 skipped, 1 invalidated-cohort assertion failure | `api-shard-{0,1,2}.log`, JUnit |
| API reconciled unique coverage after owning-file replay | 2949 passed, 19 skipped; no unresolved failure | `api-regression-summary.json` |

API groups cover 2968 distinct cases. The initial nonzero exit is retained and
is not represented as a clean full sweep. The frozen owning-file replay covers
the failed identity and nine already-passing identities; it is not added to the
denominator. The two full-suite warnings arise from the existing intentional
expression-index/schema-drift test, not new dependency errors.

Actual browser checks used installed Edge with its sandbox enabled, blocked
external requests/downloads/service workers, and made no model calls. The small
E-only page mounts the unmodified product `LocalDiffEditor`: real original/
modified models, computed diff, local Worker, injected chunk-load failure with
readable patch fallback and successful retry. Preview checks use the current
server-owned config against a fresh built-in demo copy: HTML/TSX/CSS, public
assets, React render and HMR work; editor aliases, protected/outside files and
outside CSS imports are rejected. This is component/preview compatibility,
not a new full workbench/Provider execution cohort or production deployment.

## Failures preserved and explained

- Initial RED contained two resolver errors for package manifests hidden by
  exports; the helper now follows real resolved entries before asserting floors.
- The first E UI copy linked dependencies across drives. Default Turbopack
  correctly refused packages outside its workspace. A second self-contained
  E workspace installed offline and passed the unchanged default build command;
  webpack was not substituted to hide that failure.
- Browser fixture setup initially lacked an empty public directory; subsequent
  attempts mixed an independently installed dependency tree with another
  platform's serving profile or Vite runtime, which the scope guard denied.
  A linked-dependency/native-loader fixture passed, then a self-contained E
  platform copy using byte-identical server config and its own matching Vite
  passed again with the default config loader. Earlier failures remain in their
  logs. Browser CSS-denial 500 is an intentional probe, not a failed valid asset.
- Full API's contacts feedback case ran while the parent was editing the preview
  parser/tests. Its frozen source policy detected those exact two changed files,
  raised `WORKFLOW_REPAIR_SOURCE_CHANGED`, and marked the cohort
  `evaluation_policy_changed`. The original invalidated result remains;
  after source freeze the same parametrized case passed independently (97.23s).
  The full owning file was then repeated after freeze: 10/10 passed (196.48s).
  No assertion, timeout, source binding or product safety control was weakened.

## Preservation and remaining limits

`preservation.json` confirms both product database files and Claude settings
match their initial SHA-256 values; both patch files match baseline bytes. The
copied Web/Demo source manifest matches current source; the final preview config
and helper hashes match current files. Owned temporary HTTP services were stopped.
No old measurement directory was written. Existing natural task 8/10 and contacts 28/28 / 38/38
receipts remain historical and unchanged; this maintenance does not relabel them
as measurements of the updated dependency graph. Remote CI has not run for this
uncommitted patch. Python advisory matches from the overall review remain a
separate, unstarted task.

## Source delivery

2026-10-26: the user subsequently authorized committing/pushing this change to
`dev` and fast-forwarding the same commit to remote `main`. Before the delivery
documentation update, all 17 files matched the verified final-scope SHA-256
manifest. Both remote branches were freshly fetched and matched the recorded
base; the remote default branch was `dev` and is not changed by this delivery.
Only source/manifests/lock/tests/docs are included. Local tool tests, strict
OpenSpec, staged scope and whitespace are checked before commit; all recorded
implementation-time failure/replay distinctions remain unchanged. Actual branch
publication is verified against remote refs; no current CI success is inferred
from the earlier implementation or prior commit.
