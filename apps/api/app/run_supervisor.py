from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from app.adapters import AgentAdapter
from app.models import utc_now


@dataclass(frozen=True)
class SupervisedRun:
    task_run_id: str
    adapter_run_id: Optional[str]
    adapter_type: str
    started_at: datetime
    adapter: Optional[AgentAdapter] = None


@dataclass
class RunSupervisor:
    active_runs: dict[str, SupervisedRun] = field(default_factory=dict)

    def register(
        self,
        *,
        task_run_id: str,
        adapter_type: str,
        adapter_run_id: Optional[str] = None,
        adapter: Optional[AgentAdapter] = None,
    ) -> SupervisedRun:
        run = SupervisedRun(
            task_run_id=task_run_id,
            adapter_run_id=adapter_run_id,
            adapter_type=adapter_type,
            started_at=utc_now(),
            adapter=adapter,
        )
        self.active_runs[task_run_id] = run
        return run

    def update_adapter_run_id(
        self,
        task_run_id: str,
        adapter_run_id: str,
    ) -> Optional[SupervisedRun]:
        current = self.active_runs.get(task_run_id)
        if current is None:
            return None
        updated = SupervisedRun(
            task_run_id=current.task_run_id,
            adapter_run_id=adapter_run_id,
            adapter_type=current.adapter_type,
            started_at=current.started_at,
            adapter=current.adapter,
        )
        self.active_runs[task_run_id] = updated
        return updated

    async def interrupt(self, task_run_id: str) -> bool:
        current = self.active_runs.get(task_run_id)
        if (
            current is None
            or current.adapter is None
            or current.adapter_run_id is None
        ):
            return False
        await current.adapter.interrupt(current.adapter_run_id)
        return True

    def unregister(self, task_run_id: str) -> Optional[SupervisedRun]:
        return self.active_runs.pop(task_run_id, None)

    def active(self, task_run_id: str) -> Optional[SupervisedRun]:
        return self.active_runs.get(task_run_id)


default_run_supervisor = RunSupervisor()
