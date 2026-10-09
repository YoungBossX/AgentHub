# Windows connection cleanup

## Why
The attachment acceptance API logged a real Windows 10054 error in CPython's
Proactor connection-lost cleanup, then hung after closing its listening port.
The installed callback calls socket.shutdown before closing/detaching the
transport; a reset can skip that tail and leave Server.wait_closed waiting.
The managed launcher already has a graceful timeout, but timeout/forced cleanup
does not repair the connection accounting defect.

## What Changes
Add narrowly matched, application-lifespan-owned recovery for this exact Windows
Proactor socket-shutdown failure. Finish the interrupted close/detach exactly
once, keep unrelated exceptions observable, and restore prior loop handlers.
Preserve default event loops, native subprocess support, task ownership, SSE
replay, preview cleanup, database content and existing shutdown timeouts.

## Impact
One local-runtime fix and targeted tests/evidence. No dependency installation,
global Python monkeypatch, new adapter, task resumption claim or deployment.
