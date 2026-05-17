# Codex Task Template

Use this workflow for future AgentHub Codex tasks so prompts can stay short and
repeatable.

## Standard Workflow

1. Read `AGENTS.md`.
2. Read `docs/change-log.md`.
3. Read `docs/project-state.md`.
4. Run:

   ```bash
   git status --short
   git branch --show-current
   git log --oneline -12
   ```

5. Confirm whether the working tree is clean.
6. Read files directly related to the task.
7. Summarize current state, expected modified files, and the minimal plan before
   coding.
8. Diagnose before editing.
9. Keep changes minimal.
10. Add or update tests only if behavior changes.
11. Update `docs/change-log.md` if files change.

## Final Response Checklist

Every task wrap-up should include:

- Diagnosis
- Changed files
- Tests added or updated
- Validation command results
- What was verified
- What was not verified
- Whether the fallback-based P0 demo remains intact
- Whether files were committed or left uncommitted
