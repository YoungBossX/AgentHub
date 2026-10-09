# Design

Keep the fixed button and heading anchors. Replace their contents using a callable
regex replacement, never a user-controlled regex replacement string. Ordinary
single-line copy without JSX-sensitive characters keeps its existing source form.
For markup/entity/braces/control characters, emit only a serialized string literal
inside JSX braces. Escape angle brackets in the literal so embedded closing tags
cannot terminate the next anchor match. Unicode/control characters must preserve
their JavaScript string value without becoming source syntax.

Keep existing targetText normalization, supported targets, planning, registered
scope, CSS/context behavior, adapters, read-only reviews, queue/lock/lease, Diff,
failure/no-op and snapshot behavior. Completion evidence remains file/Diff output
with functionalAcceptance=not_evaluated; runtime acceptance belongs to separately
labelled evidence, not a silent expansion of the generic server contract.

Before fixing, reproduce raw braces and markup in isolated SQLite, actual
ScriptedMock TaskRuns and healthy Vite/Edge, saving source and failure provenance.
Afterward verify exact DOM text with no injected elements/runtime errors across
direct/group/Orchestrator entry points, special-to-plain continuation, unchanged
CSS/source surroundings, Diff/events, independent read-only QA, restart/history
and TypeScript checks. Include structured multiline/control/closing-tag copy
fixtures and preserve no-op/unsupported/path failure tests. Do not change old
failed or completed run snapshots, or the existing accepted native Session.
