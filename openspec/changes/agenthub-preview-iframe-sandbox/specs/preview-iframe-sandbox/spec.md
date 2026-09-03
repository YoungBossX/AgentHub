# Preview Iframe Sandbox

## ADDED Requirements

### Requirement: Embedded Preview code receives only rendering capabilities

AgentHub SHALL embed a healthy Preview with a fixed iframe sandbox that permits
scripts, forms, and Preview-origin behavior required by the local Vite React
workflow. The iframe SHALL NOT permit top-level navigation, popups, downloads,
modals, pointer lock, presentation, or sandbox escape into the AgentHub shell.

#### Scenario: A healthy Preview is opened in the artifact panel

- **WHEN** the selected Preview has passed its health check
- **THEN** its iframe receives exactly the approved sandbox tokens
- **AND** the Preview URL and refresh behavior remain unchanged
- **AND** no dangerous navigation, popup, download, or presentation token is
  present.

### Requirement: Embedded Preview requests disclose no shell referrer or sensitive permissions

The Preview iframe SHALL use a no-referrer policy and SHALL explicitly deny
camera, microphone, geolocation, payment, USB, and clipboard permissions.

#### Scenario: Preview code requests a browser capability

- **WHEN** the embedded Preview attempts to use a denied permission
- **THEN** the iframe container policy does not delegate that capability
- **AND** the initial document request does not include the AgentHub page URL as
  its referrer.
