# Design

One focused end-to-end task covers upload, storage, message display, context
selection and native transports. Do not mark it complete after only storage/UI.

## Storage and validation
Use a MessageAttachment row with Session ownership, optional immutable Message
binding, bytes, SHA-256, normalized media kind, display filename, text extraction
status and bounded text. A raw binary upload endpoint reads with a hard byte
limit before decoding; client MIME/path claims are never authority. Only the
display basename is retained; reject paths, control characters and protected
filenames. Bound file size/count, image dimensions, document parsing time and
Session storage. Only unfinished uploads can be removed/expired; bound inputs
stay immutable so retries and historical evidence cannot silently change.

Accept common UTF-8 text/source files, text PDFs, PNG/JPEG/WebP. Reject executable,
archive and active image formats. Parse images/PDFs in a bounded child process
without shell or inherited provider credentials. Record actual format, dimensions,
extracted text size and truncation. Scanned PDFs without text are not claimed to
have been OCRed; expose a clear unsupported-extraction state and next action.
Serve bytes only through Session-scoped endpoints, safe content disposition and
nosniff; image previews use validated raster MIME, other files download as files.

## Message and context ownership
Bind uploaded IDs to the new user Message in one transaction. Reject cross-Session,
duplicate, deleted or already-bound IDs before planning or dispatch. Responses
include metadata, never raw base64; UI handles upload progress/errors/removal and
Session switches without attaching late responses to another conversation.

Select current, explicitly quoted and pinned/recent message attachments within
bounded budgets. Resolve only authoritative same-Session rows; ignore forged
attachment objects in caller-controlled context/plan dictionaries. Text is
filtered and marked as untrusted conversation reference, not system instructions
or new file/tool authorization. Preserve IDs, hashes, source messages and omission
reasons. Historical TaskRun context snapshots remain frozen.

## Provider transports
Canonical context contains text/reference evidence, not binary base64. Use typed
private image inputs resolved from immutable records. Planner payload serialization
must omit raw image data from logs/JSON evidence; OpenAI Responses, compatible Chat,
Anthropic and native Claude CLI receive their real supported image blocks.

Claude CLI uses stream-json stdin for attachment-bearing requests. Codex retains
its sandbox/ignore flags, gets text through stdin and images through exact --image
arguments referencing server-created private temporary files. Those input files
are assigned to this call, cleaned on failure/interrupt/completion and never grant
general host-directory tool access. Strict command validation checks the full
profile plus the exact server-owned image list. No arbitrary flags or paths.
Do not put large extracted documents in Windows command-line arguments.

ScriptedMock keeps its original no-attachment path; it must not claim to interpret
arbitrary attachments. Unsupported native/provider capabilities or malformed input
produce explicit failure, not a fabricated image/file-reading success.

## Verification
Cover validation/resource limits, atomic binding/ownership, old SQLite schema,
context budgets/trust/history, native command containment and lifecycle, provider
wire payloads, UI stale requests and failure recovery. Then run related and full
relevant gates, actual browser upload/history/download/theme/resize/reload, restart
persistence, and a fresh native task whose required content exists only in an
uploaded file/image. Keep fixtures, native inference, Diff and real preview
evidence distinct. No new feature task starts until this one is verified.
