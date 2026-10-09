# Validate write completion and diagnose Codex file access

## Why
The external benchmark observed Codex turn completion without file edits. Model text claimed read-only access, but no tool attempt established the cause. The engine currently accepts scoped write runs with zero new changes as completed.

## What Changes
- Compare the existing isolated Codex invocation with an explicit Windows native sandbox selection using disposable fixtures and unchanged workspace-write/no-approval policy.
- If verified, supply a fixed platform sandbox override without loading user config or widening filesystem/network access.
- Require newly observed changes and a nonempty collected Diff for write TaskRuns before successful Review and downstream execution. Preserve read-only runs and generation fencing.
- Persist bounded completion evidence and failures; rerun the external suite without replacing prior failed evidence.

## Impact
One focused runtime reliability task. No new adapters, dependencies, database entities, automatic fallback, commits, deployment, or broad platform features.
