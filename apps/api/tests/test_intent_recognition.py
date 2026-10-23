import json
from pathlib import Path

import pytest

from app.intent_decisions import decision_from_outcome, routing_text
from app.intent_evaluation import CORPUS, evaluate_intents
from app.planning_intents import recognize_intent, parse_frontend_intent, parse_app_contract_intent


CASES = json.loads(CORPUS.read_text(encoding="utf-8"))["cases"]


@pytest.mark.parametrize("case", CASES, ids=lambda case: case["id"])
def test_labeled_intent_case(case):
    actual = recognize_intent(case["content"], roles=tuple(case.get("roles", []))).to_payload()
    assert {key: actual[key] for key in case["expected"]} == case["expected"]
    if case.get("mustNotRuleExecute"):
        assert parse_frontend_intent(case["content"], include_login_creation=True) is None
        assert parse_app_contract_intent(case["content"]) is None


def test_evaluation_counts_every_case_and_retains_mismatches(tmp_path: Path):
    report = evaluate_intents()
    assert report["total"] == len(CASES)
    assert sum(group["total"] for group in report["categories"].values()) == len(CASES)
    assert report["passed"] == len(CASES)
    assert report["unsafeRuleExecutionErrors"] == 0
    assert report["nonExecutableCases"] == sum(bool(case.get("mustNotRuleExecute")) for case in CASES)
    altered = json.loads(CORPUS.read_text(encoding="utf-8"))
    altered["cases"][0]["expected"]["target"] = "deliberately_wrong"
    path = tmp_path / "negative.json"
    path.write_text(json.dumps(altered), encoding="utf-8")
    negative = evaluate_intents(path)
    assert negative["passed"] == len(CASES) - 1
    assert negative["mismatches"][0]["id"] == CASES[0]["id"]
    assert negative["corpusSha256"] != report["corpusSha256"]


def test_long_slot_is_not_silently_truncated():
    decision = recognize_intent("把标题改成" + "字" * 61)
    assert decision.route == "clarify"
    assert parse_frontend_intent("把标题改成" + "字" * 61) is None
    assert recognize_intent("把标题改成" + "字" * 60).parameters == (("targetText", "字" * 60),)
    assert recognize_intent("change theme color to " + "a" * 61).route == "clarify"
    assert recognize_intent("change theme color to !!!").route == "clarify"
    assert recognize_intent("add a " + "a" * 61 + " input field").route == "clarify"


@pytest.mark.parametrize("content", [
    '@frontend @qa 请仅把演示应用 apps/demo/src/App.tsx 中 h1#demo-heading 的标题改成“联系人故障恢复验证”。保留联系人表单、请求流程及其他现有行为，不修改后端。QA只读审查本次实际Diff。',
    'In the demo app, change title to "Ready". Preserve the existing form and layout.',
    '把标题改成“就绪”。保留“联系人”列表。',
    'add status text "Ready". Keep the existing layout.',
    '调整文案为“你好”。保留旧按钮。',
    '把演示应用标题改成“就绪”。\n保留联系人表单及其他现有行为，不修改后端。',
    '把演示应用标题改成“就绪”。保留联系人列表，不要创建联系人。',
])
def test_quoted_copy_with_additional_constraints_requires_planner(content):
    decision = recognize_intent(content)
    assert (decision.request_type, decision.route) == ("unknown", "planner")
    assert decision.reason_codes == ("QUALIFIED_TARGET_TEXT",)
    assert decision.parameters == () and decision.missing_fields == ()
    assert parse_frontend_intent(content, include_login_creation=True) is None
    assert parse_app_contract_intent(content) is None


@pytest.mark.parametrize("value", ['“”', '“' + '字' * 61 + '”', '“未闭合'])
@pytest.mark.parametrize("tail", ['。保留联系人列表。', '。保留联系人列表，不要创建联系人。'])
def test_invalid_quoted_copy_is_still_rejected_with_additional_constraints(value, tail):
    content = '把标题改成' + value + tail
    decision = recognize_intent(content)
    assert (decision.request_type, decision.route) == ("clarification", "clarify")
    assert decision.reason_codes == ("INVALID_TARGET_TEXT",)
    assert parse_frontend_intent(content) is None
    assert parse_app_contract_intent(content) is None


def test_quoted_mentions_cannot_select_agents():
    assert "@frontend" not in routing_text('explain "@frontend"')
    assert "@backend" not in routing_text('```text\n@backend\n```')
    assert routing_text("don't change it") == "don't change it"


@pytest.mark.parametrize("content", [
    '@frontend In the demo app, change the title to "AgentHub Workspace"',
    '@frontend In the demo app，change the title to "AgentHub Workspace"',
    '@frontend For this task, change the title to "AgentHub Workspace"',
    '@frontend Please, in the demo app, change the title to "AgentHub Workspace"',
    '@frontend 在演示应用中，把标题改成“AgentHub Workspace”',
    '@frontend 针对当前演示应用,把标题改成“AgentHub Workspace”',
])
def test_comma_introduction_preserves_single_copy_change(content):
    decision = recognize_intent(content, roles=("frontend",))
    assert decision.request_type == "change"
    assert decision.route == "continue"
    assert decision.target == "demo_heading_text"
    assert decision.parameters == (("targetText", "AgentHub Workspace"),)
    intent = parse_frontend_intent(content, include_login_creation=True)
    assert intent is not None and intent.target_text == "AgentHub Workspace"


@pytest.mark.parametrize("content,request_type,route", [
    ('In the demo app, change title to Hello, add a phone input field', "unknown", "planner"),
    ('In the demo app, change title to Hello and button to Continue', "unknown", "planner"),
    ('在演示应用中，把标题改成欢迎，同时把按钮改成继续', "unknown", "planner"),
    ("In the demo app, don't change title to Hello", "no_action", "reply"),
    ('在演示应用中，不要把标题改成欢迎', "no_action", "reply"),
    ('In the demo app, explain how to change title to Hello', "explain", "reply"),
    ('In the demo app, show task status and fix the button', "unknown", "planner"),
    ('In the demo app, review the code and change title to Hello', "unknown", "planner"),
    ('In the demo app, change title to', "clarification", "clarify"),
    ('"In the demo app, change title to Hello"', "clarification", "clarify"),
    ('Do not change the demo app, add a phone input field', "unknown", "planner"),
])
def test_comma_introduction_cannot_hide_other_request_boundaries(content, request_type, route):
    decision = recognize_intent(content)
    assert (decision.request_type, decision.route) == (request_type, route)
    assert parse_frontend_intent(content, include_login_creation=True) is None


def test_quoted_action_text_does_not_add_an_action_after_introduction():
    decision = recognize_intent('In the demo app, change title to "Welcome, add a phone field"')
    assert decision.request_type == "change" and decision.route == "continue"
    assert decision.parameters == (("targetText", "Welcome, add a phone field"),)


@pytest.mark.parametrize("kind,route", [("assistant_reply", "reply"), ("clarification", "clarify"), ("refusal", "reply"), ("unsupported", "reply"), ("approval_required", "reply")])
def test_llm_outcomes_share_schema_without_invented_confidence(kind, route):
    result = decision_from_outcome(recognize_intent("fix it"), {"outcomeType": kind})
    assert result.source == "llm" and result.route == route
    assert "confidence" not in result.to_payload()


def test_llm_plan_does_not_reuse_rule_slots_for_different_tasks():
    result = decision_from_outcome(recognize_intent("把标题改成欢迎"), {
        "outcomeType": "task_plan", "planDraft": {"tasks": [{"role": "frontend"}]}})
    assert result.request_type == "change" and result.source == "llm"
    assert result.parameters == () and result.target is None
