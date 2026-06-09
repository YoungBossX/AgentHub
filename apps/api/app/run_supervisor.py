from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from app.models import utc_now


@dataclass(frozen=True)
class SupervisedRun:
    task_run_id: str
    adapter_run_id: Optional[str]
    adapter_type: str
    started_at: datetime


@dataclass
class RunSupervisor:
    active_runs: dict[str, SupervisedRun] = field(default_factory=dict)

    def register(
        self,
        *,
        task_run_id: str,
        adapter_type: str,
        adapter_run_id: Optional[str] = None,
    ) -> SupervisedRun:
        run = SupervisedRun(
            task_run_id=task_run_id,
            adapter_run_id=adapter_run_id,
            adapter_type=adapter_type,
            started_at=utc_now(),
        )
        self.active_runs[task_run_id] = run
        return run

    def unregister(self, task_run_id: str) -> Optional[SupervisedRun]:
        return self.active_runs.pop(task_run_id, None)

    def active(self, task_run_id: str) -> Optional[SupervisedRun]:
        return self.active_runs.get(task_run_id)


default_run_supervisor = RunSupervisor()
