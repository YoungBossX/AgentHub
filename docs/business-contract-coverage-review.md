# Explicit contacts business acceptance

2026-10-16, item 2 of the ordered objective. Local source and disposable copies;
no installation, product restart, commit/push or deployment.

## Covered behavior

The trusted backend contract is now `agenthub.backend_contract.v2`: one syntax
check plus twelve ASGI groups. Existing health/list/create/validation/duplicate/
CORS/OpenAPI assertions remain. New groups check exact maximum name/email/company/
status lengths and rejection above each limit, body/field type and malformed JSON
rejection without mutation, two minimal creates with default company/status and
stable unique string IDs, seeded duplicate non-mutation and unsupported methods.
These follow current API declarations; no new normalization/case-folding rule is
invented. Source/policy/generation binding and fixed temporary-copy guards remain.

The integration checker retains explicit `contacts-create-v1` (ten checks) and
adds `contacts-resilience-v2` (eighteen). The latter checks initial real API data,
actual create, duplicate 409 feedback, browser empty/invalid-email rejection,
retained form/list after one trusted synthetic 503, successful real retry,
persistence after reload, layout and runtime on 1280px and 390px widths. The
coordinated workflow prompt now explicitly requests these requirements and
freezes the selected contract in its scenario manifest. V1 native-QA cohort
results are not relabeled as having this new coverage.

Integration receipts identify the contract, exact checks, both source fingerprints
and the selected policy (runner, bridge, browser/build harness and both validation
policies). Original/copy inputs and policy are rechecked after execution. Missing,
wrong-version, partial, contradictory, stale, cancelled and timed-out evidence
cannot establish pass. Synthetic 503s are labeled in request metadata and do not
count as actual backend failures; successful retries use the real ASGI app.

## Evidence and limits

The first actual business/adjacent-backend batch passed **64 tests / 125.30 s**.
It includes real API copies and browser controls for ignored response errors,
cleared failure inputs, optimistic failed rows, no recovery and missing browser
validation; backend controls loosen company length, change defaults/IDs, bypass
seed duplicates, weaken optional types and expose unsupported methods. Parser/
source-policy/cancellation doubles are distinguished by their test names.
Final list-preservation/parser hardening is verified. Both gaps were reproduced first: five non-object JSON receipts raised AttributeError, and a real browser accepted changed existing contact names when only list count was compared. Those failing controls are retained in the external before-fix logs; the fix must make both controls pass.

The first standalone positive receipt in
[contracts.json](evidence/business-contract-coverage/contracts.json) records real
Python/ASGI syntax+business checks and sandboxed Edge v1/v2 browser checks, with
source/policy identities. It evaluates no model and does not replace the negative
controls or prove product UI/SSE, a live HTTP backend preview, authentication,
concurrency, durable storage, case-insensitive duplicates or arbitrary business
requirements. Existing product QA still labels this as configured-check coverage.
The source revision and final receipt status must be checked before treating an
older positive receipt as current.

Final business/adjacent-backend verification: **70 passed / 131.80 s**, including
all six real browser defects, six real API defects, non-object receipt rejection,
source/policy/cancellation controls and preserved backend guard tests. The
[Junit-linked final receipt](evidence/business-contract-coverage/contracts-final.json)
records 29 focused business cases and the 70-test batch hash; both legacy ten and
resilience eighteen actual browser checks passed again at this final revision.
Final receipt SHA-256:
`e3fb5d27b82e7a5d1355849eb67694880de10942e9b26b35c12d1e2baa66a84a`.

Existing workflow/native-QA compatibility: **53 passed / 396.02 s**, before the
last local parser/list-content assertions. Adjacent native-review/layered QA:
**55 passed / 19.65 s**. Batches overlap and are not added into a unique total.
Root `pnpm check` passed after adding the installed Git Bash to this process PATH;
the first attempt lacked Bash and failed at the API wrapper. Final Node syntax,
strict OpenSpec and final 70-test batch passed after parser/list hardening.
No new whole-API or remote CI claim is made. External logs are
`agenthub-business-20261016b.log`, `agenthub-business-final-20261016.xml`,
`agenthub-business-workflows-20261016.log`, `agenthub-business-qa-20261016.log`
and `agenthub-ordered-rootcheck-20261016b.log` under the local Temp directory.

Item 2 is complete locally. Item 3 was completed afterward in the separate
[execution/card extraction](execution-card-modularity-review.md). All three scoped
items are complete locally; their different revisions/evidence scopes stay separate.
