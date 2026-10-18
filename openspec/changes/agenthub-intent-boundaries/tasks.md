## 1. Intent recognition boundaries

- [x] 1.1 Implement shared decision/evidence, conservative rule boundaries and routing enforcement; verify negation, questions, quoted/code input, multi-action and missing/oversized slots through parsers and production planning, preserve supported demo/direct/group/LLM paths, run the frozen offline corpus and relevant regressions, and document results and limitations.

Verified locally: authored corpus 73/73; same 49 negative parser cases 23 baseline
matches versus 0 current; final API regression 448 and adjacent context/selection/
provider contract 45 passed; root check, final API syntax, strict specification and
whitespace checks. No real-provider/browser/remote-CI claim. See
docs/intent-boundaries-review.md and docs/evidence/intent-boundaries/.
