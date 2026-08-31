## Observed failure

On the current Windows Python runtime, a newly created ordinary directory is
reported by `Path.lstat()` with `st_file_attributes == 0x10000010`. The Win32
`GetFileAttributesW` value is `0x10`, and the next `Path.lstat()` after
`os.scandir(directory)` is also `0x10`. The undocumented high bit is therefore
an observation artifact rather than a durable file attribute. Because the
collector binds a directory before enumeration and rechecks it after
enumeration, its strict tuple comparison currently rejects the same directory.

## Narrow compatibility rule

Path observations on Windows normalize `0x10000000` only when the observed
object is a directory. The rule is applied before the four-field path identity
is persisted in the in-memory observation chain. It is not applied to regular
files or descriptor observations.

All documented Windows attribute bits remain part of the identity. In
particular, the reparse-point bit is still checked before identity construction,
and named-stream enumeration remains required before and after directory scans.
Git executable path/descriptor comparison and ordinary-file fingerprint reads
remain unchanged and strict.

## Verification boundary

A Windows regression first proves that the raw Python attribute bit changes
across enumeration while the normalized `_path_observation` remains stable.
The existing nine failing nodes then prove empty-directory capture, real Git
layer capture, fallback recovery, and readonly-review write scope all recover.
Adjacent reparse, named-stream, executable, case-semantics, and protected-path
tests guard against broad normalization.
