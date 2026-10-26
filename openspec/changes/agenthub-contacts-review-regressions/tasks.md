## Ordered task

- [x] 1.1 Reproduce the three generated-case findings; add fail-closed opt-in
  regression checks without changing v1-v3 semantics; repair an external copy,
  verify fixed business behavior and current native QA, retain original results
  and configuration/data, and document separate corrective evidence.

Verified: final frozen five-suite regression 102 passed; API compile, script
syntax, strict OpenSpec and whitespace checks passed. Final native QA zero
findings, v4 38/38 and v3 28/28; independent source/receipt/Diff/event/database
checks passed. Historical failures retained. See verification.md.
