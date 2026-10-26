# Contacts review regression repair

## Why
The preserved Chinese contacts case passes the v3 business contract (28 checks),
but native QA identifies misleading empty/error states and unused login styles.
Those findings belong to the generated example, not the platform's login demo.

## What Changes
- Add an opt-in v4 fixed contract retaining the v3 checks and covering initial
  GET failure and real POST-201 responses with invalid JSON, with/without GET
  reconciliation. Keep v1-v3 identifiers, checks and historical verdicts intact.
- Repair a fresh external copy of the failing case using the existing native
  coding/review adapters. Remove login styles only where actually unused.
- Preserve original data/configuration/results and record corrective results
  separately; all runtime data and temporary files remain under E:/Docker.

## Scope
One focused regression task. No new permissions, dependencies, adapters, database
changes, timeout increases, automatic POST retries, commits or pushes.
