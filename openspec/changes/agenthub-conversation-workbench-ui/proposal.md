# Deliver the approved conversation workbench

## Why
The current workspace buries chat beneath verbose task cards, uses oversized
headers and panels, and marks Diff availability from run completion rather than
artifact evidence. The approved light conversation design must also show the
collaboration process and results described in the supplied three-page PDF.

## What Changes
- Implement the approved light IM workspace, Agent contacts, and distinct
  conversation/process/results views with responsive navigation.
- Visualize persisted task dependencies and actual execution progress; expose
  bounded SSE event records alongside existing detailed controls and traces.
- Show real inline result cards and an expandable artifact inspector with the
  existing Diff, review, document and protected preview implementations.
- Derive stage readiness from actual latest-run and artifact evidence; preserve
  failed/stopped/historical distinctions and session isolation.
- Record PDF requirement mapping, functional regression and browser evidence.

## Impact
One frontend task. Preserve backend APIs, SSE recovery, adapters, write gates,
preview sandbox and mock deployment labels. No new dependencies, production
deployment, fake examples in product data, new providers or broad platform work.
