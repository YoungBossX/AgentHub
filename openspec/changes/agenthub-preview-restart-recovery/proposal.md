# Preview restart recovery

## Why
An API restart loses its in-memory Popen registry. Existing Preview reads label
untracked processes as startup failures. Refresh also uses a stale selected
health flag, so a newly failed Preview may require a second click to restart.
Graceful API shutdown currently leaves owned preview subprocesses running.

## What Changes
Distinguish unavailable ownership from observed process exit, never signal
untracked PIDs, close owned preview processes on graceful shutdown, and let a
single explicit refresh/restart use fresh backend health state. Preserve old
artifacts and launch a new server-owned preview through existing scope gates.
Allocate browser-compatible high ports and retain the selected Preview while
independent artifact reads catch up, closing gaps found in real browser recovery.

## Impact
One local Vite Preview lifecycle task. No OS process adoption, arbitrary PID
cleanup, new dependencies, schema tables, provider execution or deployment.
