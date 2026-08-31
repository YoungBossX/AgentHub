## 1. Behavior-preserving source modularization

- [x] 1.1 Extract agent directory, profile draft, runtime configuration, and
  memory settings routes plus their response mappers from `main.py`; preserve
  the existing HTTP contract and focused tests.
- [x] 1.2 Extract TaskRun, artifact, preview/deployment, and Session SSE routes
  from `main.py` while preserving established public helper compatibility.
- [x] 1.3 Split `planning.py` into cohesive routing, intent, and task-building
  modules behind the unchanged `plan_for_message` entry point.
- [x] 1.4 Split `workspace-shell.tsx` orchestration, event refresh, and
  presentation responsibilities without changing visible behavior.
- [x] 1.5 Run the available full project checks, synchronize current
  architecture/project-state/change-log documentation, and record remaining
  structural limits.
