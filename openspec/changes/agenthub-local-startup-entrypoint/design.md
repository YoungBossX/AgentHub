# Design

Use Node standard libraries for CLI validation, installed Next CLI resolution,
Python environment selection, loopback port checks and process supervision. Match
the existing .venv/shared-main-checkout/Conda resolution, with an invalid explicit
Python override reported instead of silently ignored. Require the repository's
Node version range and Python 3.11+. Doctor imports dependencies without importing
the application, initializing SQLite, running provider tools or installing anything.

Launch the installed Next CLI directly, avoiding platform-dependent shell quoting.
Only pass system/public environment keys and the explicit BACKEND_URL to Web;
keep backend configuration in the API process. Use matching FRONTEND_ORIGIN for
custom Web ports. Validate separate numeric ports and reject browser-restricted
Web ports. Optional demo API always uses 5174, matching the target registry.

A small Python wrapper serves uvicorn without reload and accepts stop/EOF on a
private stdin pipe, allowing Windows normal shutdown to run FastAPI lifespan
cleanup.
The control pipe is duplicated privately and process stdin/Windows standard input
is set to the null device so Git/CLI children cannot inherit or consume it. Real
Windows worktree creation initially blocked until EOF without this separation;
verify a child can read stdin to EOF while the launcher pipe remains open.
The null standard-input descriptor must remain inheritable across POSIX exec;
only the separate control descriptor is non-inheritable. Exercise child commands
with both close_fds modes and include bounded stderr in regression failures.
Platform simulations in the CI regression suite replace a module-local OS view,
never the shared os.name used by pathlib and pytest on the actual host.
It reports readiness only after uvicorn has bound its socket. Wait for
the Next CLI's ready message and HTTP response before reporting the workspace
ready. Timeouts, failed binds, child exits and interrupts stop spawned siblings;
never adopt or terminate pre-existing listeners. Normal exit allows API cleanup
before bounded forced termination; Windows taskkill targets a live owned child
tree only. Hard termination of the launcher is not guaranteed graceful shutdown.

Keep existing development/reload commands for editing API source. Test meaningful
port/dependency/configuration/readiness/failure/cleanup cases using Node's built-in
runner; verify real Windows startup, custom-origin requests, fresh SQLite seeding,
history preservation across restart and process/port cleanup. Update README,
local usage, guardrails' developer commands and delivery evidence. No real model
execution needs repeating for startup-only changes.
