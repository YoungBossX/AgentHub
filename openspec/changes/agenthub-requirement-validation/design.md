# Bounded browser acceptance

Freeze a server-selected, versioned contract from the prepared plan before the
adapter executes. Only login_page, demo_heading_text and primary_action_button_text
on demo-frontend are supported. Expected copy is bounded literal data, never code
or a selector. Recheck the contract as well as source/policy at report reads.

After successful type check, build and smoke tests, execute a trusted Playwright
harness on the temporary output. Use a fresh headless browser context, browser
sandbox, no permissions/downloads/service workers, and HTTP/WebSocket interception.
Serve only bounded regular output files through intercepted requests at a fixed
synthetic origin; deny external traffic, popups and non-GET requests. There is no
local listening server and no user browser profile. This remains a bounded local
browser test, not a general hostile-code OS sandbox.

Login tests fill inputs, reject empty/invalid email submissions, and observe a
valid submit without network authentication. Copy tests verify visible literal
text and primary-button clickability. Run desktop and narrow viewports. Capture
named checks and bounded diagnostics from the trusted process, never page console
output as a success receipt. Missing browser, skipped checks or malformed output
cannot pass. Existing timeout/cancel cleanup and ownership fences remain active.

Keep requirement evidence separate from check/build/smoke evidence in QA. Passing
all layers establishes only the named requirement checks, never full application
correctness. Unsupported historical/generic plans retain configured-check semantics
and explicitly show no requirement coverage. Frozen historical receipts are not
upgraded on reads. Login form changes retain deterministic follow-up targets and
state explicitly that they do not authenticate accounts.

API references: [Playwright network interception](https://playwright.dev/docs/network)
and [browser launch options](https://playwright.dev/docs/api/class-browsertype).
Runtime setup is explicit: pinned Playwright dependency, installed Edge by default
on Windows or a prepared Chromium on Linux. CI installs its browser at setup time,
never during an Agent run. Browser host sandbox support is required; no fallback
silently disables it.
