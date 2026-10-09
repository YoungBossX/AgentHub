# Design

Install an exception handler only for the active Windows Proactor loop during
the API lifespan. Recovery must match the actual standard-library bound cleanup
callback, ConnectionResetError/WinError 10054, its traceback at socket.shutdown,
and an unfinished closing transport. Do not classify unrelated protocol errors
or arbitrary callbacks by an error-message substring.

Complete socket close and server detachment without invoking protocol.connection_lost
again. Respect the installed Server detach signature (older counter versus newer
transport set). If the private implementation does not match, delegate the original
error instead of guessing. Log successful recovery; propagate cleanup failures
to the previous/default handler. Do not modify the Python installation or its
classes, change loop policy, suppress all resets or decrement another connection.

Restore the previous handler after normal exit or startup/shutdown failure, and
do not overwrite a handler installed later by another owner. Existing request
drain and task cancellation/lease behavior remains unchanged.

Evidence must separate the historical real browser reset from controlled fault
injection and ordinary TCP reset stress. Reproduce the leaked wait using the
actual stdlib callback and Server bookkeeping, then prove release/idempotence,
unrelated error visibility, lifespan integration, real API/browser/SSE recovery,
owned preview cleanup and persistence through the managed startup entrypoint.
Verify all relevant gates and update delivery boundaries before completion.
