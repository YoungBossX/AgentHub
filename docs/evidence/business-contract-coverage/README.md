# Business-contract receipts

`contracts.json` is the first real disposable-source positive receipt after adding
the v2 business contracts: thirteen syntax/API checks, legacy ten browser checks
and eighteen resilience checks. It includes both source and selected-policy
fingerprints, real browser version and labeled synthetic 503 metadata. No actual
Provider, product HTTP/SSE/UI or deployment was exercised. Negative source
controls are verified in `apps/api/tests/test_business_contracts.py`.

See [inspection and revision limits](../../business-contract-coverage-review.md).
Later harness changes require a new receipt; never overwrite this historical one
or substitute it into the previous native-QA cohort.


`contracts-final.json` is the current final receipt after non-object JSON and
list-content preservation hardening. Both v1/v2 browser contracts and all thirteen
backend checks passed on real disposable inputs. It links the 70-test JUnit report
hash and the 29 focused business-case names/durations; other tests in that batch
preserve existing backend guards. Synthetic failures remain labeled. Its source/
policy fingerprints differ from the initial receipt; do not merge versions.
