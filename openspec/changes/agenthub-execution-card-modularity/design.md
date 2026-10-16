# Ownership authority and presentation boundaries

The backend ownership module depends only on lower-level model, scope, scheduler,
queue and task-run modules, never on run_engine. Move immutable ownership records,
exact owner/queue/lock comparisons, token capture and transactional lease renewal.
Retain compatible run_engine names. Keep orchestration/controller and finalizer
commit/launch fences in the engine; clock forwarding wrappers preserve the
existing injection seams without duplicating checks. Preserve BEGIN IMMEDIATE,
conditional writes, rollback and exact execution-generation identity.

Frontend data parsing remains pure and central; plan summaries and artifact cards
are children of the existing client boundary. TaskCardList retains asynchronous
artifact loading, selection/error state and orchestration. Preserve every JSX
label/class, callback, disable condition, artifact provenance and action order.
Keep ArtifactContextIntent available from its existing import path using a type
re-export. Do not introduce a server/client boundary with callback serialization.

Verify moved implementations against the saved pre-edit source, then run existing
execution lifecycle/lease/generation/scope/approval/fallback/provider/parallel and
artifact regression tests. Run complete Web tests and lint/types, syntax checks,
strict OpenSpec and targeted browser control checks if available. Tests must
exercise the extracted modules through current entrypoints; no duplicate
implementation or tests that only assert line counts. Record before/after sizes,
actual validation scope and limits. Reconcile current docs without rewriting the
earlier frozen native-QA and business evidence.
