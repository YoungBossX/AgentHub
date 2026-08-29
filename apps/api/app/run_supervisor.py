import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from threading import RLock
from typing import Awaitable, Callable, Optional, TypeVar

from app.adapters import AgentAdapter
from app.models import utc_now


_T = TypeVar("_T")


class RunRegistrationRejected(RuntimeError):
    pass


@dataclass
class _SupervisedRunGeneration:
    ownership_lost: asyncio.Event = field(default_factory=asyncio.Event)
    loop: Optional[asyncio.AbstractEventLoop] = field(default=None, repr=False)
    lock: RLock = field(default_factory=RLock, repr=False)
    _lost: bool = field(default=False, init=False, repr=False)
    _interrupt_claimed: bool = field(default=False, init=False, repr=False)
    _reserved: bool = field(default=False, init=False, repr=False)
    _sealed: bool = field(default=False, init=False, repr=False)

    async def wait_until_lost(self) -> None:
        loop = asyncio.get_running_loop()
        with self.lock:
            if self._lost:
                return
            if self.loop is None:
                self.loop = loop
            elif self.loop is not loop:
                raise RuntimeError("A supervised run cannot span event loops.")
        await self.ownership_lost.wait()

    def mark_lost(self) -> None:
        with self.lock:
            if self._lost:
                return
            self._lost = True
            loop = self.loop
        if loop is not None:
            try:
                loop.call_soon_threadsafe(self.ownership_lost.set)
            except RuntimeError:
                pass

    def is_lost(self) -> bool:
        with self.lock:
            return self._lost

    def is_sealed(self) -> bool:
        with self.lock:
            return self._sealed

    def is_reserved(self) -> bool:
        with self.lock:
            return self._reserved

    def try_reserve(self) -> bool:
        with self.lock:
            if self._lost or self._sealed or self._reserved or self._interrupt_claimed:
                return False
            self._reserved = True
            return True

    def release_reservation(self, *, seal: bool = False) -> None:
        with self.lock:
            if not self._reserved:
                return
            self._reserved = False
            if seal:
                self._sealed = True

    def seal_reservation(self) -> bool:
        with self.lock:
            if not self._reserved or self._lost:
                return False
            self._sealed = True
            return True

    def claim_interrupt(self) -> bool:
        with self.lock:
            if self._sealed or self._reserved or self._interrupt_claimed:
                return False
            self._interrupt_claimed = True
            return True


@dataclass(frozen=True)
class SupervisedRun:
    task_run_id: str
    adapter_run_id: Optional[str]
    adapter_type: str
    started_at: datetime
    adapter: Optional[AgentAdapter] = None
    _generation: _SupervisedRunGeneration = field(
        default_factory=_SupervisedRunGeneration,
        repr=False,
        compare=False,
    )

    async def wait_until_ownership_lost(self) -> None:
        await self._generation.wait_until_lost()


@dataclass
class RunSupervisor:
    active_runs: dict[str, SupervisedRun] = field(default_factory=dict)
    _lock: RLock = field(default_factory=RLock, init=False, repr=False)
    _sealed_generations: dict[str, _SupervisedRunGeneration] = field(
        default_factory=dict,
        init=False,
        repr=False,
    )

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
        with self._lock:
            if task_run_id in self._sealed_generations:
                raise RunRegistrationRejected(
                    f"TaskRun {task_run_id} has a sealed supervisor generation."
                )
            replaced = self.active_runs.get(task_run_id)
            if replaced is not None and replaced._generation.is_sealed():
                raise RunRegistrationRejected(
                    f"TaskRun {task_run_id} has a sealed supervisor generation."
                )
            if replaced is not None and replaced._generation.is_reserved():
                raise RunRegistrationRejected(
                    f"TaskRun {task_run_id} has a finalizing supervisor generation."
                )
            self.active_runs[task_run_id] = run
            if replaced is not None:
                replaced._generation.mark_lost()
        return run

    def update_adapter_run_id(
        self,
        task_run_id: str,
        adapter_run_id: str,
        *,
        expected: Optional[SupervisedRun] = None,
    ) -> Optional[SupervisedRun]:
        with self._lock:
            current = self.active_runs.get(task_run_id)
            if (
                current is None
                or not self._matches_expected(current, expected)
                or current._generation.is_lost()
                or current._generation.is_reserved()
            ):
                return None
            if current.adapter_run_id == adapter_run_id:
                return current
            if current.adapter_run_id is not None:
                return None
            updated = SupervisedRun(
                task_run_id=current.task_run_id,
                adapter_run_id=adapter_run_id,
                adapter_type=current.adapter_type,
                started_at=current.started_at,
                adapter=current.adapter,
                _generation=current._generation,
            )
            self.active_runs[task_run_id] = updated
            return updated

    async def interrupt(
        self,
        task_run_id: str,
        *,
        expected: Optional[SupervisedRun] = None,
    ) -> bool:
        with self._lock:
            current = self.active_runs.get(task_run_id)
            if (
                current is None
                or not self._matches_expected(current, expected)
            ):
                return False
            claimed = current._generation.claim_interrupt()
            if not claimed:
                return False
            current._generation.mark_lost()
            adapter = current.adapter
            adapter_run_id = current.adapter_run_id
        if adapter is None or adapter_run_id is None:
            return False
        await adapter.interrupt(adapter_run_id)
        return True

    async def interrupt_exact(self, run: SupervisedRun) -> bool:
        with self._lock:
            claimed = run._generation.claim_interrupt()
            if not claimed:
                return False
            run._generation.mark_lost()
            adapter = run.adapter
            adapter_run_id = run.adapter_run_id
        if adapter is None or adapter_run_id is None:
            return False
        await adapter.interrupt(adapter_run_id)
        return True

    def run_if_current(
        self,
        expected: SupervisedRun,
        operation: Callable[[], _T],
    ) -> tuple[bool, Optional[_T]]:
        with self._lock:
            current = self.active_runs.get(expected.task_run_id)
            if (
                current is None
                or current._generation is not expected._generation
                or current._generation.is_lost()
                or current._generation.is_sealed()
                or not current._generation.try_reserve()
            ):
                return False, None
        try:
            result = operation()
        except BaseException:
            current._generation.release_reservation()
            raise
        current._generation.release_reservation()
        return True, result

    async def run_async_if_current(
        self,
        expected: SupervisedRun,
        operation: Callable[[], Awaitable[_T]],
    ) -> tuple[bool, Optional[_T]]:
        with self._lock:
            current = self.active_runs.get(expected.task_run_id)
            if (
                current is None
                or current._generation is not expected._generation
                or current._generation.is_lost()
                or current._generation.is_sealed()
                or not current._generation.try_reserve()
            ):
                return False, None
        try:
            result = await operation()
        finally:
            with self._lock:
                current._generation.release_reservation()
        return True, result

    def commit_if_current(
        self,
        expected: SupervisedRun,
        operation: Callable[[], _T],
    ) -> tuple[bool, Optional[_T]]:
        with self._lock:
            current = self.active_runs.get(expected.task_run_id)
            if (
                current is None
                or current._generation is not expected._generation
                or current._generation.is_lost()
                or current._generation.is_sealed()
                or not current._generation.try_reserve()
            ):
                return False, None
        try:
            result = operation()
        except BaseException:
            current._generation.release_reservation()
            raise
        with self._lock:
            sealed = current._generation.is_sealed()
            current._generation.release_reservation()
            if not sealed:
                return False, None
            self._sealed_generations[expected.task_run_id] = current._generation
        return True, result

    def seal_reserved_if_current(self, expected: SupervisedRun) -> bool:
        with self._lock:
            current = self.active_runs.get(expected.task_run_id)
            if (
                current is None
                or current._generation is not expected._generation
                or not current._generation.seal_reservation()
            ):
                return False
            self._sealed_generations[expected.task_run_id] = current._generation
            return True

    def unregister(
        self,
        task_run_id: str,
        *,
        expected: Optional[SupervisedRun] = None,
    ) -> Optional[SupervisedRun]:
        with self._lock:
            current = self.active_runs.get(task_run_id)
            if (
                current is None
                or not self._matches_expected(current, expected)
                or current._generation.is_reserved()
            ):
                return None
            removed = self.active_runs.pop(task_run_id)
            if removed._generation.is_sealed():
                self._sealed_generations[task_run_id] = removed._generation
        removed._generation.mark_lost()
        return removed

    def active(self, task_run_id: str) -> Optional[SupervisedRun]:
        with self._lock:
            return self.active_runs.get(task_run_id)

    def is_current(self, run: SupervisedRun) -> bool:
        with self._lock:
            current = self.active_runs.get(run.task_run_id)
            return bool(
                current is not None
                and current._generation is run._generation
                and not current._generation.is_lost()
            )

    @staticmethod
    def _matches_expected(
        current: SupervisedRun,
        expected: Optional[SupervisedRun],
    ) -> bool:
        return expected is None or current._generation is expected._generation


default_run_supervisor = RunSupervisor()
