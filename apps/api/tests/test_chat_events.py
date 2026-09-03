import asyncio
from collections.abc import Iterator
from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session as DbSession
from sqlmodel import SQLModel, create_engine, select

from app import events as events_module
from app import main as main_module
from app.routes import session_events as session_event_routes
from app.events import (
    append_task_run_event,
    list_session_events,
    publish_event,
    stage_task_run_event,
)
from app.main import app, get_db
from app.models import Agent, Message, Session, Task, TaskRun, TaskRunEvent, Workspace
from app.task_run_scope import TaskRunScopeError
from app.task_runs import require_task_run_artifact_scope_passed


@pytest.fixture
def client() -> Iterator[TestClient]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)

    with DbSession(engine) as db:
        workspace = Workspace(
            name="AgentHub Demo",
            repo_url="local://apps/demo",
            root_path="apps/demo",
            default_branch="main",
        )
        orchestrator = Agent(
            name="Orchestrator",
            role="orchestrator",
            adapter_type="scripted_mock",
            provider="local",
            enabled=True,
        )
        agent = Agent(
            name="Frontend Agent",
            role="frontend",
            adapter_type="codex",
            provider="local",
            enabled=True,
        )
        session_one = Session(
            workspace_id=workspace.id,
            title="Session one",
            bound_branch="main",
            worktree_path=".worktrees/session-one",
        )
        session_two = Session(
            workspace_id=workspace.id,
            title="Session two",
            bound_branch="main",
            worktree_path=".worktrees/session-two",
        )
        db.add(workspace)
        db.add(orchestrator)
        db.add(agent)
        db.add(session_one)
        db.add(session_two)
        db.commit()

    def override_db() -> Iterator[DbSession]:
        with DbSession(engine) as db:
            yield db

    app.dependency_overrides[get_db] = override_db
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def db_from_override() -> Iterator[DbSession]:
    override = app.dependency_overrides[get_db]
    return override()


def create_session_event_pair() -> tuple[str, str, str, str, str]:
    with next(db_from_override()) as db:
        session = db.exec(select(Session).where(Session.title == "Session one")).one()
        agent = db.exec(select(Agent).where(Agent.role == "frontend")).one()
        task = Task(
            session_id=session.id,
            title="Replay task",
            intent_type="frontend_change",
            assigned_agent_id=agent.id,
        )
        db.add(task)
        db.commit()
        db.refresh(task)
        task_run = TaskRun(
            task_id=task.id,
            agent_id=agent.id,
            state="created",
            worktree_path=session.worktree_path,
        )
        db.add(task_run)
        db.commit()
        db.refresh(task_run)

        first = append_task_run_event(db, task_run.id, "task.state")
        second = append_task_run_event(db, task_run.id, "message.delta")
        first.created_at = datetime(2026, 5, 17, 10, 0, 0)
        second.created_at = first.created_at + timedelta(seconds=1)
        db.add(first)
        db.add(second)
        db.commit()

        return (
            session.id,
            first.id,
            second.id,
            events_module.format_session_cursor(first),
            events_module.format_session_cursor(second),
        )


def test_messages_are_persisted_and_scoped_to_selected_session(
    client: TestClient,
) -> None:
    with next(db_from_override()) as db:
        sessions = db.exec(select(Session).order_by(Session.title)).all()
        session_one = sessions[0]
        session_two = sessions[1]

    first = client.post(
        f"/sessions/{session_one.id}/messages",
        json={"contentMd": "@orchestrator build a login page"},
    )
    second = client.post(
        f"/sessions/{session_two.id}/messages",
        json={"contentMd": "separate thread", "senderType": "system"},
    )

    assert first.status_code == 201
    assert second.status_code == 201

    session_one_messages = client.get(f"/sessions/{session_one.id}/messages")
    session_two_messages = client.get(f"/sessions/{session_two.id}/messages")

    session_one_content = [message["contentMd"] for message in session_one_messages.json()]
    assert session_one_content[0] == "@orchestrator build a login page"
    assert "不能安全地把这条消息直接变成可执行任务" in session_one_content[1]
    assert "注册为外部工作区/目标" in session_one_content[1]
    assert [message["contentMd"] for message in session_two_messages.json()] == [
        "separate thread"
    ]

    with next(db_from_override()) as db:
        stored_session = db.get(Session, session_one.id)
        stored_message = db.exec(
            select(Message)
            .where(Message.session_id == session_one.id)
            .order_by(Message.created_at.desc())
        ).first()
        assert stored_session is not None
        assert stored_message is not None
        assert stored_session.last_message_at == stored_message.created_at


def test_task_run_events_append_and_query_by_sequence(client: TestClient) -> None:
    with next(db_from_override()) as db:
        session = db.exec(select(Session).where(Session.title == "Session one")).one()
        agent = db.exec(select(Agent).where(Agent.role == "frontend")).one()
        task = Task(
            session_id=session.id,
            title="Future task",
            intent_type="frontend_change",
            assigned_agent_id=agent.id,
        )
        db.add(task)
        db.commit()
        db.refresh(task)

        task_run = TaskRun(
            task_id=task.id,
            agent_id=agent.id,
            state="created",
            worktree_path=session.worktree_path,
        )
        db.add(task_run)
        db.commit()
        db.refresh(task_run)

        first = append_task_run_event(
            db,
            task_run_id=task_run.id,
            event_type="task.state",
            payload_json='{"state":"queued"}',
        )
        second = append_task_run_event(
            db,
            task_run_id=task_run.id,
            event_type="message.delta",
            payload_json='{"text":"working"}',
        )

        assert first.sequence == 1
        assert second.sequence == 2

        replayed = list_session_events(
            db,
            session_id=session.id,
            after=events_module.format_session_cursor(first),
        )
        assert [event.sequence for event in replayed] == [2]
        assert replayed[0].event_type == "message.delta"
        assert [
            event.id
            for event in list_session_events(db, session_id=session.id, limit=1)
        ] == [first.id]
        with pytest.raises(ValueError, match="limit must be positive"):
            list_session_events(db, session_id=session.id, limit=0)

    response = client.get(
        f"/sessions/{session.id}/events?after={events_module.format_session_cursor(first)}",
        headers={"accept": "text/event-stream"},
    )

    assert response.status_code == 200
    assert "event: message.delta" not in response.text
    assert '"sequence":2' in response.text


def test_task_run_scope_refusal_is_replayed_as_standard_session_message(
    client: TestClient,
) -> None:
    with next(db_from_override()) as db:
        session = db.exec(select(Session).where(Session.title == "Session one")).one()
        agent = db.exec(select(Agent).where(Agent.role == "frontend")).one()
        task = Task(
            session_id=session.id,
            title="Scope refusal task",
            intent_type="frontend_change",
            assigned_agent_id=agent.id,
        )
        db.add(task)
        db.commit()
        db.refresh(task)
        task_run = TaskRun(
            task_id=task.id,
            agent_id=agent.id,
            state="created",
            worktree_path=session.worktree_path,
        )
        db.add(task_run)
        db.commit()
        db.refresh(task_run)

        baseline = append_task_run_event(db, task_run.id, "task.state")
        with pytest.raises(TaskRunScopeError) as exc_info:
            require_task_run_artifact_scope_passed(db, task_run.id)

        assert exc_info.value.error_code == "TASK_RUN_SCOPE_UNVERIFIABLE"
        refused = db.exec(
            select(TaskRunEvent)
            .where(TaskRunEvent.task_run_id == task_run.id)
            .where(TaskRunEvent.event_type == "task.artifact_scope_refused")
        ).one()
        session_id = session.id
        baseline_cursor = events_module.format_session_cursor(baseline)
        refused_cursor = events_module.format_session_cursor(refused)

    response = client.get(
        f"/sessions/{session_id}/events?after={baseline_cursor}",
        headers={"accept": "text/event-stream"},
    )

    assert response.status_code == 200
    assert "event:" not in response.text
    assert f"id: {refused_cursor}" in response.text
    assert '"eventType":"task.artifact_scope_refused"' in response.text
    assert '"errorCode":"TASK_RUN_SCOPE_UNVERIFIABLE"' in response.text


def test_session_replay_uses_created_at_and_id_across_task_runs(
    client: TestClient,
) -> None:
    with next(db_from_override()) as db:
        session = db.exec(select(Session).where(Session.title == "Session one")).one()
        agent = db.exec(select(Agent).where(Agent.role == "frontend")).one()
        first_task = Task(
            session_id=session.id,
            title="First task",
            intent_type="frontend_change",
            assigned_agent_id=agent.id,
        )
        second_task = Task(
            session_id=session.id,
            title="Second task",
            intent_type="frontend_change",
            assigned_agent_id=agent.id,
        )
        db.add(first_task)
        db.add(second_task)
        db.commit()
        db.refresh(first_task)
        db.refresh(second_task)

        first_run = TaskRun(
            task_id=first_task.id,
            agent_id=agent.id,
            state="created",
            worktree_path=session.worktree_path,
        )
        second_run = TaskRun(
            task_id=second_task.id,
            agent_id=agent.id,
            state="created",
            worktree_path=session.worktree_path,
        )
        db.add(first_run)
        db.add(second_run)
        db.commit()
        db.refresh(first_run)
        db.refresh(second_run)

        first_event = append_task_run_event(
            db,
            task_run_id=first_run.id,
            event_type="task.state",
        )
        second_event = append_task_run_event(
            db,
            task_run_id=second_run.id,
            event_type="task.state",
        )
        first_event.created_at = datetime(2026, 5, 17, 10, 0, 0)
        second_event.created_at = first_event.created_at + timedelta(seconds=1)
        db.add(first_event)
        db.add(second_event)
        db.commit()

        assert first_event.sequence == 1
        assert second_event.sequence == 1
        replayed = list_session_events(
            db,
            session_id=session.id,
            after=events_module.format_session_cursor(first_event),
        )

    assert [event.id for event in replayed] == [second_event.id]
    assert [event.sequence for event in replayed] == [1]


def test_session_events_reject_malformed_cursor(client: TestClient) -> None:
    with next(db_from_override()) as db:
        session = db.exec(select(Session).where(Session.title == "Session one")).one()

    response = client.get(f"/sessions/{session.id}/events?after=1")

    assert response.status_code == 400


def test_session_events_replay_from_last_event_id(client: TestClient) -> None:
    session_id, first_id, second_id, first_cursor, _ = create_session_event_pair()

    response = client.get(
        f"/sessions/{session_id}/events",
        headers={"Last-Event-ID": first_cursor},
    )

    assert response.status_code == 200
    assert f'"id":"{first_id}"' not in response.text
    assert f'"id":"{second_id}"' in response.text


def test_session_events_prefer_last_event_id_over_query_cursor(client: TestClient) -> None:
    session_id, first_id, second_id, first_cursor, second_cursor = create_session_event_pair()

    response = client.get(
        f"/sessions/{session_id}/events",
        params={"after": second_cursor},
        headers={"Last-Event-ID": first_cursor},
    )

    assert response.status_code == 200
    assert f'"id":"{first_id}"' not in response.text
    assert f'"id":"{second_id}"' in response.text


def test_session_events_prefer_last_event_id_before_validating_after_query(
    client: TestClient,
) -> None:
    session_id, first_id, second_id, first_cursor, _ = create_session_event_pair()

    response = client.get(
        f"/sessions/{session_id}/events",
        params={"after": "not-a-cursor"},
        headers={"Last-Event-ID": first_cursor},
    )

    assert response.status_code == 200
    assert f'"id":"{first_id}"' not in response.text
    assert f'"id":"{second_id}"' in response.text


def test_session_events_reject_malformed_last_event_id(client: TestClient) -> None:
    with next(db_from_override()) as db:
        session = db.exec(select(Session).where(Session.title == "Session one")).one()

    response = client.get(
        f"/sessions/{session.id}/events",
        headers={"Last-Event-ID": "malformed"},
    )

    assert response.status_code == 400


@pytest.mark.anyio
async def test_stream_registers_before_backlog_and_deduplicates_queued_events(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with next(db_from_override()) as db:
        session = db.exec(select(Session).where(Session.title == "Session one")).one()
        agent = db.exec(select(Agent).where(Agent.role == "frontend")).one()
        task = Task(
            session_id=session.id,
            title="Streaming task",
            intent_type="frontend_change",
            assigned_agent_id=agent.id,
        )
        db.add(task)
        db.commit()
        db.refresh(task)
        task_run = TaskRun(
            task_id=task.id,
            agent_id=agent.id,
            state="created",
            worktree_path=session.worktree_path,
        )
        db.add(task_run)
        db.commit()
        db.refresh(task_run)

        first = append_task_run_event(db, task_run.id, "task.state")
        second = append_task_run_event(db, task_run.id, "message.delta")
        third = append_task_run_event(db, task_run.id, "completed")
        first.created_at = datetime(2026, 5, 17, 10, 0, 0)
        second.created_at = first.created_at + timedelta(seconds=1)
        third.created_at = second.created_at + timedelta(seconds=1)
        db.add(first)
        db.add(second)
        db.add(third)
        db.commit()
        first_id = first.id
        second_id = second.id
        third_id = third.id

        registered_before_backlog: list[bool] = []
        replay_calls = 0

        def replay_with_event_published_during_query(
            replay_db: DbSession,
            *,
            session_id: str,
            after: str | None,
            through: str | None = None,
            limit: int | None = None,
        ) -> list:
            nonlocal replay_calls
            replay_calls += 1
            if replay_calls == 1:
                registered_before_backlog.append(
                    bool(events_module._session_subscribers[session_id])
                )
                publish_event(session_id, second)
                return [first, second]
            return events_module.list_session_events(
                replay_db,
                session_id=session_id,
                after=after,
                through=through,
                limit=limit,
            )

        monkeypatch.setattr(main_module, "list_session_events", replay_with_event_published_during_query)
        response = await main_module.stream_session_events(
            session.id,
            after=None,
            last_event_id=None,
            stream=True,
            db=db,
        )
        body = response.body_iterator

        first_frame = await anext(body)
        second_frame = await anext(body)
        publish_event(session.id, third)
        third_frame = await asyncio.wait_for(anext(body), timeout=1)
        await body.aclose()
        assert not events_module._session_subscribers.get(session.id)

    assert registered_before_backlog == [True]
    assert '"id":"' + first_id + '"' in first_frame
    assert '"id":"' + second_id + '"' in second_frame
    assert '"id":"' + third_id + '"' in third_frame


@pytest.mark.anyio
async def test_stream_replays_persisted_order_when_notifications_are_reversed(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with next(db_from_override()) as db:
        session = db.exec(select(Session).where(Session.title == "Session one")).one()
        agent = db.exec(select(Agent).where(Agent.role == "frontend")).one()
        task = Task(
            session_id=session.id,
            title="Reversed notification task",
            intent_type="frontend_change",
            assigned_agent_id=agent.id,
        )
        db.add(task)
        db.commit()
        db.refresh(task)
        task_run = TaskRun(
            task_id=task.id,
            agent_id=agent.id,
            state="created",
            worktree_path=session.worktree_path,
        )
        db.add(task_run)
        db.commit()
        db.refresh(task_run)

        response = await main_module.stream_session_events(
            session.id,
            after=None,
            last_event_id=None,
            stream=True,
            db=db,
        )
        body = response.body_iterator
        first_frame_task = asyncio.create_task(anext(body))
        for _ in range(10):
            await asyncio.sleep(0)
            if events_module._session_subscribers.get(session.id):
                break
        assert events_module._session_subscribers.get(session.id)

        fixed_now = datetime(2026, 8, 30, 12, 0, 0)
        monkeypatch.setattr(events_module, "_naive_utc_now", lambda: fixed_now)
        first = stage_task_run_event(db, task_run.id, "task.state")
        second = stage_task_run_event(db, task_run.id, "message.delta")
        db.commit()
        db.refresh(first)
        db.refresh(second)

        assert first.created_at < second.created_at
        first_id = first.id
        second_id = second.id
        publish_event(session.id, second)
        publish_event(session.id, first)
        first_frame = await asyncio.wait_for(first_frame_task, timeout=1)
        second_frame = await asyncio.wait_for(anext(body), timeout=1)
        await body.aclose()

    assert '"id":"' + first_id + '"' in first_frame
    assert '"id":"' + second_id + '"' in second_frame


@pytest.mark.anyio
async def test_stream_replays_large_backlog_in_bounded_batches(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(session_event_routes, "SESSION_EVENT_REPLAY_BATCH_SIZE", 2)

    with next(db_from_override()) as db:
        session = db.exec(select(Session).where(Session.title == "Session one")).one()
        agent = db.exec(select(Agent).where(Agent.role == "frontend")).one()
        task = Task(
            session_id=session.id,
            title="Bounded replay task",
            intent_type="frontend_change",
            assigned_agent_id=agent.id,
        )
        db.add(task)
        db.commit()
        db.refresh(task)
        task_run = TaskRun(
            task_id=task.id,
            agent_id=agent.id,
            state="created",
            worktree_path=session.worktree_path,
        )
        db.add(task_run)
        db.commit()
        db.refresh(task_run)

        persisted = [
            append_task_run_event(db, task_run.id, event_type)
            for event_type in ("task.state", "message.delta", "completed")
        ]
        persisted_ids = [event.id for event in persisted]
        expected_high_water = events_module.format_session_cursor(persisted[-1])
        observed_limits: list[int | None] = []
        observed_high_water_cursors: list[str | None] = []
        late_event_id: str | None = None

        def recording_replay(
            replay_db: DbSession,
            *,
            session_id: str,
            after: str | None,
            through: str | None = None,
            limit: int | None = None,
        ) -> list[TaskRunEvent]:
            nonlocal late_event_id
            if late_event_id is None:
                late_event_id = append_task_run_event(
                    db,
                    task_run.id,
                    "post-snapshot.event",
                ).id
            observed_limits.append(limit)
            observed_high_water_cursors.append(through)
            replay_kwargs: dict[str, object] = {
                "after": after,
                "limit": limit,
            }
            if through is not None:
                replay_kwargs["through"] = through
            events = events_module.list_session_events(
                replay_db,
                session_id=session_id,
                **replay_kwargs,
            )
            return events if limit is None else events[:limit]

        monkeypatch.setattr(main_module, "list_session_events", recording_replay)
        response = await main_module.stream_session_events(
            session.id,
            after=None,
            last_event_id=None,
            stream=False,
            db=db,
        )
        body = response.body_iterator
        frames = [frame async for frame in body]
        await body.aclose()

        monkeypatch.setattr(
            main_module,
            "list_session_events",
            events_module.list_session_events,
        )
        followup_response = await main_module.stream_session_events(
            session.id,
            after=expected_high_water,
            last_event_id=None,
            stream=False,
            db=db,
        )
        followup_body = followup_response.body_iterator
        followup_frames = [frame async for frame in followup_body]
        await followup_body.aclose()

    assert observed_limits == [2, 2]
    assert observed_high_water_cursors == [expected_high_water, expected_high_water]
    assert len(frames) == len(persisted_ids)
    assert all(
        f'"id":"{event_id}"' in frame
        for event_id, frame in zip(persisted_ids, frames, strict=True)
    )
    assert late_event_id is not None
    assert all(f'"id":"{late_event_id}"' not in frame for frame in frames)
    assert len(followup_frames) == 1
    assert f'"id":"{late_event_id}"' in followup_frames[0]


@pytest.mark.anyio
async def test_stream_polls_persisted_events_without_local_notification(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(main_module, "SESSION_EVENT_POLL_INTERVAL_SECONDS", 0.01)

    with next(db_from_override()) as db:
        session = db.exec(select(Session).where(Session.title == "Session one")).one()
        agent = db.exec(select(Agent).where(Agent.role == "frontend")).one()
        task = Task(
            session_id=session.id,
            title="Cross-process polling task",
            intent_type="frontend_change",
            assigned_agent_id=agent.id,
        )
        db.add(task)
        db.commit()
        db.refresh(task)
        task_run = TaskRun(
            task_id=task.id,
            agent_id=agent.id,
            state="created",
            worktree_path=session.worktree_path,
        )
        db.add(task_run)
        db.commit()
        db.refresh(task_run)

        response = await main_module.stream_session_events(
            session.id,
            after=None,
            last_event_id=None,
            stream=True,
            db=db,
        )
        body = response.body_iterator
        frame_task = asyncio.create_task(anext(body))
        for _ in range(10):
            await asyncio.sleep(0)
            if events_module._session_subscribers.get(session.id):
                break
        assert events_module._session_subscribers.get(session.id)

        event = stage_task_run_event(db, task_run.id, "task.state")
        db.commit()
        db.refresh(event)
        event_id = event.id

        frame = await asyncio.wait_for(frame_task, timeout=1)
        await body.aclose()

    assert '"id":"' + event_id + '"' in frame


@pytest.mark.anyio
async def test_idle_stream_emits_comment_heartbeat(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(main_module, "SESSION_EVENT_POLL_INTERVAL_SECONDS", 0.01)
    monkeypatch.setattr(main_module, "SESSION_EVENT_HEARTBEAT_INTERVAL_SECONDS", 0.02)

    with next(db_from_override()) as db:
        session = db.exec(select(Session).where(Session.title == "Session one")).one()
        response = await main_module.stream_session_events(
            session.id,
            after=None,
            last_event_id=None,
            stream=True,
            db=db,
        )
        body = response.body_iterator
        heartbeat = await asyncio.wait_for(anext(body), timeout=1)
        await body.aclose()

    assert heartbeat == ": keep-alive\n\n"
