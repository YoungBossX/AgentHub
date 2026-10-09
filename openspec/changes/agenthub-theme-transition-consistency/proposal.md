# Theme transition consistency

## Why
Real browser sampling shows that the result-card title adopts the new theme
immediately while the background and inherited button text keep animating from
the old theme. A screenshot during that interval looks like a persistent white
card defect, but settled colors are correct. The temporary mismatch is real.

## What Changes
Apply explicit and cross-tab theme changes with a short document-level transition
pause so foreground and background adopt the palette together. Restore normal
hover transitions after the browser has rendered the new palette. Keep existing
theme persistence, failure handling, hydration and iframe boundaries.

## Impact
One frontend theme consistency task. No component redesign, provider/model
execution, new dependencies, API/schema changes or deployment.
