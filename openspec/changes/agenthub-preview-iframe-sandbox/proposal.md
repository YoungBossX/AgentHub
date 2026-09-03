## Why

The right-side artifact panel embeds agent-modified Vite output in an iframe
without a `sandbox` policy. The preview is deliberately untrusted application
code, so browser same-origin rules alone do not prevent it from attempting
top-level navigation, opening auxiliary windows, initiating downloads, or using
browser capabilities that the AgentHub shell never intended to delegate.

The backend already creates Preview URLs on a dedicated loopback port. The UI
must preserve interactive React/Vite behavior while making the iframe capability
boundary explicit and reviewable.

## What changes

- Add one fixed least-privilege sandbox policy at the only Preview iframe
  rendering boundary.
- Preserve scripts, forms, and Preview-origin storage/resources required by the
  local Vite React workflow.
- Do not grant top navigation, popups, downloads, modals, pointer lock, or
  presentation escape capabilities.
- Explicitly deny sensitive delegated browser permissions and suppress the
  parent-page referrer.
- Lock the exact positive and negative capability set with focused DOM tests.

## Out of scope

- Proxying Preview traffic, rewriting the generated application, or adding a
  broad Content Security Policy service.
- Blocking all network requests made by Preview code.
- Changing Preview process startup, loopback binding, health checks, or Vite HMR.
- Generated-project dependency pinning or SSE backpressure.
