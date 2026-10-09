# Reliable local Claude execution

Windows coding and health checks can select an npm shim that CreateProcess cannot
launch. Restricted Claude execution ignores user settings, including the user's
SDK authentication and model transport. Preserve containment while resolving the
installed native executable and passing only approved provider environment fields.

## Impact
Existing Claude coding, read-only review, CLI health and Planner launch plumbing.
No new adapter, dependency, user configuration writes, or broader tool permissions.
