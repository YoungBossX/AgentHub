import json
from contextlib import contextmanager

import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import Session as DbSession, SQLModel, create_engine, select

from app.context_pack import build_session_context_pack
from app.llm_planner import build_llm_planner_input
from app.memory_retrieval import (
    MemoryContextBudgetError, retrieve_relevant_memories, retrieved_memory_context,
    select_memory_context, serialized_memory_chars,
)
from app.memory_store import MemoryItemInput, create_memory_item
from app.models import Agent, Message, Session, Task, TaskRun, Workspace


@contextmanager
def world():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)
    with DbSession(engine) as db:
        workspace = Workspace(name="Rule budget", root_path="apps/demo", repo_url="local://apps/demo", default_branch="main")
        session = Session(workspace_id=workspace.id, title="Rule budget", bound_branch="main", worktree_path=".worktrees/rule-budget")
        frontend = Agent(name="Frontend", role="frontend", adapter_type="codex", provider="local")
        db.add_all([workspace, session, frontend,
                    Agent(name="Orchestrator", role="orchestrator", adapter_type="scripted_mock", provider="local")])
        db.commit()
        yield db, workspace, session, frontend
    engine.dispose()


def remember(db, workspace, **overrides):
    values = dict(workspace_id=workspace.id, scope="project", memory_type="project_rule", source="user_explicit",
                  status="active", trust_level="user_confirmed", title="Release policy", content_md="Preserve compatibility.")
    values.update(overrides)
    return create_memory_item(db, MemoryItemInput(**values))


def retrieve(db, workspace, **kwargs):
    return retrieve_relevant_memories(db, workspace_id=workspace.id, query=kwargs.pop("query", "canvas"), **kwargs)


@pytest.mark.parametrize("query", ["canvas", "", "!?", "中文界面"])
def test_trusted_rules_survive_unrelated_queries_and_zero_experience_slots(query):
    with world() as (db, workspace, _session, _frontend):
        rule = remember(db, workspace)
        preference = remember(db, workspace, memory_type="user_preference", title="Writing style", content_md="Use concise explanations.")
        remember(db, workspace, memory_type="pattern", title="Canvas", content_md="canvas painting")
        results = retrieve(db, workspace, query=query, limit=0)
        assert [item.memory_item.id for item in results] == [rule.id, preference.id]


def test_optional_memories_cannot_exceed_default_serialized_budget():
    with world() as (db, workspace, _session, _frontend):
        oversized = remember(db, workspace, memory_type="pattern", title="Canvas experience", content_md="canvas " * 9000)
        small = remember(db, workspace, memory_type="pattern", title="Canvas note", content_md="canvas accessibility")
        contexts = retrieved_memory_context(retrieve(db, workspace))
        assert len(json.dumps(contexts, ensure_ascii=True, sort_keys=True, indent=2)) <= 16000
        assert oversized.id not in {item["id"] for item in contexts}
        assert small.id in {item["id"] for item in contexts}


@pytest.mark.parametrize("restriction,context", [
    ({"target_ids": ("demo-frontend",)}, {}),
    ({"target_ids": ("demo-frontend",)}, {"target_id": "demo-backend"}),
    ({"agent_roles": ("frontend",)}, {}),
    ({"agent_roles": ("frontend",)}, {"agent_role": "backend"}),
])
def test_unknown_and_mismatched_context_exclude_restricted_rules(restriction, context):
    with world() as (db, workspace, _session, _frontend):
        remember(db, workspace, title="Canvas rule", content_md="canvas validation", **restriction)
        assert retrieve(db, workspace, **context) == []


def test_planner_and_coding_include_rules_without_keyword_matches():
    with world() as (db, workspace, session, frontend):
        rule = remember(db, workspace)
        message = Message(session_id=session.id, sender_type="user", content_md="Update canvas")
        task = Task(session_id=session.id, title="Update canvas", intent_type="frontend_change", assigned_agent_id=frontend.id,
                    plan_json=json.dumps({"targetId": "demo-frontend", "originalRequest": "Update canvas"}))
        db.add_all([message, task])
        db.commit()
        planner = build_llm_planner_input(db, message)["canonicalSharedContext"]["fields"]
        coding = build_session_context_pack(db, task)
        assert [item["id"] for item in planner["relevantMemories"]["value"]] == [rule.id]
        assert coding["relevantMemories"] == planner["relevantMemories"]["value"]
        assert coding["memorySelection"] == planner["memorySelection"]["value"]


@pytest.mark.parametrize("status", ["pending_review", "archived", "rejected", "deleted", "warm"])
def test_only_active_confirmed_rules_are_always_included(status):
    with world() as (db, workspace, _session, _frontend):
        remember(db, workspace, status=status)
        assert retrieve(db, workspace) == []


@pytest.mark.parametrize("trust", ["untrusted", "external"])
def test_untrusted_rules_are_optional_lexical_experience(trust):
    with world() as (db, workspace, _session, _frontend):
        memory = remember(db, workspace, trust_level=trust)
        assert retrieve(db, workspace) == []
        selected = retrieve(db, workspace, query="compatibility")
        assert [item.memory_item.id for item in selected] == [memory.id]
        assert selected[0].layer == "experience"


def test_rules_do_not_compete_for_experience_slots_and_preferences_precede_experience():
    with world() as (db, workspace, _session, _frontend):
        rules = [remember(db, workspace, title=f"Rule {index}", importance=index) for index in range(7)]
        preference = remember(db, workspace, memory_type="user_preference", content_md="Brief answers.")
        for index in range(3):
            remember(db, workspace, memory_type="pattern", title=f"Canvas {index}", content_md="canvas drawing")
        result = select_memory_context(db, workspace_id=workspace.id, query="canvas", limit=1)
        contexts = result.to_context()
        assert [item["id"] for item in contexts[:7]] == [item.id for item in reversed(rules)]
        assert contexts[7]["id"] == preference.id
        assert contexts[8]["layer"] == "experience"
        assert result.evidence["selectedCounts"] == {"rule": 7, "preference": 1, "experience": 1}
        assert result.evidence["omittedByExperienceLimit"] == 2


def test_budget_boundary_preserves_full_unicode_content_and_hash():
    with world() as (db, workspace, _session, _frontend):
        memory = remember(db, workspace, content_md='中文规则 "quoted" 🧠\n下一行')
        kwargs = dict(workspace_id=workspace.id, query="canvas")
        full = select_memory_context(db, **kwargs)
        exact = serialized_memory_chars(full.to_context())
        assert select_memory_context(db, max_chars=exact, **kwargs).to_context() == full.to_context()
        assert full.to_context()[0]["contentMd"] == memory.content_md
        assert full.to_context()[0]["contentHash"] == memory.content_hash
        with pytest.raises(MemoryContextBudgetError):
            select_memory_context(db, max_chars=exact - 1, **kwargs)
        db.refresh(memory)
        assert memory.content_md == full.to_context()[0]["contentMd"]


def test_budget_omissions_do_not_consume_experience_slots():
    with world() as (db, workspace, _session, _frontend):
        rule = remember(db, workspace)
        remember(db, workspace, memory_type="user_preference", content_md="preference " * 20000)
        remember(db, workspace, memory_type="pattern", content_md="canvas " * 9000)
        small = remember(db, workspace, memory_type="pattern", content_md="canvas drawing")
        selected = select_memory_context(db, workspace_id=workspace.id, query="canvas", limit=1)
        assert [item["id"] for item in selected.to_context()] == [rule.id, small.id]
        assert selected.evidence["omittedByBudget"] == {"preference": 1, "experience": 1}
        assert selected.evidence["usedChars"] == serialized_memory_chars(selected.to_context())


def test_confirmed_target_rule_requires_matching_target_and_role():
    with world() as (db, workspace, _session, _frontend):
        memory = remember(db, workspace, target_ids=("demo-frontend",), agent_roles=("frontend",))
        selected = retrieve(db, workspace, target_id="demo-frontend", agent_role="frontend")
        assert [item.memory_item.id for item in selected] == [memory.id]


@pytest.mark.parametrize("scope", ["session", "target"])
def test_missing_scope_owner_cannot_be_promoted_to_workspace_rule(scope):
    with world() as (db, workspace, _session, _frontend):
        remember(db, workspace, scope=scope, content_md="canvas policy")
        assert retrieve(db, workspace, target_id="demo-frontend", agent_role="frontend") == []


def test_other_workspace_rules_cannot_enter_frozen_candidate_selection():
    with world() as (db, workspace, _session, _frontend):
        foreign = remember(db, workspace, workspace_id="another-workspace")
        unscoped = remember(db, workspace, workspace_id=None)
        selected = select_memory_context(db, query="compatibility", workspace_id=workspace.id, candidates=[foreign, unscoped])
        assert selected.to_context() == []


def test_budget_selection_is_stable_for_frozen_candidates_after_live_edits():
    from app.memory_snapshots import create_memory_snapshot, read_memory_snapshot_content
    with world() as (db, workspace, _session, _frontend):
        memory = remember(db, workspace)
        content = read_memory_snapshot_content(create_memory_snapshot(db, workspace_id=workspace.id))
        kwargs = dict(workspace_id=workspace.id, query="canvas", candidates=content.items, as_of=content.as_of)
        before = select_memory_context(db, **kwargs)
        memory.content_md = "changed " * 20000
        memory.status = "archived"
        db.add(memory)
        db.commit()
        after = select_memory_context(db, **kwargs)
        assert after.to_context() == before.to_context()
        assert after.evidence == before.evidence


def test_budget_error_prevents_planner_invocation_and_is_sanitized_http_error(monkeypatch):
    from fastapi.testclient import TestClient
    from app.config import Settings
    from app.main import app, get_db
    from app.planner_providers import FakePlannerProvider
    import app.planning as planning

    class MustNotRunProvider(FakePlannerProvider):
        def create_plan(self, planner_input):
            pytest.fail("Over-budget rules reached the planner provider")

    provider = MustNotRunProvider(payload={})
    monkeypatch.setattr(planning, "resolve_planner_provider", lambda *args, **kwargs: provider)
    monkeypatch.setattr(planning, "_planner_runtime_resolution", lambda *args: None)
    monkeypatch.setattr(planning, "get_settings", lambda: Settings(llm_planner_enabled=True, llm_planner_provider="claude_cli"))
    with world() as (db, workspace, session, _frontend):
        remember(db, workspace, content_md="private-budget-canary " * 3000)
        overrides = dict(app.dependency_overrides)
        app.dependency_overrides[get_db] = lambda: db
        try:
            response = TestClient(app, raise_server_exceptions=False).post(
                f"/sessions/{session.id}/messages", json={"senderType": "user", "contentMd": "@orchestrator update canvas"})
            assert response.status_code == 422, response.text
            assert response.json()["code"] == "MEMORY_CONTEXT_BUDGET_EXCEEDED"
            assert "refresh" in response.json()["detail"]
            assert "private-budget-canary" not in response.text
            assert db.exec(select(Task)).all() == []
            assert db.exec(select(TaskRun)).all() == []
        finally:
            app.dependency_overrides.clear()
            app.dependency_overrides.update(overrides)


@pytest.mark.parametrize("adapter_type", ["codex", "claude_code", "scripted_mock"])
def test_prepared_coding_receipt_keeps_selection_evidence_and_visible_size(adapter_type):
    from app.memory_snapshots import ensure_session_memory_snapshot, memory_snapshot_metadata
    from app.run_engine import agent_run_request_for
    with world() as (db, workspace, session, frontend):
        remember(db, workspace)
        task = Task(session_id=session.id, title="Update canvas", intent_type="frontend_change", assigned_agent_id=frontend.id,
                    plan_json=json.dumps({"targetId": "demo-frontend"}))
        db.add(task)
        db.commit()
        binding = memory_snapshot_metadata(ensure_session_memory_snapshot(db, session))
        run = TaskRun(task_id=task.id, agent_id=frontend.id, state="created", worktree_path=session.worktree_path,
                      metrics_json=json.dumps({"memorySnapshot": binding}))
        db.add(run)
        db.commit()
        request = agent_run_request_for(db, run, adapter_type=adapter_type)
        fields = request.plan_context["sessionContext"]["providerVisibleContext"]["canonicalContext"]["fields"]
        receipt = json.loads(run.metrics_json)["memoryUsage"]
        assert receipt["selection"] == fields["memorySelection"]["value"]
        assert receipt["items"][0]["layer"] == "rule"
        assert receipt["visibleChars"] == serialized_memory_chars(fields["relevantMemories"]["value"])
        assert receipt["visibleChars"] <= receipt["selection"]["maxChars"]
        assert receipt["evidenceType"] == "prepared_provider_request"
