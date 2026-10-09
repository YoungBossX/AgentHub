# Style the actual scripted login form

## Why
The previous fresh fallback acceptance rendered email/password fields with browser
defaults. ScriptedMock creates the form but never adds its stylesheet rules, so
the demo is functional as a mutation fixture but poor as a personal-project result.

## What Changes
Add a bounded, managed login-form CSS block to the assigned demo stylesheet when
creating the scripted login template. Improve semantic input attributes, spacing,
full-width controls and visible keyboard focus. Preserve other source/styles and
copy-only follow-ups. Prepare both outputs before writing and restore originals
if a write fails; report failures honestly.

## Impact
One local template repair. Keep the three adapters, task bindings, scope/queue and
Preview gates. No dependency, auth implementation, product UI redesign, migration,
installation, history rewrite or deployment.
