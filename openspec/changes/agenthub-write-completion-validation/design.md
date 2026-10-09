# Design

Keep provider completion distinct from application completion. Validate write output using the existing trusted pre-run scope baseline, then collect the real Diff. Zero newly changed paths, empty Diff, or failed Diff collection fails the write run before Review or successful downstream side effects. Read-only work does not require a patch. Do not reinterpret historical completed runs or claim functional correctness from a patch alone.

Store versioned completionValidation metrics and a task.completion_validation event, with status, access mode, observed path count, Diff identity and error code. All new finalizer mutations remain inside the existing exact-generation commit fence. Keep scope validation first and do not expose internal fingerprints or host paths.

Diagnose Windows CLI access with isolated fresh fixtures, sanitized child environment and raw JSONL. Vary only the documented native Windows sandbox selection; never use danger-full-access or disable sandboxing. Preserve ignore-user-config/rules, assigned cwd, workspace-write and network-off. A model's unsupported permission claim is not OS evidence. Preserve reports and document residual uncertainty.
