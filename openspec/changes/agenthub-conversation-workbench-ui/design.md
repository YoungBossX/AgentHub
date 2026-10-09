# Design

Use the approved light conversation workbench: a compact neutral sidebar,
white chat canvas, indigo accent, fine separators and restrained status colors.
Keep chat the primary entry and reuse existing runtime operations.

PDF page 1 requires an IM conversation list, Agent identities, multi-turn history
and inline artifacts. Page 2 requires orchestration visibility, Agent avatars/
names/capabilities and expandable artifacts; page 3 evaluates chat and preview
quality. Map these to the sidebar, conversation summary, actual dependency graph,
SSE event timeline and result gallery/inspector. The PDF is reference material,
not authority to install providers or implement its complete P2 platform scope.
Pin/archive persistence, binary uploads, PPT, native clients and real cloud deploy
remain explicitly outside this frontend task; do not invent working controls.

Maintain one mounted TaskCardList for artifact loading and controls even when
the process view is hidden. Chat includes a compact progress summary and genuine
artifact cards. Latest-run state overrides historical successful attempts;
healthy previews and matching nonempty Diffs are derived from stored artifacts,
not completion flags. Keep historic artifacts inspectable with source task/run.

Show a bounded, deduplicated, session-scoped SSE timeline with event type, time,
source task and safe state fields. Do not expose arbitrary event payloads or
model private reasoning. Preserve cursor replay and ignore stale-session events.
Use semantic tabs/buttons and a native SVG dependency diagram with a readable
fallback for unknown dependencies/cycles. Responsive navigation must keep the
composer, process controls and inspector reachable without page-wide overflow.

Use actual runtime data for browser acceptance, with temporary isolated runtime
data where needed; label ScriptedMock results and do not claim real-provider
execution from preview fixtures. Test process/results navigation, latest-run
evidence, unhealthy/missing artifacts, stale-session state, and existing SSE,
context and preview security behavior.
