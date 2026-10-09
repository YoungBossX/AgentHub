# Version-bound native review

For new Claude read-only requests, freeze a bounded target-file fingerprint before
launch and include a server-owned JSON review contract. Retain frozen prompt,
profile, Read-only tools, execution lease and target validation. Native CLI result
text is the authoritative output; streamed prose/tool diagnostics cannot substitute
for it. Record successful native Read evidence and validate the returned schema,
status/risk, files/findings, and absence of claimed test execution.

Before marking the run complete, verify its target-file fingerprint is unchanged,
collect the matching Diff, and persist the native Review/Artifact with real
provider/run/output/file receipts. Invalid, missing, stale, or unverifiable output
fails honestly without producing a scripted replacement. A completed review may
have findings and a warning/failed assessment; execution success is separate from
assessment status. Native assessments remain advisory, not functional test proof.

Existing completed runs retain their original artifacts. Coding advisory reports
and ScriptedMock review remain labelled scripted. UI shows actual source, findings,
suggestions and test-not-run boundary, with refresh/replay preserving provenance.
Verify controlled invalid-output/version/ownership cases and a fresh real native
review, then run relevant regression and record evidence.
