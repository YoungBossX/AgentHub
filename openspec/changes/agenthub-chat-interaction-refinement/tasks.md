## 1. Chat interaction refinement

- [x] 1.1 Implement all six user-specified chat refinements with focused regression tests, preserve existing behavior/data boundaries, verify responsive themes and actual browser interactions, and record the change log and acceptance evidence.
- [x] 1.2 Investigate the source-delivery CI failure, reproduce the supervisor-generation test startup timeout with delayed real preflight, retain its race assertions while bounding startup waits appropriately, and verify locally for authorized redelivery to dev. Exact-commit CI is a separate delivery gate, recorded externally until it completes.
