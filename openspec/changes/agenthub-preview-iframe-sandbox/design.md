## Finding boundary

The source is agent-modified Vite React code served from the persisted Preview
URL. `PreviewPanel` is the only sink that embeds that code into the AgentHub Web
shell, and the current iframe has no sandbox or explicit permissions policy.

The security invariant is that a Preview may execute and interact within its own
frame, but it must not receive browser-container capabilities unrelated to
rendering the local application.

## Patch strategy

Apply a static iframe policy directly at `PreviewPanel`. Allow only scripts,
forms, and same-origin behavior. Same-origin is required for ordinary Vite
module/resource loading and application storage; the Preview remains
cross-origin from AgentHub because the backend allocates a distinct loopback
port. Omit every navigation, popup, download, modal, pointer-lock, orientation,
and presentation sandbox token.

Add a restrictive iframe `allow` policy for camera, microphone, geolocation,
payment, USB, and clipboard access, and use `no-referrer` so the Preview request
does not receive the AgentHub page URL.

Keep the policy as module constants so the positive grant set has one shared,
auditable definition and tests can detect later broadening.

## Validation

Use a RED DOM test against the healthy Preview path, then prove the exact
sandbox/referrer/permissions attributes and the absence of dangerous tokens.
Retain the existing healthy/unhealthy, refresh, close, and artifact-selection
tests. Run the complete Preview component suite, Web lint/typecheck/Vitest,
strict OpenSpec validation, and one independent read-only patch review.
