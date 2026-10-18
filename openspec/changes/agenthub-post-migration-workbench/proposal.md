# Post-migration workbench verification

## Why

The user requested recovery of the two previews stopped during local database
maintenance, a fresh execution/Diff/preview acceptance run, and a balanced message
composer. The existing composer bottom-aligns unequal controls around a nested
input surface, making its padding and alignment appear inconsistent.

## What Changes

- Restore the two preview outputs through the existing guarded restart path;
  preserve historical records and verify actual HTTP/browser output.
- Run a bounded task in a new Session and retain execution, Diff and preview
  evidence, distinguishing real-provider execution from fallback.
- Put the existing textarea above a shared attachment/send toolbar with equal
  vertical alignment and outer padding; retain keyboard, attachment, context,
  theme and disabled-state behavior.

## Impact

Local single-user operation and a focused composer layout change. No new adapter,
permissions, dependencies, database schema, deployment, commit or push.
