# User-supplied AgentHub brand icon

## Why

The user supplied a finished icon and requested project integration. Replace the
generic sidebar Git glyph and supply browser/mobile icons using that exact artwork.

## What Changes

- Preserve the uploaded PNG as a source brand asset.
- Render the sidebar mark at 40px with a bounded viewport trimming presentation
  padding, without redrawing or changing the source pixels.
- Use existing Next.js ImageResponse metadata conventions for small browser and
  Apple touch icons, avoiding a full 1.6MB favicon download.
- Keep workspace names, themes, role icons, prior UI changes and data intact.

## Impact

Frontend brand presentation only. No dependencies, schema, Provider or permission
changes. No commit/push. New verification evidence stays under E:\Docker.
