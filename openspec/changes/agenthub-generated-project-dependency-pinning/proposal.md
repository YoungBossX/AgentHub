## Why

The selected-folder provisioning path writes a runnable Vite React/FastAPI
skeleton, but every generated JavaScript dependency uses the moving `latest`
tag and every generated Python requirement is unversioned. An approved setup
therefore resolves a different direct dependency set over time and can ingest
an incompatible or newly compromised release without any source change.

## What changes

- Replace every generated frontend `latest` tag with an exact version from the
  repository's currently verified dependency snapshot.
- Declare the repository's verified pnpm release in the generated manifest so
  Corepack does not select a moving package-manager version.
- Pin every generated backend direct requirement and declare the `httpx`
  dependency required by the generated TestClient test.
- Lock the complete generated manifests with focused provisioning regression
  tests while preserving the existing approval-gated install flow.
- Document that exact direct dependencies do not replace a generated project's
  own lockfile for transitive reproducibility.

## Out of scope

- Embedding or synthesizing a pnpm lockfile before the approved install step.
- Freezing Python transitive dependencies or introducing a Python lock tool.
- Changing the Vite React/FastAPI scaffold, approval policy, package-manager
  family, external target registration, or repair-existing-scaffold behavior.
- SSE backpressure or final release-candidate cleanup.
