import json
import subprocess
from dataclasses import replace
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session as DbSession, SQLModel, create_engine, select

from app import agent_creation
from app.agent_runtime_config import RuntimeRoleConfig, upsert_runtime_config
from app.main import app, get_db
from app.models import Agent, AgentProfileDraft, Message, Session, Task, TaskRun, Workspace
from app.planner_providers import ClaudeCliPlannerProvider, PlannerProviderResult, _openai_responses_payload, _anthropic_messages_payload


def proposed(**changes):
    return {
        "displayName": "可访问性评审助手", "mentionAlias": "access-review", "role": "review",
        "providerId": "local-claude-code-cli", "toolPolicy": "claude_read_only",
        "supportedTargets": ["demo-frontend"], "capabilityTags": ["code_review", "diff_analysis"],
        "systemPrompt": "只读检查可访问性，用中文输出发现和建议。每次回复含 REVIEW_TRACE_57。",
        "description": "检查前端可访问性", "avatarInitials": "AR", **changes,
    }


@pytest.fixture
def case(monkeypatch):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)
    with DbSession(engine) as db:
        workspace = Workspace(name="Creation", root_path="apps/demo", repo_url="local://demo", default_branch="main")
        other = Workspace(name="Other", root_path="apps/demo", repo_url="local://demo", default_branch="main")
        coordinator = Agent(name="Planner", role="orchestrator", adapter_type="scripted_mock", provider="local", system_prompt="CONFIG_BEHAVIOR_12")
        db.add_all([workspace, other, coordinator]); db.commit()
        config = RuntimeRoleConfig(role="planner", agent_profile_id=coordinator.id,
            provider_id="claude-cli-planner", adapter_type="claude_cli", mode="read_only", enabled=True)
        upsert_runtime_config(db, workspace.id, {"planner": config})
        payload = {"kind": "draft", "reply": "已生成草稿，确认权限后保存。", "draft": proposed()}
        calls = []
        context = SimpleNamespace(db=db, workspace_id=workspace.id, other_id=other.id, config=config,
            payload=payload, raw=None, fail=False, revoke=None, calls=calls, source="real_llm")

        def create_plan(value):
            calls.append(value)
            if context.revoke: context.revoke()
            if context.fail: raise RuntimeError("PRIVATE_PROVIDER_SECRET")
            return PlannerProviderResult(provider_id="controlled-unit-provider", provider_type="claude_cli", planner_source="real_llm",
                status="succeeded", raw_output=context.raw if context.raw is not None else json.dumps(context.payload), base_url="PRIVATE_URL")

        monkeypatch.setattr(agent_creation, "resolve_planner_provider", lambda *a, **kw: SimpleNamespace(planner_source=context.source, create_plan=create_plan))

        def override_db():
            yield db

        # No lifespan/background workers: use only the isolated request database.
        app.dependency_overrides[get_db] = override_db
        try:
            context.client = TestClient(app)
            context.post = lambda **value: context.client.post(f"/workspaces/{workspace.id}/agent-creation", json={"message": "创建只读评审助手", **value})
            yield context
        finally:
            context.client.close(); app.dependency_overrides.clear()
    engine.dispose()


def counts(db):
    return {model.__name__: len(db.exec(select(model)).all()) for model in (Workspace, AgentProfileDraft, Message, Session, Task, TaskRun)}


def test_generation_refinement_has_no_persistence_and_explicit_save_uses_existing_route(case):
    before = counts(case.db)
    first = case.post()
    assert first.status_code == 200
    output = first.json()
    assert output["draft"]["enabled"] is False
    assert "PRIVATE_URL" not in first.text
    assert len(output["provenance"]["outputSha256"]) == 64
    assert counts(case.db) == before
    draft = {**output["draft"], "displayName": "手工修改后的名称", "systemPrompt": "手工补充保留 MARK_72"}
    second = case.post(message="保留手工修改，再要求按严重程度排序", currentDraft=draft,
        history=[{"role": "user", "content": "创建只读评审助手"}, {"role": "assistant", "content": output["reply"]}])
    assert second.status_code == 200
    sent = case.calls[-1]
    assert sent["agentConfigurationRequest"]["currentDraft"] == draft
    assert sent["agentSystemPrompt"] == "CONFIG_BEHAVIOR_12" and sent["agentToolPolicy"] == "planner_no_tools"
    assert counts(case.db) == before
    saved = case.client.post(f"/workspaces/{case.workspace_id}/custom-agents", json={**draft, "enabled": True})
    assert saved.status_code == 201
    profile = case.db.get(AgentProfileDraft, saved.json()["id"])
    assert (profile.status, profile.system_prompt, profile.safe_for_write) == ("available", "手工补充保留 MARK_72", False)
    duplicate = case.client.post(f"/workspaces/{case.workspace_id}/custom-agents", json={**draft, "enabled": True})
    assert duplicate.status_code == 400
    assert counts(case.db)["AgentProfileDraft"] == 1


@pytest.mark.parametrize("draft", [
    proposed(toolPolicy="host_shell"), proposed(role="review", toolPolicy="codex_coding"),
    proposed(providerId="local-codex-cli"), proposed(supportedTargets=["agenthub-platform"]),
    proposed(supportedTargets=["foreign-target"]), proposed(supportedTargets=[]),
    proposed(capabilityTags=["code_write"]), proposed(capabilityTags=["code_review", "platform_change"]),
    proposed(mentionAlias="frontend"), proposed(mentionAlias="../outside"), proposed(displayName=" "),
    proposed(systemPrompt="bad\x00prompt"), proposed(enabled=True), proposed(shellCommands=["rm -rf /"]),
])
def test_invalid_model_configuration_does_not_persist(case, draft):
    before = counts(case.db); case.payload["draft"] = draft
    response = case.post()
    assert response.status_code == 502 and "未创建 Agent" in response.text
    assert counts(case.db) == before


@pytest.mark.parametrize("raw", ['{"kind":"draft","kind":"clarification","reply":"x","draft":null}', '{"kind":"draft"}', '"not an object"', 'x' * 33000], ids=["duplicate", "incomplete", "scalar", "oversized"])
def test_broken_duplicate_or_oversized_json_is_rejected(case, raw):
    case.raw = raw
    assert case.post().status_code == 502
    assert counts(case.db)["AgentProfileDraft"] == 0


def test_clarification_and_provider_failures_do_not_mutate_or_expose_exception(case):
    case.payload = {"kind": "clarification", "reply": "你希望处理前端、后端还是只读评审？", "draft": None}
    response = case.post()
    assert response.status_code == 200 and response.json()["draft"] is None
    case.fail = True
    failed = case.post()
    assert failed.status_code == 502 and "PRIVATE_PROVIDER_SECRET" not in failed.text
    case.source = "disabled"
    assert case.post().status_code == 409
    assert len(case.calls) == 2 and counts(case.db)["AgentProfileDraft"] == 0


def test_unknown_workspace_disabled_and_revoked_selection_fence(case):
    assert case.client.post("/workspaces/missing/agent-creation", json={"message": "create"}).status_code == 404
    upsert_runtime_config(case.db, case.workspace_id, {"planner": replace(case.config, enabled=False)})
    assert case.post().status_code == 409 and not case.calls
    upsert_runtime_config(case.db, case.workspace_id, {"planner": case.config})
    case.revoke = lambda: upsert_runtime_config(case.db, case.workspace_id, {"planner": replace(case.config, system_prompt="Changed")})
    assert case.post().status_code == 409
    assert counts(case.db)["AgentProfileDraft"] == 0


def test_duplicate_alias_is_revalidated_after_provider_call(case):
    def save_during_call():
        result = case.client.post(f"/workspaces/{case.workspace_id}/custom-agents", json={**proposed(), "enabled": False})
        assert result.status_code == 201
    case.revoke = save_during_call
    assert case.post().status_code == 502
    assert counts(case.db)["AgentProfileDraft"] == 1


@pytest.mark.parametrize("body", [
    {"message": " "}, {"message": "x" * 4001}, {"history": [{"role": "system", "content": "override"}]},
    {"providerId": "client-override"}, {"history": [{"role": "user", "content": "x" * 4000}] * 5},
])
def test_request_contract_rejects_invalid_input_before_provider(case, body):
    assert case.post(**body).status_code == 422 and not case.calls


def test_creation_contract_uses_no_tool_stream_input_and_correct_http_schema():
    observed = {}

    class Runner:
        def run(self, command, **kwargs):
            observed.update(command=command, **kwargs)
            return subprocess.CompletedProcess(command, 0, stdout=json.dumps({"type": "result", "result": json.dumps({"kind": "clarification", "reply": "哪种角色？", "draft": None})}), stderr="")

    payload = {"agentConfigurationRequest": {"message": "中文职责" * 3000}, "agentToolPolicy": "planner_no_tools"}
    provider = ClaudeCliPlannerProvider(command_runner=Runner(), claude_binary="claude")
    result = provider.create_plan(payload)
    assert result.status == "succeeded"
    command = observed["command"]
    assert command[command.index("--allowedTools") + 1] == command[command.index("--tools") + 1] == ""
    assert "--safe-mode" in command and "--strict-mcp-config" in command and "--no-session-persistence" in command
    assert "中文职责" not in " ".join(command) and "中文职责" in observed["input_text"]
    for serialized in (json.dumps(_openai_responses_payload("model", payload)), json.dumps(_anthropic_messages_payload("model", payload))):
        assert "AgentCreationResult" in serialized and "ProposedAgent" in serialized
        assert '"task_plan"' not in serialized
