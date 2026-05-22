# AgentHub Demo API

`apps/demo-api` is the isolated backend target for Backend Agent work. It is
application code for the demo app, not the AgentHub platform backend.

## Endpoints

- `GET /health`
- `GET /contacts`
- `POST /contacts`

The first scaffold uses in-memory contacts so agents can modify backend app
behavior without adding a cloud database, auth, tenancy, or production deploy.

## Commands

From the repo root:

```bash
pnpm demo:api:dev
pnpm demo:api:test
pnpm check:demo-api
```

The dev server runs on `127.0.0.1:${AGENTHUB_DEMO_API_PORT:-5174}`.

Frontend demo code may call this backend in local mode through
`http://127.0.0.1:5174`, but P6-4 does not wire the Vite app to this API yet.
