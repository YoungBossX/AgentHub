## Why

The complete API suite retains nine Windows failures because a newly created
directory can expose an undocumented transient `0x10000000` bit through
CPython `lstat().st_file_attributes` until that directory is enumerated. The
TaskRun scope collector currently treats that observation-only transition as a
filesystem identity change, makes the complete snapshot unavailable, and then
correctly fails writing runs closed. This blocks otherwise valid empty-directory
snapshots, fallback recovery, and scripted write-scope execution.

## What changes

- Normalize only the transient Windows directory path-observation bit before
  comparing path identities.
- Keep device, inode, file type, every documented file attribute, reparse-point
  rejection, ordinary-file descriptor identity, and Git executable identity
  strict.
- Add a focused Windows regression for the pre/post-enumeration observation and
  rerun the nine affected API nodes plus adjacent scope security coverage.

## Impact

- Changes only TaskRun scope path-observation compatibility, focused tests, and
  current documentation.
- Does not weaken fail-closed behavior for unknown files, reparse points, named
  streams, protected paths, executable swaps, or any other attribute change.
- Adds no schema, adapter, API, frontend, dependency, or product-scope change.
