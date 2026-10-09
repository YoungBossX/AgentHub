# Design

Wrap the existing three mounted panes in a resizable layout. Use CSS custom
properties for sidebar and inspector widths and actual container measurements.
Desktop bounds are sidebar 180–360px, inspector 280–720px and center at least
400px; constrain preferred widths when the container shrinks. Defaults stay
220/360px, or 240/420px for containers at least 1600px wide.

Use Pointer Events with capture and a temporary transparent drag shield, so
preview iframes cannot consume drag input. Cancellation, Escape, blur and leaving
desktop size must clean up drag state. Retain one mounted task list throughout.
Expose vertical separator semantics, keyboard arrows (16px), Home/End and a
double-click reset for each pane. Save only finite bounded widths to a dedicated
localStorage key; invalid or unavailable storage must not break resizing.

Below 1200px hide separators and retain existing fixed two-column/overlay and
mobile drawer layouts. Expanded/collapsed inspector hides the appropriate
separator without losing the user's preferred width. Verify pointer/keyboard
bounds, cancellation, persistence, shrinking containers and actual browser drag.
