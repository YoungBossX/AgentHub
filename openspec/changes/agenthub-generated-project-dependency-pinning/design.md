## Finding boundary

The source is the selected-folder provisioning apply endpoint. For a validated
empty directory, `apply_project_provisioning` calls `_write_project_skeleton`,
which writes `frontend/package.json` and `backend/requirements.txt`. The setup
plan later offers approval-gated `pnpm install` and `pip install -r
requirements.txt` commands against those manifests.

The security invariant is that a source-controlled provisioning template must
select a reviewable direct dependency set. Registry tags, semver ranges, and
unversioned Python requirements are not acceptable in generated manifests.

## Patch strategy

Define one immutable-by-convention set of exact frontend and backend template
versions next to the provisioning defaults. Pin the generated `packageManager`
to the repository's verified pnpm release. Frontend versions come from the
current verified pnpm resolution for the Demo/Web toolchain. Backend versions
match `apps/api/requirements.txt`; add its pinned `httpx` because the generated
health test imports FastAPI's `TestClient`.

Keep dependency grouping, scripts, install approval, target registration, and
the repair path unchanged. Focused tests compare the full dependency mappings
and requirements list so a later moving tag, range, deletion, or addition is
visible in review.

## Evidence boundary

Exact generated manifests and package-manager selection make direct dependency
resolution stable. They do not freeze transitive JavaScript or Python
dependencies. The first approved pnpm
install creates the external project's lockfile, which must be retained and
used with frozen-lockfile semantics for full JavaScript graph reproducibility.
Python transitive locking remains outside this focused task.

## Validation

Capture a RED provisioning regression against the moving manifests, then run
the focused provisioning suite, adjacent target/runtime checks, the complete
API suite, strict OpenSpec validation, candidate whitespace checks, and one
fresh independent read-only review.
