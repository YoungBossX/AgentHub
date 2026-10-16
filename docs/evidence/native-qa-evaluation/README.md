# Native QA evaluation evidence

2026-10-16. These are isolated CLI workflows, not product database/UI/SSE or
production-deployment acceptance. No mock transport output is counted as live.

| Evidence | Status / interpretation |
| --- | --- |
| [pilot.json](pilot.json) | One real backend pilot: native Planner, Codex writer and Claude read-only QA; first attempt passed, no retry, independent ASGI checks and immutable inputs passed. Execution 91.891 s, coding run 52.697 s, QA run 18.247 s; total including preparation 93.063 s. This single pilot is not a general success estimate. |

The pilot cohort is
`0789f80faf6b3e8c94e4d5479954517886e6bd455456c3a8ba8c9004f3c49d82`.
The expanded ten-sample cohort completed separately:
`dd27e0051a7b422a84af09a11da212b3eee6bc024b3145c6da93a87d62419565`.
Its selected five categories each have two repetitions; the platform source/
policy map matches the pilot, but the selection identity differs. Do not merge
the pilot into that ten-sample denominator. [batch.json](batch.json) records all ten samples: first attempt 4/10, final 6/10; natural 4/8 first/final, injected 0/2 first and 2/2 final with two explicit retries. Ten native QA attempts have verified receipts. Four failures remain (one type warning, one Planner timeout, two context-budget rejections); see [inspection](../../native-qa-evaluation-review.md). The process exited 1, with cohort frozen and unchanged. No failed sample was replaced.

The JSON is a bounded metadata selection from its original report; the original
SHA-256 and directory name are retained. It preserves cohort source policy,
case/phase outcomes, first/retry/timing counts, source hashes, actual native
provider observation, full-file Read/assessment/source-binding receipts and
independent acceptance identities. It omits source prose, prompts outside the
frozen scenario declaration, CLI logs and private paths. Hashes detect mismatched
records; they are not an external cryptographic attestation of model quality.

Original pilot:
`C:/Users/XCC/AppData/Local/Temp/agenthub-native-qa-pilot-23de161e-ee33-45b4-84d4-999effcca280`.
Expanded run:
`C:/Users/XCC/AppData/Local/Temp/agenthub-native-qa-batch-c43191aa-9464-482e-b56a-ee4d117e78ce`.
Raw reports and SQLite retain execution details; this export does not replace
them or rewrite previous v1 scripted-QA failures.
