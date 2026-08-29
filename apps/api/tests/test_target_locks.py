import json
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path
from threading import Barrier, Event, Thread
from time import monotonic

import app.events as events_module
import app.target_locks as target_locks_module
import pytest
from sqlalchemy import event
from sqlalchemy.pool import StaticPool
from sqlmodel import Session as DbSession
from sqlmodel import SQLModel, create_engine
from sqlmodel import select

from app.models import (
    Agent,
    Session,
    SessionQueueEntry,
    TargetLock,
    Task,
    TaskRun,
    TaskRunEvent,
    Workspace,
    utc_now,
)
from app.target_locks import (
    acquire_target_lock,
    held_lock_for_target,
    recover_terminal_holder_target_locks,
    recover_stale_target_locks,
    release_target_lock_for_task_run,
)
from app.task_runs import claim_task_run_for_worker, create_task_run
from app.target_registry import DEMO_BACKEND_TARGET_ID, DEMO_FRONTEND_TARGET_ID


def test_target_lock_allows_different_targets_concurrently() -> None:
    with lock_db() as db:
        first_session, first_run = seed_lock_run(
            db,
            session_title="First session",
            target_id=DEMO_FRONTEND_TARGET_ID,
        )
        second_session, second_run = seed_lock_run(
            db,
            session_title="Second session",
            target_id=DEMO_BACKEND_TARGET_ID,
        )
        first_run = claim_task_run_for_worker(db, first_run.id, worker_id="worker:first")
        second_run = claim_task_run_for_worker(db, second_run.id, worker_id="worker:second")

        first = acquire_target_lock(
            db,
            target_id=DEMO_FRONTEND_TARGET_ID,
            session_id=first_session.id,
            task_run_id=first_run.id,
            worker_id="worker:first",
            lease_expires_at=first_run.lease_expires_at,
        )
        second = acquire_target_lock(
            db,
            target_id=DEMO_BACKEND_TARGET_ID,
            session_id=second_session.id,
            task_run_id=second_run.id,
            worker_id="worker:second",
            lease_expires_at=second_run.lease_expires_at,
        )

        assert first.acquired is True
        assert second.acquired is True


@pytest.mark.parametrize(
    "lease_offset",
    (timedelta(0), -timedelta(seconds=1)),
    ids=("equal-now", "before-now"),
)
def test_target_lock_rejects_initial_expired_lease_without_persisting_or_event(
    monkeypatch: pytest.MonkeyPatch,
    lease_offset: timedelta,
) -> None:
    now = datetime(2026, 7, 26, 12, 0, 0)
    monkeypatch.setattr(target_locks_module, "utc_now", lambda: now)
    with lock_db() as db:
        session, run = seed_lock_run(db, session_title="Expired initial lease")
        run = claim_task_run_for_worker(db, run.id, worker_id="worker:expired")

        result = acquire_target_lock(
            db,
            target_id=DEMO_FRONTEND_TARGET_ID,
            session_id=session.id,
            task_run_id=run.id,
            worker_id="worker:expired",
            lease_expires_at=now + lease_offset,
        )

        locks = db.exec(select(TargetLock)).all()
        acquired_events = db.exec(
            select(TaskRunEvent)
            .where(TaskRunEvent.task_run_id == run.id)
            .where(TaskRunEvent.event_type == "target_lock.acquired")
        ).all()

        assert result.acquired is False
        assert result.lock is None
        assert result.holder_task_run_id is None
        assert locks == []
        assert acquired_events == []


def test_released_same_owner_reacquire_rotates_private_generation_at_fixed_time(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    now = utc_now()
    monkeypatch.setattr(target_locks_module, "utc_now", lambda: now)
    with lock_db() as db:
        session, run = seed_lock_run(db, session_title="Fixed-clock reacquire")
        run = claim_task_run_for_worker(db, run.id, worker_id="worker:fixed")
        first = acquire_target_lock(
            db,
            target_id=DEMO_FRONTEND_TARGET_ID,
            session_id=session.id,
            task_run_id=run.id,
            worker_id="worker:fixed",
            lease_expires_at=now + timedelta(minutes=5),
        )
        assert first.acquired is True
        assert first.lock is not None
        first_lock_id = first.lock.id
        first_acquired_at = first.lock.acquired_at
        first_lease = first.lock.lease_expires_at

        released = release_target_lock_for_task_run(
            db,
            target_id=DEMO_FRONTEND_TARGET_ID,
            expected_lock_id=first_lock_id,
            worker_id="worker:fixed",
            task_run_id=run.id,
            session_id=session.id,
            release_reason="fixed_clock_reacquire",
        )
        assert released is not None
        second = acquire_target_lock(
            db,
            target_id=DEMO_FRONTEND_TARGET_ID,
            session_id=session.id,
            task_run_id=run.id,
            worker_id="worker:fixed",
            lease_expires_at=now + timedelta(minutes=5),
        )
        locks = db.exec(select(TargetLock)).all()

        assert second.acquired is True
        assert second.lock is not None
        second_lock_id = second.lock.id
        second_acquired_at = second.lock.acquired_at
        second_lease = second.lock.lease_expires_at
        with DbSession(db.get_bind()) as fresh_db:
            durable = fresh_db.exec(
                select(TargetLock).where(
                    TargetLock.lock_key
                    == f"target:{DEMO_FRONTEND_TARGET_ID}:write"
                )
            ).one()

        assert second_lock_id != first_lock_id
        assert second_acquired_at == first_acquired_at
        assert second_lease == first_lease
        assert [lock.id for lock in locks] == [second_lock_id]
        assert durable.id == second_lock_id
        assert durable.acquired_at == second_acquired_at
        assert durable.lease_expires_at == second_lease
        assert durable.state == "held"


def test_delayed_release_for_old_generation_cannot_release_reacquired_generation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    now = utc_now()
    monkeypatch.setattr(target_locks_module, "utc_now", lambda: now)
    with lock_db() as db:
        session, run = seed_lock_run(db, session_title="Delayed generation release")
        run = claim_task_run_for_worker(db, run.id, worker_id="worker:delayed")
        first = acquire_target_lock(
            db,
            target_id=DEMO_FRONTEND_TARGET_ID,
            session_id=session.id,
            task_run_id=run.id,
            worker_id="worker:delayed",
            lease_expires_at=now + timedelta(minutes=5),
        )
        assert first.acquired is True
        assert first.lock is not None
        first_lock_id = first.lock.id

        released = release_target_lock_for_task_run(
            db,
            target_id=DEMO_FRONTEND_TARGET_ID,
            task_run_id=run.id,
            session_id=session.id,
            worker_id="worker:delayed",
            expected_lock_id=first_lock_id,
            release_reason="generation_a_complete",
        )
        assert released is not None
        second = acquire_target_lock(
            db,
            target_id=DEMO_FRONTEND_TARGET_ID,
            session_id=session.id,
            task_run_id=run.id,
            worker_id="worker:delayed",
            lease_expires_at=now + timedelta(minutes=5),
        )
        assert second.acquired is True
        assert second.lock is not None
        second_lock_id = second.lock.id
        assert second_lock_id != first_lock_id

        delayed = release_target_lock_for_task_run(
            db,
            target_id=DEMO_FRONTEND_TARGET_ID,
            task_run_id=run.id,
            session_id=session.id,
            worker_id="worker:delayed",
            expected_lock_id=first_lock_id,
            release_reason="delayed_generation_a_duplicate",
        )
        with DbSession(db.get_bind()) as fresh_db:
            durable = fresh_db.exec(
                select(TargetLock).where(
                    TargetLock.lock_key
                    == f"target:{DEMO_FRONTEND_TARGET_ID}:write"
                )
            ).one()

        assert delayed is None
        assert durable.id == second_lock_id
        assert durable.state == "held"
        assert durable.release_reason is None


def test_release_receipt_survives_same_key_reacquire_after_commit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = file_lock_engine(tmp_path)
    with DbSession(engine) as setup_db:
        first_session, first_run = seed_lock_run(
            setup_db,
            session_title="Release receipt generation A",
        )
        second_session, second_run = seed_lock_run(
            setup_db,
            session_title="Release receipt generation B",
        )
        first_worker_id = "worker:release-receipt:a"
        second_worker_id = "worker:release-receipt:b"
        first_run = claim_task_run_for_worker(
            setup_db,
            first_run.id,
            worker_id=first_worker_id,
        )
        second_run = claim_task_run_for_worker(
            setup_db,
            second_run.id,
            worker_id=second_worker_id,
        )
        acquired = acquire_target_lock(
            setup_db,
            target_id=DEMO_FRONTEND_TARGET_ID,
            session_id=first_session.id,
            task_run_id=first_run.id,
            worker_id=first_worker_id,
            lease_expires_at=first_run.lease_expires_at,
        )
        assert acquired.lock is not None
        first_lock_id = acquired.lock.id
        first_session_id = first_session.id
        first_run_id = first_run.id
        second_session_id = second_session.id
        second_run_id = second_run.id
        second_lease_expires_at = second_run.lease_expires_at

    replacement_lock_ids: list[str] = []
    with DbSession(engine) as release_db, DbSession(engine) as replacement_db:
        original_commit = release_db.commit

        def commit_then_reacquire() -> None:
            original_commit()
            if replacement_lock_ids:
                return
            replacement = acquire_target_lock(
                replacement_db,
                target_id=DEMO_FRONTEND_TARGET_ID,
                session_id=second_session_id,
                task_run_id=second_run_id,
                worker_id=second_worker_id,
                lease_expires_at=second_lease_expires_at,
            )
            assert replacement.acquired is True
            assert replacement.lock is not None
            replacement_lock_ids.append(replacement.lock.id)

        monkeypatch.setattr(release_db, "commit", commit_then_reacquire)
        released = release_target_lock_for_task_run(
            release_db,
            target_id=DEMO_FRONTEND_TARGET_ID,
            expected_lock_id=first_lock_id,
            worker_id=first_worker_id,
            task_run_id=first_run_id,
            session_id=first_session_id,
            release_reason="generation_a_complete_before_b_reacquire",
        )

    with DbSession(engine) as fresh_db:
        durable_lock = fresh_db.exec(
            select(TargetLock).where(
                TargetLock.lock_key
                == f"target:{DEMO_FRONTEND_TARGET_ID}:write"
            )
        ).one()
        release_events = fresh_db.exec(
            select(TaskRunEvent)
            .where(TaskRunEvent.task_run_id == first_run_id)
            .where(TaskRunEvent.event_type == "target_lock.released")
        ).all()
        first_metrics = fresh_db.get(TaskRun, first_run_id).metrics_json
        second_metrics = fresh_db.get(TaskRun, second_run_id).metrics_json
    engine.dispose()

    assert released is not None
    assert len(replacement_lock_ids) == 1
    assert durable_lock.id == replacement_lock_ids[0]
    assert durable_lock.state == "held"
    assert durable_lock.task_run_id == second_run_id
    assert len(release_events) == 1
    durable_evidence = " ".join(
        [
            release_events[0].payload_json,
            first_metrics,
            second_metrics,
            repr(released),
        ]
    )
    assert first_lock_id not in durable_evidence
    assert replacement_lock_ids[0] not in durable_evidence


def test_continuous_same_holder_acquire_preserves_lock_generation_and_lease(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    now = utc_now()
    monkeypatch.setattr(target_locks_module, "utc_now", lambda: now)
    with lock_db() as db:
        session, run = seed_lock_run(db, session_title="Continuous holder")
        run = claim_task_run_for_worker(db, run.id, worker_id="worker:continuous")
        original_lease = now + timedelta(minutes=5)
        first = acquire_target_lock(
            db,
            target_id=DEMO_FRONTEND_TARGET_ID,
            session_id=session.id,
            task_run_id=run.id,
            worker_id="worker:continuous",
            lease_expires_at=original_lease,
        )
        assert first.acquired is True
        assert first.lock is not None
        first_lock_id = first.lock.id
        first_acquired_at = first.lock.acquired_at
        first_lease = first.lock.lease_expires_at

        repeated = acquire_target_lock(
            db,
            target_id=DEMO_FRONTEND_TARGET_ID,
            session_id=session.id,
            task_run_id=run.id,
            worker_id="worker:continuous",
            lease_expires_at=now + timedelta(minutes=10),
        )
        acquired_events = db.exec(
            select(TaskRunEvent)
            .where(TaskRunEvent.task_run_id == run.id)
            .where(TaskRunEvent.event_type == "target_lock.acquired")
            .order_by(TaskRunEvent.sequence)
        ).all()
        repeated_lock_id = repeated.lock.id if repeated.lock is not None else None
        repeated_acquired_at = (
            repeated.lock.acquired_at if repeated.lock is not None else None
        )
        repeated_lease = (
            repeated.lock.lease_expires_at if repeated.lock is not None else None
        )
        with DbSession(db.get_bind()) as fresh_db:
            durable = fresh_db.exec(
                select(TargetLock).where(
                    TargetLock.lock_key
                    == f"target:{DEMO_FRONTEND_TARGET_ID}:write"
                )
            ).one()

        assert repeated.acquired is True
        assert repeated.lock is not None
        assert repeated_lock_id == first_lock_id
        assert repeated_acquired_at == first_acquired_at
        assert repeated_lease == first_lease == original_lease
        assert durable.id == first_lock_id
        assert durable.acquired_at == first_acquired_at
        assert durable.lease_expires_at == first_lease
        acquired_payloads = [json.loads(item.payload_json) for item in acquired_events]
        assert [payload["acquiredAt"] for payload in acquired_payloads] == [
            first_acquired_at.isoformat(),
            first_acquired_at.isoformat(),
        ]
        assert all(payload["reason"] == "acquired" for payload in acquired_payloads)


def test_acquired_generation_is_omitted_from_runtime_repr() -> None:
    with lock_db() as db:
        session, run = seed_lock_run(
            db,
            session_title="Private acquisition repr",
        )
        worker_id = "worker:private-acquisition-repr"
        run = claim_task_run_for_worker(db, run.id, worker_id=worker_id)
        result = acquire_target_lock(
            db,
            target_id=DEMO_FRONTEND_TARGET_ID,
            session_id=session.id,
            task_run_id=run.id,
            worker_id=worker_id,
            lease_expires_at=run.lease_expires_at,
        )
        assert result.lock is not None
        private_lock_id = result.lock.id

        assert private_lock_id not in repr(result)
        assert private_lock_id not in repr(result.lock)


def test_target_lock_lifecycle_sse_omits_private_generations() -> None:
    boundary = utc_now()
    with lock_db() as db:
        session, run = seed_lock_run(
            db,
            session_title="Private lock SSE lifecycle",
            target_id=DEMO_BACKEND_TARGET_ID,
        )
        worker_id = "worker:private-lock-sse"
        run = claim_task_run_for_worker(db, run.id, worker_id=worker_id)
        acquired = acquire_target_lock(
            db,
            target_id=DEMO_BACKEND_TARGET_ID,
            session_id=session.id,
            task_run_id=run.id,
            worker_id=worker_id,
            lease_expires_at=boundary + timedelta(minutes=5),
        )
        assert acquired.lock is not None
        released_generation_id = acquired.lock.id
        assert acquired.lock.acquired_at is not None
        assert acquired.lock.lease_expires_at is not None
        acquired_at = acquired.lock.acquired_at.isoformat()
        acquired_lease_expires_at = acquired.lock.lease_expires_at.isoformat()
        expected_acquired_payload = {
            "lockKey": f"target:{DEMO_BACKEND_TARGET_ID}:write",
            "targetId": DEMO_BACKEND_TARGET_ID,
            "sessionId": session.id,
            "holderTaskRunId": run.id,
            "workerId": worker_id,
            "mode": "write",
            "state": "held",
            "leaseExpiresAt": acquired_lease_expires_at,
            "acquiredAt": acquired_at,
            "releasedAt": None,
            "releaseReason": None,
            "reason": "acquired",
        }
        released = release_target_lock_for_task_run(
            db,
            target_id=DEMO_BACKEND_TARGET_ID,
            expected_lock_id=released_generation_id,
            worker_id=worker_id,
            task_run_id=run.id,
            session_id=session.id,
            release_reason="private_lock_sse_release",
        )
        assert released is not None
        expected_released_payload = {
            "lockKey": f"target:{DEMO_BACKEND_TARGET_ID}:write",
            "targetId": DEMO_BACKEND_TARGET_ID,
            "sessionId": session.id,
            "holderTaskRunId": run.id,
            "workerId": None,
            "mode": "write",
            "state": "released",
            "leaseExpiresAt": None,
            "acquiredAt": acquired_at,
            "releasedAt": released.released_at.isoformat(),
            "releaseReason": "private_lock_sse_release",
            "reason": "private_lock_sse_release",
        }

        stale_candidate = seed_stale_recovery_candidate(
            db,
            boundary=boundary,
            title="Private stale lock SSE",
        )
        stale_generation_id = stale_candidate["lock_id"]
        stale_lock = db.get(TargetLock, stale_generation_id)
        assert stale_lock is not None
        assert stale_lock.acquired_at is not None
        stale_acquired_at = stale_lock.acquired_at.isoformat()
        recovered = recover_stale_target_locks(db, now=boundary)
        assert [item.id for item in recovered] == [stale_generation_id]

        stale_run = db.get(TaskRun, stale_candidate["task_run_id"])
        assert stale_run is not None
        stale_task = db.get(Task, stale_run.task_id)
        assert stale_task is not None
        expected_stale_payload = {
            "lockKey": f"target:{DEMO_FRONTEND_TARGET_ID}:write",
            "targetId": DEMO_FRONTEND_TARGET_ID,
            "sessionId": stale_task.session_id,
            "holderTaskRunId": stale_run.id,
            "workerId": None,
            "mode": "write",
            "state": "stale_released",
            "leaseExpiresAt": None,
            "acquiredAt": stale_acquired_at,
            "releasedAt": boundary.isoformat(),
            "releaseReason": "stale_lease_expired",
            "reason": "stale_lease_expired",
        }
        replayed_events = [
            *events_module.list_session_events(db, session.id),
            *events_module.list_session_events(db, stale_task.session_id),
        ]
        selected_events = tuple(
            next(
                event
                for event in replayed_events
                if event.task_run_id == task_run_id
                and event.event_type == event_type
            )
            for task_run_id, event_type in (
                (run.id, "target_lock.acquired"),
                (run.id, "target_lock.released"),
                (stale_run.id, "target_lock.stale_released"),
            )
        )
        encoded = {
            event.event_type: events_module.encode_sse_event(event)
            for event in selected_events
        }

    decoded = {}
    for event in selected_events:
        wire = encoded[event.event_type]
        data_line = next(
            line for line in wire.splitlines() if line.startswith("data: ")
        )
        data = json.loads(data_line.removeprefix("data: "))
        decoded[event.event_type] = data
        assert set(data) == {
            "id",
            "taskRunId",
            "eventType",
            "payload",
            "sequence",
            "createdAt",
        }
        assert data["id"] == event.id
        assert data["taskRunId"] == event.task_run_id
        assert data["eventType"] == event.event_type
        assert data["sequence"] == event.sequence
        assert data["createdAt"] == event.created_at.isoformat()

    assert {
        event_type: data["payload"] for event_type, data in decoded.items()
    } == {
        "target_lock.acquired": expected_acquired_payload,
        "target_lock.released": expected_released_payload,
        "target_lock.stale_released": expected_stale_payload,
    }

    forbidden_generation_keys = {
        "id",
        "lockId",
        "lock_id",
        "targetLockId",
        "generationId",
    }
    for generation_id in (released_generation_id, stale_generation_id):
        assert all(generation_id not in wire for wire in encoded.values())
    assert all(
        forbidden_generation_keys.isdisjoint(data["payload"])
        for data in decoded.values()
    )


def test_released_generation_has_one_durable_winner_under_concurrent_acquire(
    tmp_path: Path,
) -> None:
    engine = file_lock_engine(tmp_path)
    with DbSession(engine) as setup_db:
        original_session, original_run = seed_lock_run(
            setup_db,
            session_title="Original released generation",
        )
        original_run = claim_task_run_for_worker(
            setup_db,
            original_run.id,
            worker_id="worker:original-generation",
        )
        original = acquire_target_lock(
            setup_db,
            target_id=DEMO_FRONTEND_TARGET_ID,
            session_id=original_session.id,
            task_run_id=original_run.id,
            worker_id="worker:original-generation",
            lease_expires_at=original_run.lease_expires_at,
        )
        assert original.acquired is True
        assert original.lock is not None
        original_generation_id = original.lock.id
        released = release_target_lock_for_task_run(
            setup_db,
            target_id=DEMO_FRONTEND_TARGET_ID,
            expected_lock_id=original_generation_id,
            worker_id="worker:original-generation",
            task_run_id=original_run.id,
            session_id=original_session.id,
            release_reason="prepare_concurrent_acquire",
        )
        assert released is not None

        contenders: dict[str, dict[str, object]] = {}
        for name in ("first", "second"):
            contender_session, contender_run = seed_lock_run(
                setup_db,
                session_title=f"Concurrent contender {name}",
            )
            worker_id = f"worker:concurrent:{name}"
            contender_run = claim_task_run_for_worker(
                setup_db,
                contender_run.id,
                worker_id=worker_id,
            )
            contenders[name] = {
                "session_id": contender_session.id,
                "task_run_id": contender_run.id,
                "worker_id": worker_id,
                "lease_expires_at": contender_run.lease_expires_at,
            }

    acquire_barrier = Barrier(3)
    results: dict[str, dict[str, object]] = {}
    errors: list[BaseException] = []

    def synchronize_acquire_update(
        connection,
        cursor,
        statement,
        parameters,
        context,
        executemany,
    ) -> None:
        normalized = " ".join(statement.lower().split())
        if normalized.startswith("update targetlock set id="):
            acquire_barrier.wait(timeout=5)

    def contend(name: str) -> None:
        contender = contenders[name]
        try:
            with DbSession(engine) as contender_db:
                result = acquire_target_lock(
                    contender_db,
                    target_id=DEMO_FRONTEND_TARGET_ID,
                    session_id=contender["session_id"],
                    task_run_id=contender["task_run_id"],
                    worker_id=contender["worker_id"],
                    lease_expires_at=contender["lease_expires_at"],
                )
                results[name] = {
                    "acquired": result.acquired,
                    "lock_id": result.lock.id if result.lock is not None else None,
                    "holder_task_run_id": result.holder_task_run_id,
                }
        except BaseException as exc:
            errors.append(exc)

    event.listen(engine, "before_cursor_execute", synchronize_acquire_update)
    threads = [
        Thread(target=contend, args=(name,), daemon=True)
        for name in contenders
    ]
    try:
        for thread in threads:
            thread.start()
        acquire_barrier.wait(timeout=5)
        for thread in threads:
            thread.join(timeout=5)
    finally:
        for thread in threads:
            thread.join(timeout=5)
        event.remove(engine, "before_cursor_execute", synchronize_acquire_update)

    assert all(thread.is_alive() is False for thread in threads)
    assert errors == []
    assert set(results) == set(contenders)
    winners = [name for name, result in results.items() if result["acquired"] is True]
    assert len(winners) == 1
    winner_name = winners[0]
    loser_name = next(name for name in contenders if name != winner_name)
    winner = contenders[winner_name]
    loser = contenders[loser_name]

    with DbSession(engine) as fresh_db:
        durable = fresh_db.exec(
            select(TargetLock).where(
                TargetLock.lock_key
                == f"target:{DEMO_FRONTEND_TARGET_ID}:write"
            )
        ).one()
        contender_run_ids = [
            contender["task_run_id"] for contender in contenders.values()
        ]
        lock_events = fresh_db.exec(
            select(TaskRunEvent)
            .where(TaskRunEvent.task_run_id.in_(contender_run_ids))
            .where(
                TaskRunEvent.event_type.in_(
                    ["target_lock.acquired", "target_lock.acquire_failed"]
                )
            )
            .order_by(TaskRunEvent.sequence)
        ).all()
    engine.dispose()

    assert durable.id != original_generation_id
    assert durable.id == results[winner_name]["lock_id"]
    assert durable.session_id == winner["session_id"]
    assert durable.task_run_id == winner["task_run_id"]
    assert durable.worker_id == winner["worker_id"]
    assert durable.state == "held"
    assert results[loser_name]["holder_task_run_id"] == winner["task_run_id"]
    acquired_events = [
        item for item in lock_events if item.event_type == "target_lock.acquired"
    ]
    failed_events = [
        item for item in lock_events if item.event_type == "target_lock.acquire_failed"
    ]
    assert len(acquired_events) == 1
    assert acquired_events[0].task_run_id == winner["task_run_id"]
    assert len(failed_events) == 1
    assert failed_events[0].task_run_id == loser["task_run_id"]
    failed_payload = json.loads(failed_events[0].payload_json)
    assert failed_payload["holderTaskRunId"] == winner["task_run_id"]
    assert failed_payload["waitingTaskRunId"] == loser["task_run_id"]
    assert failed_payload["waitingSessionId"] == loser["session_id"]
    assert failed_payload["reason"] == "waiting_lock"


def test_expired_same_holder_cannot_reacquire_without_release(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clock = {"now": utc_now()}
    monkeypatch.setattr(target_locks_module, "utc_now", lambda: clock["now"])
    with lock_db() as db:
        session, run = seed_lock_run(db, session_title="Expired holder")
        run = claim_task_run_for_worker(db, run.id, worker_id="worker:expired-holder")
        first = acquire_target_lock(
            db,
            target_id=DEMO_FRONTEND_TARGET_ID,
            session_id=session.id,
            task_run_id=run.id,
            worker_id="worker:expired-holder",
            lease_expires_at=clock["now"] + timedelta(seconds=1),
        )
        assert first.acquired is True
        assert first.lock is not None
        first_lock_id = first.lock.id
        first_acquired_at = first.lock.acquired_at
        first_lease = first.lock.lease_expires_at
        clock["now"] += timedelta(seconds=2)

        repeated = acquire_target_lock(
            db,
            target_id=DEMO_FRONTEND_TARGET_ID,
            session_id=session.id,
            task_run_id=run.id,
            worker_id="worker:expired-holder",
            lease_expires_at=clock["now"] + timedelta(minutes=5),
        )

        assert repeated.acquired is False
        assert repeated.lock is not None
        assert repeated.lock.id == first_lock_id
        assert repeated.lock.acquired_at == first_acquired_at
        assert repeated.lock.lease_expires_at == first_lease
        assert held_lock_for_target(db, DEMO_FRONTEND_TARGET_ID) is None


@pytest.mark.parametrize("acquire_path", ("released-update", "absent-insert"))
def test_acquire_event_failure_rolls_back_generation_mutation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    acquire_path: str,
) -> None:
    engine = file_lock_engine(tmp_path)
    with DbSession(engine) as setup_db:
        candidate = seed_acquire_candidate(
            setup_db,
            acquire_path=acquire_path,
            title="Atomic acquired event failure",
        )

    with DbSession(engine) as acquire_db:
        original_flush = acquire_db.flush

        def fail_acquired_event_flush(objects=None) -> None:
            if any(
                isinstance(item, TaskRunEvent)
                and item.event_type == "target_lock.acquired"
                for item in acquire_db.new
            ):
                raise RuntimeError("injected acquired event insertion failure")
            original_flush(objects)

        monkeypatch.setattr(acquire_db, "flush", fail_acquired_event_flush)
        with pytest.raises(
            RuntimeError,
            match="injected acquired event insertion failure",
        ):
            acquire_target_lock(
                acquire_db,
                target_id=DEMO_FRONTEND_TARGET_ID,
                session_id=candidate["session_id"],
                task_run_id=candidate["task_run_id"],
                worker_id=candidate["worker_id"],
                lease_expires_at=candidate["lease_expires_at"],
            )

    with DbSession(engine) as fresh_db:
        durable_lock = fresh_db.exec(select(TargetLock)).first()
        acquired_events = fresh_db.exec(
            select(TaskRunEvent)
            .where(TaskRunEvent.task_run_id == candidate["task_run_id"])
            .where(TaskRunEvent.event_type == "target_lock.acquired")
        ).all()
    engine.dispose()

    assert acquired_events == []
    if acquire_path == "released-update":
        assert durable_lock is not None
        assert durable_lock.id == candidate["original_lock_id"]
        assert durable_lock.state == "released"
    else:
        assert durable_lock is None


@pytest.mark.parametrize("acquire_path", ("released-update", "absent-insert"))
def test_acquire_publication_failure_preserves_durable_receipt(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    acquire_path: str,
) -> None:
    engine = file_lock_engine(tmp_path)
    with DbSession(engine) as setup_db:
        candidate = seed_acquire_candidate(
            setup_db,
            acquire_path=acquire_path,
            title="Acquired event publication failure",
        )

    publication_attempts = 0

    def fail_acquired_event_publication(db, event) -> None:
        nonlocal publication_attempts
        publication_attempts += 1
        raise RuntimeError("injected acquired event publication failure")

    monkeypatch.setattr(
        events_module,
        "publish_task_run_event",
        fail_acquired_event_publication,
    )
    monkeypatch.setattr(
        target_locks_module,
        "publish_task_run_event",
        fail_acquired_event_publication,
    )
    with DbSession(engine) as acquire_db:
        result = acquire_target_lock(
            acquire_db,
            target_id=DEMO_FRONTEND_TARGET_ID,
            session_id=candidate["session_id"],
            task_run_id=candidate["task_run_id"],
            worker_id=candidate["worker_id"],
            lease_expires_at=candidate["lease_expires_at"],
        )

    with DbSession(engine) as fresh_db:
        durable_lock = fresh_db.exec(select(TargetLock)).one()
        acquired_events = fresh_db.exec(
            select(TaskRunEvent)
            .where(TaskRunEvent.task_run_id == candidate["task_run_id"])
            .where(TaskRunEvent.event_type == "target_lock.acquired")
        ).all()
    engine.dispose()

    assert publication_attempts == 1
    assert result.acquired is True
    assert result.lock is not None
    assert durable_lock.id == result.lock.id
    assert durable_lock.state == "held"
    assert len(acquired_events) == 1


@pytest.mark.parametrize("acquire_path", ("released-update", "absent-insert"))
def test_acquire_uses_durable_receipt_after_post_commit_lease_expiry(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    acquire_path: str,
) -> None:
    engine = file_lock_engine(tmp_path)
    with DbSession(engine) as setup_db:
        candidate = seed_acquire_candidate(
            setup_db,
            acquire_path=acquire_path,
            title="Post commit lease boundary",
        )

    acquisition_started_at = utc_now()
    lease_expires_at = acquisition_started_at + timedelta(minutes=5)
    clock_calls = 0

    def cross_expiry_after_mutation() -> datetime:
        nonlocal clock_calls
        clock_calls += 1
        if clock_calls == 1:
            return acquisition_started_at
        return lease_expires_at + timedelta(seconds=1)

    monkeypatch.setattr(
        target_locks_module,
        "utc_now",
        cross_expiry_after_mutation,
    )
    with DbSession(engine) as acquire_db:
        result = acquire_target_lock(
            acquire_db,
            target_id=DEMO_FRONTEND_TARGET_ID,
            session_id=candidate["session_id"],
            task_run_id=candidate["task_run_id"],
            worker_id=candidate["worker_id"],
            lease_expires_at=lease_expires_at,
        )

    with DbSession(engine) as fresh_db:
        durable_lock = fresh_db.exec(select(TargetLock)).one()
        acquired_events = fresh_db.exec(
            select(TaskRunEvent)
            .where(TaskRunEvent.task_run_id == candidate["task_run_id"])
            .where(TaskRunEvent.event_type == "target_lock.acquired")
        ).all()
    engine.dispose()

    assert result.acquired is True
    assert result.lock is not None
    assert durable_lock.id == result.lock.id
    assert durable_lock.state == "held"
    assert len(acquired_events) == 1


@pytest.mark.parametrize(
    "acquire_path",
    ("released-update", "absent-insert"),
)
def test_acquire_rechecks_sqlite_time_after_write_lock_wait(
    tmp_path: Path,
    acquire_path: str,
) -> None:
    engine = file_lock_engine(tmp_path)
    with engine.connect() as connection:
        connection.exec_driver_sql("PRAGMA journal_mode=WAL")

    original_lock_id = None
    if acquire_path == "released-update":
        with DbSession(engine) as setup_db:
            original_session, original_run = seed_lock_run(
                setup_db,
                session_title="Released row before delayed acquire",
            )
            original_run = claim_task_run_for_worker(
                setup_db,
                original_run.id,
                worker_id="worker:delayed-acquire:original",
            )
            original = acquire_target_lock(
                setup_db,
                target_id=DEMO_FRONTEND_TARGET_ID,
                session_id=original_session.id,
                task_run_id=original_run.id,
                worker_id="worker:delayed-acquire:original",
                lease_expires_at=original_run.lease_expires_at,
            )
            assert original.lock is not None
            original_lock_id = original.lock.id
            released = release_target_lock_for_task_run(
                setup_db,
                target_id=DEMO_FRONTEND_TARGET_ID,
                expected_lock_id=original_lock_id,
                worker_id="worker:delayed-acquire:original",
                task_run_id=original_run.id,
                session_id=original_session.id,
                release_reason="prepare_delayed_acquire",
            )
            assert released is not None

    with DbSession(engine) as setup_db:
        contender_session, contender_run = seed_lock_run(
            setup_db,
            session_title=f"Delayed acquire {acquire_path}",
        )
        worker_id = f"worker:delayed-acquire:{acquire_path}"
        contender_run = claim_task_run_for_worker(
            setup_db,
            contender_run.id,
            worker_id=worker_id,
        )
        contender_session_id = contender_session.id
        contender_run_id = contender_run.id

    with engine.connect() as connection:
        lease_text = connection.exec_driver_sql(
            "SELECT strftime('%Y-%m-%d %H:%M:%f', 'now', '+2 seconds')"
        ).scalar_one()
    lease_expires_at = datetime.fromisoformat(lease_text)

    write_started = Event()
    acquire_finished = Event()
    results: list[dict[str, object]] = []
    errors: list[BaseException] = []

    def before_cursor_execute(
        connection,
        cursor,
        statement,
        parameters,
        context,
        executemany,
    ) -> None:
        normalized = " ".join(statement.lower().split())
        if normalized.startswith("update targetlock set id="):
            write_started.set()

    def delayed_acquire() -> None:
        try:
            with DbSession(engine) as contender_db:
                result = acquire_target_lock(
                    contender_db,
                    target_id=DEMO_FRONTEND_TARGET_ID,
                    session_id=contender_session_id,
                    task_run_id=contender_run_id,
                    worker_id=worker_id,
                    lease_expires_at=lease_expires_at,
                )
                results.append(
                    {
                        "acquired": result.acquired,
                        "lock_id": result.lock.id if result.lock is not None else None,
                    }
                )
        except BaseException as exc:
            errors.append(exc)
        finally:
            acquire_finished.set()

    event.listen(engine, "before_cursor_execute", before_cursor_execute)
    blocker = engine.connect()
    thread = Thread(target=delayed_acquire, daemon=True)
    try:
        blocker.exec_driver_sql("BEGIN IMMEDIATE")
        thread.start()
        assert write_started.wait(timeout=5)
        assert acquire_finished.is_set() is False
        assert blocker.exec_driver_sql(
            "SELECT julianday(?) > julianday('now')",
            (lease_text,),
        ).scalar_one() == 1

        deadline = monotonic() + 5
        while blocker.exec_driver_sql(
            "SELECT julianday(?) <= julianday('now')",
            (lease_text,),
        ).scalar_one() != 1:
            assert monotonic() < deadline
            acquire_finished.wait(timeout=0.01)

        assert acquire_finished.is_set() is False
        blocker.commit()
        assert acquire_finished.wait(timeout=5)
        thread.join(timeout=5)
    finally:
        if blocker.in_transaction():
            blocker.rollback()
        blocker.close()
        thread.join(timeout=5)
        event.remove(engine, "before_cursor_execute", before_cursor_execute)

    assert thread.is_alive() is False
    assert errors == []
    assert results == [{"acquired": False, "lock_id": original_lock_id}]

    with DbSession(engine) as fresh_db:
        durable_lock = fresh_db.exec(select(TargetLock)).first()
        acquired_events = fresh_db.exec(
            select(TaskRunEvent)
            .where(TaskRunEvent.task_run_id == contender_run_id)
            .where(TaskRunEvent.event_type == "target_lock.acquired")
        ).all()
        current_held = held_lock_for_target(fresh_db, DEMO_FRONTEND_TARGET_ID)
    engine.dispose()

    assert current_held is None
    assert acquired_events == []
    if acquire_path == "released-update":
        assert durable_lock is not None
        assert durable_lock.id == original_lock_id
        assert durable_lock.state == "released"
    else:
        assert durable_lock is None


def test_target_lock_acquire_blocks_second_holder_until_release() -> None:
    with lock_db() as db:
        first_session, first_run = seed_lock_run(db, session_title="First session")
        second_session, second_run = seed_lock_run(db, session_title="Second session")
        first_run = claim_task_run_for_worker(db, first_run.id, worker_id="worker:first")
        second_run = claim_task_run_for_worker(db, second_run.id, worker_id="worker:second")

        first = acquire_target_lock(
            db,
            target_id=DEMO_FRONTEND_TARGET_ID,
            session_id=first_session.id,
            task_run_id=first_run.id,
            worker_id="worker:first",
            lease_expires_at=first_run.lease_expires_at,
        )
        second = acquire_target_lock(
            db,
            target_id=DEMO_FRONTEND_TARGET_ID,
            session_id=second_session.id,
            task_run_id=second_run.id,
            worker_id="worker:second",
            lease_expires_at=second_run.lease_expires_at,
        )

        assert first.acquired is True
        assert first.lock is not None
        assert second.acquired is False
        assert second.holder_task_run_id == first_run.id

        release_target_lock_for_task_run(
            db,
            target_id=DEMO_FRONTEND_TARGET_ID,
            expected_lock_id=first.lock.id,
            worker_id="worker:first",
            task_run_id=first_run.id,
            session_id=first_session.id,
            release_reason="test_complete",
        )
        retried = acquire_target_lock(
            db,
            target_id=DEMO_FRONTEND_TARGET_ID,
            session_id=second_session.id,
            task_run_id=second_run.id,
            worker_id="worker:second",
            lease_expires_at=second_run.lease_expires_at,
        )
        assert retried.acquired is True


def test_target_lock_release_is_idempotent_and_holder_scoped() -> None:
    with lock_db() as db:
        first_session, first_run = seed_lock_run(db, session_title="First session")
        second_session, second_run = seed_lock_run(db, session_title="Second session")
        first_run = claim_task_run_for_worker(db, first_run.id, worker_id="worker:first")
        second_run = claim_task_run_for_worker(db, second_run.id, worker_id="worker:second")
        first_lock = acquire_target_lock(
            db,
            target_id=DEMO_FRONTEND_TARGET_ID,
            session_id=first_session.id,
            task_run_id=first_run.id,
            worker_id="worker:first",
            lease_expires_at=first_run.lease_expires_at,
        )
        assert first_lock.acquired is True
        assert first_lock.lock is not None
        first_lock_id = first_lock.lock.id

        mismatch = release_target_lock_for_task_run(
            db,
            target_id=DEMO_FRONTEND_TARGET_ID,
            expected_lock_id=first_lock_id,
            worker_id="worker:second",
            task_run_id=second_run.id,
            session_id=second_session.id,
            release_reason="wrong_holder",
        )
        held = held_lock_for_target(db, DEMO_FRONTEND_TARGET_ID)
        released = release_target_lock_for_task_run(
            db,
            target_id=DEMO_FRONTEND_TARGET_ID,
            expected_lock_id=first_lock_id,
            worker_id="worker:first",
            task_run_id=first_run.id,
            session_id=first_session.id,
            release_reason="owner_complete",
        )
        duplicate = release_target_lock_for_task_run(
            db,
            target_id=DEMO_FRONTEND_TARGET_ID,
            expected_lock_id=first_lock_id,
            worker_id="worker:first",
            task_run_id=first_run.id,
            session_id=first_session.id,
            release_reason="duplicate",
        )

        assert mismatch is None
        assert held.task_run_id == first_run.id
        assert released.release_reason == "owner_complete"
        assert duplicate is None


def test_recover_stale_lock_fails_uncertain_holder_without_claiming_success() -> None:
    with lock_db() as db:
        session, run = seed_lock_run(db, session_title="Stale session")
        run = claim_task_run_for_worker(db, run.id, worker_id="worker:stale")
        lock_result = acquire_target_lock(
            db,
            target_id=DEMO_FRONTEND_TARGET_ID,
            session_id=session.id,
            task_run_id=run.id,
            worker_id="worker:stale",
            lease_expires_at=run.lease_expires_at,
        )
        run.lease_expires_at = utc_now() - timedelta(minutes=1)
        lock_result.lock.lease_expires_at = run.lease_expires_at
        db.add(run)
        db.add(lock_result.lock)
        db.commit()

        recovered = recover_stale_target_locks(db)

        stored_run = db.get(TaskRun, run.id)
        assert [lock.lock_key for lock in recovered] == [f"target:{DEMO_FRONTEND_TARGET_ID}:write"]
        assert stored_run.state == "failed"
        assert stored_run.error_code == "TASK_RUN_STALE"
        assert stored_run.error_message
        assert "success" not in stored_run.error_message.lower()


def test_recover_terminal_holder_locks_does_not_release_uncertain_active_run() -> None:
    with lock_db() as db:
        session, run = seed_lock_run(db, session_title="Active lock session")
        run = claim_task_run_for_worker(db, run.id, worker_id="worker:active")
        acquire_target_lock(
            db,
            target_id=DEMO_FRONTEND_TARGET_ID,
            session_id=session.id,
            task_run_id=run.id,
            worker_id="worker:active",
            lease_expires_at=run.lease_expires_at,
        )
        run.lease_expires_at = utc_now() - timedelta(minutes=1)
        db.add(run)
        db.commit()

        recovered = recover_terminal_holder_target_locks(db)

        stored_run = db.get(TaskRun, run.id)
        assert recovered == []
        assert stored_run.state == "queued"
        assert held_lock_for_target(db, DEMO_FRONTEND_TARGET_ID).task_run_id == run.id


def test_recover_terminal_holder_locks_releases_completed_holder() -> None:
    with lock_db() as db:
        session, run = seed_lock_run(db, session_title="Completed lock session")
        run = claim_task_run_for_worker(db, run.id, worker_id="worker:complete")
        acquire_target_lock(
            db,
            target_id=DEMO_FRONTEND_TARGET_ID,
            session_id=session.id,
            task_run_id=run.id,
            worker_id="worker:complete",
            lease_expires_at=run.lease_expires_at,
        )
        run.state = "completed"
        run.ended_at = utc_now()
        db.add(run)
        db.commit()

        recovered = recover_terminal_holder_target_locks(db)

        assert [lock.lock_key for lock in recovered] == [f"target:{DEMO_FRONTEND_TARGET_ID}:write"]
        assert held_lock_for_target(db, DEMO_FRONTEND_TARGET_ID) is None


def test_recovery_result_remains_readable_after_same_lock_key_is_reacquired(
    tmp_path: Path,
) -> None:
    engine = file_lock_engine(tmp_path)
    with DbSession(engine) as db:
        session, run = seed_lock_run(
            db,
            session_title="Immutable recovery result",
        )
        worker_id = "worker:immutable-recovery-result"
        run = claim_task_run_for_worker(db, run.id, worker_id=worker_id)
        acquired = acquire_target_lock(
            db,
            target_id=DEMO_FRONTEND_TARGET_ID,
            session_id=session.id,
            task_run_id=run.id,
            worker_id=worker_id,
            lease_expires_at=run.lease_expires_at,
        )
        assert acquired.lock is not None
        original_lock_id = acquired.lock.id
        run.state = "completed"
        run.ended_at = utc_now()
        db.add(run)
        db.commit()

        recovered = recover_terminal_holder_target_locks(db)
        assert len(recovered) == 1

        replacement = acquire_target_lock(
            db,
            target_id=DEMO_FRONTEND_TARGET_ID,
            session_id=session.id,
            task_run_id=run.id,
            worker_id=worker_id,
            lease_expires_at=utc_now() + timedelta(minutes=5),
        )
        assert replacement.acquired is True
        assert replacement.lock is not None
        assert replacement.lock.id != original_lock_id

        recovered_lock = recovered[0]
        assert recovered_lock.id == original_lock_id
        assert recovered_lock.lock_key == (
            f"target:{DEMO_FRONTEND_TARGET_ID}:write"
        )
        assert recovered_lock.task_run_id == run.id
        assert recovered_lock.target_id == DEMO_FRONTEND_TARGET_ID
        assert recovered_lock.state == "stale_released"
        assert recovered_lock.release_reason == "terminal_holder"


@pytest.mark.parametrize("recovery_mode", ("stale", "terminal"))
def test_recovery_does_not_release_generation_rotated_after_first_commit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    recovery_mode: str,
) -> None:
    engine = file_lock_engine(tmp_path)
    boundary = utc_now()
    monkeypatch.setattr(target_locks_module, "utc_now", lambda: boundary)
    with DbSession(engine) as setup_db:
        first_session, first_run = seed_lock_run(
            setup_db,
            session_title=f"{recovery_mode} first generation",
            target_id=DEMO_FRONTEND_TARGET_ID,
        )
        second_session, second_run = seed_lock_run(
            setup_db,
            session_title=f"{recovery_mode} second generation",
            target_id=DEMO_BACKEND_TARGET_ID,
        )
        first_run = claim_task_run_for_worker(
            setup_db,
            first_run.id,
            worker_id=f"worker:{recovery_mode}:first",
        )
        second_run = claim_task_run_for_worker(
            setup_db,
            second_run.id,
            worker_id=f"worker:{recovery_mode}:second",
        )
        first = acquire_target_lock(
            setup_db,
            target_id=DEMO_FRONTEND_TARGET_ID,
            session_id=first_session.id,
            task_run_id=first_run.id,
            worker_id=f"worker:{recovery_mode}:first",
            lease_expires_at=boundary + timedelta(minutes=5),
        )
        second = acquire_target_lock(
            setup_db,
            target_id=DEMO_BACKEND_TARGET_ID,
            session_id=second_session.id,
            task_run_id=second_run.id,
            worker_id=f"worker:{recovery_mode}:second",
            lease_expires_at=boundary + timedelta(minutes=5),
        )
        assert first.lock is not None
        assert second.lock is not None
        first.lock.acquired_at = boundary
        second.lock.acquired_at = boundary + timedelta(seconds=1)
        if recovery_mode == "terminal":
            first_run.state = "completed"
            second_run.state = "completed"
            first_run.ended_at = boundary
            second_run.ended_at = boundary
        else:
            expired_at = boundary - timedelta(seconds=1)
            first_run.lease_expires_at = expired_at
            second_run.lease_expires_at = expired_at
            first.lock.lease_expires_at = expired_at
            second.lock.lease_expires_at = expired_at
        setup_db.add(first_run)
        setup_db.add(second_run)
        setup_db.add(first.lock)
        setup_db.add(second.lock)
        setup_db.commit()
        first_run_id = first_run.id
        second_run_id = second_run.id
        second_session_id = second_session.id
        second_lock_id = second.lock.id

    with DbSession(engine) as recovery_db, DbSession(engine) as concurrent_db:
        original_publish_event = target_locks_module._publish_staged_lock_event
        rotated_lock_id: list[str] = []

        def rotate_second_generation_after_first_commit(db_arg, staged_event):
            result = original_publish_event(db_arg, staged_event)
            if (
                staged_event is not None
                and staged_event.task_run_id == first_run_id
                and staged_event.event_type == "target_lock.stale_released"
                and not rotated_lock_id
            ):
                released = release_target_lock_for_task_run(
                    concurrent_db,
                    target_id=DEMO_BACKEND_TARGET_ID,
                    expected_lock_id=second_lock_id,
                    worker_id=f"worker:{recovery_mode}:second",
                    task_run_id=second_run_id,
                    session_id=second_session_id,
                    release_reason="rotate_during_recovery",
                )
                assert released is not None
                reacquired = acquire_target_lock(
                    concurrent_db,
                    target_id=DEMO_BACKEND_TARGET_ID,
                    session_id=second_session_id,
                    task_run_id=second_run_id,
                    worker_id=f"worker:{recovery_mode}:second",
                    lease_expires_at=boundary + timedelta(minutes=10),
                )
                assert reacquired.acquired is True
                assert reacquired.lock is not None
                rotated_lock_id.append(reacquired.lock.id)
            return result

        monkeypatch.setattr(
            target_locks_module,
            "_publish_staged_lock_event",
            rotate_second_generation_after_first_commit,
        )
        recovered = (
            recover_terminal_holder_target_locks(recovery_db)
            if recovery_mode == "terminal"
            else recover_stale_target_locks(recovery_db, now=boundary)
        )
        recovered_lock_keys = [lock.lock_key for lock in recovered]

    with DbSession(engine) as fresh_db:
        durable = fresh_db.exec(
            select(TargetLock).where(
                TargetLock.lock_key == f"target:{DEMO_BACKEND_TARGET_ID}:write"
            )
        ).one()

    assert len(rotated_lock_id) == 1
    assert recovered_lock_keys == [
        f"target:{DEMO_FRONTEND_TARGET_ID}:write"
    ]
    assert durable.id == rotated_lock_id[0]
    assert durable.id != second_lock_id
    assert durable.state == "held"
    assert durable.release_reason is None


def test_stale_recovery_does_not_terminalize_holder_after_generation_rotation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = file_lock_engine(tmp_path)
    boundary = utc_now()
    monkeypatch.setattr(target_locks_module, "utc_now", lambda: boundary)
    with DbSession(engine) as setup_db:
        session, run = seed_lock_run(
            setup_db,
            session_title="Rotate generation before stale terminalization",
        )
        worker_id = "worker:stale-generation-race"
        run = claim_task_run_for_worker(setup_db, run.id, worker_id=worker_id)
        acquired = acquire_target_lock(
            setup_db,
            target_id=DEMO_FRONTEND_TARGET_ID,
            session_id=session.id,
            task_run_id=run.id,
            worker_id=worker_id,
            lease_expires_at=boundary + timedelta(minutes=5),
        )
        assert acquired.lock is not None
        expired_at = boundary - timedelta(seconds=1)
        run.lease_expires_at = expired_at
        acquired.lock.lease_expires_at = expired_at
        setup_db.add(run)
        setup_db.add(acquired.lock)
        setup_db.commit()
        task_run_id = run.id
        session_id = session.id
        original_lock_id = acquired.lock.id

    with DbSession(engine) as recovery_db, DbSession(engine) as concurrent_db:
        original_generation_check = target_locks_module._lock_generation_is_current
        rotated_lock_ids: list[str] = []

        def rotate_after_generation_check(db_arg, expected):
            is_current = original_generation_check(db_arg, expected)
            if is_current and not rotated_lock_ids:
                released = release_target_lock_for_task_run(
                    concurrent_db,
                    target_id=DEMO_FRONTEND_TARGET_ID,
                    expected_lock_id=original_lock_id,
                    worker_id=worker_id,
                    task_run_id=task_run_id,
                    session_id=session_id,
                    release_reason="rotate_before_stale_terminalization",
                )
                assert released is not None
                replacement = acquire_target_lock(
                    concurrent_db,
                    target_id=DEMO_FRONTEND_TARGET_ID,
                    session_id=session_id,
                    task_run_id=task_run_id,
                    worker_id=worker_id,
                    lease_expires_at=boundary + timedelta(minutes=10),
                )
                assert replacement.acquired is True
                assert replacement.lock is not None
                rotated_lock_ids.append(replacement.lock.id)
            return is_current

        monkeypatch.setattr(
            target_locks_module,
            "_lock_generation_is_current",
            rotate_after_generation_check,
        )
        recovered = recover_stale_target_locks(recovery_db, now=boundary)

    with DbSession(engine) as fresh_db:
        durable_lock = fresh_db.exec(
            select(TargetLock).where(
                TargetLock.lock_key == f"target:{DEMO_FRONTEND_TARGET_ID}:write"
            )
        ).one()
        durable_run = fresh_db.get(TaskRun, task_run_id)
        stale_events = fresh_db.exec(
            select(TaskRunEvent)
            .where(TaskRunEvent.task_run_id == task_run_id)
            .where(TaskRunEvent.event_type == "task.stale")
        ).all()

    assert len(rotated_lock_ids) == 1
    assert recovered == []
    assert durable_lock.id == rotated_lock_ids[0]
    assert durable_lock.id != original_lock_id
    assert durable_lock.state == "held"
    assert durable_run.state not in {"completed", "failed", "interrupted", "cancelled"}
    assert stale_events == []


def test_stale_recovery_rechecks_matching_holder_heartbeat_under_write_lock(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = file_lock_engine(tmp_path)
    with engine.connect() as connection:
        connection.exec_driver_sql("PRAGMA journal_mode=WAL")
    boundary = utc_now()
    worker_id = "worker:heartbeat-recovery-gate"
    with DbSession(engine) as setup_db:
        session, run = seed_lock_run(
            setup_db,
            session_title="Heartbeat recovery gate",
        )
        run = claim_task_run_for_worker(setup_db, run.id, worker_id=worker_id)
        acquired = acquire_target_lock(
            setup_db,
            target_id=DEMO_FRONTEND_TARGET_ID,
            session_id=session.id,
            task_run_id=run.id,
            worker_id=worker_id,
            lease_expires_at=boundary + timedelta(minutes=5),
        )
        assert acquired.lock is not None
        expired_at = boundary - timedelta(seconds=1)
        task = setup_db.get(Task, run.task_id)
        task.status = "running"
        run.state = "running"
        run.last_heartbeat_at = expired_at
        run.lease_expires_at = expired_at
        acquired.lock.lease_expires_at = expired_at
        setup_db.add(task)
        setup_db.add(run)
        setup_db.add(acquired.lock)
        setup_db.commit()
        task_id = task.id
        task_run_id = run.id
        lock_id = acquired.lock.id

    heartbeat_refreshed = False
    original_begin_recovery = target_locks_module._begin_immediate_generation_recovery
    with DbSession(engine) as recovery_db, DbSession(engine) as heartbeat_db:

        def refresh_heartbeat_before_write_reservation(db_arg, expected):
            nonlocal heartbeat_refreshed
            if not heartbeat_refreshed:
                holder = heartbeat_db.get(TaskRun, task_run_id)
                holder.last_heartbeat_at = boundary
                holder.lease_expires_at = boundary + timedelta(minutes=5)
                heartbeat_db.add(holder)
                heartbeat_db.commit()
                heartbeat_refreshed = True
            return original_begin_recovery(db_arg, expected)

        monkeypatch.setattr(
            target_locks_module,
            "_begin_immediate_generation_recovery",
            refresh_heartbeat_before_write_reservation,
        )
        recovered = recover_stale_target_locks(recovery_db, now=boundary)

    with DbSession(engine) as fresh_db:
        durable_lock = fresh_db.get(TargetLock, lock_id)
        durable_run = fresh_db.get(TaskRun, task_run_id)
        durable_task = fresh_db.get(Task, task_id)
        event_types = {
            item.event_type
            for item in fresh_db.exec(
                select(TaskRunEvent).where(TaskRunEvent.task_run_id == task_run_id)
            ).all()
        }
    engine.dispose()

    assert heartbeat_refreshed is True
    assert recovered == []
    assert durable_lock is not None
    assert durable_lock.state == "held"
    assert durable_lock.worker_id == worker_id
    assert durable_lock.release_reason is None
    assert durable_lock.released_at is None
    assert durable_run is not None
    assert durable_run.state == "running"
    assert durable_run.runner_id == worker_id
    assert durable_run.last_heartbeat_at == boundary
    assert durable_run.lease_expires_at == boundary + timedelta(minutes=5)
    assert durable_run.error_code is None
    assert durable_run.stale_detected_at is None
    assert durable_run.stale_reason is None
    assert durable_task is not None
    assert durable_task.status == "running"
    assert "task.stale" not in event_types
    assert "target_lock.stale_released" not in event_types


@pytest.mark.parametrize(
    "failure_point",
    ("scope-failure-event", "task-stale-event", "queue-bookkeeping"),
)
def test_stale_recovery_failure_rolls_back_and_retries_same_generation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    failure_point: str,
) -> None:
    engine = file_lock_engine(tmp_path)
    boundary = utc_now()
    with DbSession(engine) as setup_db:
        candidate = seed_stale_recovery_candidate(
            setup_db,
            boundary=boundary,
            title=f"Atomic recovery {failure_point}",
            run_state=(
                "collecting_diff"
                if failure_point == "scope-failure-event"
                else "running"
            ),
        )

    failure_injected = False
    with DbSession(engine) as recovery_db:
        original_flush = recovery_db.flush

        def fail_recovery_staging_once(objects=None) -> None:
            nonlocal failure_injected
            new_event_types = {
                item.event_type
                for item in recovery_db.new
                if isinstance(item, TaskRunEvent)
            }
            queue_is_dirty = any(
                isinstance(item, SessionQueueEntry)
                for item in recovery_db.dirty
            )
            should_fail = (
                failure_point == "scope-failure-event"
                and "task.scope_validation.failed" in new_event_types
            ) or (
                failure_point == "task-stale-event"
                and "task.stale" in new_event_types
            ) or (
                failure_point == "queue-bookkeeping"
                and queue_is_dirty
            )
            if should_fail and not failure_injected:
                failure_injected = True
                raise RuntimeError(f"injected {failure_point} failure")
            original_flush(objects)

        monkeypatch.setattr(recovery_db, "flush", fail_recovery_staging_once)
        with pytest.raises(RuntimeError, match=f"injected {failure_point} failure"):
            recover_stale_target_locks(recovery_db, now=boundary)
        recovery_db.rollback()

    required_event_types = {
        "target_lock.stale_released",
        "task.stale",
        "session_queue.advanced",
    }
    if failure_point == "scope-failure-event":
        required_event_types.add("task.scope_validation.failed")
    with DbSession(engine) as failed_db:
        failed_lock = failed_db.get(TargetLock, candidate["lock_id"])
        failed_run = failed_db.get(TaskRun, candidate["task_run_id"])
        failed_task = failed_db.get(Task, candidate["task_id"])
        failed_queue = failed_db.exec(
            select(SessionQueueEntry).where(
                SessionQueueEntry.task_run_id == candidate["task_run_id"]
            )
        ).one()
        failed_event_types = {
            item.event_type
            for item in failed_db.exec(
                select(TaskRunEvent).where(
                    TaskRunEvent.task_run_id == candidate["task_run_id"]
                )
            ).all()
        }
        failed_state = {
            "lock_state": failed_lock.state,
            "lock_worker_id": failed_lock.worker_id,
            "lock_lease_expires_at": failed_lock.lease_expires_at,
            "lock_released_at": failed_lock.released_at,
            "lock_release_reason": failed_lock.release_reason,
            "run_state": failed_run.state,
            "run_error_code": failed_run.error_code,
            "run_error_message": failed_run.error_message,
            "run_stale_detected_at": failed_run.stale_detected_at,
            "run_stale_reason": failed_run.stale_reason,
            "run_ended_at": failed_run.ended_at,
            "task_status": failed_task.status,
            "queue_state": failed_queue.state,
            "queue_finished_at": failed_queue.finished_at,
            "queue_blocked_reason": failed_queue.blocked_reason,
        }

    commit_count = 0
    with DbSession(engine) as retry_db:
        original_commit = retry_db.commit

        def count_recovery_commit() -> None:
            nonlocal commit_count
            commit_count += 1
            original_commit()

        monkeypatch.setattr(retry_db, "commit", count_recovery_commit)
        recovered = recover_stale_target_locks(retry_db, now=boundary)

    with DbSession(engine) as fresh_db:
        durable_lock = fresh_db.get(TargetLock, candidate["lock_id"])
        durable_run = fresh_db.get(TaskRun, candidate["task_run_id"])
        durable_task = fresh_db.get(Task, candidate["task_id"])
        durable_queue = fresh_db.exec(
            select(SessionQueueEntry).where(
                SessionQueueEntry.task_run_id == candidate["task_run_id"]
            )
        ).one()
        required_events = [
            item
            for item in fresh_db.exec(
                select(TaskRunEvent)
                .where(TaskRunEvent.task_run_id == candidate["task_run_id"])
                .order_by(TaskRunEvent.sequence)
            ).all()
            if item.event_type in required_event_types
        ]
        required_event_records = [
            (item.event_type, item.sequence, item.payload_json)
            for item in required_events
        ]
    engine.dispose()

    assert failure_injected is True
    assert failed_state == {
        "lock_state": "held",
        "lock_worker_id": candidate["worker_id"],
        "lock_lease_expires_at": candidate["expired_at"],
        "lock_released_at": None,
        "lock_release_reason": None,
        "run_state": candidate["run_state"],
        "run_error_code": None,
        "run_error_message": None,
        "run_stale_detected_at": None,
        "run_stale_reason": None,
        "run_ended_at": None,
        "task_status": "running",
        "queue_state": candidate["queue_state"],
        "queue_finished_at": None,
        "queue_blocked_reason": candidate["queue_blocked_reason"],
    }
    assert failed_event_types.isdisjoint(required_event_types)
    assert commit_count == 1
    assert len(recovered) == 1
    assert recovered[0].id == candidate["lock_id"]
    assert candidate["lock_id"] not in repr(recovered[0])
    assert durable_lock.state == "stale_released"
    assert durable_lock.release_reason == "stale_lease_expired"
    assert durable_run.state == "failed"
    assert durable_run.error_code == (
        "TASK_RUN_SCOPE_UNVERIFIABLE"
        if failure_point == "scope-failure-event"
        else "TASK_RUN_STALE"
    )
    assert durable_task.status == "failed"
    assert durable_queue.state == "failed"
    expected_event_types = ["target_lock.stale_released"]
    if failure_point == "scope-failure-event":
        expected_event_types.append("task.scope_validation.failed")
    expected_event_types.extend(["task.stale", "session_queue.advanced"])
    assert [item[0] for item in required_event_records] == expected_event_types
    event_sequences = [item[1] for item in required_event_records]
    assert event_sequences == list(
        range(event_sequences[0], event_sequences[0] + len(event_sequences))
    )
    assert all(
        candidate["lock_id"] not in item[2]
        for item in required_event_records
    )


def test_stale_recovery_publication_failure_is_noncritical_and_continues(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = file_lock_engine(tmp_path)
    boundary = utc_now()
    with DbSession(engine) as setup_db:
        candidate = seed_stale_recovery_candidate(
            setup_db,
            boundary=boundary,
            title="Recovery publication failure",
        )

    publication_attempts: list[str] = []

    def fail_first_publication(db, event) -> None:
        publication_attempts.append(event.event_type)
        if len(publication_attempts) == 1:
            raise RuntimeError("injected first recovery publication failure")

    monkeypatch.setattr(
        events_module,
        "publish_task_run_event",
        fail_first_publication,
    )
    monkeypatch.setattr(
        target_locks_module,
        "publish_task_run_event",
        fail_first_publication,
    )
    with DbSession(engine) as recovery_db:
        recovered = recover_stale_target_locks(recovery_db, now=boundary)

    with DbSession(engine) as fresh_db:
        durable_lock = fresh_db.get(TargetLock, candidate["lock_id"])
        durable_run = fresh_db.get(TaskRun, candidate["task_run_id"])
        durable_queue = fresh_db.exec(
            select(SessionQueueEntry).where(
                SessionQueueEntry.task_run_id == candidate["task_run_id"]
            )
        ).one()
        required_events = [
            item
            for item in fresh_db.exec(
                select(TaskRunEvent)
                .where(TaskRunEvent.task_run_id == candidate["task_run_id"])
                .order_by(TaskRunEvent.sequence)
            ).all()
            if item.event_type
            in {
                "target_lock.stale_released",
                "task.stale",
                "session_queue.advanced",
            }
        ]
    engine.dispose()

    assert len(recovered) == 1
    assert recovered[0].id == candidate["lock_id"]
    assert candidate["lock_id"] not in repr(recovered[0])
    assert publication_attempts == [
        "target_lock.stale_released",
        "task.stale",
        "session_queue.advanced",
    ]
    assert durable_lock.state == "stale_released"
    assert durable_run.state == "failed"
    assert durable_queue.state == "failed"
    assert [item.event_type for item in required_events] == publication_attempts
    assert all(candidate["lock_id"] not in item.payload_json for item in required_events)


@pytest.mark.parametrize(
    "recovery_entrypoint",
    ("stale-scan", "terminal-only"),
)
def test_terminal_holder_recovery_queue_failure_rolls_back_and_retries_generation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    recovery_entrypoint: str,
) -> None:
    engine = file_lock_engine(tmp_path)
    boundary = utc_now()
    monkeypatch.setattr(target_locks_module, "utc_now", lambda: boundary)
    with DbSession(engine) as setup_db:
        candidate = seed_terminal_recovery_candidate(
            setup_db,
            boundary=boundary,
            title=f"Terminal recovery {recovery_entrypoint}",
        )

    def recover(db: DbSession):
        if recovery_entrypoint == "stale-scan":
            return recover_stale_target_locks(db, now=boundary)
        return recover_terminal_holder_target_locks(db)

    failure_injected = False
    with DbSession(engine) as recovery_db:
        original_flush = recovery_db.flush

        def fail_queue_bookkeeping_once(objects=None) -> None:
            nonlocal failure_injected
            queue_is_dirty = any(
                isinstance(item, SessionQueueEntry)
                for item in recovery_db.dirty
            )
            if queue_is_dirty and not failure_injected:
                failure_injected = True
                raise RuntimeError("injected terminal queue bookkeeping failure")
            original_flush(objects)

        monkeypatch.setattr(recovery_db, "flush", fail_queue_bookkeeping_once)
        with pytest.raises(
            RuntimeError,
            match="injected terminal queue bookkeeping failure",
        ):
            recover(recovery_db)
        recovery_db.rollback()

    required_event_types = {
        "target_lock.stale_released",
        "session_queue.advanced",
    }
    with DbSession(engine) as failed_db:
        failed_lock = failed_db.get(TargetLock, candidate["lock_id"])
        failed_queue = failed_db.exec(
            select(SessionQueueEntry).where(
                SessionQueueEntry.task_run_id == candidate["task_run_id"]
            )
        ).one()
        failed_event_types = {
            item.event_type
            for item in failed_db.exec(
                select(TaskRunEvent).where(
                    TaskRunEvent.task_run_id == candidate["task_run_id"]
                )
            ).all()
        }
        failed_state = {
            "lock_state": failed_lock.state,
            "lock_worker_id": failed_lock.worker_id,
            "lock_release_reason": failed_lock.release_reason,
            "lock_released_at": failed_lock.released_at,
            "queue_state": failed_queue.state,
            "queue_finished_at": failed_queue.finished_at,
            "queue_blocked_reason": failed_queue.blocked_reason,
        }

    commit_count = 0
    with DbSession(engine) as retry_db:
        original_commit = retry_db.commit

        def count_recovery_commit() -> None:
            nonlocal commit_count
            commit_count += 1
            original_commit()

        monkeypatch.setattr(retry_db, "commit", count_recovery_commit)
        recovered = recover(retry_db)

    with DbSession(engine) as fresh_db:
        durable_lock = fresh_db.get(TargetLock, candidate["lock_id"])
        durable_queue = fresh_db.exec(
            select(SessionQueueEntry).where(
                SessionQueueEntry.task_run_id == candidate["task_run_id"]
            )
        ).one()
        required_events = [
            item
            for item in fresh_db.exec(
                select(TaskRunEvent)
                .where(TaskRunEvent.task_run_id == candidate["task_run_id"])
                .order_by(TaskRunEvent.sequence)
            ).all()
            if item.event_type in required_event_types
        ]
        event_records = [
            (item.event_type, item.sequence, item.payload_json)
            for item in required_events
        ]
    engine.dispose()

    assert failure_injected is True
    assert failed_state == {
        "lock_state": "held",
        "lock_worker_id": candidate["worker_id"],
        "lock_release_reason": None,
        "lock_released_at": None,
        "queue_state": candidate["queue_state"],
        "queue_finished_at": None,
        "queue_blocked_reason": candidate["queue_blocked_reason"],
    }
    assert failed_event_types.isdisjoint(required_event_types)
    assert commit_count == 1
    assert len(recovered) == 1
    assert recovered[0].id == candidate["lock_id"]
    assert candidate["lock_id"] not in repr(recovered[0])
    assert durable_lock.state == "stale_released"
    assert durable_lock.release_reason == "terminal_holder"
    assert durable_queue.state == "completed"
    assert [item[0] for item in event_records] == [
        "target_lock.stale_released",
        "session_queue.advanced",
    ]
    assert event_records[1][1] == event_records[0][1] + 1
    assert all(candidate["lock_id"] not in item[2] for item in event_records)


def test_recover_stale_lock_includes_lease_equal_to_recovery_boundary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    boundary = utc_now()
    monkeypatch.setattr(target_locks_module, "utc_now", lambda: boundary)
    with lock_db() as db:
        session, run = seed_lock_run(db, session_title="Equal lease boundary")
        run = claim_task_run_for_worker(db, run.id, worker_id="worker:equal-boundary")
        acquired = acquire_target_lock(
            db,
            target_id=DEMO_FRONTEND_TARGET_ID,
            session_id=session.id,
            task_run_id=run.id,
            worker_id="worker:equal-boundary",
            lease_expires_at=boundary + timedelta(minutes=5),
        )
        assert acquired.lock is not None
        run.lease_expires_at = boundary
        acquired.lock.lease_expires_at = boundary
        db.add(run)
        db.add(acquired.lock)
        db.commit()

        recovered = recover_stale_target_locks(db, now=boundary)
        durable = db.exec(
            select(TargetLock).where(
                TargetLock.lock_key == f"target:{DEMO_FRONTEND_TARGET_ID}:write"
            )
        ).one()

    assert [lock.lock_key for lock in recovered] == [
        f"target:{DEMO_FRONTEND_TARGET_ID}:write"
    ]
    assert durable.state == "stale_released"
    assert durable.release_reason == "stale_lease_expired"


def file_lock_engine(tmp_path: Path):
    database_path = tmp_path / "target-locks.db"
    engine = create_engine(
        f"sqlite:///{database_path.as_posix()}",
        connect_args={"check_same_thread": False, "timeout": 5},
    )
    SQLModel.metadata.create_all(engine)
    return engine


def seed_acquire_candidate(
    db: DbSession,
    *,
    acquire_path: str,
    title: str,
) -> dict[str, object]:
    original_lock_id = None
    if acquire_path == "released-update":
        original_session, original_run = seed_lock_run(
            db,
            session_title=f"{title} original",
        )
        original_worker_id = f"worker:{title}:original"
        original_run = claim_task_run_for_worker(
            db,
            original_run.id,
            worker_id=original_worker_id,
        )
        original = acquire_target_lock(
            db,
            target_id=DEMO_FRONTEND_TARGET_ID,
            session_id=original_session.id,
            task_run_id=original_run.id,
            worker_id=original_worker_id,
            lease_expires_at=original_run.lease_expires_at,
        )
        assert original.lock is not None
        original_lock_id = original.lock.id
        released = release_target_lock_for_task_run(
            db,
            target_id=DEMO_FRONTEND_TARGET_ID,
            expected_lock_id=original_lock_id,
            worker_id=original_worker_id,
            task_run_id=original_run.id,
            session_id=original_session.id,
            release_reason="prepare_atomic_acquire_test",
        )
        assert released is not None

    session, run = seed_lock_run(
        db,
        session_title=f"{title} candidate",
    )
    worker_id = f"worker:{title}:candidate"
    run = claim_task_run_for_worker(db, run.id, worker_id=worker_id)
    return {
        "original_lock_id": original_lock_id,
        "session_id": session.id,
        "task_run_id": run.id,
        "worker_id": worker_id,
        "lease_expires_at": run.lease_expires_at,
    }


def seed_stale_recovery_candidate(
    db: DbSession,
    *,
    boundary: datetime,
    title: str,
    run_state: str = "running",
) -> dict[str, object]:
    session, run = seed_lock_run(db, session_title=title)
    worker_id = f"worker:{title.lower().replace(' ', '-')}"
    run = claim_task_run_for_worker(db, run.id, worker_id=worker_id)
    acquired = acquire_target_lock(
        db,
        target_id=DEMO_FRONTEND_TARGET_ID,
        session_id=session.id,
        task_run_id=run.id,
        worker_id=worker_id,
        lease_expires_at=boundary + timedelta(minutes=5),
    )
    assert acquired.lock is not None
    task = db.get(Task, run.task_id)
    queue_entry = db.exec(
        select(SessionQueueEntry).where(SessionQueueEntry.task_run_id == run.id)
    ).one()
    expired_at = boundary - timedelta(seconds=1)
    task.status = "running"
    run.state = run_state
    run.last_heartbeat_at = expired_at
    run.lease_expires_at = expired_at
    acquired.lock.lease_expires_at = expired_at
    db.add(task)
    db.add(run)
    db.add(acquired.lock)
    db.commit()
    return {
        "task_id": task.id,
        "task_run_id": run.id,
        "worker_id": worker_id,
        "lock_id": acquired.lock.id,
        "expired_at": expired_at,
        "run_state": run_state,
        "queue_state": queue_entry.state,
        "queue_blocked_reason": queue_entry.blocked_reason,
    }


def seed_terminal_recovery_candidate(
    db: DbSession,
    *,
    boundary: datetime,
    title: str,
) -> dict[str, object]:
    session, run = seed_lock_run(db, session_title=title)
    worker_id = f"worker:{title.lower().replace(' ', '-')}"
    run = claim_task_run_for_worker(db, run.id, worker_id=worker_id)
    acquired = acquire_target_lock(
        db,
        target_id=DEMO_FRONTEND_TARGET_ID,
        session_id=session.id,
        task_run_id=run.id,
        worker_id=worker_id,
        lease_expires_at=boundary + timedelta(minutes=5),
    )
    assert acquired.lock is not None
    task = db.get(Task, run.task_id)
    queue_entry = db.exec(
        select(SessionQueueEntry).where(SessionQueueEntry.task_run_id == run.id)
    ).one()
    task.status = "completed"
    run.state = "completed"
    run.ended_at = boundary
    db.add(task)
    db.add(run)
    db.commit()
    return {
        "task_run_id": run.id,
        "worker_id": worker_id,
        "lock_id": acquired.lock.id,
        "queue_state": queue_entry.state,
        "queue_blocked_reason": queue_entry.blocked_reason,
    }


@contextmanager
def lock_db() -> Iterator[DbSession]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    with DbSession(engine) as db:
        yield db


def seed_lock_run(
    db: DbSession,
    *,
    session_title: str,
    target_id: str = DEMO_FRONTEND_TARGET_ID,
) -> tuple[Session, TaskRun]:
    role = "backend" if target_id == DEMO_BACKEND_TARGET_ID else "frontend"
    intent_type = "backend_change" if target_id == DEMO_BACKEND_TARGET_ID else "frontend_change"
    safe_target = "apps/demo-api/app" if target_id == DEMO_BACKEND_TARGET_ID else "apps/demo/src"
    workspace = Workspace(
        name=session_title,
        repo_url="local://apps/demo",
        root_path="apps/demo",
        default_branch="main",
    )
    session = Session(
        workspace_id=workspace.id,
        title=session_title,
        bound_branch="main",
        worktree_path=f".worktrees/{session_title.lower().replace(' ', '-')}",
    )
    agent = db.exec(select(Agent).where(Agent.role == role)).first()
    if agent is None:
        agent = Agent(
            name=f"{role.title()} Agent",
            role=role,
            adapter_type="codex",
            provider="local",
        )
        db.add(agent)
    task = Task(
        session_id=session.id,
        title=f"{session_title} write",
        intent_type=intent_type,
        status="pending",
        assigned_agent_id=agent.id,
        plan_json=json.dumps(
            {
                "targetId": target_id,
                "safeTarget": safe_target,
                "files": [f"{safe_target}/main.py"],
            },
            separators=(",", ":"),
        ),
    )
    db.add(workspace)
    db.add(session)
    db.add(task)
    db.commit()
    db.refresh(session)
    db.refresh(task)
    return session, create_task_run(db, task.id)
