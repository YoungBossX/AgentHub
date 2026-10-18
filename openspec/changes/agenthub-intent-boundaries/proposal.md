# Bound intent recognition before task creation

## Why
Substring rules and generic fallback can turn negation, quoted examples, questions
or a partially matched multi-action request into a write task. Explicit mentions
select a recipient, not permission to treat every message as a code change.

## What Changes
- Add a bounded, server-generated IntentDecision shared by rule routing, Planner
  outcomes and persisted message/task evidence, without a new table or model call.
- Reject ambiguous rule shortcuts, preserve supported single-action demo requests,
  and prevent direct/group/generic fallback from bypassing the same boundary.
- Keep real Planner planning and all execution/target/approval controls. A Planner
  failure cannot turn an unresolved request into an executable template.
- Add a versioned offline evaluation corpus with explicit expected labels, slots,
  routing and negative controls; report denominators and actual evidence limits.

## Scope
One focused recognition task. No embedding service, trained classifier, dependency,
adapter, UI redesign, production deployment or expanded execution permissions.
