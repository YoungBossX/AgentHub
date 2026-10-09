# Design

The existing palette and selectors are correct when settled. Reproduce both
immediate and settled states before changing them; do not replace working
theme colors based on a screenshot of an active transition.

Before changing data-theme, mark the document as changing theme. A scoped CSS
rule temporarily disables transitions for elements and pseudo-elements in
this document. Use two animation frames to keep that rule through the first
render of the new colors and then restore hover transitions. A generation
fence prevents callbacks from an earlier switch from clearing a later pause.
Apply the same path for same-origin storage updates/clears. Initial before-
interactive theme restoration remains unchanged; iframe documents are separate.

Verify frame timing, rapid switches, storage sync/failure and existing theme
tests. In actual Edge, sample immediate and animation-frame foreground and
background colors for results, actions and inspector in both directions;
compare contrast against the lower of their settled contrast values to prove
there is no mixed-palette dip. Verify hover transitions resume, persistence,
cross-tab synchronization, dark/light narrow layout, unchanged native Preview
document, no new TaskRuns and unchanged source. Run Web/static and strict
OpenSpec checks and freeze scoped evidence. Do not repeat API/model execution
when no backend code changed.
