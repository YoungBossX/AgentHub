# Content and presentation verification

## 2026-10-23 confirmed platform-first presentation, task 1.3

The user confirmed the task / execution / Diff / review / preview narrative.
Homepage copy now follows these five steps, without changing the six sections,
outer layout, CSS or scripts. README leads with the full workspace and groups
the contacts example under a disclosure. The example is explicitly an Agent-built
application, not a platform address book. Original screenshots and all seven
image hashes remain unchanged; historical review expiry is not concealed.

The sidebar, its existing settings link/page and role-list heading now use
"协作 Agent" wording. Routes, API types, stored data, role/alias selection and
availability controls are unchanged. The existing workspace navigation assertions
were updated, without introducing a new runtime behavior.

Fresh verification:

- `pnpm --filter @agenthub/web test src/components/session-sidebar.test.tsx src/components/workspace-shell.test.tsx`: **23 passed**, two files.
- `pnpm check:web`: ESLint and TypeScript passed.
- `E:/Docker/AgentHub/platform-focus-20261023-01/check-page.cjs`: **six** Edge
  configurations, 1440/1024/390px in light/dark, no page errors or horizontal
  overflow, four HTML images loaded, theme keyboard/persistence and the new
  workflow anchor passed. Original CSS/scripts, HTML sections, README outline,
  seven image hashes and absence of image/metadata jump links verified.
- Desktop and mobile captures visually inspected. README now contains six
  local showcase images including the brand; three are in the optional case.
- Strict OpenSpec and whitespace checks passed.

Evidence and screenshots stay in the new E-drive directory. This is a text and
presentation change, not a fresh model execution, full API regression or product
data migration. No dependencies installed, services started, commit, push or
publication performed.

## 2026-10-23 user correction, task 1.2

The public page no longer wraps images in links or exposes source/raw-image/
metadata jump links in captions. Captions explain visible behavior. README keeps
its section order; root HTML keeps all six sections, original CSS and both script
blocks. Existing outer layouts, theme controls and navigation remain intact.

Selected scenes now have a specific purpose: the full dark workbench shows
roles/dependencies/execution; the light task-plan crop shows all four tasks;
the backend Diff makes `casefold()` comparison and `_contacts.append(contact)`
readable; the result crop shows an actual created contact. README also shows a
390px duplicate-email rejection with Chinese error and retained input/list.
Expired QA imagery is not rendered as current acceptance. Its historical image,
reports and original benchmark records remain unchanged.

Fresh validation under `E:/Docker/AgentHub/showcase-focus-20261023-01`:

- `capture-result.json` and `hero-capture.json`: actual Edge captures, no product
  mutation requests, no page errors or new Provider calls. No response fixtures
  or synthetic DOM states. Generated demo interactions use a new unchanged
  source copy, actual ASGI and actual POST 201 / POST 409 responses. A subsequent
  page reload reads back the created record from the same service process.
- `page-check.json`: **six** responsive/theme configurations, 1440/1024/390px in
  light/dark, all images loaded and no horizontal overflow. Navigation and
  keyboard theme persistence passed; all seven stored image hashes match.
  No figure links, image-source links, obsolete screenshot audit captions or
  expired-QA image appear in the root presentation.
- Original-vs-final CSS/script blocks and README outline match. HTML has four
  images after removing the QA figure; README uses five including the brand.
  `preview-final.png` is an ordinary viewport capture, without stitching a
  sticky header through the content. Final desktop/mobile pages were inspected.
- `integrity.json` and final source verification: original evidence DB file
  hash, all historical rows and every copied generated source file match.
  Strict OpenSpec and `git diff --check` passed. No runtime code changed; no
  fresh full API regression or new model task is claimed.

An initial isolated preview failed because its cache directory did not exist
when the fixed serving profile collected allowed roots. Creating that exact
E-drive cache before loading the existing profile resolved the operator setup
issue; scope guards were not disabled and original failure logs are retained.
All helper services were stopped and generated Next type paths restored.
No dependencies installed, product DB modified, commit, push or publication.
Source/capture dates and deployment/storage limits remain in image metadata:
the backend was operator-started, contact storage is process-local, and none of
these new UI interactions changes the frozen 50-task or recovery statistics.

## Original task 1.1

2026-10-23, local `dev` worktree. No commit/push/publication. Previous UI/icon
changes remain uncommitted and are not part of this content-only implementation.

## Requirement audit

| User requirement | Verified result |
| --- | --- |
| Update README content | Current introduction, capability table, architecture/workflow wording, real screenshots, stack/modules and Chinese startup example updated. Existing h2 titles and their order remain identical. |
| Update index content | Refreshed hero, overview, architecture labels, engineering, evidence and module text within existing containers. Generic mock task statuses and fabricated event-log illustration replaced with sourced actual screenshots. |
| Preserve overall framework | Original HTML has hero plus five numbered sections; all section IDs/classes and 27 major layout/card class counts match. The original style block and both script blocks are byte-identical. |
| Show actual project pages | Four 2026-10-23 current-UI screenshots display the 2026-10-20 native contacts run, plus two unchanged historical generated-result images. Existing application metadata provides the brand image. Every picture has a hash and provenance. No fixture task states invented. |
| Avoid false claims | Historical strict40/50, business46/50, complete receipts197/198, separate recovery10/10 match the frozen report. Version and fixed-scenario limits remain explicit. Model review/fixed checks/script fallback/assisted preview/deployment are distinguished. |
| Usable presentation | Local links/anchors exist, all images load, full-resolution links work, 1440/1024/390px both themes have no horizontal overflow. Theme keyboard/persistence and direct file opening work. |
| Deliverable assets | Exact Git-ignore exceptions admit only the nine intentional showcase image/provenance files; sibling images, logs and SQLite examples remain ignored. Nothing staged, committed or pushed. |

## Fresh checks and evidence

Evidence root: `E:\Docker\AgentHub\public-docs-20261023-01`.

- `check-docs.py` / `content-check.json`: original-vs-current outline, IDs, layout
  counts, CSS/scripts, local links, target modules and image hash/size checks.
- `check-browser.cjs` / `browser-check.json`: **9 actual Edge checks**, zero page
  errors/bad resources, six responsive theme configurations, navigation, theme
  keyboard/persistence and direct `file://` opening. No dependency downloads.
- `capture-product.cjs` / `product-capture.json`: actual current UI; read-only
  localhost GET/OPTIONS only, no Provider or mutation requests.
- `records-unchanged.json`: original showcase DB unchanged; historical Task,
  TaskRun, Artifact, Diff and Review rowsets in the readback copy match the source.
- README Chinese login example passed the pure intent parser; no model executed.
- Strict OpenSpec and whitespace checks passed. No runtime code changed, so this
  task does not claim a fresh product API/Web unit regression or live-model test.

Independent read-only review found the ignored-asset delivery issue; narrowed
exceptions fixed it. Reviewer found no blocking factual or framework issue.
Snapshots during a theme transition were replaced by stable screenshots after
the existing 180ms transition; no theme implementation was changed.

## Scope and limits

Native records belong to one selected passing sample, not all 50 UI executions.
Current UI readback is not a fresh execution or active preview. Generated-result
images retain their original date and use platform Vite plus operator-assisted
ASGI; production deployment was not tested. Original failures, unknown usage,
previous benchmark evidence, primary product DB, adapters and worktrees are not
modified. Source image files are documentation assets, not build outputs.
