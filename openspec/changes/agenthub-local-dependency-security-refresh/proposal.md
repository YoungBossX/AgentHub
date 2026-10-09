# Refresh local workspace dependency security

## Why
A fresh production audit reports 12 advisories in the existing dependency tree,
including Next.js, DOMPurify, sharp, source-map-js and baseline-browser-mapping.
The complete local build/test tree also contains brace-expansion advisories and
an unpatched braces recursion advisory. Historical zero-advisory evidence is
not a current result.

## What Changes
Apply compatible patched versions to the affected runtime and tool families,
keep Next and its ESLint config aligned, and verify local behavior. Investigate
the unpatched development-only dependency separately within this one security
task; do not hide raw audit results or equate a dependency finding with a proven
application exploit. Any local mitigation must have a bounded reproduction and
preserve normal glob behavior.

## Impact
Explicit dependency installation with lifecycle scripts disabled; limited
manifest, lockfile and, only if necessary, tracked package patch changes. No
Agent adapter, database, permission, product feature or deployment expansion.
