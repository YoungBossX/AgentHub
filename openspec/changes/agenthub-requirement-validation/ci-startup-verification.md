# CI startup resilience verification

## Reproduced failure

Base commit: `ffd4ca4e4d924cc725aeaa708541ddd557dc07eb`.
The [dev run](https://github.com/YoungBossX/AgentHub/actions/runs/40296869833),
job 121484939582, failed before installing API dependencies or running project
checks. `chromium.launch` started system Chrome but did not connect within
30000ms. Its log also contains a DBus warning/error; that alone does not establish
the operating-system cause. The [same-source main run](https://github.com/YoungBossX/AgentHub/actions/runs/40296879374),
job 121484968870, passed the sandboxed browser probe, checks and full tests:
API 2903 passed/65 skipped, Web 386 passed, Demo API 5 passed.

Both jobs used Ubuntu image 20261012.334.1 and Node 22.23.3. The evidence points
to a startup timing/environment failure; no project test or dependency failure
was observed in dev. Logs are preserved externally, not rewritten as success.

## Scope and policy

Only the developer CI preflight is changed. The extracted probe retains the
installed channel, headless mode and `chromiumSandbox: true`. Two launch attempts
maximum, 60000ms each, with a single retry only for Playwright TimeoutError
during launch. Missing browser, sandbox/configuration errors and page failures
are fatal without retry. The trusted HTML readiness checks each have a 10000ms
bound; returned browsers are always closed, and cleanup failures propagate.
GitHub limits the whole step to three minutes. No browser installation, disabled
sandbox, changed host policy, skipped test, new dependency or product-harness
timeout change is introduced.

## Local evidence

Artifacts: `E:\Docker\AgentHub\ci-browser-startup-20261026-01`; temporary data
continues under `E:\Docker\fs26`.

- Original inline behavior extracted without improvement: 7 tests passed,
  4 failed (`old-behavior-red.log`). The missing-module RED is also retained.
- Final local tool regression: 64/64 passed, including 11 new probe checks
  (`local-green.log`). Actual sandboxed Edge probe passed, version
  156.0.4314.42 (`actual-edge-probe.log`). An actual unsupported channel exited 1
  (`invalid-channel.log`), rather than succeeding or selecting a fallback.
- Script syntax, strict OpenSpec and whitespace checks passed. Remote Ubuntu
  verification remains a separate publication gate; new run outcomes are stored
  in the external closeout record and are not inferred from these local checks.
- The new tests cover normal readiness/cleanup, recovery after a launch timeout,
  exhaustion after two attempts, fatal missing/sandbox/configuration errors,
  readiness mismatch/timeout, page creation and cleanup failures, plus CI wiring.

## Delivery and limits

The user requested fixing the published CI; the focused fix is committed/pushed
to dev and synchronized to main when local verification passes. Existing data,
credentials, adapters and all earlier measurement results are preserved.
Remote success is verified against each new commit/run, not inferred from the
passing old main run. New run identifiers and final outcomes are recorded in the
external closeout evidence; completion is not claimed while relevant CI fails.
