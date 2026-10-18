## 1. Intent recognition boundaries

- [x] 1.1 Implement shared decision/evidence, conservative rule boundaries and routing enforcement; verify negation, questions, quoted/code input, multi-action and missing/oversized slots through parsers and production planning, preserve supported demo/direct/group/LLM paths, run the frozen offline corpus and relevant regressions, and document results and limitations.

Verified locally: authored corpus 73/73; same 49 negative parser cases 23 baseline
matches versus 0 current; final API regression 448 and adjacent context/selection/
provider contract 45 passed; root check, final API syntax, strict specification and
whitespace checks. No real-provider/browser/remote-CI claim. See
docs/intent-boundaries-review.md and docs/evidence/intent-boundaries/.

- [x] 1.2 Fix the exact-commit CI regression for native multi-file/coordinated group planning: allow planner-required groups only after a validated native plan, keep unavailable/failed/non-task plans from persisting detached tasks, reproduce both workflow failures and verify negative controls before delivery.

Verified locally: routing/group/recognition 260 passed; workflow evaluation/native
QA/scoring 53 passed, including both failed complete workflows; API syntax and
strict specification passed. First remote failure retained in ci-followup.json;
follow-up remote result must be checked against the pushed fix commit.
