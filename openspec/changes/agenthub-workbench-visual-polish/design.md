# Design

Use the user's palette: light canvas #f5f5f3 and surface #fcfcfb; dark canvas
#0b0b0a and surfaces #151515, #1a1a19 and #20201e. Distinguish adjacent panels
with fills rather than outlines. Keep status text/badges and selected state
recognizable. Preserve table readability and focus indications.

Define shared typography weights with a dark offset of 40, including Markdown
emphasis and headings. A static system font may map intermediate weights to its
available faces; do not fetch fonts or claim variable Chinese font support.
Use tabular-nums, text-wrap:pretty and -0.125em inline icon alignment globally.

Input focus uses two concentric shadows without an outline. Keep keyboard focus
visible on all controls and support forced colors and reduced motion. Composer
retains a full-width textarea above an evenly aligned attachment/send toolbar.

Use a shared Disclosure with an accessible button, aria-expanded/controls,
inert collapsed content, and Grid 0fr/1fr. No height measurement. Preserve state
and mount identity, lazy content reads and initial-open evidence sections.

Incremental Markdown prose uses grapheme-safe spans only for appended text,
90ms blur(6px)-to-clear, cubic-bezier(.215,.61,.355,1), 30ms stagger. Initial
history, replacements, code and URLs stay readable without a replay. Bound an
animation batch to 32 graphemes so large SSE snapshots cannot accumulate seconds
of invisible content. Text is never withheld by a JS typing timer.

Derive CSS linear() spring curves from mass=1, stiffness/damping 1200/80 for
drag feedback and 380/18 for confirmation. Widths follow pointer input directly;
animate the separator grip on release, not the layout behind the pointer.
Copy confirmation starts its 2500ms lifetime only after clipboard success,
fades back to the copy icon, restarts on another success and cleans up on
unmount/content change. Stale clipboard promises must not affect a newer copy.

Keep all new test output and screenshots under E:\Docker. Do not commit or push
without a new explicit instruction.
