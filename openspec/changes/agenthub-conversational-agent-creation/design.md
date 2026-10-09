# Design

The Agent directory gains a dedicated creation conversation, with an entry next
to workbench contacts. This separates configuration requests from ordinary coding
chat so a creation request cannot accidentally start file modification. The user
describes responsibilities and can clarify/refine over multiple turns. A validated
draft appears in the existing editable custom-Agent form before explicit saving.

The workspace's current Planner and effective behavior preferences are resolved
server-side. A mandatory JSON contract asks for a clarification or complete draft.
Only registered non-platform targets, supported role capabilities, available
provider/tool-policy combinations and unused aliases are sent as the catalog.
The model cannot define commands, new tools, credentials or unrestricted paths.
Enforce the same custom-profile validation before returning a draft and again at
save time. Generated drafts start disabled; the user can enable them in the form.
Revalidate the selected generator after the call. No fallback-generated text is
presented as a real model result; errors remain actionable and do not create data.

Requests carry bounded dialogue and the current manually edited draft. Generation
has no database mutations or tool execution. The response exposes safe provider
identity and hashes, not raw provider errors or host configuration. No secrets,
files, conversation history from other Sessions or ambient memory are added.

The browser keeps the unfinished conversation and current form in sessionStorage,
keyed by backend and workspace. On unavailable storage it explains the limitation.
Concurrent submits are blocked; stale responses after scope changes/unmount are
discarded. Generation never overwrites a form edited while a request is pending.
A returned draft replaces the creation form only in this dedicated builder.
Saving uses the existing custom endpoint; directory refresh failures must not
turn a successful save into another create. Starting over is an explicit action.

Verification covers malformed/oversized output, role/tool/target/alias boundaries,
provider failure/disabled/revocation, no generation mutations, manual refinement,
explicit save, storage/scope/race behavior, real no-tool synthesis and execution
of the saved profile, browser themes/narrow widths, refresh and API restart.
