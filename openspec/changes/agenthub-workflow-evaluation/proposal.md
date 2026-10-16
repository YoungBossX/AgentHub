# Representative local workflow evaluation

Complement the three fixed single-file external tasks with reproducible built-in
workspace scenarios: backend API repair, multiple source files, frontend/backend
coordination, same-session follow-up and explicit failure/retry recovery. Exercise
natural-language planning/dispatch and the existing queue/provider pipeline rather
than equating a preconstructed coding Task with a full workflow.

Use fresh external output directories, fixture Git repositories and isolated
SQLite databases. Keep raw attempt history and fixed independent acceptance;
report first-attempt and final results, retries, elapsed time, provider identity
actually observed, and failure categories. Never convert prepared/test-double or
injected-failure evidence into live model performance. No production data, new
adapters, dependency installation, publishing or development-checkout commits.
