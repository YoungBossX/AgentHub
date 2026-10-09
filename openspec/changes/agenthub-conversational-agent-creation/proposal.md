# Conversational Agent creation

## Why
The design PDF requires creating Agents through conversation. Executable custom
profiles already have a validated form and native runtime, but natural-language
requirements cannot yet become a configuration that the user can review and save.

## What Changes
Add a conversational builder in the Agent directory, reachable from contacts.
Use the configured Planner without execution tools to propose or refine a bounded
custom profile. Support clarification, manual edits, browser draft recovery,
explicit save/enable, errors and visible provider provenance. Reuse the same
validation and save path as the existing custom editor. Generation alone creates
no profiles, messages, coding tasks or file changes.

## Impact
One focused task. No new dependency, adapter, database entity, marketplace,
permission grants or production deployment. Existing manual creation stays usable
when a real generation provider is not configured.
