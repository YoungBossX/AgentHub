## 1. Focused maintainability extraction

- [x] 1.1 Extract independent execution ownership and task-card data/plan/artifact responsibilities while preserving existing entrypoints, exact state/safety and UI behavior; verify meaningful existing regression coverage and source equivalence, then reconcile current documentation and overall completion evidence.

Verified: eleven ownership definitions and 74 remaining engine definitions, 28 moved frontend declarations and twelve remaining entry declarations compared against the saved baseline; 548/1 POSIX-only skip lifecycle/safety, 139 adjacent tests, Web 326 and lint/types/root/strict checks. Initial global-DB schema failures and correction recorded; no product runtime or real Provider claim. See docs/execution-card-modularity-review.md.
