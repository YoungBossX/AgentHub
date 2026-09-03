## Finding boundary

The production audit identifies two Web runtime families:

- `apps/web -> next@16.2.6`, including vulnerable PostCSS 8.4.31,
  nanoid 3.3.12, and sharp 0.34.5 paths;
- `apps/web -> monaco-editor@0.55.1 -> dompurify@3.2.7`.

Next.js receives requests and renders the App Router workspace. Monaco renders
agent-produced diff content. Whether every advisory is reachable through the
current local-only UI is not assumed; the invariant is that shipped production
dependency versions must not remain inside published vulnerable ranges when a
compatible patched owner release exists.

## Patch strategy

Set the `next` and `eslint-config-next` manifest floor together at 16.3.3. The
current lock resolves both to 16.3.4; this line declares PostCSS 8.5.23 and
sharp `^0.35.3`, closing the original audited transitive families without
independently overriding those framework internals.

Upgrade `monaco-editor` to 0.56.0. It still declares DOMPurify 3.4.8, while the
latest audited sanitizer fix requires 3.4.13. Apply one root pnpm override for
DOMPurify 3.4.13 so every current and future workspace importer resolves the
same patched sanitizer. Do not add overrides for packages already owned by the
upgraded Next release.

The refreshed tree also exposes `next -> styled-jsx -> @babel/core@7.29.0`,
which remains in the audited arbitrary source-map file-read range. Apply a
second root override to the patched Babel 7.29.6 release. This retains Babel 7
compatibility rather than broadening the task to Babel 8.

The legitimate behavior to preserve is the existing Next App Router workspace,
Monaco DiffEditor rendering, React 19 compatibility, local 127.0.0.1 development
command, and the existing pnpm/Node runtime contract.

## Validation

The original trigger is `pnpm audit --prod`. It must return exit 0 with no
production advisories after lockfile regeneration. Compatibility gates are the
Web lint/type check, complete Vitest suite, production Next build, full API and
demo-api tests, repository `pnpm check`, strict OpenSpec validation, and final
candidate/temporary-artifact audit.
