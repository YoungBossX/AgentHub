# Design

Use a fixed CSS block delimited by ScriptedMock-owned comments in
`apps/demo/src/styles.css`. Preserve existing bytes outside that block; append it
when absent and replace only a well-formed single owned block when present.
Reject ambiguous markers and an unsafe stylesheet before any writes. The CSS is
fixed and scoped to the generated `.login-form`, without imports or network URLs.
Do not accept an arbitrary stylesheet path from plan content.

Prepare the existing App mutation and stylesheet update together. Keep copy
mutations App-only and read-only reviews mutation-free. Copy planning includes
the demo stylesheet as context so the Session's validated, uncommitted login CSS
does not block its normal follow-up through the existing dirty-worktree gate;
the fixed demo scope and outside-file rejection remain unchanged. Report the actual changed
file paths. Write the CSS before App and restore already attempted outputs after a
filesystem error; if restoration fails, report that failure rather than success.
Keep unsupported target and no-op rejection.

Inputs retain implicit accessible labels and add name/autocomplete attributes.
CSS provides a grid, legible labels, inherited 16px input fonts, flexible widths,
normal/hover/focus-visible states and no fixed width causing mobile overflow.
This remains a frontend demo, not a working authentication service.

Verify actual adapter/engine scope, Diff, failure rollback, unsafe/malformed/no-op
cases, old styles and supported follow-ups. In isolated SQLite/real Git/Vite,
inspect desktop and 320/390px previews, accessible labels, real computed styles,
keyboard focus, follow-up source preservation and refreshed/restarted results.
Preserve the existing accepted native source and keep all scripted origins clear.
