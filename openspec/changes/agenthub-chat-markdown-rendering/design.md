# Design

Use react-markdown's syntax-tree-to-React rendering and remark-gfm for nested
lists, tables, task lists, strikethrough and autolinks. Do not use raw HTML/MDX
execution or dangerouslySetInnerHTML. Preserve unsupported/raw HTML as visible
text. Only explicit HTTP(S), mailto and in-document fragment links may navigate;
reject credentials, control characters, backslashes and other protocols.
External image references need an explicit local preview button before creating
an image element. Preserve descriptive fallback for invalid/failed images.

Code blocks retain whitespace and literal characters, expose a language label
and copy only rendered code text (no fence, language label or buttons). Inline
code has separate styling. Show success and failure for clipboard operations;
preserve whole-message copying and raw quoting. Avoid stale clipboard outcomes
when message contents change. Use existing theme variables, scoped styles,
semantic structure and local horizontal overflow, including narrow screens.
Use unique per-message fragment prefixes for footnotes. Messages over 100,000
characters use a labelled plain-text fallback with all content retained.

Read installed Next.js client-component and CSS guides before implementation.
Add the two announced dependencies with install scripts disabled; no unrelated
dependency upgrades. Verify real ordinary API message persistence in the UI,
not only mocked components. Test headings/nesting/links/code/HTML, exact copy,
clipboard failure, hostile URLs, unfinished fences, theme/narrow overflow and
reload. Existing group summary, pin/quote and workspace tests must still pass.
No native model rerun is necessary to prove a presentation-only change; retain
the real execution and pinned-context evidence from the preceding task.
