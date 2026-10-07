import hashlib
import json
from collections.abc import Iterator
from datetime import timedelta

import pytest
from sqlmodel import Session as DbSession, SQLModel, create_engine

from app.context_pack import build_session_context_pack
from app.llm_planner import (
    build_llm_planner_input,
    create_llm_conversation_outcome,
    create_llm_plan_tasks_from_outcome,
)
from app.memory_snapshots import (
    MemorySnapshotError,
    create_memory_snapshot,
    ensure_session_memory_snapshot,
    memory_snapshot_metadata,
    read_memory_snapshot_content,
    refresh_session_memory_snapshot,
)
from app.memory_store import (
    MemoryItemInput,
    create_memory_item,
    memory_content_hash,
    supersede_memory_item,
    transition_memory_item,
)
from app.memory_retrieval import retrieve_relevant_memories
from app.models import Agent, MemorySnapshot, Message, Session, Task, TaskRun, Workspace, utc_now
from app.planner_providers import FakePlannerProvider
from app.planning import _attach_planner_runtime_evidence
from app.run_engine import agent_run_request_for


@pytest.fixture
def world(tmp_path) -> Iterator[tuple[DbSession, Workspace, Session, Agent]]:
    engine = create_engine(f"sqlite:///{tmp_path / 'memory.db'}", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    with DbSession(engine) as db:
        workspace = Workspace(name="Memory test", root_path="apps/demo", repo_url="local://apps/demo", default_branch="main")
        session = Session(workspace_id=workspace.id, title="Memory test", bound_branch="main",
                          worktree_path=".worktrees/memory-consistency")
        frontend = Agent(name="Frontend", role="frontend", adapter_type="codex", provider="local")
        db.add_all([workspace, session, frontend,
                    Agent(name="Orchestrator", role="orchestrator", adapter_type="scripted_mock", provider="local"),
                    Agent(name="QA", role="qa", adapter_type="scripted_mock", provider="local")])
        db.commit()
        yield db, workspace, session, frontend
    engine.dispose()


def _memory_input(workspace_id, **overrides):
    values = dict(workspace_id=workspace_id, scope="project", memory_type="project_rule",
                  source="user_explicit", status="active", trust_level="user_confirmed",
                  title="Canvas rule", content_md="Canvas changes require keyboard checks.")
    values.update(overrides)
    return MemoryItemInput(**values)


def _task(db, session, frontend):
    task = Task(session_id=session.id, title="Update canvas", intent_type="frontend_change",
                assigned_agent_id=frontend.id,
                plan_json=json.dumps({"targetId": "demo-frontend", "originalRequest": "Update canvas"}))
    db.add(task)
    db.commit()
    return task


@pytest.mark.parametrize("change", ["edit", "archive", "delete", "supersede", "add", "metadata"])
def test_snapshot_keeps_content_until_explicit_refresh(world, change):
    db, workspace, session, frontend = world
    memory = create_memory_item(db, _memory_input(workspace.id))
    task = _task(db, session, frontend)
    before = build_session_context_pack(db, task)
    assert before["relevantMemories"]
    if change == "edit":
        memory.content_md = "Canvas changes require pointer checks."
        memory.content_hash = memory_content_hash(memory.content_md)
        memory.version += 1
        db.add(memory)
        db.commit()
    elif change == "archive":
        transition_memory_item(db, memory.id, "archived")
    elif change == "delete":
        db.delete(memory)
        db.commit()
    elif change == "supersede":
        supersede_memory_item(db, memory.id, _memory_input(workspace.id, content_md="Canvas replacement rule."))
    elif change == "metadata":
        memory.status = "warm"
        memory.importance = 1
        memory.last_used_at = utc_now() - timedelta(days=300)
        memory.agent_roles_json = '["backend"]'
        memory.target_ids_json = '["demo-backend"]'
        db.add(memory)
        db.commit()
    else:
        create_memory_item(db, _memory_input(workspace.id, title="Another canvas rule"))
    db.expire_all()
    after = build_session_context_pack(db, task)
    assert after["memorySnapshot"] == before["memorySnapshot"]
    assert after["relevantMemories"] == before["relevantMemories"]
    refresh_session_memory_snapshot(db, session.id)
    refreshed = build_session_context_pack(db, task)
    assert refreshed["memorySnapshot"]["memorySnapshotId"] != before["memorySnapshot"]["memorySnapshotId"]
    assert refreshed["relevantMemories"] != before["relevantMemories"]


def test_snapshot_ranking_uses_frozen_time(world, monkeypatch):
    db, workspace, session, frontend = world
    create_memory_item(db, _memory_input(workspace.id, memory_type="pattern", status="warm"))
    task = _task(db, session, frontend)
    before = build_session_context_pack(db, task)["relevantMemories"]
    assert before
    future = utc_now() + timedelta(days=900)
    monkeypatch.setattr("app.memory_retrieval.utc_now", lambda: future)
    assert build_session_context_pack(db, task)["relevantMemories"] == before


def test_task_run_uses_bound_snapshot_after_session_refresh(world):
    db, workspace, session, frontend = world
    memory = create_memory_item(db, _memory_input(workspace.id))
    task = _task(db, session, frontend)
    first = ensure_session_memory_snapshot(db, session)
    run = TaskRun(task_id=task.id, agent_id=frontend.id, state="completed",
                  worktree_path=session.worktree_path,
                  metrics_json=json.dumps({"memorySnapshot": memory_snapshot_metadata(first)}))
    db.add(run)
    db.commit()
    transition_memory_item(db, memory.id, "archived")
    refresh_session_memory_snapshot(db, session.id)
    request = agent_run_request_for(db, run, adapter_type="codex",
                                    plan_context={"memorySnapshot": {"memorySnapshotId": session.memory_snapshot_id}})
    context = request.plan_context["sessionContext"]
    assert context["memorySnapshot"]["memorySnapshotId"] == first.id
    assert [item["id"] for item in context["relevantMemories"]] == [memory.id]
    assert json.loads(run.metrics_json)["memorySnapshot"]["memorySnapshotId"] == first.id


@pytest.mark.parametrize("adapter_type", ["codex", "claude_code"])
def test_task_run_receipt_matches_filtered_instruction(world, adapter_type):
    db, workspace, session, frontend = world
    safe = create_memory_item(db, _memory_input(workspace.id))
    redacted = create_memory_item(db, _memory_input(workspace.id, content_md="Canvas uses secrets/private.txt"))
    task = _task(db, session, frontend)
    snapshot = ensure_session_memory_snapshot(db, session)
    run = TaskRun(task_id=task.id, agent_id=frontend.id, state="created",
                  worktree_path=session.worktree_path,
                  metrics_json=json.dumps({"memorySnapshot": memory_snapshot_metadata(snapshot)}))
    db.add(run)
    db.commit()
    request = agent_run_request_for(db, run, adapter_type=adapter_type)
    sent = json.loads(request.instruction.split("Canonical Shared Context:\n```json\n", 1)[1].split("\n```", 1)[0])
    metrics = json.loads(run.metrics_json)
    assert metrics["canonicalContextSnapshot"] == sent
    receipt = metrics["memoryUsage"]
    assert receipt["memorySnapshotId"] == snapshot.id
    items = {item["id"]: item for item in receipt["items"]}
    assert items[safe.id]["version"] == safe.version
    assert items[safe.id]["contentHash"] == safe.content_hash
    assert items[safe.id]["visibleContentHash"] == safe.content_hash
    assert items[safe.id]["contentVisible"] is True
    assert items[redacted.id]["contentVisible"] is False
    assert items[redacted.id]["visibleContentHash"] is None
    assert "contentMd" not in items[redacted.id]["visibleFields"]
    assert "secrets/private.txt" not in json.dumps(receipt)
    assert receipt["snapshotContentStatus"] == "frozen"
    assert receipt["visibleMemoriesHash"] == _digest(sent["fields"]["relevantMemories"]["value"])
    assert receipt["snapshotItemsHash"] == memory_snapshot_metadata(snapshot)["snapshotItemsHash"]


def test_legacy_snapshot_does_not_fabricate_old_content(world):
    db, workspace, session, frontend = world
    create_memory_item(db, _memory_input(workspace.id))
    task = _task(db, session, frontend)
    snapshot = ensure_session_memory_snapshot(db, session)
    snapshot.schema_version = "memory_snapshot_v1"
    snapshot.meta_json = "{}"
    db.add(snapshot)
    db.commit()
    context = build_session_context_pack(db, task)
    assert context["relevantMemories"] == []
    assert context["memorySnapshot"]["contentStatus"] == "legacy_unavailable"
    refresh_session_memory_snapshot(db, session.id)
    assert build_session_context_pack(db, task)["relevantMemories"]


def test_corrupt_snapshot_never_falls_back_to_live_memory(world):
    db, workspace, session, frontend = world
    create_memory_item(db, _memory_input(workspace.id))
    task = _task(db, session, frontend)
    snapshot = ensure_session_memory_snapshot(db, session)
    snapshot.meta_json = '{"memoryItems": []}'
    db.add(snapshot)
    db.commit()
    with pytest.raises(MemorySnapshotError, match="content"):
        build_session_context_pack(db, task)


@pytest.mark.parametrize("content", [
    "Canvas changes require keyboard checks.",
    "Canvas uses secrets/private.txt",
    "Canvas api_key=dummy-test-value must remain private.",
])
def test_planner_evidence_uses_original_request_even_after_refresh(world, content):
    db, workspace, session, _frontend = world
    memory = create_memory_item(db, _memory_input(workspace.id, content_md=content))
    message = Message(session_id=session.id, sender_type="user", content_md="Update canvas game")
    db.add(message)
    db.commit()
    provider = FakePlannerProvider(payload={
        "planId": "memory-plan", "planner": "llm_v1", "plannerMode": "llm_v1", "version": 1,
        "rationale": "Update the canvas inside the registered target.",
        "acceptanceCriteria": ["Keyboard works"],
        "validationExpectations": ["pnpm build"],
        "tasks": [{"title": "Update canvas", "intentType": "frontend_change", "role": "frontend",
                   "targetId": "demo-frontend", "plannedFiles": ["apps/demo/src/App.tsx"],
                   "expectedArtifactTypes": ["diff"], "acceptanceCriteria": ["Keyboard works"],
                   "validationExpectations": ["pnpm build"], "riskLevel": "low", "requiresApproval": False}],
    })
    conversation = create_llm_conversation_outcome(db, message, provider=provider)
    original = conversation.planner_input["canonicalSharedContext"]["fields"]["memorySnapshot"]["value"]
    transition_memory_item(db, memory.id, "archived")
    refresh_session_memory_snapshot(db, session.id)
    outcome = create_llm_plan_tasks_from_outcome(db, message, conversation=conversation)
    _attach_planner_runtime_evidence(db, outcome.tasks, None)
    evidence = json.loads(outcome.tasks[0].plan_json)["plannerEvidence"]
    assert evidence["memorySnapshot"] == original
    assert evidence["memoryUsage"]["memorySnapshotId"] == original["memorySnapshotId"]
    assert [item["id"] for item in evidence["memoryUsage"]["items"]] == [memory.id]
    sent_memories = conversation.planner_input["canonicalSharedContext"]["fields"]["relevantMemories"]["value"]
    receipt = evidence["memoryUsage"]
    assert receipt["visibleMemoriesHash"] == _digest(sent_memories)
    assert receipt["items"][0]["contentHash"] == memory.content_hash
    visible_body = sent_memories[0].get("contentMd")
    assert receipt["items"][0]["contentVisible"] is (visible_body is not None)
    expected_hash = hashlib.sha256(visible_body.encode("utf-8")).hexdigest() if visible_body is not None else None
    assert receipt["items"][0]["visibleContentHash"] == expected_hash
    assert "dummy-test-value" not in json.dumps(receipt)
    assert build_llm_planner_input(db, message)["canonicalSharedContext"]["fields"]["relevantMemories"]["value"] == []


def test_frozen_memories_and_run_binding_survive_database_reopen(world):
    db, workspace, session, frontend = world
    memory = create_memory_item(db, _memory_input(workspace.id))
    task = _task(db, session, frontend)
    before = build_session_context_pack(db, task)
    run = TaskRun(task_id=task.id, agent_id=frontend.id, state="completed",
                  worktree_path=session.worktree_path,
                  metrics_json=json.dumps({"memorySnapshot": before["memorySnapshot"]}))
    db.add(run)
    db.commit()
    run_id = run.id
    db.delete(memory)
    db.commit()
    refresh_session_memory_snapshot(db, session.id)
    engine = db.get_bind()
    url = engine.url
    db.close()
    engine.dispose()

    reopened = create_engine(url)
    try:
        with DbSession(reopened) as fresh_db:
            request = agent_run_request_for(fresh_db, fresh_db.get(TaskRun, run_id), adapter_type="codex")
            restored = request.plan_context["sessionContext"]
            assert restored["memorySnapshot"] == before["memorySnapshot"]
            assert restored["relevantMemories"] == before["relevantMemories"]
    finally:
        reopened.dispose()


def test_snapshot_retrieval_preserves_role_target_status_and_workspace_boundaries(world):
    db, workspace, session, frontend = world
    common = create_memory_item(db, _memory_input(workspace.id))
    scoped = create_memory_item(db, _memory_input(
        workspace.id, agent_roles=("frontend",), target_ids=("demo-frontend",), status="warm"
    ))
    for overrides in [
        {"agent_roles": ("backend",)}, {"target_ids": ("demo-backend",)},
        {"status": "pending_review"}, {"status": "deleted"},
    ]:
        create_memory_item(db, _memory_input(workspace.id, **overrides))
    unscoped = create_memory_item(db, _memory_input(None))
    task = _task(db, session, frontend)
    memories = build_session_context_pack(db, task)["relevantMemories"]
    assert {item["id"] for item in memories} == {common.id, scoped.id}
    snapshot = create_memory_snapshot(db, workspace_id=None)
    content = read_memory_snapshot_content(snapshot)
    assert [item.id for item in content.items] == [unscoped.id]
    for candidates in [None, content.items]:
        retrieved = retrieve_relevant_memories(
            db, query="canvas", workspace_id=None, candidates=candidates, as_of=content.as_of
        )
        assert [item.memory_item.id for item in retrieved] == [unscoped.id]


@pytest.mark.parametrize("damage", ["no_binding", "missing_snapshot", "wrong_schema", "foreign_workspace"])
def test_invalid_task_run_binding_fails_without_falling_back_to_session(world, damage):
    db, workspace, session, frontend = world
    create_memory_item(db, _memory_input(workspace.id))
    task = _task(db, session, frontend)
    snapshot = ensure_session_memory_snapshot(db, session)
    binding = memory_snapshot_metadata(snapshot)
    if damage == "no_binding":
        binding = None
    elif damage == "missing_snapshot":
        binding["memorySnapshotId"] = "missing-memory-snapshot"
    elif damage == "wrong_schema":
        binding["schemaVersion"] = "memory_snapshot_v1"
    else:
        binding = memory_snapshot_metadata(create_memory_snapshot(db, workspace_id=None))
    run = TaskRun(task_id=task.id, agent_id=frontend.id, state="created",
                  worktree_path=session.worktree_path,
                  metrics_json=json.dumps({"memorySnapshot": binding}))
    db.add(run)
    db.commit()
    with pytest.raises(MemorySnapshotError):
        agent_run_request_for(db, run, adapter_type="codex")
    db.refresh(run)
    assert "memoryUsage" not in json.loads(run.metrics_json)
    assert "canonicalContextSnapshot" not in json.loads(run.metrics_json)


def test_missing_session_snapshot_is_not_silently_replaced(world):
    db, _workspace, session, frontend = world
    task = _task(db, session, frontend)
    session.memory_snapshot_id = "missing-memory-snapshot"
    db.add(session)
    db.commit()
    with pytest.raises(MemorySnapshotError):
        build_session_context_pack(db, task)
    assert session.memory_snapshot_id == "missing-memory-snapshot"


def _digest(value):
    return hashlib.sha256(json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")).hexdigest()


def _rehash(snapshot, meta, *, member_hashes=True):
    if member_hashes:
        for item in meta["memoryItems"]:
            item["itemHash"] = _digest({key: value for key, value in item.items() if key != "itemHash"})
    meta["snapshotItemsHash"] = _digest(meta["memoryItems"])
    _rehash_context(snapshot, meta)


def _rehash_context(snapshot, meta):
    snapshot.context_pack_hash = _digest({
        "schemaVersion": snapshot.schema_version,
        "workspaceId": snapshot.workspace_id,
        "retrievalAsOf": meta["retrievalAsOf"],
        "snapshotItemsHash": meta["snapshotItemsHash"],
        "agentsMdHash": snapshot.agents_md_hash,
        "claudeMdHash": snapshot.claude_md_hash,
        "projectMemoryVersion": snapshot.project_memory_version,
        "userPreferenceVersion": snapshot.user_preference_version,
        "targetRegistryVersion": snapshot.target_registry_version,
        "runtimeConfigVersion": snapshot.runtime_config_version,
    })


@pytest.mark.parametrize("damage", [
    "member_hash", "items_hash", "content_hash", "missing_metadata", "invalid_time",
    "workspace", "boolean_version", "duplicate", "collection_version", "unknown_schema",
    "metadata_hash",
])
def test_invalid_frozen_members_are_rejected_even_with_recomputed_envelope_hash(world, damage):
    db, workspace, session, frontend = world
    create_memory_item(db, _memory_input(workspace.id))
    task = _task(db, session, frontend)
    snapshot = ensure_session_memory_snapshot(db, session)
    meta = json.loads(snapshot.meta_json)
    item = meta["memoryItems"][0]
    if damage == "content_hash":
        item["contentMd"] = "Canvas altered content with original hash."
    elif damage == "missing_metadata":
        del item["importance"]
    elif damage == "invalid_time":
        item["lastUsedAt"] = "not-a-date"
    elif damage == "workspace":
        item["workspaceId"] = None
    elif damage == "boolean_version":
        item["version"] = True
    elif damage == "duplicate":
        meta["memoryItems"].append(dict(item))
    elif damage == "collection_version":
        snapshot.project_memory_version = "0" * 64
    elif damage == "unknown_schema":
        snapshot.schema_version = "memory_snapshot_future"
    elif damage == "metadata_hash":
        snapshot.agents_md_hash = ""
    _rehash(snapshot, meta)
    if damage == "member_hash":
        item["title"] = "Changed canvas title"
        _rehash(snapshot, meta, member_hashes=False)
    elif damage == "items_hash":
        meta["snapshotItemsHash"] = "0" * 64
        _rehash_context(snapshot, meta)
    snapshot.meta_json = json.dumps(meta)
    db.add(snapshot)
    db.commit()
    with pytest.raises(MemorySnapshotError, match="content"):
        build_session_context_pack(db, task)


def test_rule_planner_metadata_does_not_claim_a_provider_memory_receipt(world):
    db, workspace, session, frontend = world
    create_memory_item(db, _memory_input(workspace.id))
    task = _task(db, session, frontend)
    _attach_planner_runtime_evidence(db, [task], None)
    evidence = json.loads(task.plan_json)["plannerEvidence"]
    assert evidence["memorySnapshot"]["memorySnapshotId"] == session.memory_snapshot_id
    assert "memoryUsage" not in evidence



@pytest.mark.parametrize("damage", ["digest", "missing_digest", "member_digest", "scoring_time", "replaced_content"])
def test_request_rejects_changed_snapshot_binding_without_writing_receipt(world, damage):
    db, workspace, session, frontend = world
    create_memory_item(db, _memory_input(workspace.id))
    task = _task(db, session, frontend)
    snapshot = ensure_session_memory_snapshot(db, session)
    binding = memory_snapshot_metadata(snapshot)
    if damage == "digest":
        binding["contextPackHash"] = "0" * 64
    elif damage == "missing_digest":
        del binding["contextPackHash"]
    elif damage == "member_digest":
        binding["snapshotItemsHash"] = "0" * 64
    elif damage == "scoring_time":
        binding["retrievalAsOf"] = "2000-01-01T00:00:00"
    else:
        create_memory_item(db, _memory_input(workspace.id, content_md="Canvas replacement policy."))
        replacement = create_memory_snapshot(db, workspace_id=workspace.id)
        # A self-consistent rewritten row must not pass the earlier run's binding.
        for name, value in replacement.model_dump().items():
            if name != "id":
                setattr(snapshot, name, value)
        db.add(snapshot)
        db.commit()
    run = TaskRun(task_id=task.id, agent_id=frontend.id, state="created",
                  worktree_path=session.worktree_path,
                  metrics_json=json.dumps({"memorySnapshot": binding}))
    db.add(run)
    db.commit()
    original_metrics = run.metrics_json
    with pytest.raises(MemorySnapshotError):
        agent_run_request_for(db, run, adapter_type="codex")
    db.refresh(run)
    assert run.metrics_json == original_metrics


def test_legacy_task_run_binding_accepts_original_metadata_without_backfill(world):
    db, workspace, session, frontend = world
    create_memory_item(db, _memory_input(workspace.id))
    task = _task(db, session, frontend)
    snapshot = ensure_session_memory_snapshot(db, session)
    snapshot.schema_version = "memory_snapshot_v1"
    snapshot.meta_json = "{}"
    db.add(snapshot)
    db.commit()
    binding = memory_snapshot_metadata(snapshot)
    for name in ("contentStatus", "snapshotItemsHash", "retrievalAsOf"):
        del binding[name]
    run = TaskRun(task_id=task.id, agent_id=frontend.id, state="created",
                  worktree_path=session.worktree_path,
                  metrics_json=json.dumps({"memorySnapshot": binding}))
    db.add(run)
    db.commit()
    request = agent_run_request_for(db, run, adapter_type="codex")
    assert request.plan_context["sessionContext"]["relevantMemories"] == []
    assert json.loads(run.metrics_json)["memoryUsage"]["snapshotContentStatus"] == "legacy_unavailable"
    db.refresh(snapshot)
    assert snapshot.meta_json == "{}"


@pytest.mark.parametrize("endpoint", ["session", "run", "message"])
def test_damaged_snapshot_returns_recoverable_http_error_without_new_tasks(world, endpoint):
    from fastapi.testclient import TestClient
    from sqlmodel import select
    from app.dependencies import get_db
    from app.main import app

    db, workspace, session, frontend = world
    memory = create_memory_item(db, _memory_input(workspace.id))
    task = _task(db, session, frontend)
    snapshot = ensure_session_memory_snapshot(db, session)
    snapshot.meta_json = '{"private": "private-canary-do-not-expose"}'
    db.add(snapshot)
    db.commit()
    original_ids = [entry.id for entry in db.exec(select(Task)).all()]
    overrides = dict(app.dependency_overrides)
    app.dependency_overrides[get_db] = lambda: db
    try:
        client = TestClient(app, raise_server_exceptions=False)
        if endpoint == "session":
            response = client.get(f"/sessions/{session.id}")
        elif endpoint == "run":
            response = client.post(f"/tasks/{task.id}/runs")
        else:
            response = client.post(f"/sessions/{session.id}/messages", json={
                "senderType": "user", "contentMd": "@frontend build a login page",
            })
        assert response.status_code == 409, response.text
        assert "snapshot" in response.json()["detail"].lower()
        assert "private-canary-do-not-expose" not in response.text
        assert [entry.id for entry in db.exec(select(Task)).all()] == original_ids
        assert db.exec(select(TaskRun)).all() == []
        repaired = client.post(f"/sessions/{session.id}/memory-snapshot/refresh")
        assert repaired.status_code == 200, repaired.text
        assert repaired.json()["memorySnapshotId"] != snapshot.id
        assert client.get(f"/sessions/{session.id}").status_code == 200
        restored = build_session_context_pack(db, task)
        assert [entry["id"] for entry in restored["relevantMemories"]] == [memory.id]
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(overrides)


def test_refresh_holds_writer_boundary_until_snapshot_binding_is_saved(world, monkeypatch):
    from sqlalchemy.exc import OperationalError
    from sqlmodel import select
    import app.memory_snapshots as snapshots

    db, workspace, session, frontend = world
    create_memory_item(db, _memory_input(workspace.id))
    task = _task(db, session, frontend)
    original = ensure_session_memory_snapshot(db, session)
    task_id, agent_id, worktree_path = task.id, frontend.id, session.worktree_path
    competing_engine = create_engine(db.get_bind().url, connect_args={"timeout": 0})
    original_create = snapshots.create_memory_snapshot
    committed = []

    def create_while_another_connection_attempts_to_queue(*args, **kwargs):
        with DbSession(competing_engine) as other:
            other.add(TaskRun(task_id=task_id, agent_id=agent_id, state="queued",
                              worktree_path=worktree_path))
            try:
                other.commit()
            except OperationalError as exc:
                other.rollback()
                assert "locked" in str(exc).lower()
                committed.append(False)
            else:
                committed.append(True)
        return original_create(*args, **kwargs)

    monkeypatch.setattr(snapshots, "create_memory_snapshot", create_while_another_connection_attempts_to_queue)
    try:
        refreshed = refresh_session_memory_snapshot(db, session.id)
        assert committed == [False], "A run was queued between the active-run check and Session refresh"
        assert refreshed.id != original.id
        db.refresh(session)
        assert session.memory_snapshot_id == refreshed.id
        assert db.exec(select(TaskRun)).all() == []
    finally:
        competing_engine.dispose()


@pytest.mark.parametrize("outcome", ["assistant_reply", "invalid_plan", "provider_error", "malformed_output"])
def test_planner_fallback_preserves_the_original_memory_request(world, monkeypatch, outcome):
    import app.planning as planning
    from app.config import Settings
    from app.models import ExternalProjectTarget
    from app.planner_providers import PlannerProviderResult

    db, workspace, session, _frontend = world
    target = ExternalProjectTarget(
        workspace_id=workspace.id, target_id="external-memory-fixture",
        name="Memory frontend", root_path=workspace.root_path,
        project_type="vite-react", allowed_paths_json='["src"]',
    )
    session.active_frontend_target_id = target.target_id
    memory = create_memory_item(db, _memory_input(workspace.id,
        content_md="Dashboard pages require keyboard checks."))
    message = Message(session_id=session.id, sender_type="user",
                      content_md="build a dashboard page with cards")
    db.add_all([target, session, message])
    db.commit()
    captured = {}

    class RefreshingProvider(FakePlannerProvider):
        def create_plan(self, planner_input):
            captured.update(planner_input)
            transition_memory_item(db, memory.id, "archived")
            refresh_session_memory_snapshot(db, session.id)
            if outcome == "provider_error":
                raise RuntimeError("Controlled provider failure")
            if outcome == "malformed_output":
                return PlannerProviderResult(provider_id=self.provider_id,
                    provider_type=self.provider_type, planner_source=self.planner_source,
                    status="succeeded", raw_output="not json")
            return super().create_plan(planner_input)

    payload = {"outcomeType": "assistant_reply", "reply": "I can help plan that.",
               "riskLevel": "low", "validationResult": "not_required"}
    if outcome == "invalid_plan":
        payload = {
            "planId": "invalid-memory-plan", "planner": "llm_v1", "plannerMode": "llm_v1", "version": 1,
            "rationale": "Unsupported target", "acceptanceCriteria": ["Keyboard works"],
            "validationExpectations": ["pnpm build"],
            "tasks": [{"title": "Update dashboard", "intentType": "frontend_change", "role": "frontend",
                       "targetId": "unregistered-target", "plannedFiles": ["src/App.tsx"],
                       "expectedArtifactTypes": ["diff"], "acceptanceCriteria": ["Keyboard works"],
                       "validationExpectations": ["pnpm build"], "riskLevel": "low", "requiresApproval": False}],
        }
    provider = RefreshingProvider(payload=payload)
    monkeypatch.setattr(planning, "resolve_planner_provider", lambda *args, **kwargs: provider)
    monkeypatch.setattr(planning, "_planner_runtime_resolution", lambda *args: None)
    monkeypatch.setattr(planning, "get_settings", lambda: Settings(
        llm_planner_enabled=True, llm_planner_provider="claude_cli"))
    tasks = planning.plan_for_message(db, message, message.content_md)
    assert tasks
    sent = captured["canonicalSharedContext"]
    original = sent["fields"]["memorySnapshot"]["value"]
    assert original["memorySnapshotId"] != session.memory_snapshot_id
    for task in tasks:
        evidence = json.loads(task.plan_json)["plannerEvidence"]
        assert evidence["plannerSource"] == "fallback"
        if outcome == "invalid_plan":
            assert evidence["fallbackReason"] == "task_plan_validation_failed"
            assert evidence["errorCode"] == "LLM_TASK_PLAN_VALIDATION_FAILED"
        assert evidence["memorySnapshot"] == original
        receipt = evidence["memoryUsage"]
        assert receipt["memorySnapshotId"] == original["memorySnapshotId"]
        assert [item["id"] for item in receipt["items"]] == [memory.id]
        assert receipt["visibleMemoriesHash"] == _digest(sent["fields"]["relevantMemories"]["value"])
        assert receipt["evidenceType"] == "prepared_provider_request"
