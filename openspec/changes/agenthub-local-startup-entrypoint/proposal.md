# Local startup entrypoint

## Why
The documented local startup requires two terminals and Bash on Windows, does
not connect custom API/Web ports automatically, and understates the Python
version required by datetime.UTC. A personal project needs a reproducible local
entrypoint with honest dependency, readiness and port diagnostics.

## What Changes
Add a portable, installed-dependencies-only local launcher and read-only doctor.
Start the product API and Web together on loopback; optionally start the built-in
demo API on its contract's fixed port 5174. Set BACKEND_URL and CORS consistently,
fail on occupied ports, and clean up only processes spawned by this invocation.
Document setup, configuration, actual workflow, restart and local limitations.

## Impact
One local developer workflow task. Preserve existing commands, adapters, database
and Agent execution boundaries. No dependency installation during startup,
schema change, provider probe, deployment or broad platform feature.
