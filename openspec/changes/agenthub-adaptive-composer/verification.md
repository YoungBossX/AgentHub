# Verification

2026-10-24, local dev based on 4fe6d77. User-authorized local implementation;
no commit or push at implementation time. Evidence stays in
E:/Docker/AgentHub/adaptive-composer-20261024-01.

## Source delivery

The user subsequently authorized committing and pushing this refinement to dev.
The delivery retains exactly the 17 intended source, test, script, OpenSpec and
documentation files; README and index.html still change only one text location
each. Build outputs, dependencies, screenshots, test fixtures/logs, caches,
databases and local API configuration are excluded. Fresh checks, scope audit
and the remote-SHA receipt are recorded separately under
E:/Docker/AgentHub/adaptive-composer-delivery-20261024-01.
Historical no-commit/no-push statements below describe implementation-time scope.
Fresh delivery checks passed: 386 Web tests, root pnpm check, strict OpenSpec,
browser-script syntax and whitespace checks.
This delivery does not claim that a new GitHub CI run has passed.

## Delivered behavior

- The controlled textarea measures its draft and width, grows/shrinks without
  changing content/selection, and retains the external focus ref. Normal bounds
  are 64–240px with native internal scrolling. Short viewport flex layouts may
  shrink to a single line while preserving the toolbar.
- Narrow unzoomed visualViewport height/top updates fit the shell. Desktop,
  absent/invalid viewport and pinch zoom retain dvh fallback. Callback-ref node
  ownership rebinds listeners after a Session-keyed shell replacement.
- Composer actions have 44px touch targets and safe-area spacing. Short viewports
  expose an expandable context/attachment summary, preserve mounted skills and
  frozen outgoing context, and keep the view tabs while condensing duplicated
  header progress/breadcrumb. References scroll independently.
- The message viewport wrapper clips its own children: a zero-height flex item
  can no longer let the padded scroller intercept adjacent reference controls.
- README changed one capability cell; index.html changed one existing caption.
  Public structure, CSS, scripts, attributes, assets, headings and historic
  measurement values remain unchanged. Existing screenshots are not relabeled
  as captures of this implementation.

## Evidence

- Original focused RED: three sizing failures and missing viewport module;
  viewport skeleton then reproduced three behavioral failures with one fallback
  passing. Review/compact RED reproduced two additional missing behaviors.
- Final pnpm test:web: **386 passed**, 51 files, all-web-tests-final.log.
- pnpm check:web passed, web-check-final.log. Production build passed,
  build-05.log; no product source changed after that build.
- Actual Edge offline component browser acceptance: **16 checks**, zero page
  errors and zero mutation requests, browser-06/result.json. Uses production CSS,
  actual WorkspaceHeader/composer/panes/scroller, 1440/1024/390px light/dark,
  input grow/clear/width/selection, emulated touch, existing IME and reading/pane
  contracts, synthetic 360/320px keyboard viewport, context access and shell
  rebinding. Screenshots were inspected.
- Public page: **6** responsive light/dark checks, zero page errors, loaded images
  and no horizontal overflow, public-browser.json. Initial external harness
  assumptions about section count and unloaded lazy images were corrected; the
  page itself was unchanged. Structural invariants are recorded in
  public-copy-invariants.json.
- Strict OpenSpec, browser-script syntax and whitespace checks passed.

## Review and reproduced layout corrections

Independent read-only review confirmed one important issue: an effect with an
empty dependency list kept the original shell node after Session replacement.
A focused keyed-node regression failed first and now passes with listener
cleanup/rebind. The browser also checks the replacement node and visible Send.
No Critical or Minor findings were reported. Additional compact-reference layout
work after that review was verified by the author, not independently rereviewed.

Browser RED records retain Send initially outside the short viewport and later
the message scroller intercepting the expanded summary control. Geometry and
elementFromPoint diagnostics isolated the padded scroll child extending outside
its zero-height flex parent; bounding the wrapper fixes the original touch/click
reproduction. Intermediate failures remain under browser-01 through browser-04.

## Validation limits

This is actual browser/component evidence and a static public-page check, not a
server-backed full workbench, physical phone, OS keyboard/IME, native desktop
window, real pinch-zoom or new Provider benchmark. Keyboard bounds and touch
inputs are emulated. Product data, backend, adapters, runtime permissions, API
configuration and old metrics were untouched. No dependencies installed and no
build outputs, temporary fixtures, screenshots or logs added to Git.
