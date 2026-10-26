# Verification ledger

Evidence root: `E:/Docker/AgentHub/readiness-20261025-01`.
Base HEAD: `1c0e54ed4fe85e3051a764cfbb643a2b47240830`, existing dev checkout.
No commit/push or implicit dependency installation authorized.

## 1.1 Startup diagnostics

- Baseline: actual Windows EACCES on 127.0.0.1:8000, excluded TCP 7963–8062;
  old doctor called this occupied/unavailable. Explicit API 18000 doctor passed.
- RED: 19 launcher tests, 11 passed / 8 failed, `startup/red.log`.
- GREEN: launcher 19/19; complete local tools 31/31, `startup/green.log`,
  `startup/local-suite.log`. Existing real occupied listener survives.
- Real default doctor exits 1 with actual EACCES/range and probed 18000 suggestion;
  explicit 18000 doctor exits 0. No API/Web/Provider started by doctor.
- Independent read-only review found no blocker and reran 19/19. Two suggested
  branch cases (Web command and Windows EADDRINUSE query exclusion) were added
  as test-only coverage without changing product code; final launcher 21/21 and
  local tools 33/33. Original RED and first GREEN remain preserved.
- Syntax, whitespace and strict OpenSpec passed. No product data or runtime
  process was changed by this startup-only task.

## 1.2 Final pre-freeze engineering

- Extracted pipeline and provider-selection responsibilities; nine extracted AST bodies
  are equivalent after explicit parameter substitutions; other 60 engine functions unchanged.
  Independent engine review found no blocker. Focused before/after: 522/522 each.
- Chinese operator entrypoint: 17 offline tests passed; prepare-only five scenarios
  produced no model calls and verified source/product/config preservation. Independent
  review findings on report invalidation, preparation failure and bytecode were fixed.
- Original complete API: 2908 passed, 2 failed, 19 skipped. Both failures were Windows
  path length in cleanup fixtures. Short E-drive root cleanup retest: 12 passed.
- Final API: three disjoint whole-file shards, 146 files, 2946 unique case IDs;
  2927 passed, 19 skipped, zero failure/error. JUnit aggregate: api-final-aggregate.json.
  Shard durations 600.03 / 649.60 / 645.07 seconds. Original failures remain archived.
- Root check passed; Web 386 passed; demo API 5 passed; local tools 33 passed.
- No real model calls yet at this gate. Subsequent ten-task cohort is separate from
  historical 50-task evidence; source/config preservation is checked before reporting.

## 1.3 Interrupted upstream attempt; task remains open

E:/Docker/zh25-01: three Planner timeouts, fourth workflow in progress when user
requested waiting for a model switch. Direct minimal transport diagnostics returned
HTTP 500 InternalServiceError (separate probes, not workflow samples). Revalidated
owned evaluation process tree was stopped; raw report-before-user-pause.json retained.
Report is interrupted with null rates. execution-state.json is an operator stop record,
not an automatic finalizer success. Local model settings changed as user requested;
see preserved-at-user-pause.json for separate product/config hashes. Do not combine
this partial outage run with a later fresh cohort. Tasks 1.3 and 1.4 remain unchecked.

## 1.3 Frozen natural cohort and separately versioned fixes

- Switched local provider after upstream outage; configured deepseek-flash direct
  transport HTTP200 and isolated CLI exit0. Diagnostics are separate from tasks.
- E:/Docker/zh25-02: ten natural workflows, five categories twice, no fault injection.
  Completed/frozen, strict first/final8/10; business8/10. Both contacts frontend
  attempts timed out. Independent reconciliation:12phases,24attempts,12Planner calls,
  41225 events,22 Diff hashes; all SQLite quick/FK checks and source/config/product
  preservation passed. Cohort d00ce229b5e9c0858431259e4a8ec4b282e74ac9bdfcbc157b77644853c39327.
- 36 logical call/attempt records,34 complete Token receipts, known890826 Token,
  2 unknown, full total null. Pipeline nearest-rank P50/P9566.656/726.469 seconds.
  Model alias, fixed repetitions and application timing limits remain explicit.
- Closed cohort before edits. Real-Git retry incorrectly rejected unchanged prior
  backend file because creation checkpoint predated execution; exact owned ScopeEntry
  comparison now allows it. CLI thinking_tokens/ui_invalidate notifications no longer
  become persisted task states; initialization/unknown/text/usage/terminal fences remain.
  External RED14:4failed/10passed; new retry8/8 and Claude27/27 GREEN. Broader related
  722passed/2skipped, syntax/strict/whitespace passed; independent review no blockers.
- Separate copied fixture E:/Docker/zretry25-01: actual coding retry admitted, frontend
  completed and contacts28/28 passed, then native backend QA scope violation. Separate
  E:/Docker/zqa25-01 trace confirms five bound Reads then unlisted Read; rejected,
  not relaxed. Added exhaustive relative Read manifest to instruction only (no parser,
  tool, permission or validation change). RED1 then related native suites92passed;
  independent review no blockers. Closed each earlier episode before source changes.
- C frozen QA retry E:/Docker/zqa25-02: two native review runs completed with verified
  full-read/structured receipts and8 bound Reads plus2 StructuredOutput events, no unlisted Read; backend passed,
  frontend warning with3 low findings. All original tasks completed and business28/28,
  but strict recovery remains FAILED. Native receipt verification is separate from
  assessment status. Product/config/original evidence preserved. Extra5 provider
  attempts across3 corrective episodes are not part of the natural10 denominator.
- corrective-independent-verification.json independently reconciles these facts.
  No claim of10/10, billing accuracy, HTTP/UI/preview or production performance.

## 1.4 Actual current HTTP/UI/preview handoff

- E:/Docker/rd25 keeps all copies/output. Installed Next runtime copied/hash-checked,
  UI sources copied/read-only; no dependency installation. Existing X .next junction
  and original frontend sources remain unchanged. Windows copies use short E paths.
- First actual browser history readback passed HTTP/iframe transport but correctly
  showed expired fixed-validation policy after platform fixes. Retained as diagnosis,
  not qualified current acceptance. A first new HTTP request selected builtin @qa
  rather than native Profile and failed SCRIPTED_MOCK_MUTATION_FAILED; retained.
  A preparation retry hit an existing isolated CLI-config folder before any task call;
  its log and metadata recovery are retained. No failure was relabeled passed.
- Fresh current-version case explicitly bound native aliases; HTTP201 message
  930a066d-f28d-4d30-a6af-71faee0e6877, Session e2f45745-dcb4-43ac-be35-4fbb10980aaa.
  Actual server queue completed two claude_code runs; native planning observed,
  current native QA passed with verified receipt, independent multi-file acceptance
  passed. Source policy unchanged, snapshot archived. This is separate from natural10.
- Actual platform Preview HTTP201 healthy, URL was loopback port61672. Sandboxed
  Edge156.0.4314.42 opened actual workbench/Diff/current native QA/iframe and desktop/
  390px preview. Seven current screenshots, zero page errors/failed HTTP responses.
  Browser capture performed no model requests and is history readback; preview really
  started during capture. Viewport simulation is not physical mobile/IME verification.
- Actual finite HTTP SSE replay381 frames at captured high water, unique cursors;
  query-after and Last-Event-ID continuation matched. Raw .sse and receipts retained.
  Current Git patch947bytes matches persisted writer Diff hash; readable process export.
- README/index minimal content changes: HTML tag/attribute signature unchanged,
  README headings/order unchanged, existing public image bytes untouched. Static
  landing copy passed six 1440/768/390 light/dark browser checks. Runtime logs,
  screenshots and builds not copied into Git. Demo guide corrects legacy migration text.
- Teardown: stop Preview through actual control endpoint; terminate only revalidated
  owned API/Web process trees. Owned ports13025/18025/61672 closed. Remove only
  this operation's revalidated dependency symlinks; original measured fixture restored
  with matching source/DB hashes. Product/config and UI sources unchanged; copied
  SQLite quick/FK checks pass and final backup retained. final-preservation.json passed.
- Final source verification commands and checklist status are recorded after this ledger.
  No project commit/push, new remote CI result, Docker requalification or deployment.

Final gate: 189 current API/operator Python files compiled in memory without
writing bytecode; local tools33/33; strict OpenSpec and whitespace passed.
No staged files, no project commit/push. Later task checkbox marked only after
current HTTP/native/preview, six public layouts and preservation gates passed.
