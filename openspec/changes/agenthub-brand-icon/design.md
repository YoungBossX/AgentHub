# Design

This is a small artwork integration, with the image and destination project
already supplied. Use the existing Next.js stack and automatic image optimization.

## Approaches

Use the supplied raster artwork as-is, rather than hand-tracing or regenerating
it, to preserve the user's finished design. A common presentation frame enlarges
the image to 128%, offsets left -14% / top -11.8%, and clips its outer background;
this is a builder choice to make the central tile readable at small sizes.

The sidebar uses a local optimized Next Image in a fixed 40px frame. Browser
64px and Apple 180px icons use the same source/frame with Next ImageResponse,
served through metadata file conventions. The renderer reads only the fixed
public asset, uses no remote URL, and is force-static so it generates at build.
The original PNG remains byte-for-byte identical to the user's file.

Do not apply theme filters or replace role/task/tool icons. Keep original
workspace display names. The adjacent product title names the decorative sidebar
image, so the image has empty alt and does not create redundant announcements.

## Verification

Run existing sidebar/page tests, Web checks, production build and strict OpenSpec.
Inspect actual light/dark sidebar and 390px drawer in Edge with the existing
independent E-drive UI fixture. Verify source hash, fixed frame dimensions,
image loading, PNG dimensions/byte sizes and metadata links. No Provider runs or
product DB writes, dependency installs, or commit/push.
