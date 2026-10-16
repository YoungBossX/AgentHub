# Version-bound review repair workflow

Allow users to select concrete review findings or failed configured checks,
prepare an explicit repair draft, send it through the existing conversation and
execution pipeline, and inspect new verification linked to the original report.
Preserve original reports, selected issue identity, source versions and retry
lineage. A changed file or a passed model opinion alone cannot resolve an issue.

Reuse existing Message/TaskRun/Artifact JSON evidence and local request guards;
do not add adapters, database entities, general commands or automatic unattended
repair loops. This is the next task after the locally verified backend validation
and representative workflow evaluation tasks.
