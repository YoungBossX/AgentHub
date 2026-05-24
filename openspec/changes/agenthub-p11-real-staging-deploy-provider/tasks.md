## 1. Real Staging Deploy Provider

- [ ] 1.1 P11-1 Deploy Provider Abstraction: define a deploy provider interface and result contract with providerId, providerType, targetId, buildCommand, deployCommand, outputUrl, status, and logs; adapt the existing mock deploy path to remain available through the same deployment surface; add tests for provider selection, unknown-provider rejection, failed provider results, and mock deploy compatibility.
- [ ] 1.2 P11-2 Target-aware Deploy Configuration: extend the Target Registry so built-in demo frontend and registered external frontend targets can expose staging deploy metadata, including build command, output directory, preview/staging command where applicable, and allowed provider IDs; ensure targets without deploy configuration fail honestly; add tests that frontend deploy config is read from target metadata instead of scattered constants.
- [ ] 1.3 P11-3 Local Staging Deploy Provider: implement a local staging provider that runs the target build command, serves the built output directory locally, records a reachable staging URL, and reports failed build/output/server startup states without faking success; add backend tests and one bounded manual/API smoke for either the built-in demo frontend or an external Vite sample target.
- [ ] 1.4 P11-4 Deploy Logs and Status Artifact: persist deploy status transitions for queued, building, deploying, ready, failed, and cancelled; record logs, staging URL, target metadata, source diff/review/preview references, and provider details in a deployment artifact; expose this evidence through the existing artifact/deploy UI without removing mock deploy cards; add tests for log/status visibility and artifact linkage.
- [ ] 1.5 P11-5 Deploy Gate: block staging deploy when the latest review failed, preview failed, target policy violations exist, or a production deployment is requested; preserve clear staging-only labeling; add tests for each blocked state and for a successful gated staging deploy path.
- [ ] 1.6 P11-6 P11 E2E Rehearsal and Freeze Review: rehearse a real local staging deploy for the built-in demo frontend or an external Vite sample target, verify the staging URL is reachable, verify logs and deploy artifact evidence are recorded, verify mock deploy remains available where needed, verify P6/P7/P8/P9/P10 baselines remain intact, update project docs and change log, and mark P11 ready to freeze only if validation passes.

## 2. Explicit Non-goals

- [ ] 2.1 Confirm P11 does not implement production deploy, cloud provider token management, Vercel/Netlify/Render full integration, Docker/Kubernetes, domain management, database hosting, automatic rollback, multi-user deploy approvals, provider marketplace, PR creation, or unrestricted repository editing.

## 3. Validation

- [ ] 3.1 Run `pnpm check`.
- [ ] 3.2 Run `pnpm test`.
- [ ] 3.3 Run any target-specific staging deploy tests added during implementation.
- [ ] 3.4 Run `git diff --check`.
- [ ] 3.5 Run `openspec validate agenthub-p11-real-staging-deploy-provider --strict`.
