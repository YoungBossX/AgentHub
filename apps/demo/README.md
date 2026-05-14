# AgentHub Vite React Demo App

This is the fixed P0 agent-modified demo app at `apps/demo`. It is intentionally
Vite React only; do not replace it with Next.js or broaden it into a framework
matrix.

Install dependencies during setup:

```bash
pnpm demo:setup
```

Start the app with the same command shape the future preview runner will use:

```bash
pnpm --filter @agenthub/demo dev --host 127.0.0.1 --port <port>
```

The repo-level convenience command uses port 5173 by default:

```bash
pnpm demo:dev
```

Agent execution must not run dependency installation. `node_modules` may be
created by setup only and remains a protected path.

Deterministic mutation targets:

- `data-agenthub-target="login-page-slot"` marks the area where a later adapter
  can add a login page.
- `data-agenthub-target="primary-action-button"` marks the button text for the
  follow-up request: "make the button text more friendly".
