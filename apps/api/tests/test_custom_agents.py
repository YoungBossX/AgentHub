import json
from dataclasses import replace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.pool import StaticPool
from sqlmodel import Session as DbSession, SQLModel, create_engine, select

from app.agent_profiles import profile_for_draft
from app.agent_runtime_config import validate_runtime_config, upsert_runtime_config
from app.claude_code_adapter import ClaudeCodeAdapter
from app.custom_agents import (
    CustomAgentError, CustomAgentInput, custom_launch_permissions,
    custom_runtime_resolution, require_custom_agent, save_custom_agent,
)
from app.db import _ensure_sqlite_demo_schema_columns, _ensure_sqlite_demo_schema_indexes
from app.guardrails import evaluate_command
from app.llm_planner import build_llm_planner_request
from app.main import app, get_db, task_run_response
from app.models import Agent, AgentProfileDraft, Message, Session, Task, Workspace
from app.planner_providers import ClaudeCliPlannerProvider
from app.planning import plan_for_message, _planner_runtime_resolution
from app.planning_intents import MentionParseError, parse_mentions
from app.provider_configs import list_provider_configs
from app.run_engine import agent_run_request_for
from app.task_runs import create_task_run, TaskRunLifecycleError, require_task_run_execution_access_mode


@pytest.fixture
def db():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)
    with DbSession(engine) as db:
        workspace = Workspace(name="Custom workspace", root_path="apps/demo", repo_url="local://apps/demo", default_branch="main")
        session = Session(workspace_id=workspace.id, title="Custom session", bound_branch="main", worktree_path=".worktrees/custom-test")
        agents = [Agent(name=role, role=role, adapter_type="codex" if role == "frontend" else "scripted_mock", provider="local") for role in ["frontend", "qa", "orchestrator"]]
        db.add_all([workspace, session, *agents]); db.commit()
        yield db
    engine.dispose()


def value(**kwargs):
    return replace(CustomAgentInput(
        display_name="界面工程师", mention_alias="ui-designer", role="frontend", provider_id="local-codex-cli",
        tool_policy="codex_coding", supported_targets=["demo-frontend"], capability_tags=["code_write", "diff_analysis"],
        system_prompt="Frozen custom behavior", description="Scoped UI work",
    ), **kwargs)


def workspace_id(db):
    return db.exec(select(Workspace)).first().id


def save(db, **kwargs):
    return save_custom_agent(db, workspace_id=workspace_id(db), value=value(**kwargs))


def task(db, profile, *, explicit=True):
    role = "qa" if profile.role == "review" else profile.role
    agent = db.exec(select(Agent).where(Agent.role == role)).one()
    plan = {"targetId": "demo-frontend", "assignedRole": profile.role, "files": ["apps/demo/src/App.tsx"]}
    if explicit: plan["agentProfileId"] = profile.id
    result = Task(session_id=db.exec(select(Session)).first().id, title="Change demo button", intent_type="review" if role == "qa" else "frontend_change", assigned_agent_id=agent.id, plan_json=json.dumps(plan))
    db.add(result); db.commit()
    return result


@pytest.mark.parametrize("kwargs", [
    {"mention_alias": "FRONTEND"}, {"mention_alias": "非法别名"}, {"display_name": " "},
    {"tool_policy": "host_shell"}, {"provider_id": "missing"}, {"provider_id": "local-claude-code-cli"},
    {"capability_tags": ["code_write", "platform_change"]}, {"capability_tags": ["diff_analysis"]},
    {"supported_targets": []}, {"supported_targets": ["unknown"]}, {"supported_targets": ["agenthub-platform"]},
    {"supported_targets": ["demo-backend"]}, {"system_prompt": "bad\x00prompt"}, {"system_prompt": "x" * 8001},
])
def test_invalid_profiles_do_not_persist(db, kwargs):
    with pytest.raises(ValueError): save(db, **kwargs)
    assert db.exec(select(AgentProfileDraft)).all() == []


def test_alias_uniqueness_lifecycle_workspace_isolation_and_legacy_draft(db):
    profile = save(db, mention_alias="UI-Designer")
    profile_id = profile.id
    assert profile.mention_alias == "ui-designer"
    with pytest.raises(CustomAgentError, match="already exists"): save(db)
    other = Workspace(name="Other", root_path="apps/demo", repo_url="local://apps/demo", default_branch="main")
    db.add(other); db.commit()
    second = save_custom_agent(db, workspace_id=other.id, value=value())
    with pytest.raises(CustomAgentError, match="workspace"): require_custom_agent(db, workspace_id(db), second.id)
    changed = save_custom_agent(db, workspace_id=workspace_id(db), profile_id=profile_id, value=value(display_name="新版名称", enabled=False))
    db.expire_all()
    assert changed.id == profile_id and db.get(AgentProfileDraft, profile_id).status == "disabled"
    with pytest.raises(MentionParseError, match="disabled"): parse_mentions(db, "@ui-designer update demo button", workspace_id(db))
    legacy = AgentProfileDraft(workspace_id=workspace_id(db), display_name="Legacy", avatar_initials="LG", role="frontend", adapter_type="scripted_mock", provider_id="local-scripted-mock", safe_for_write=True)
    db.add(legacy); db.commit()
    assert profile_for_draft(legacy).safe_for_write is False
    with pytest.raises(CustomAgentError): require_custom_agent(db, workspace_id(db), legacy.id)


def test_direct_alias_routes_actual_profile_and_rejects_foreign_unknown_and_ambiguity(db):
    profile = save(db)
    session = db.exec(select(Session)).first()
    message = Message(session_id=session.id, sender_type="user", content_md="@ui-designer change the button to Custom in the demo app")
    db.add(message); db.commit()
    tasks = plan_for_message(db, message, message.content_md)
    assert len(tasks) == 1
    plan = json.loads(tasks[0].plan_json)
    assert plan["agentProfileId"] == profile.id and plan["agentProfileDisplayName"] == profile.display_name
    save(db, mention_alias="another-ui")
    with pytest.raises(MentionParseError, match="ambiguous"): parse_mentions(db, "@ui-designer @another-ui", workspace_id(db))
    with pytest.raises(MentionParseError, match="Unknown"): parse_mentions(db, "@ui-designer", "foreign")
    with pytest.raises(MentionParseError, match="Unknown"): parse_mentions(db, "@unknown", workspace_id(db))


@pytest.mark.parametrize("explicit", [True, False])
def test_task_run_uses_custom_selection_and_freezes_prompt_policy_and_identity(db, explicit):
    profile = save(db)
    if not explicit:
        upsert_runtime_config(db, workspace_id(db), {"frontend": custom_runtime_resolution(profile).role_config})
    run = create_task_run(db, task(db, profile, explicit=explicit).id)
    save_custom_agent(db, workspace_id=workspace_id(db), profile_id=profile.id, value=value(
        display_name="Renamed", system_prompt="Changed instruction", provider_id="local-claude-code-cli", tool_policy="claude_file_edit",
    ))
    request = agent_run_request_for(db, run, adapter_type="codex")
    public = task_run_response(db, run).metrics_json
    assert request.permission_profile == {"network": "off", "toolPolicy": "codex_coding"}
    assert "Frozen custom behavior" in request.instruction and "Changed instruction" not in request.instruction
    assert public["agentSelection"]["customProfile"]["displayName"] == "界面工程师"
    assert public["agentInstruction"]["profileId"] == profile.id
    assert "agentInstructionBinding" not in public and "Frozen custom behavior" not in json.dumps(public)
    profile.status = "disabled"; db.add(profile); db.commit()
    with pytest.raises(CustomAgentError, match="disabled"): custom_launch_permissions(db, workspace_id(db), json.loads(run.metrics_json), "codex")
    with pytest.raises(CustomAgentError, match="disabled"): agent_run_request_for(db, run, adapter_type="codex")


def test_explicit_profile_does_not_inherit_unrelated_role_provider_or_prompt(db):
    profile = save(db)
    frontend = db.exec(select(Agent).where(Agent.role == "frontend")).one()
    resolution = replace(custom_runtime_resolution(profile).role_config, agent_profile_id=frontend.id, adapter_type="claude_code", provider_id="local-claude-code-cli", system_prompt="Unrelated role override")
    upsert_runtime_config(db, workspace_id(db), {"frontend": resolution})
    run = create_task_run(db, task(db, profile).id)
    metrics = json.loads(run.metrics_json)
    assert metrics["runtimeConfigResolution"]["providerId"] == profile.provider_id
    assert metrics["providerAssignment"]["providerId"] == profile.provider_id
    assert "Unrelated role override" not in agent_run_request_for(db, run, adapter_type="codex").instruction


def test_prompt_binding_cannot_use_another_custom_profile_identity(db):
    profile = save(db)
    run = create_task_run(db, task(db, profile).id)
    metrics = json.loads(run.metrics_json)
    metrics["agentInstructionBinding"]["profileId"] = "other-profile"
    run.metrics_json = json.dumps(metrics)
    db.add(run); db.commit()
    with pytest.raises(TaskRunLifecycleError, match="identity"):
        agent_run_request_for(db, run, adapter_type="codex")


def test_read_only_claude_has_native_tools_and_read_only_execution_binding(db):
    profile = save(db, role="review", provider_id="local-claude-code-cli", tool_policy="claude_read_only", capability_tags=["code_review"])
    run = create_task_run(db, task(db, profile).id)
    assert require_task_run_execution_access_mode(db, run, require_started=False) == "readonly"
    request = agent_run_request_for(db, run, adapter_type="claude_code")
    adapter = ClaudeCodeAdapter(read_only=True)
    assert adapter.getCapabilities().supports_file_edit is False
    assert adapter.getCapabilities().supports_shell_command is False
    command = adapter._build_command(request)
    assert command[9] == command[11] == "Read"
    assert evaluate_command(command).allowed
    command[11] = "Read,Write,Edit,MultiEdit"
    assert not evaluate_command(command).allowed
    config = replace(custom_runtime_resolution(profile).role_config, mode="review")
    assert validate_runtime_config({"review": config}, profiles=[profile_for_draft(profile)], providers=list_provider_configs()).valid


def test_custom_planner_routes_profile_prompt_target_scope_and_native_no_tools(db):
    profile = save(db, role="orchestrator", provider_id="claude-cli-planner", tool_policy="planner_no_tools", capability_tags=["code_review"])
    message = Message(session_id=db.exec(select(Session)).first().id, sender_type="user", content_md="@ui-designer plan a demo login page")
    db.add(message); db.commit()
    request = build_llm_planner_request(db, message)
    assert _planner_runtime_resolution(db, message).role_config.agent_profile_id == profile.id
    assert request.agent_system_prompt == profile.system_prompt
    assert [target["targetId"] for target in request.target_registry] == ["demo-frontend"]
    command = ClaudeCliPlannerProvider(claude_binary="claude")._build_command(request.to_provider_payload())
    assert command[command.index("--tools") + 1] == ""
    assert command[command.index("--allowedTools") + 1] == ""
    assert "--strict-mcp-config" in command


def test_api_create_edit_contacts_reload_duplicate_and_foreign_update(db, monkeypatch):
    import app.main as main_module

    def unexpected_global_init(*args, **kwargs):
        pytest.fail("Custom profile API test must not initialize the global runtime database.")
    monkeypatch.setattr(main_module, "init_database", unexpected_global_init)
    def override(): yield db
    app.dependency_overrides[get_db] = override
    try:
        client = TestClient(app)
        payload = {"displayName": "My UI", "mentionAlias": "my-ui", "role": "frontend", "providerId": "local-codex-cli", "toolPolicy": "codex_coding", "supportedTargets": ["demo-frontend"], "capabilityTags": ["code_write"], "systemPrompt": "Use Chinese"}
        endpoint = f"/workspaces/{workspace_id(db)}/custom-agents"
        response = client.post(endpoint, json=payload)
        assert response.status_code == 201
        profile = response.json()
        assert profile["origin"] == "custom" and profile["systemPrompt"] == "Use Chinese"
        assert client.post(endpoint, json=payload).status_code == 400
        assert any(contact.get("mentionAlias") == "my-ui" for contact in client.get(f"/workspaces/{workspace_id(db)}/agents").json())
        updated = client.put(f"{endpoint}/{profile['id']}", json={**payload, "displayName": "Changed", "enabled": False})
        assert updated.json()["id"] == profile["id"] and updated.json()["status"] == "disabled"
        assert all(contact.get("mentionAlias") != "my-ui" for contact in client.get(f"/workspaces/{workspace_id(db)}/agents").json())
        assert client.put(f"/workspaces/missing/custom-agents/{profile['id']}", json=payload).status_code == 404
    finally: app.dependency_overrides.clear()


def test_legacy_sqlite_columns_and_unique_index_preserve_drafts(tmp_path):
    engine = create_engine(f"sqlite:///{(tmp_path / 'legacy.sqlite3').as_posix()}")
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE agentprofiledraft (id TEXT PRIMARY KEY, workspace_id TEXT, display_name TEXT)"))
        connection.execute(text("INSERT INTO agentprofiledraft VALUES ('legacy', 'workspace', 'Legacy')"))
    for _ in range(2):
        _ensure_sqlite_demo_schema_columns(engine); _ensure_sqlite_demo_schema_indexes(engine)
    assert {column["name"] for column in inspect(engine).get_columns("agentprofiledraft")} >= {"system_prompt", "mention_alias", "tool_policy"}
    with engine.begin() as connection:
        assert connection.execute(text("SELECT display_name, system_prompt, mention_alias, tool_policy FROM agentprofiledraft")).one() == ("Legacy", "", None, "")
        connection.execute(text("INSERT INTO agentprofiledraft (id,workspace_id,mention_alias) VALUES ('one','workspace','alias')"))
        with pytest.raises(IntegrityError): connection.execute(text("INSERT INTO agentprofiledraft (id,workspace_id,mention_alias) VALUES ('two','workspace','alias')"))
    engine.dispose()
