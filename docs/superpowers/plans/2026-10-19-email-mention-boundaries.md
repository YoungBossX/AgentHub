# Email and Agent mention boundary repair

Task: `agenthub-intent-boundaries`1.4. The real unquoted repair instruction was rejected with `400: Unknown mention @example` before any Planner call. This is a routing defect, not a Provider failure.

- [x] Add RED tests using real profile/SQLite fixtures for email domains matching known, unknown and disabled custom aliases; preserve email copy text, Chinese adjacent mentions, and explicit unknown/disabled failures. Initial14:9failed/5passed; Unicode extension4failed/14passed.
- [x] Share lexical helpers from `intent_decisions.py` with recipient selection and all mention stripping consumers. Exclude ordinary ASCII local-part/address tokens and Unicode letter/combining-mark local parts followed by a dotted ASCII domain while keeping Chinese adjacent aliases. Keep existing quote policy and all permissions.
- [x] Verify focused/adjacent338, authored corpus85/85, final root check and full pnpm test exit0: API2782/19skip/2warnings, Web333/tools24/demoAPI5. Source216plus3additional files frozen and rechecked. No dependency install, product migration or commit/push; new evidence uses E:/Docker.
- [x] Repeat the SAME rejected real repair instruction on frozen B1, preserving the rejected report. Real Planner plus4coding/review turns,2nativeQA passed and24/24 independent business checks. Frozen A remains unchanged; final Unicode repair B2 does not inherit B1 model measurement.
- [x] Independent source and resume/showcase review found no remainingP1/P2 or misleading claim. Evidence and task checkbox updated after verification. User explicitly confirmed retaining the2policy-denied pytest caches on2026-10-20; no further deletion attempt.

Source A and its10-case cohort are already frozen under E:/Docker/AgentHub/live-fixes-20261019/source-A-context-fix. Do not recompute those rates as source B results. Do not claim a complete RFC email parser or grant new recipients/tools from text recognition.
