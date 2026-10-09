# Design

Use `data-theme` on the document root and shared CSS palette tokens. Keep the
approved light palette as the default. A small external store reads the root
attribute via `useSyncExternalStore`, publishes explicit changes and handles
storage events from other tabs. Store only `light` or `dark` under a dedicated
localStorage key; failures must not prevent the current page from switching.

Initialize the preference with a fixed beforeInteractive root-layout script;
the server snapshot stays light and root hydration differences are suppressed.
The toolbar button exposes the action (switch to dark/light), current pressed
state, and focus indication. Existing neutral/status utility colors are mapped
centrally for dark mode; SVG graph fills use semantic tokens and Monaco follows
the same store. Do not recolor sandboxed preview documents or alter iframe policy.

Verify persistence, storage failure, tab synchronization, malformed preferences,
Monaco theme selection, and actual light/dark UI rendering at normal/narrow sizes.
