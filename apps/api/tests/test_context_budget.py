import asyncio
import copy
import hashlib
import json

import pytest
from sqlmodel import select

from app import context_budget as budget
from app.adapters import AgentRunRequest
from app.attachment_inputs import ImageInput, PlannerPayload
from app.claude_code_adapter import ClaudeCodeAdapter
from app.instruction_adapters.shared_sections import context_section
from app.models import Artifact
from app.planner_providers import (
    ClaudeCliPlannerProvider, OpenAIResponsesPlannerProvider, OpenAICompatibleChatPlannerProvider,
    AnthropicMessagesPlannerProvider, _openai_responses_payload, _openai_compatible_chat_payload,
    _anthropic_messages_payload,
)
from app.run_engine import agent_run_request_for, execute_task_run
from app.run_supervisor import RunSupervisor
from test_native_review_artifacts import fixture, ReviewRunner
from test_planner_providers import FakePlannerHttpClient
from test_llm_planner import db as planner_db, _message


def test_unicode_boundary_and_serialized_context_preserves_content(monkeypatch):
    monkeypatch.setattr(budget, "MAX_TEXT_CHARACTERS", 4)
    text = "中文😀x"
    value = budget.audit(text, transport="test")
    assert value["textCharacters"] == 4 and value["textUtf8Bytes"] == len(text.encode())
    with pytest.raises(budget.ContextBudgetError) as exc: budget.audit(text + "y", transport="test")
    assert exc.value.error_code == "CONTEXT_BUDGET_EXCEEDED"
    context = {"fields": {"rule": {"value": "必要规则：不能修改秘密😀"}}}
    rendered = context_section({"canonicalContext": context})
    assert "必要规则" in rendered and "\\u5fc5" not in rendered
    assert json.loads(rendered.split("```json\n")[1].split("\n```")[0]) == context


def test_combined_sources_fail_without_modifying_frozen_input():
    payload = PlannerPayload({"agentSystemPrompt": "r" * 80000, "originalUserRequest": "q" * 70000,
                             "canonicalSharedContext": {"fields": {"relevantMemories": {"value": "m" * 70000}}}})
    before = copy.deepcopy(dict(payload))
    with pytest.raises(budget.ContextBudgetError) as exc: _openai_compatible_chat_payload("test", payload)
    assert exc.value.receipt["status"] == "rejected"
    assert all(len(part) < budget.MAX_TEXT_CHARACTERS for part in (payload["agentSystemPrompt"], payload["originalUserRequest"]))
    assert dict(payload) == before and "context_budget" not in json.dumps(payload)
    assert payload.context_budget == exc.value.receipt


@pytest.mark.parametrize("builder,transport", [(_openai_responses_payload, "openai_responses"), (_openai_compatible_chat_payload, "openai_compatible_chat"), (_anthropic_messages_payload, "anthropic_messages")])
def test_final_http_json_schema_image_and_byte_accounting(builder, transport):
    image = ImageInput(attachment_id="img", sha256=hashlib.sha256(b"private-image-bytes").hexdigest(), media_type="image/png", data=b"private-image-bytes")
    payload = PlannerPayload({"originalUserRequest": "中文请求", "agentSystemPrompt": "private-system-content"}, (image,))
    sent = builder("test", payload)
    receipt = payload.context_budget
    assert receipt["transport"] == transport and receipt["managedBytes"] == len(json.dumps(sent).encode())
    assert receipt["imageCount"] == 1 and receipt["imageBytes"] == len(image.data)
    assert receipt["textCharacters"] < receipt["managedBytes"]
    assert "private-system-content" not in json.dumps(receipt) and "private-image-bytes" not in json.dumps(receipt)
    if transport != "openai_compatible_chat":
        assert receipt["textCharacters"] > len(payload["originalUserRequest"]) + len(payload["agentSystemPrompt"])
    assert "contextBudget" not in json.dumps(sent)


def test_image_and_wire_limits_are_independent_of_text_limit(monkeypatch):
    image = ImageInput(attachment_id="img", sha256="a" * 64, media_type="image/png", data=b"123456")
    monkeypatch.setattr(budget, "MAX_IMAGE_BYTES", 5)
    with pytest.raises(budget.ContextBudgetError): budget.audit("small", transport="test", images=(image,))
    monkeypatch.setattr(budget, "MAX_IMAGE_BYTES", 6)
    monkeypatch.setattr(budget, "MAX_MANAGED_BYTES", 5)
    with pytest.raises(budget.ContextBudgetError): budget.audit("中文", transport="test")


@pytest.mark.parametrize("builder", [_openai_responses_payload, _anthropic_messages_payload])
def test_large_output_schema_is_included_before_http_invocation(monkeypatch, builder):
    monkeypatch.setattr("app.planner_providers._request_json_schema", lambda *a: {"description": "schema" * 40000})
    with pytest.raises(budget.ContextBudgetError) as exc: builder("test", PlannerPayload({"originalUserRequest": "short"}))
    assert exc.value.receipt["textCharacters"] > budget.MAX_TEXT_CHARACTERS


def test_json_escaping_and_repetition_count_towards_final_budget():
    text = '\\"\n' * 40000
    assert len(text) < budget.MAX_TEXT_CHARACTERS
    payload = PlannerPayload({"originalUserRequest": text})
    with pytest.raises(budget.ContextBudgetError): _openai_compatible_chat_payload("test", payload)
    assert payload["originalUserRequest"] == text


@pytest.mark.parametrize("kind", ["responses", "chat", "anthropic", "cli"])
def test_rejected_provider_input_starts_no_http_or_cli_process(kind):
    client = FakePlannerHttpClient({})
    class Runner:
        def run(self, *a, **k): pytest.fail("Rejected input invoked CLI")
    if kind == "cli": provider = ClaudeCliPlannerProvider(command_runner=Runner())
    else:
        cls = {"responses": OpenAIResponsesPlannerProvider, "chat": OpenAICompatibleChatPlannerProvider, "anthropic": AnthropicMessagesPlannerProvider}[kind]
        provider = cls(http_client=client, api_key_env="TEST_ONLY", model="test", base_url="https://test.invalid", environ={"TEST_ONLY": "fixture-key"})
    payload = PlannerPayload({"originalUserRequest": "x" * (budget.MAX_TEXT_CHARACTERS + 1)})
    result = provider.create_plan(payload)
    assert result.status == "failed" and result.error_code == "CONTEXT_BUDGET_EXCEEDED"
    assert client.url is None and payload.context_budget["status"] == "rejected"


def test_inventory_explains_source_policy_without_retaining_raw_content():
    context = {"canonicalContext": {"fields": {
        "relevantMemories": {"value": [{"layer": "rule", "contentMd": "private-rule-content"}]},
        "pinnedMessageContext": {"value": {"messages": [], "selection": {"total": 2, "included": 0, "omitted": 2}}},
        "memorySelection": {"value": {"omittedByBudget": ["omitted-id"], "omittedByExperienceLimit": []}},
    }}}
    result = budget.inventory(context)
    assert next(v for v in result if v["source"] == "projectRules")["status"] == "included"
    assert next(v for v in result if v["source"] == "pinnedMessages")["status"] == "metadata_only"
    assert next(v for v in result if v["source"] == "memorySelection")["upstreamSelection"]["omittedByBudget"] == 1
    assert "private-rule-content" not in json.dumps(result)


@pytest.mark.parametrize("over", [False, True])
def test_real_native_launch_binds_final_contract_budget_and_rejects_before_process(fixture, monkeypatch, over):
    db, run, _, source = fixture
    # This preparation is not a provider call; its snapshot remains server-owned.
    base = agent_run_request_for(db, run, adapter_type="claude_code")
    if over: monkeypatch.setattr(budget, "MAX_TEXT_CHARACTERS", len(base.instruction) + 32)
    before = source.read_bytes()
    class ObservedRunner(ReviewRunner):
        def start(self, command, cwd, *, input_text=None):
            self.prompt = json.loads(input_text)["message"]["content"][0]["text"] if input_text else command[-1]
            return super().start(command, cwd, input_text=input_text)
    runner = ObservedRunner()
    completed = asyncio.run(execute_task_run(db, run, adapter_type="claude_code", adapter=ClaudeCodeAdapter(process_runner=runner, read_only=True), supervisor=RunSupervisor()))
    metrics = json.loads(completed.metrics_json)
    receipt = metrics["contextBudget"]
    assert source.read_bytes() == before
    if over:
        assert completed.state == "failed" and completed.error_code == "CONTEXT_BUDGET_EXCEEDED"
        assert not hasattr(runner, "process") and receipt["status"] == "rejected"
        assert not db.exec(select(Artifact).where(Artifact.task_run_id == run.id)).all()
    else:
        assert completed.state == "completed" and "SERVER NATIVE REVIEW CONTRACT" in runner.prompt
        assert receipt["textCharacters"] == len(runner.prompt)
        assert receipt["textSha256"] == hashlib.sha256(runner.prompt.encode()).hexdigest()
        assert receipt["status"] == "within_limit"


def test_mcp_instruction_is_counted_after_it_is_added(monkeypatch):
    request = AgentRunRequest(taskRunId="r", sessionId="s", workspaceId="w", worktreePath="fixture", agentId="a", adapterType="codex", instruction="required rules", planContext={}, permissionProfile={}, demoMode=True, fallbackPolicy="none")
    monkeypatch.setattr(budget, "MAX_TEXT_CHARACTERS", len(request.instruction))
    assert budget.audit_agent(request)["status"] == "within_limit"
    request.instruction += "\nMCP reference tools: agenthub_docs."
    with pytest.raises(budget.ContextBudgetError): budget.audit_agent(request)


def test_planner_budget_failure_has_no_deterministic_fallback_and_keeps_diagnostic_reply(planner_db, monkeypatch):
    from app.config import Settings
    from app.models import Message, Task
    from app.planning import plan_for_message
    from app.routes.messages import message_response

    class Runner:
        def run(self, *a, **k): pytest.fail("Overflow invoked process")
    provider = ClaudeCliPlannerProvider(command_runner=Runner())
    monkeypatch.setattr("app.planning.resolve_planner_provider", lambda *a, **k: provider)
    monkeypatch.setattr("app.planning.get_settings", lambda: Settings(llm_planner_enabled=True))
    monkeypatch.setattr(budget, "MAX_TEXT_CHARACTERS", 100)
    message = _message(planner_db, "@orchestrator build a login page for the demo app")
    tasks = plan_for_message(planner_db, message, message.content_md)
    assert not tasks and not planner_db.exec(select(Task)).all()
    reply = planner_db.exec(select(Message).where(Message.parent_message_id == message.id)).one()
    assert "不会被静默截断" in reply.content_md
    response = message_response(planner_db, reply)
    assert response.context_budget["status"] == "rejected"


def test_planner_success_evidence_is_outside_serialized_request_and_preserves_snapshot(planner_db, monkeypatch):
    import subprocess
    from app.llm_planner import build_llm_planner_input, create_llm_conversation_outcome

    class Runner:
        def run(self, command, **kwargs):
            return subprocess.CompletedProcess(command, 0, stdout=json.dumps({"outcomeType": "assistant_reply", "reply": "测试回复"}), stderr="")
    message = _message(planner_db, "你好")
    prepared = build_llm_planner_input(planner_db, message)
    before = copy.deepcopy(dict(prepared))
    monkeypatch.setattr("app.llm_planner.build_llm_planner_input", lambda *a, **k: prepared)
    result = create_llm_conversation_outcome(planner_db, message, provider=ClaudeCliPlannerProvider(command_runner=Runner()))
    assert result.provider_result.context_budget["status"] == "within_limit"
    assert result.provider_result.to_metadata()["contextBudget"]["textCharacters"] > 0
    assert dict(prepared) == before and "contextBudget" not in json.dumps(prepared)
