# Design

Add a strict shared API instant parser for ISO datetimes with optional seconds,
fractional seconds and Z or numeric offsets. Offset-free datetimes are UTC,
consistent with existing utc_now storage and API serializers. Reject invalid
calendar dates, dates without a time and invalid clock/offset values. Do not
interpret arbitrary strings through browser-local Date.parse. Preserve raw
strings for diagnostics; display invalid timestamps without fabricating dates.

Use deterministic pure formatters with an explicit timezone (UTC by default).
A client hook resolves the browser IANA timezone only after hydration through
useSyncExternalStore's server snapshot. SSR and the initial client snapshot
show clearly labeled UTC; hydration updates all timestamps and labels to local
time. Invalid/unsupported timezone resolution falls back to explicit UTC.

Reuse a timestamp component for sidebar recency, Preview health check and SSE
event time. Semantic time datetime contains the normalized UTC instant; title
contains full displayed date/time, timezone/offset, UTC and exact original API
value. Timezone labels explain local display without widening sidebar rows.
Search uses the same displayed session time. Sorting and overlap calculations
use parsed instants, not formatted local strings; equivalent offset encodings
must compare consistently. SSE visuals continue to whitelist only public fields.

Verify fractional/naive/Z/offset inputs, midnight/year crossings, DST and a
negative-offset timezone; invalid input rejection and unknown-value display;
event normalization and overlap consistency; SSR and hydration across differing
server/browser zones; actual stored timestamps from the running local API,
reload, light/dark and narrow layouts. Run full Web and project static checks.
No backend write or fresh model execution is required for a display-only task.
