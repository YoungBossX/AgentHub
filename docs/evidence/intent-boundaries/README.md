# Intent boundary evidence

- `offline.json`: versioned authored corpus result and same-negative-case parser
  comparison against `bc839966e3bb56a48f65f71bf56484e25646efb8`.
- `verification.json`: current source/corpus/test hashes, final JUnit totals,
  checked commands and local-only evidence limits.
- `ci-followup.json`: the first remote failure on `531bb89`, its native group
  routing repair, subsequent local regression receipts and updated source hashes.
  Earlier receipts retain their original local validation snapshot.

See [acceptance review](../../intent-boundaries-review.md) and
[usage/schema](../../intent-recognition.md). A zero negative-case mismatch count
is not a global safety, real-provider accuracy or full-workflow success guarantee.
