# Workbench usability

Derive guidance from persisted Task/Run/scheduler/approval state and current
artifact receipts. Distinguish queued work from running, completed execution from
verified outcomes and mock deployment from production. Route actions to existing
process/result/composer controls; never execute from an informational notice.

Skill references stay in the existing SQLite package and revision-checked API.
Use explicit relative path/content rows and bounded UTF-8 file import, eight
resources maximum. Validate duplicates/unsafe paths/size before saving and retain
drafts on server conflict. Importing reference text grants no filesystem scope.

Measure history before choosing a bound. Add stable Session-owned cursor paging
and merge updates by identity when required. Initial history and subsequent DOM
must be bounded; older messages remain explicitly loadable. Pins, regenerate
identity recovery, messages with attachments and SSE updates must remain correct.
Do not truncate backend planning context or rewrite historical messages to speed
up rendering. Bound visible pins separately, with an explicit indication of more.
