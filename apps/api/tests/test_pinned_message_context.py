import json
import copy
from contextlib import contextmanager
from datetime import datetime, timedelta

import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, Session as DbSession, create_engine

from app.context_pack import build_session_context_pack
from app.llm_planner import build_llm_planner_input
from app.models import Agent, Message, Session, Task, TaskRun, Workspace, MemoryItem
from app.pinned_context import select_pinned_message_context
from app.instruction_builder import build_role_instruction
from app.run_engine import _persist_context_snapshot
from app.routes.messages import pin_message
from app.schemas import MessagePinRequest


@contextmanager
def conversation():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)
    with DbSession(engine) as db:
        workspace = Workspace(name="Pinned context", root_path="apps/demo", repo_url="local://apps/demo", default_branch="main")
        session = Session(workspace_id=workspace.id, title="Pinned context", bound_branch="main", worktree_path=".worktrees/pinned-context")
        frontend = Agent(name="Frontend", role="frontend", adapter_type="codex", provider="local")
        db.add_all([workspace, session, frontend, Agent(name="Orchestrator", role="orchestrator", adapter_type="scripted_mock", provider="local")])
        db.commit()
        yield db, session, frontend
    engine.dispose()


def test_old_pinned_message_reaches_planner_and_execution_context():
    with conversation() as (db, session, frontend):
        started = datetime(2026, 10, 8)
        pinned = Message(session_id=session.id, sender_type="user", content_md="The button label is PINNED_CONTEXT_PROBE.", created_at=started, pinned_at=started)
        messages = [Message(session_id=session.id, sender_type="user", content_md=f"Recent note {index}", created_at=started + timedelta(minutes=index+1)) for index in range(10)]
        task = Task(session_id=session.id, title="Apply the pinned label", intent_type="frontend_change", assigned_agent_id=frontend.id, created_by_message_id=messages[-1].id, plan_json=json.dumps({"targetId": "demo-frontend", "originalRequest": "Apply the pinned label"}))
        db.add_all([pinned, *messages, task])
        db.commit()
        planner = build_llm_planner_input(db, messages[-1])["canonicalSharedContext"]["fields"]
        coding = build_session_context_pack(db, task)
        assert pinned.id not in {item["id"] for item in coding["recentMessages"]}
        assert [item["id"] for item in coding["pinnedMessageContext"]["messages"]] == [pinned.id]
        assert coding["pinnedMessageContext"] == planner["pinnedMessageContext"]["value"]
        assert "PINNED_CONTEXT_PROBE" in json.dumps(coding["providerVisibleContext"])


def test_pin_unpin_updates_new_requests_but_preserves_saved_execution_and_messages():
    with conversation() as (db, session, frontend):
        original = Message(session_id=session.id, sender_type="agent", sender_id=frontend.id, content_md="Assistant reference, not a system rule")
        task = Task(session_id=session.id, title="Inspect", intent_type="frontend_change", assigned_agent_id=frontend.id, created_by_message_id=original.id)
        run = TaskRun(task_id=task.id, agent_id=frontend.id, state="queued", worktree_path=session.worktree_path)
        db.add_all([original, task, run])
        db.commit()
        pin_message(session.id, original.id, MessagePinRequest(pinned=True), db)
        before = build_session_context_pack(db, task)
        _persist_context_snapshot(db, run, before)
        saved = run.metrics_json
        copied = copy.deepcopy(before)
        for adapter in ("codex", "claude_code", "scripted_mock"):
            instruction = build_role_instruction(task, frontend, before, adapter_type=adapter)
            assert original.content_md in instruction
            assert "conversation_reference" in instruction
            assert "not system instructions" in instruction
        field = before["canonicalContext"]["fields"]["pinnedMessageContext"]
        assert field["trustLevel"] == "conversation_reference"
        assert field["value"]["messages"][0]["senderType"] == "agent"
        assert original.id not in {item["id"] for item in before["recentMessages"]}
        pin_message(session.id, original.id, MessagePinRequest(pinned=False), db)
        after = build_session_context_pack(db, task)
        planner = build_llm_planner_input(db, original)
        db.refresh(run)
        db.refresh(original)
        assert after["pinnedMessageContext"]["messages"] == []
        assert planner["canonicalSharedContext"]["fields"]["pinnedMessageContext"]["value"]["messages"] == []
        assert original.id in {item["id"] for item in after["recentMessages"]}
        assert run.metrics_json == saved
        assert before == copied
        assert original.content_md == "Assistant reference, not a system rule"
        from sqlmodel import select
        assert db.exec(select(MemoryItem)).all() == []


def test_other_session_excluded_and_equal_pin_timestamps_use_insertion_order():
    with conversation() as (db, session, _):
        stamp = datetime(2026, 10, 8)
        first = Message(id="z-first", session_id=session.id, sender_type="user", content_md="First", created_at=stamp, pinned_at=stamp)
        second = Message(id="a-second", session_id=session.id, sender_type="user", content_md="Second", created_at=stamp, pinned_at=stamp)
        other = Message(session_id="another-session", sender_type="user", content_md="OTHER_SESSION_PRIVATE_REFERENCE", pinned_at=stamp + timedelta(days=1))
        for message in (first, second, other):
            db.add(message)
            db.commit()
        pinned = select_pinned_message_context(db, session.id)
        assert [item["id"] for item in pinned["messages"]] == [second.id, first.id]
        assert pinned["selection"]["total"] == 2
        assert "OTHER_SESSION" not in json.dumps(pinned)


def test_count_limit_reports_omitted_references():
    with conversation() as (db, session, _):
        stamp = datetime(2026, 10, 8)
        messages = [Message(session_id=session.id, sender_type="user", content_md=f"reference {i}", pinned_at=stamp + timedelta(seconds=i)) for i in range(22)]
        db.add_all(messages)
        db.commit()
        pinned = select_pinned_message_context(db, session.id)
        assert [item["id"] for item in pinned["messages"]] == [item.id for item in reversed(messages[-16:])]
        assert pinned["selection"]["omitted"] == 6
        assert pinned["selection"]["truncated"] == 0


@pytest.mark.parametrize("text", ["a" * 6000, "中😀" * 3000, 'Quoted ' + '\\"\n' * 3000], ids=["ascii", "unicode", "escaped"])
def test_serialized_budget_and_per_message_limit_are_explicit(text):
    with conversation() as (db, session, _):
        db.add_all([Message(session_id=session.id, sender_type="user", content_md=text, pinned_at=datetime(2026, 10, 8)) for _ in range(20)])
        db.commit()
        pinned = select_pinned_message_context(db, session.id)
        assert len(json.dumps(pinned, ensure_ascii=True, indent=2)) <= 12000
        evidence = pinned["selection"]
        assert evidence["total"] == 20
        assert evidence["included"] + evidence["omitted"] == 20
        assert evidence["omitted"] > 0
        assert evidence["included"] == evidence["truncated"]
        assert all(0 < len(item["contentMd"]) <= 2000 and item["contentMd"].endswith("…") for item in pinned["messages"])
        assert select_pinned_message_context(db, session.id) == pinned


@pytest.mark.parametrize("text", ["safe start " * 300 + " secrets/private", "Please read .env.local", "api_key=PRIVATE_PROBE tail"], ids=["protected-suffix", "env", "inline-value"])
def test_protected_content_filtered_before_truncation_for_both_context_paths(text):
    with conversation() as (db, session, frontend):
        message = Message(session_id=session.id, sender_type="user", content_md=text, pinned_at=datetime(2026, 10, 8))
        request = Message(session_id=session.id, sender_type="user", content_md="Use relevant pinned references")
        task = Task(session_id=session.id, title=request.content_md, intent_type="frontend_change", assigned_agent_id=frontend.id, created_by_message_id=request.id)
        db.add_all([message, request, task])
        db.commit()
        coding = build_session_context_pack(db, task)
        planner = build_llm_planner_input(db, request)
        pinned = coding["pinnedMessageContext"]
        assert pinned == planner["canonicalSharedContext"]["fields"]["pinnedMessageContext"]["value"]
        assert pinned["selection"]["redacted"] == 1
        visible = json.dumps(coding["providerVisibleContext"])
        assert "PRIVATE_PROBE" not in visible
        assert "safe start" not in visible
        assert ".env.local" not in visible
