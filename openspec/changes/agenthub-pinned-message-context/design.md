# Design

Read Message.pinned_at from the same Session for both build_session_context_pack
and build_llm_planner_request. Use a deterministic most-recent-pin order with
message insertion order as the final tie breaker. Keep up to 16 references,
2,000 text characters per reference and 12,000 ASCII JSON serialized characters
for the pinned payload (ensure_ascii=True, indent=2). Report total/included/omitted/truncated counts and the
selection limits; filter protected values before considering text for budgets.
Truncation must not hide whether a message is partial. Avoid repeating selected
pinned messages in the recent-message list.

Reuse the Planner's inline credential-assignment redaction in the shared
context filter as well: a pinned message may also appear in the session goal,
so filtering only its new reference would leave a duplicate execution path.

The canonical field is provider-visible user-selected conversation reference.
Preserve the original sender type and do not turn assistant/tool text into
trusted rules or grant tools/target access. Existing current request, system
prompt and guardrail precedence remains. No MemoryItem is created by pinning.
Planner and execution use the same selector; provider instruction paths retain
the canonical field. Existing saved TaskRun request snapshots remain immutable;
pin/unpin is observed when a later request is prepared.

Prove the existing failure with a pinned message older than eight newer
messages. Test session isolation, planner/coding agreement, deduplication,
unpin/new preparation, historical snapshot preservation, equal timestamps,
protected data and serialized Unicode budgets. Exercise actual pin controls and
inspect a fresh real provider request/output using an old pinned reference;
keep ScriptedMock and any deliberate failures separately labelled. Verify
restart persistence and relevant/full regressions before marking completion.

The final PDF audit also found separate candidates to verify later: rich chat
message rendering/attachments, message regeneration, conversational Agent
creation and direct code editing. They are not implemented by this task and
remain explicit open requirements in the overall delivery audit.
