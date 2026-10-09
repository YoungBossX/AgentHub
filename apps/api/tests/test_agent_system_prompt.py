from dataclasses import replace
import hashlib

import pytest
from pydantic import ValidationError
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, Session, create_engine

from app.agent_instructions import capture_agent_instruction, bound_agent_instruction
from app.agent_runtime_config import (
    AgentRuntimeConfigError, default_runtime_config, get_effective_runtime_config,
    upsert_runtime_config,
)
from app.models import Agent, Workspace
from app.schemas import RuntimeRoleConfigRequest
from app.routes.agent_settings import runtime_role_config_from_request, runtime_role_config_response
from app.planner_providers import (
    ClaudeCliPlannerProvider, _anthropic_messages_payload,
    _openai_compatible_chat_payload, _openai_responses_payload,
)


@pytest.fixture
def db():
    engine = create_engine("sqlite://", poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    engine.dispose()


def test_prompt_round_trip_reload_and_workspace_isolation(db):
    first, second = [
        Workspace(
            name=name, repo_url="local://apps/demo", root_path="apps/demo",
            default_branch="main",
        )
        for name in ("First", "Second")
    ]
    agent = Agent(
        name="Frontend", role="frontend", adapter_type="codex", provider="local",
        system_prompt="Default behavior",
    )
    db.add_all([first, second, agent])
    db.commit()
    text = "请使用简洁中文。\nPreserve accessibility."
    request = RuntimeRoleConfigRequest(enabled=True, systemPrompt=text)
    role = runtime_role_config_from_request("frontend", request)
    upsert_runtime_config(db, first.id, {"frontend": role})
    db.expire_all()
    reloaded = get_effective_runtime_config(db, first.id).roles["frontend"]
    assert runtime_role_config_response(reloaded).model_dump(by_alias=True)["systemPrompt"] == text
    assert get_effective_runtime_config(db, second.id).roles["frontend"].system_prompt is None
    binding = capture_agent_instruction(db, workspace_id=first.id, agent=agent, role="frontend")
    assert binding["text"] == text
    assert binding["sha256"] == hashlib.sha256(text.encode()).hexdigest()
    assert capture_agent_instruction(db, workspace_id=second.id, agent=agent, role="frontend")["text"] == agent.system_prompt


@pytest.mark.parametrize("enabled,prompt", [(False, "Ignored override"), (True, " \n "), (True, None)])
def test_disabled_and_blank_prompt_inherit_agent_default(db, enabled, prompt):
    agent = Agent(name="Frontend", role="frontend", system_prompt="Default behavior")
    role = replace(default_runtime_config("workspace").roles["frontend"], enabled=enabled, system_prompt=prompt)
    upsert_runtime_config(db, "workspace", {"frontend": role})
    assert capture_agent_instruction(db, workspace_id="workspace", agent=agent, role="frontend")["text"] == "Default behavior"


@pytest.mark.parametrize("text", ["x" * 8001, "bad\x00prompt", 123])
def test_invalid_prompt_is_rejected(db, text):
    if text != "bad\x00prompt":
        with pytest.raises(ValidationError):
            RuntimeRoleConfigRequest(systemPrompt=text)
    role = replace(default_runtime_config(None).roles["frontend"], system_prompt=text)
    with pytest.raises(AgentRuntimeConfigError, match="systemPrompt"):
        upsert_runtime_config(db, "workspace", {"frontend": role})
    assert get_effective_runtime_config(db, "workspace").config_source == "default"


@pytest.mark.parametrize("field,value", [("workspaceId", "other"), ("agentId", "other"), ("text", "tampered")])
def test_binding_rejects_corrupt_identity_and_text(db, field, value):
    agent = Agent(name="Frontend", role="frontend", system_prompt="Default behavior")
    binding = capture_agent_instruction(db, workspace_id="workspace", agent=agent, role="frontend")
    binding[field] = value
    with pytest.raises(ValueError, match="binding"):
        bound_agent_instruction(binding, workspace_id="workspace", agent_id=agent.id)


def test_all_planner_transports_include_prompt_and_mandatory_contract():
    payload = {"agentSystemPrompt": "Explain plans in Chinese.", "originalUserRequest": "Build a page"}
    prompts = [
        _openai_responses_payload("model", payload)["input"][0]["content"][0]["text"],
        _openai_compatible_chat_payload("model", payload)["messages"][0]["content"],
        _anthropic_messages_payload("model", payload)["system"],
        "\n".join(ClaudeCliPlannerProvider(claude_binary="claude")._build_command(payload)),
    ]
    for prompt in prompts:
        assert "Explain plans in Chinese." in prompt
        assert "Return ONLY one JSON object" in prompt
        assert "Never execute code or call agents directly" in prompt
        assert prompt.index("Explain plans in Chinese.") < prompt.index("Return ONLY")
