# Instruction package lifecycle

WorkspaceSkill stores validated SKILL.md and bounded textual resources in SQLite.
Three built-ins are catalog defaults; workspace overrides use optimistic revision
checks. Users import/edit packages and choose default Agent identities. Message
skillIds null uses defaults; an explicit empty list disables Skills for that
message; explicit selections freeze validated packages before planning. A group
applies selected skills only to matching roles and records incompatible skips.

TaskRun stores an immutable workspace/Agent/message-bound content snapshot and a
public receipt. Retries use the original run snapshot. Tampering fails closed;
old runs without bindings do not silently acquire newly configured skills.
Selected instructions and directly referenced textual resources enter the
existing prompt builder under platform guardrails. ScriptedMock records unsupported
instruction execution rather than pretending to follow natural-language Skills.
Planner receives its compatible skills before its actual provider call.

Bound count, file sizes, prompt size, names, resource paths and default identities.
Reject scripts, protected/absolute/parent paths and unknown cross-workspace
identities. SKILL.md allowed-tools is metadata, never a permission grant.
UI includes package import/edit, Agent defaults, message selection, and per-run
loaded/skipped/version/source details with existing dark/light responsive tokens.
