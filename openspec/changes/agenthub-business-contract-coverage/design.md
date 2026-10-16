# Fixed contracts and independent negative controls

Extend the existing server-owned Python ASGI harness, never importing edited
target tests or running their configuration. Preserve its temporary copy,
source/policy/generation currentness, cancellation and process/file/network guards.
The contract follows existing ContactCreate constraints; it does not introduce
case folding, whitespace normalization, authentication or durable storage rules.

The existing sandboxed Playwright/ASGI bridge accepts only a fixed contract enum.
Legacy v1 retains ten checks. Resilience v2 runs eighteen exact named checks over
desktop and 390px, using random fresh records, actual API responses and DOM state.
Reject missing/wrong-version/incoherent receipts. Inject a single labeled 503 in
the trusted route (not backend code) and prove a later real POST/GET/reload works.
Require visible accessible error feedback and retained form/list after rejection.
Update the coordinated scenario's frozen prompt to state these expectations.

Include contract, exact check IDs, frontend/backend source and validation-policy
fingerprints, runner/bridge/harness digests in integration identity; verify
original and copied input immutability and policy currentness after execution.
Do not relabel this in-process ASGI transport as a live HTTP preview. Existing
product QA continues to say configured checks, not arbitrary business acceptance.

Verify real positive copies and realistic source mutations: loose field limits,
wrong defaults/IDs, missing duplicate protection, ignored POST errors, optimistic
failed rows, cleared input on failure and no recovery. Parser tests alone cannot
establish that browser/API contracts detect defects.
