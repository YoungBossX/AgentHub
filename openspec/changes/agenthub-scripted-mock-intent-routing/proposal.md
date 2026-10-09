# Route scripted demo mutations by structured task intent

## Why
ScriptedMock searches the complete rendered instruction for title/heading/button.
Task metadata and historical context can therefore turn a login task or button
follow-up into a heading change, despite a valid target and nonempty Diff.

## What Changes
- Select login, primary-button copy and heading copy from the persisted task's
  existing target field before considering instruction prose.
- Use targetText for structured copy changes and reject unsupported/malformed
  structured targets or missing copy text without mutation.
- Preserve the no-target legacy demo compatibility path and existing protection,
  scope, completion, interruption, approval and failure behavior.
- Verify functional source output and same-Session follow-up through the actual
  request builder and execution engine, clearly distinguishing fixed follow-up
  fixtures from complete chat/QA/Preview acceptance.

## Impact
One adapter routing repair. No new adapters, schema, planner/QA scheduling rules,
UI, dependencies, real providers, Preview or deployment changes.
