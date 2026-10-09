# Preserve literal copy in scripted JSX output

## Why
The current scripted button/heading replacement writes targetText directly into
JSX. Braces, tags and entities can become code or markup instead of the requested
copy. A scope-valid Diff and healthy Vite process do not prove React rendered it.

## What Changes
Encode sensitive copy as a JavaScript string literal in a JSX text expression,
with closing-tag characters escaped so subsequent bounded replacements remain
safe. Use callable regex replacement to preserve literal backslashes. Keep
ordinary copy source compatibility and the existing task/path/no-op boundaries.

## Impact
One ScriptedMock template repair. No new adapter, broader intent/target support,
generic functional-completion contract, dependency, migration, UI redesign,
history rewrite or production deployment.
