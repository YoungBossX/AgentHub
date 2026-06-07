import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from sqlmodel import Session as DbSession
from sqlmodel import select

from app.config import get_settings
from app.llm_planner import (
    LLMPlannerError,
    create_llm_conversation_outcome,
    create_llm_plan_tasks_from_outcome,
    llm_planner_fallback_metadata,
)
from app.memory_snapshots import (
    ensure_session_memory_snapshot,
    memory_snapshot_metadata,
)
from app.memory_write_policy import maybe_create_explicit_user_memory
from app.agent_runtime_config import resolve_runtime_role_config
from app.models import Agent, Message, Task
from app.models import Session as AgentHubSession
from app.plan_validator import PlanValidationError, validate_task_graph
from app.planner_service import build_plan_draft
from app.planner_providers import PlannerProviderError, resolve_planner_provider
from app.repositories import create_session_message, list_session_tasks
from app.target_registry import (
    AGENTHUB_PLATFORM_TARGET_ID,
    DEMO_BACKEND_TARGET_ID,
    DEMO_FRONTEND_TARGET_ID,
    TargetProject,
    TargetRegistryError,
    get_related_backend_target,
    get_target,
    get_target_for_workspace,
)
from app.task_graph_builder import TaskGraphTaskSpec, task_graph_metadata

SUPPORTED_MENTION_ROLES = {"orchestrator", "frontend", "backend", "qa", "review"}
MENTION_AGENT_ROLE = {"review": "qa"}
MENTION_PATTERN = re.compile(r"@([A-Za-z][A-Za-z0-9_-]*)")
CHANGE_TO_PATTERN = re.compile(
    r"(?:change\s+(?:the\s+)?(?:primary\s+)?(?:login\s+page\s+)?"
    r"(?P<english_target>button|button text|primary button text|title|heading)"
    r"(?:\s+(?:text|copy))?\s+to\s+|"
    r"(?:把|再把)?(?:登录页)?(?P<chinese_target>按钮文案|按钮|标题|标题文案)"
    r"改成\s+)"
    r"(?P<value>.+)",
    re.IGNORECASE,
)
THEME_COLOR_PATTERN = re.compile(
    r"(?:change\s+(?:the\s+)?(?:theme|accent|primary|brand)\s+color\s+to\s+|"
    r"(?:把|将)?(?:主题色|主色|强调色|品牌色)改成\s+)"
    r"(?P<value>#[0-9a-fA-F]{3,8}|[A-Za-z][A-Za-z0-9\s-]{0,40})",
    re.IGNORECASE,
)
INPUT_FIELD_PATTERN = re.compile(
    r"(?:add\s+(?:a\s+)?(?P<english_label>[A-Za-z][A-Za-z0-9\s-]{1,40})\s+"
    r"(?:input\s+)?field|"
    r"(?:添加|新增)(?:一个)?(?P<chinese_label>[\u4e00-\u9fffA-Za-z0-9\s-]{1,40})(?:输入框|字段))",
    re.IGNORECASE,
)
STATUS_TEXT_PATTERN = re.compile(
    r"(?:add\s+(?:a\s+)?(?:status|help|helper)\s+(?:text|copy|message)\s*(?:[:：]|to)?\s*|"
    r"(?:添加|新增)(?:状态|帮助|提示)(?:文本|文案)?\s*)"
    r"(?P<value>.+)",
    re.IGNORECASE,
)
LAYOUT_COPY_PATTERN = re.compile(
    r"(?:adjust\s+(?:the\s+)?(?:layout\s+)?copy\s+to\s+|"
    r"(?:update|change)\s+(?:the\s+)?lede\s+copy\s+to\s+|"
    r"(?:调整|更新)(?:布局)?文案(?:为|成)\s*)"
    r"(?P<value>.+)",
    re.IGNORECASE,
)


class MentionParseError(ValueError):
    pass


@dataclass(frozen=True)
class ParsedMentions:
    roles: list[str]


@dataclass(frozen=True)
class FollowupChange:
    target: str
    target_text: str


@dataclass(frozen=True)
class FrontendIntent:
    intent: str
    target: str
    target_text: str
    files: list[str]
    summary: str


@dataclass(frozen=True)
class AppContractIntent:
    app_type: str
    app_name: str
    summary: str


TaskSpec = TaskGraphTaskSpec


def parse_mentions(db: DbSession, content: str) -> ParsedMentions:
    roles: list[str] = []
    for raw_role in MENTION_PATTERN.findall(content):
        role = raw_role.lower()
        mention = f"@{raw_role}"
        if role not in SUPPORTED_MENTION_ROLES:
            raise MentionParseError(f"Unknown mention {mention}. Supported mentions are @orchestrator, @frontend, @backend, @qa, and @review.")

        agent_role = MENTION_AGENT_ROLE.get(role, role)
        agent = db.exec(select(Agent).where(Agent.role == agent_role)).first()
        if agent is None or not agent.enabled:
            raise MentionParseError(f"Mention {mention} is disabled or unavailable.")

        if role not in roles:
            roles.append(role)

    return ParsedMentions(roles=roles)


def _planner_runtime_resolution(db: DbSession, message: Message):
    session = db.get(AgentHubSession, message.session_id)
    if session is None:
        return None
    return resolve_runtime_role_config(db, session.workspace_id, "planner")


def _attach_planner_runtime_evidence(
    db: DbSession,
    tasks: list[Task],
    runtime_resolution,
) -> None:
    if not tasks:
        return
    session = db.get(AgentHubSession, tasks[0].session_id)
    memory_snapshot = (
        ensure_session_memory_snapshot(db, session)
        if session is not None
        else None
    )
    runtime_metadata = (
        runtime_resolution.to_metadata()
        if runtime_resolution is not None
        else None
    )
    snapshot_metadata = memory_snapshot_metadata(memory_snapshot)
    for task in tasks:
        try:
            plan = json.loads(task.plan_json)
        except json.JSONDecodeError:
            plan = {}
        if not isinstance(plan, dict):
            plan = {}
        planner_evidence = plan.get("plannerEvidence")
        if not isinstance(planner_evidence, dict):
            planner_evidence = {}
        if runtime_metadata is not None:
            planner_evidence["runtimeConfigResolution"] = runtime_metadata
            plan["runtimeConfigResolution"] = runtime_metadata
        if snapshot_metadata:
            planner_evidence["memorySnapshot"] = snapshot_metadata
            plan["memorySnapshot"] = snapshot_metadata
        plan["plannerEvidence"] = planner_evidence
        task.plan_json = json.dumps(plan, separators=(",", ":"))
        db.add(task)
    db.commit()
    for task in tasks:
        db.refresh(task)


def plan_for_message(
    db: DbSession,
    message: Message,
    content: str,
) -> list[Task]:
    parsed = parse_mentions(db, content)
    existing_tasks = list_session_tasks(db, message.session_id)
    routed_role = parsed.roles[0] if parsed.roles else "orchestrator"
    if routed_role == "orchestrator":
        memory_write = _maybe_handle_explicit_memory_write(db, message, content)
        if memory_write:
            return []
    llm_fallback = None
    if routed_role == "orchestrator":
        try:
            planner_runtime = _planner_runtime_resolution(db, message)
            planner_provider = resolve_planner_provider(
                get_settings(),
                provider_id=(
                    planner_runtime.role_config.provider_id
                    if planner_runtime is not None
                    else None
                ),
                adapter_type=(
                    planner_runtime.role_config.adapter_type
                    if planner_runtime is not None
                    else None
                ),
                provider_preset_id=(
                    planner_runtime.role_config.provider_preset_id
                    if planner_runtime is not None
                    else None
                ),
                model=(
                    planner_runtime.role_config.model
                    if planner_runtime is not None
                    else None
                ),
                base_url=(
                    planner_runtime.role_config.base_url
                    if planner_runtime is not None
                    else None
                ),
                api_key_env=(
                    planner_runtime.role_config.api_key_env
                    if planner_runtime is not None
                    else None
                ),
                timeout_seconds=(
                    planner_runtime.role_config.timeout_seconds
                    if planner_runtime is not None
                    else None
                ),
            )
            if planner_provider.planner_source != "disabled":
                conversation = None
                try:
                    conversation = create_llm_conversation_outcome(
                        db,
                        message,
                        provider=planner_provider,
                    )
                    if conversation.outcome["outcomeType"] != "task_plan":
                        fallback_tasks = _fallback_tasks_for_non_task_llm_outcome(
                            db,
                            message,
                            content,
                            conversation.outcome,
                            planner_provider,
                        )
                        if fallback_tasks:
                            _attach_planner_runtime_evidence(
                                db,
                                fallback_tasks,
                                planner_runtime,
                            )
                            return fallback_tasks
                        if _should_request_target_setup_for_non_task_llm_outcome(
                            db,
                            message,
                            content,
                            conversation.outcome,
                        ):
                            _create_orchestrator_boundary_message(
                                db,
                                message,
                                _unsupported_or_unregistered_target_reply(),
                            )
                            return []
                        _create_conversation_outcome_message(
                            db,
                            message,
                            conversation.outcome,
                        )
                        return []
                    llm_outcome = create_llm_plan_tasks_from_outcome(
                        db,
                        message,
                        conversation=conversation,
                    )
                    llm_tasks = llm_outcome.tasks
                    if llm_tasks:
                        _attach_planner_runtime_evidence(
                            db,
                            llm_tasks,
                            planner_runtime,
                        )
                        return llm_tasks
                except LLMPlannerError as exc:
                    outcome = conversation.outcome if conversation is not None else {}
                    is_task_plan_validation_failure = outcome.get("outcomeType") == "task_plan"
                    llm_fallback = llm_planner_fallback_metadata(
                        (
                            "task_plan_validation_failed"
                            if is_task_plan_validation_failure
                            else "provider_failed"
                        ),
                        provider_result=(
                            conversation.provider_result
                            if conversation is not None
                            else None
                        ),
                        provider=None if conversation is not None else planner_provider,
                    )
                    if is_task_plan_validation_failure:
                        llm_fallback["originalOutcomeType"] = "task_plan"
                        llm_fallback["validationResult"] = "failed"
                        llm_fallback["errorCode"] = "LLM_TASK_PLAN_VALIDATION_FAILED"
                    else:
                        llm_fallback["errorCode"] = "LLM_PLANNER_FAILED"
                    llm_fallback["errorSummary"] = _safe_planner_error_summary(str(exc))
            else:
                llm_fallback = llm_planner_fallback_metadata(
                    "provider_unavailable" if get_settings().llm_planner_enabled else "disabled",
                    provider=planner_provider,
                )
        except PlannerProviderError as exc:
            llm_fallback = {
                "attemptedPlanner": "llm_v1",
                "reason": "invalid_provider",
                "providerId": exc.provider_id or "unknown",
                "plannerSource": "fallback",
                "status": "failed",
                "errorCode": exc.code,
                "errorSummary": exc.summary,
            }

    if routed_role in {"frontend", "backend", "qa", "review"}:
        return _create_direct_assignment_tasks(
            db,
            message,
            routed_role,
            existing_tasks=existing_tasks,
        )

    if routed_role == "orchestrator" and llm_fallback is not None and _is_pure_chat_request(content):
        _create_orchestrator_boundary_message(
            db,
            message,
            _friendly_chat_fallback_reply(llm_fallback),
        )
        return []

    contract_intent = parse_app_contract_intent(content)
    bounded_intent = parse_frontend_intent(content)
    if contract_intent is not None and not existing_tasks:
        return _create_contract_first_plan(
            db,
            message,
            contract_intent,
            llm_fallback=llm_fallback,
        )
    if contract_intent is not None and existing_tasks:
        return []

    if _is_explicit_platform_mode_request(content) and not existing_tasks:
        return _create_platform_maintenance_task(
            db,
            message,
            llm_fallback=llm_fallback,
        )

    if bounded_intent is not None and existing_tasks:
        return _create_dynamic_frontend_tasks(
            db,
            message,
            bounded_intent,
            existing_tasks=existing_tasks,
            auto_start=True,
        )

    if existing_tasks:
        return []

    if "login page" not in content.lower() or "demo app" not in content.lower():
        if bounded_intent is None:
            active_frontend_target = _active_external_target_for_role(db, message, "frontend")
            if active_frontend_target is not None and _is_safe_external_frontend_request(content):
                return _create_orchestrator_external_frontend_task(
                    db,
                    message,
                    active_frontend_target,
                    llm_fallback=llm_fallback,
                )
            if _is_safe_demo_frontend_request(content):
                return _create_orchestrator_demo_frontend_task(
                    db,
                    message,
                    llm_fallback=llm_fallback,
                )
            _create_orchestrator_boundary_message(
                db,
                message,
                _unsupported_or_unregistered_target_reply(llm_fallback),
            )
            return []
        return _create_dynamic_frontend_tasks(
            db,
            message,
            bounded_intent,
            auto_start=True,
            llm_fallback=llm_fallback,
        )

    return _create_login_page_plan(db, message, llm_fallback=llm_fallback)


def _create_login_page_plan(
    db: DbSession,
    message: Message,
    *,
    llm_fallback: Optional[dict] = None,
) -> list[Task]:
    agents = {
        agent.role: agent
        for agent in db.exec(select(Agent).where(Agent.role.in_(SUPPORTED_MENTION_ROLES))).all()
        if agent.enabled
    }
    required_roles = ["orchestrator", "frontend", "qa"]
    missing = [role for role in required_roles if role not in agents]
    if missing:
        raise MentionParseError(f"Planning requires enabled agents: {', '.join(missing)}.")

    task_specs = [
        TaskSpec(
            title="Plan the login page change",
            intent_type="planning",
            role="orchestrator",
            priority=0,
            plan={
                "target": "login_page",
                "summary": "Confirm the demo login-page scope and execution order.",
                "parallelGroup": None,
            },
            expected_artifact_types=["plan"],
        ),
        TaskSpec(
            title="Build the Vite React login page",
            intent_type="frontend_change",
            role="frontend",
            priority=1,
            plan={
                "target": "login_page",
                "files": ["apps/demo/src/App.tsx", "apps/demo/src/styles.css"],
                "parallelGroup": None,
            },
            expected_artifact_types=["diff", "review"],
        ),
        TaskSpec(
            title="Review the login page demo path",
            intent_type="qa_review",
            role="qa",
            priority=2,
            plan={
                "target": "login_page",
                "checks": ["page renders", "button target remains deterministic"],
                "parallelGroup": None,
            },
            expected_artifact_types=["review"],
        ),
    ]
    _validate_task_graph(task_specs)

    tasks: list[Task] = []
    graph = _graph_metadata(
        goal=message.content_md,
        intent="login_page",
        planner="deterministic_login_v1",
        task_specs=task_specs,
    )
    plan_draft = _plan_draft_metadata(
        goal=message.content_md,
        intent="login_page",
        planner="deterministic_login_v1",
        task_specs=task_specs,
    )
    for index, spec in enumerate(task_specs):
        depends_on = [tasks[index - 1].id] if index > 0 else []
        plan = {
            **spec.plan,
            "planner": "deterministic_login_v1",
            "goal": message.content_md,
            "expectedArtifactTypes": spec.expected_artifact_types,
            "taskGraph": graph,
            "planDraft": plan_draft,
            **_fallback_plan_metadata(llm_fallback),
        }
        task = Task(
            session_id=message.session_id,
            created_by_message_id=message.id,
            title=spec.title,
            intent_type=spec.intent_type,
            status="pending",
            priority=spec.priority,
            plan_json=json.dumps(plan, separators=(",", ":")),
            depends_on_task_ids=json.dumps(depends_on, separators=(",", ":")),
            assigned_agent_id=agents[spec.role].id,
        )
        db.add(task)
        db.commit()
        db.refresh(task)
        tasks.append(task)

    summary = Message(
        session_id=message.session_id,
        sender_type="orchestrator",
        sender_id=agents["orchestrator"].id,
        content_md="I created a 3-step plan for the demo login page.",
        message_kind="plan",
        parent_message_id=message.id,
    )
    create_session_message(db, _session_for_message(db, message), summary)
    return tasks


def parse_frontend_intent(content: str) -> Optional[FrontendIntent]:
    followup = parse_followup_change(content)
    if followup is not None:
        target_label = (
            "primary button text"
            if followup.target == "primary_action_button_text"
            else "demo heading text"
        )
        return FrontendIntent(
            intent="copy_change",
            target=followup.target,
            target_text=followup.target_text,
            files=["apps/demo/src/App.tsx"],
            summary=f"Change only the {target_label}.",
        )

    normalized = MENTION_PATTERN.sub("", content).strip()

    color_match = THEME_COLOR_PATTERN.search(normalized)
    if color_match is not None:
        value = _clean_target_text(color_match.group("value"))
        if value:
            return FrontendIntent(
                intent="theme_accent_color_change",
                target="theme_accent_color",
                target_text=value,
                files=["apps/demo/src/styles.css"],
                summary="Change only the demo app accent color tokens.",
            )

    input_match = INPUT_FIELD_PATTERN.search(normalized)
    if input_match is not None:
        label = _clean_target_text(
            input_match.group("english_label") or input_match.group("chinese_label") or ""
        )
        if label:
            return FrontendIntent(
                intent="simple_input_field_addition",
                target="simple_input_field",
                target_text=label,
                files=["apps/demo/src/App.tsx"],
                summary="Add one simple input field inside the demo mutation area.",
            )

    status_match = STATUS_TEXT_PATTERN.search(normalized)
    if status_match is not None:
        value = _clean_target_text(status_match.group("value"))
        if value:
            return FrontendIntent(
                intent="status_help_text_addition",
                target="status_help_text",
                target_text=value,
                files=["apps/demo/src/App.tsx"],
                summary="Add one short status or help text line to the demo app.",
            )

    layout_match = LAYOUT_COPY_PATTERN.search(normalized)
    if layout_match is not None:
        value = _clean_target_text(layout_match.group("value"))
        if value:
            return FrontendIntent(
                intent="layout_copy_adjustment",
                target="layout_copy",
                target_text=value,
                files=["apps/demo/src/App.tsx"],
                summary="Adjust a small layout copy block without broader layout changes.",
            )

    return None


def parse_app_contract_intent(content: str) -> Optional[AppContractIntent]:
    normalized = MENTION_PATTERN.sub("", content).lower()
    if _is_unsupported_broad_request(normalized):
        return None
    if any(signal in normalized for signal in ["mini crm", "crm", "联系人", "contacts"]):
        return AppContractIntent(
            app_type="mini_crm_contacts",
            app_name="Mini CRM Contacts",
            summary="Mini CRM contacts app with contacts and notes.",
        )
    if any(signal in normalized for signal in ["todo", "to-do", "待办", "任务清单"]):
        return AppContractIntent(
            app_type="todo",
            app_name="Todo App",
            summary="Todo app with items, completion state, and simple filtering.",
        )
    if any(signal in normalized for signal in ["notes", "note app", "笔记", "备注"]):
        return AppContractIntent(
            app_type="notes",
            app_name="Notes App",
            summary="Notes app with note title, body, and timestamps.",
        )
    return None


def parse_followup_change(content: str) -> Optional[FollowupChange]:
    normalized = MENTION_PATTERN.sub("", content).strip()
    match = CHANGE_TO_PATTERN.search(normalized)
    if match is None:
        return None

    raw_target = (match.group("english_target") or match.group("chinese_target") or "").lower()
    target_text = _clean_target_text(match.group("value"))
    if not target_text:
        return None

    if "title" in raw_target or "heading" in raw_target or "标题" in raw_target:
        return FollowupChange(target="demo_heading_text", target_text=target_text)
    return FollowupChange(target="primary_action_button_text", target_text=target_text)


def _clean_target_text(value: str) -> str:
    cleaned = value.strip().strip("\"'“”‘’")
    cleaned = re.sub(r"[。.!?]+$", "", cleaned).strip()
    return cleaned[:60]


def _create_contract_first_plan(
    db: DbSession,
    message: Message,
    intent: AppContractIntent,
    *,
    llm_fallback: Optional[dict] = None,
) -> list[Task]:
    agents = {
        agent.role: agent
        for agent in db.exec(select(Agent).where(Agent.role.in_({"orchestrator", "backend", "frontend", "qa"}))).all()
        if agent.enabled
    }
    missing = [
        role
        for role in ["orchestrator", "backend", "frontend", "qa"]
        if role not in agents
    ]
    if missing:
        raise MentionParseError(f"Contract-first planning requires enabled agents: {', '.join(missing)}.")
    if not _demo_backend_target_exists():
        _create_orchestrator_boundary_message(
            db,
            message,
            "Contract-first planning needs the safe demo backend target apps/demo-api first. I did not create unrestricted backend tasks.",
        )
        return []

    frontend_target = get_target(DEMO_FRONTEND_TARGET_ID)
    backend_target = get_related_backend_target(frontend_target.target_id)
    frontend_allowed_path = _primary_allowed_path(frontend_target)
    backend_allowed_path = _primary_allowed_path(backend_target)
    contract = _app_contract_for(
        message.content_md,
        intent,
        frontend_target=frontend_target,
        backend_target=backend_target,
    )
    task_specs = [
        TaskSpec(
            title=f"Create {intent.app_name} contract",
            intent_type="planning",
            role="orchestrator",
            priority=0,
            plan={
                "target": "app_contract",
                "frontendTargetId": frontend_target.target_id,
                "backendTargetId": backend_target.target_id,
                "summary": intent.summary,
                "parallelGroup": None,
            },
            expected_artifact_types=["plan"],
        ),
        TaskSpec(
            title=f"Implement {intent.app_name} backend scaffold",
            intent_type="backend_change",
            role="backend",
            priority=1,
            plan={
                "target": "demo_backend_contract",
                "targetId": backend_target.target_id,
                "backendTargetId": backend_target.target_id,
                "frontendTargetId": frontend_target.target_id,
                "safeTarget": backend_allowed_path,
                "files": [
                    f"{backend_target.root}/app/main.py",
                    f"{backend_target.root}/tests/test_contacts.py",
                ],
                "parallelGroup": None,
            },
            expected_artifact_types=["diff", "review"],
        ),
        TaskSpec(
            title=f"Implement {intent.app_name} frontend scaffold",
            intent_type="frontend_change",
            role="frontend",
            priority=2,
            plan={
                "target": "demo_frontend_contract",
                "targetId": frontend_target.target_id,
                "frontendTargetId": frontend_target.target_id,
                "backendTargetId": backend_target.target_id,
                "safeTarget": frontend_allowed_path,
                "frontendTarget": frontend_target.root,
                "files": [
                    f"{frontend_allowed_path}/App.tsx",
                    f"{frontend_allowed_path}/styles.css",
                ],
                "parallelGroup": None,
            },
            expected_artifact_types=["diff", "review"],
        ),
        TaskSpec(
            title=f"Review {intent.app_name} contract implementation",
            intent_type="review",
            role="qa",
            priority=3,
            plan={
                "target": "contract_review",
                "targetId": frontend_target.target_id,
                "frontendTargetId": frontend_target.target_id,
                "backendTargetId": backend_target.target_id,
                "checks": [
                    "backend and frontend reference the same contract",
                    "apps/api remains untouched",
                    "preview remains eligible",
                ],
                "parallelGroup": None,
            },
            expected_artifact_types=["review"],
        ),
    ]
    _validate_task_graph(task_specs)
    graph = _graph_metadata(
        goal=message.content_md,
        intent=intent.app_type,
        planner="contract_first_v1",
        task_specs=task_specs,
    )
    plan_draft = _plan_draft_metadata(
        goal=message.content_md,
        intent=intent.app_type,
        planner="contract_first_v1",
        task_specs=task_specs,
    )
    contract["taskGraph"] = graph

    tasks: list[Task] = []
    for index, spec in enumerate(task_specs):
        depends_on = [tasks[index - 1].id] if index > 0 else []
        plan = {
            **spec.plan,
            "planner": "contract_first_v1",
            "goal": message.content_md,
            "originalRequest": message.content_md,
            "intent": intent.app_type,
            "appContract": contract,
            "contractId": contract["contractId"],
            "expectedArtifactTypes": spec.expected_artifact_types,
            "taskGraph": graph,
            "planDraft": plan_draft,
            "autoStart": spec.intent_type in {"backend_change", "frontend_change"},
            **_fallback_plan_metadata(llm_fallback),
        }
        task = Task(
            session_id=message.session_id,
            created_by_message_id=message.id,
            title=spec.title,
            intent_type=spec.intent_type,
            status="pending",
            priority=spec.priority,
            plan_json=json.dumps(plan, separators=(",", ":")),
            depends_on_task_ids=json.dumps(depends_on, separators=(",", ":")),
            assigned_agent_id=agents[spec.role].id,
        )
        db.add(task)
        db.commit()
        db.refresh(task)
        tasks.append(task)

    summary = Message(
        session_id=message.session_id,
        sender_type="orchestrator",
        sender_id=agents["orchestrator"].id,
        content_md=(
            f"I created a contract-first plan for {intent.app_name} with shared "
            f"contract `{contract['contractId']}` across backend, frontend, and review tasks."
        ),
        message_kind="plan",
        parent_message_id=message.id,
    )
    create_session_message(db, _session_for_message(db, message), summary)
    return tasks


def _app_contract_for(
    user_goal: str,
    intent: AppContractIntent,
    *,
    frontend_target: TargetProject,
    backend_target: TargetProject,
) -> dict:
    fields_by_type = {
        "todo": [
            {"name": "id", "type": "string", "required": True},
            {"name": "title", "type": "string", "required": True},
            {"name": "completed", "type": "boolean", "required": True},
            {"name": "priority", "type": "string", "required": False},
        ],
        "notes": [
            {"name": "id", "type": "string", "required": True},
            {"name": "title", "type": "string", "required": True},
            {"name": "body", "type": "string", "required": True},
            {"name": "updatedAt", "type": "string", "required": False},
        ],
        "mini_crm_contacts": [
            {"name": "id", "type": "string", "required": True},
            {"name": "name", "type": "string", "required": True},
            {"name": "email", "type": "string", "required": True},
            {"name": "company", "type": "string", "required": False},
            {"name": "status", "type": "string", "required": False},
            {"name": "notes", "type": "string", "required": False},
        ],
    }
    entity_by_type = {
        "todo": "TodoItem",
        "notes": "Note",
        "mini_crm_contacts": "Contact",
    }
    route_base_by_type = {
        "todo": "/todos",
        "notes": "/notes",
        "mini_crm_contacts": "/contacts",
    }
    page_by_type = {
        "todo": "Todo board",
        "notes": "Notes workspace",
        "mini_crm_contacts": "Contacts workspace",
    }
    entity = entity_by_type[intent.app_type]
    route_base = route_base_by_type[intent.app_type]
    frontend_allowed_path = _primary_allowed_path(frontend_target)
    backend_allowed_path = _primary_allowed_path(backend_target)
    backend_base_url = backend_target.base_url or ""
    return {
        "contractId": f"contract-{intent.app_type}",
        "appName": intent.app_name,
        "appType": intent.app_type,
        "userGoal": user_goal,
        "entities": [{"name": entity, "fields": fields_by_type[intent.app_type]}],
        "fields": fields_by_type[intent.app_type],
        "apiRoutes": [
            {"method": "GET", "path": "/health", "description": "Health check"},
            {"method": "GET", "path": route_base, "description": f"List {entity} records"},
            {"method": "POST", "path": route_base, "description": f"Create a {entity} record"},
        ],
        "frontendPages": [
            {
                "name": page_by_type[intent.app_type],
                "target": frontend_target.root,
                "targetId": frontend_target.target_id,
                "states": ["list", "create", "empty"],
            }
        ],
        "backendTargetId": backend_target.target_id,
        "frontendTargetId": frontend_target.target_id,
        "backendTarget": backend_target.root,
        "frontendTarget": frontend_target.root,
        "backendAllowedPaths": list(backend_target.allowed_paths),
        "frontendAllowedPaths": list(frontend_target.allowed_paths),
        "backendBaseUrl": backend_base_url,
        "demoApiBaseUrl": backend_base_url,
        "validationExpectations": [
            f"Backend task must stay in {backend_allowed_path}.",
            f"Frontend task must stay in {frontend_allowed_path}.",
            f"Frontend app data calls must use the demo API base URL {backend_base_url}.",
            "Do not modify apps/api.",
            "Review is advisory and non-blocking.",
            "Preview and mock deploy remain existing local demo evidence.",
        ],
    }


def _create_dynamic_frontend_tasks(
    db: DbSession,
    message: Message,
    intent: FrontendIntent,
    existing_tasks: Optional[list[Task]] = None,
    auto_start: bool = False,
    llm_fallback: Optional[dict] = None,
) -> list[Task]:
    existing_tasks = existing_tasks or []
    frontend = db.exec(select(Agent).where(Agent.role == "frontend")).first()
    orchestrator = db.exec(select(Agent).where(Agent.role == "orchestrator")).first()
    qa = db.exec(select(Agent).where(Agent.role == "qa")).first()
    if frontend is None or not frontend.enabled:
        raise MentionParseError("Dynamic Manager planning requires the enabled frontend agent.")
    if qa is None or not qa.enabled:
        raise MentionParseError("Dynamic Manager planning requires the enabled QA agent.")
    if not existing_tasks and (orchestrator is None or not orchestrator.enabled):
        raise MentionParseError("Dynamic Manager planning requires the enabled orchestrator agent.")

    base_priority = max((task.priority for task in existing_tasks), default=-1) + 1
    task_specs: list[TaskSpec] = []
    if not existing_tasks:
        task_specs.append(
            TaskSpec(
                title="Plan the bounded frontend change",
                intent_type="planning",
                role="orchestrator",
                priority=base_priority,
                plan={
                    "target": intent.target,
                    "summary": intent.summary,
                    "parallelGroup": None,
                },
                expected_artifact_types=["plan"],
            )
        )

    task_specs.extend(
        [
            TaskSpec(
                title=_coding_title_for(intent),
                intent_type="frontend_change",
                role="frontend",
                priority=base_priority + len(task_specs),
                plan={
                    "target": intent.target,
                    "targetText": intent.target_text,
                    "files": intent.files,
                    "summary": intent.summary,
                    "parallelGroup": None,
                },
                expected_artifact_types=["diff", "review"],
            ),
            TaskSpec(
                title=f"Review {intent.target.replace('_', ' ')} change",
                intent_type="review",
                role="qa",
                priority=base_priority + len(task_specs) + 1,
                plan={
                    "target": intent.target,
                    "checks": ["diff is focused", "preview remains eligible"],
                    "parallelGroup": None,
                },
                expected_artifact_types=["review"],
            ),
        ]
    )
    _validate_task_graph(task_specs)

    agents = {"frontend": frontend, "qa": qa}
    if orchestrator is not None and orchestrator.enabled:
        agents["orchestrator"] = orchestrator

    graph = _graph_metadata(
        goal=message.content_md,
        intent=intent.intent,
        planner="dynamic_manager_v1",
        task_specs=task_specs,
    )
    plan_draft = _plan_draft_metadata(
        goal=message.content_md,
        intent=intent.intent,
        planner="dynamic_manager_v1",
        task_specs=task_specs,
    )
    tasks: list[Task] = []
    prior_task_id = existing_tasks[-1].id if existing_tasks else None
    for index, spec in enumerate(task_specs):
        depends_on = [tasks[index - 1].id] if index > 0 else []
        if index == 0 and prior_task_id is not None:
            depends_on = [prior_task_id]
        plan = {
            **spec.plan,
            "planner": "dynamic_manager_v1",
            "goal": message.content_md,
            "originalRequest": message.content_md,
            "intent": intent.intent,
            "expectedArtifactTypes": spec.expected_artifact_types,
            "taskGraph": graph,
            "planDraft": plan_draft,
            **_fallback_plan_metadata(llm_fallback),
        }
        if auto_start and spec.intent_type == "frontend_change":
            plan["autoStart"] = True
            plan["safeTarget"] = "apps/demo/src"
        task = Task(
            session_id=message.session_id,
            created_by_message_id=message.id,
            title=spec.title,
            intent_type=spec.intent_type,
            status="pending",
            priority=spec.priority,
            plan_json=json.dumps(plan, separators=(",", ":")),
            depends_on_task_ids=json.dumps(depends_on, separators=(",", ":")),
            assigned_agent_id=agents[spec.role].id,
        )
        db.add(task)
        db.commit()
        db.refresh(task)
        tasks.append(task)

    if orchestrator is not None and orchestrator.enabled:
        summary = Message(
            session_id=message.session_id,
            sender_type="orchestrator",
            sender_id=orchestrator.id,
            content_md=(
                f"I created a bounded dynamic plan for {intent.target.replace('_', ' ')}."
            ),
            message_kind="plan",
            parent_message_id=message.id,
        )
        create_session_message(db, _session_for_message(db, message), summary)

    return tasks


def _create_direct_assignment_tasks(
    db: DbSession,
    message: Message,
    role: str,
    *,
    existing_tasks: list[Task],
) -> list[Task]:
    if role == "backend":
        active_backend_target = _active_external_target_for_role(db, message, "backend")
        if active_backend_target is not None:
            backend = _enabled_agent_or_raise(db, "backend")
            return [
                _create_external_assignment_task(
                    db,
                    message,
                    agent=backend,
                    role="backend",
                    target=active_backend_target,
                    intent_type="backend_change",
                    priority=_next_priority(existing_tasks),
                    depends_on=[] if not existing_tasks else [existing_tasks[-1].id],
                )
            ]
        if _is_explicit_platform_mode_request(message.content_md):
            return _create_platform_maintenance_task(
                db,
                message,
                depends_on=[] if not existing_tasks else [existing_tasks[-1].id],
                priority=_next_priority(existing_tasks),
            )
        if not _demo_backend_target_exists():
            _create_orchestrator_boundary_message(
                db,
                message,
                "Backend Agent execution needs a safe demo backend target first. P6-4 will add that target; I did not create an unrestricted AgentHub backend task.",
            )
            return []
        backend = _enabled_agent_or_raise(db, "backend")
        backend_target = get_target(DEMO_BACKEND_TARGET_ID)
        return [
            _create_single_task(
                db,
                message,
                agent=backend,
                title=_task_title("Backend", message.content_md),
                intent_type="backend_change",
                priority=_next_priority(existing_tasks),
                depends_on=[] if not existing_tasks else [existing_tasks[-1].id],
                plan={
                    "planner": "direct_assignment_v1",
                    "routing": "direct_mention",
                    "assignedRole": "backend",
                    "target": "demo_backend_request",
                    "targetId": backend_target.target_id,
                    "backendTargetId": backend_target.target_id,
                    "safeTarget": _primary_allowed_path(backend_target),
                    "files": [
                        f"{backend_target.root}/app/main.py",
                        f"{backend_target.root}/tests/test_contacts.py",
                    ],
                    "originalRequest": message.content_md,
                    "expectedArtifactTypes": ["diff", "review"],
                    "autoStart": False,
                },
            )
        ]

    if role == "frontend":
        active_frontend_target = _active_external_target_for_role(db, message, "frontend")
        if active_frontend_target is not None:
            frontend = _enabled_agent_or_raise(db, "frontend")
            return [
                _create_external_assignment_task(
                    db,
                    message,
                    agent=frontend,
                    role="frontend",
                    target=active_frontend_target,
                    intent_type="frontend_change",
                    priority=_next_priority(existing_tasks),
                    depends_on=[] if not existing_tasks else [existing_tasks[-1].id],
                )
            ]
        if not _is_safe_demo_frontend_request(message.content_md):
            _create_orchestrator_boundary_message(
                db,
                message,
                "That frontend assignment is too broad for the current safe demo target. Please bound it to the demo app UI.",
            )
            return []
        frontend = _enabled_agent_or_raise(db, "frontend")
        frontend_target = get_target(DEMO_FRONTEND_TARGET_ID)
        return [
            _create_single_task(
                db,
                message,
                agent=frontend,
                title=_task_title("Frontend", message.content_md),
                intent_type="frontend_change",
                priority=_next_priority(existing_tasks),
                depends_on=[] if not existing_tasks else [existing_tasks[-1].id],
                plan={
                    "planner": "direct_assignment_v1",
                    "routing": "direct_mention",
                    "assignedRole": "frontend",
                    "target": "demo_frontend_request",
                    "targetId": frontend_target.target_id,
                    "frontendTargetId": frontend_target.target_id,
                    "safeTarget": _primary_allowed_path(frontend_target),
                    "files": _demo_frontend_task_files(
                        frontend_target,
                        message.content_md,
                    ),
                    "originalRequest": message.content_md,
                    "expectedArtifactTypes": ["diff", "review"],
                    "autoStart": False,
                },
            )
        ]

    qa = _enabled_agent_or_raise(db, "qa")
    review_role = "review" if role == "review" else "qa"
    active_review_target = _active_external_target_for_role(db, message, "frontend") or _active_external_target_for_role(db, message, "backend")
    target_plan = {}
    if active_review_target is not None:
        target_plan = {
            "targetId": active_review_target.target_id,
            "safeTarget": _primary_allowed_path(active_review_target),
            "readOnly": True,
        }
    return [
        _create_single_task(
            db,
            message,
            agent=qa,
            title=_task_title("Review" if review_role == "review" else "QA", message.content_md),
            intent_type="review" if review_role == "review" else "qa_review",
            priority=_next_priority(existing_tasks),
            depends_on=[] if not existing_tasks else [existing_tasks[-1].id],
            plan={
                "planner": "direct_assignment_v1",
                "routing": "direct_mention",
                "assignedRole": review_role,
                "target": "external_review_request" if active_review_target is not None else "session_review_request",
                **target_plan,
                "originalRequest": message.content_md,
                "expectedArtifactTypes": ["review"],
                "autoStart": False,
            },
        )
    ]


def _create_orchestrator_demo_frontend_task(
    db: DbSession,
    message: Message,
    *,
    llm_fallback: Optional[dict] = None,
) -> list[Task]:
    frontend = _enabled_agent_or_raise(db, "frontend")
    frontend_target = get_target(DEMO_FRONTEND_TARGET_ID)
    frontend_allowed_path = _primary_allowed_path(frontend_target)
    passthrough = _is_passthrough_frontend_request(message.content_md)
    planner = "passthrough_v1" if passthrough else "orchestrator_auto_run_v1"
    passthrough_plan = (
        {
            "plannerMode": "passthrough_v1",
            "instructionMode": "passthrough_v1",
            "allowedPaths": list(frontend_target.allowed_paths),
            "deniedPaths": list(frontend_target.denied_paths),
            "rationale": (
                "The user requested bounded frontend implementation work inside "
                "the registered demo frontend target, so preserve the original "
                "request instead of rewriting it into a demo template."
            ),
            "acceptanceCriteria": [
                "The implemented UI reflects the user's original request.",
                "The app remains usable in the browser preview.",
            ],
            "validationExpectations": [
                frontend_target.build_command or "pnpm build",
                "Preview should remain startable.",
            ],
        }
        if passthrough
        else {}
    )
    task = _create_single_task(
        db,
        message,
        agent=frontend,
        title=_task_title("Frontend", message.content_md),
        intent_type="frontend_change",
        priority=0,
        depends_on=[],
        plan={
            "planner": planner,
            "routing": "orchestrator_default",
            "assignedRole": "frontend",
            "target": "demo_frontend_request",
            "targetId": frontend_target.target_id,
            "frontendTargetId": frontend_target.target_id,
            "safeTarget": frontend_allowed_path,
            "files": [
                f"{frontend_allowed_path}/App.tsx",
                f"{frontend_allowed_path}/styles.css",
            ],
            "originalRequest": message.content_md,
            "expectedArtifactTypes": ["diff", "review"],
            "autoStart": True,
            **passthrough_plan,
            **_fallback_plan_metadata(llm_fallback),
        },
    )
    _create_orchestrator_boundary_message(
        db,
        message,
        (
            "I routed this to the Frontend Agent in passthrough mode and started it automatically."
            if passthrough
            else "I routed this to the Frontend Agent as a safe demo-app task and started it automatically."
        ),
    )
    return [task]


def _create_orchestrator_external_frontend_task(
    db: DbSession,
    message: Message,
    target: TargetProject,
    *,
    llm_fallback: Optional[dict] = None,
) -> list[Task]:
    frontend = _enabled_agent_or_raise(db, "frontend")
    task = _create_external_assignment_task(
        db,
        message,
        agent=frontend,
        role="frontend",
        target=target,
        intent_type="frontend_change",
        priority=0,
        depends_on=[],
        auto_start=True,
        planner="orchestrator_external_target_v1",
        routing="orchestrator_default",
        extra_plan=_fallback_plan_metadata(llm_fallback),
    )
    _create_orchestrator_boundary_message(
        db,
        message,
        f"I routed this to the Frontend Agent for external target `{target.target_id}` and started it automatically.",
    )
    return [task]


def _create_external_assignment_task(
    db: DbSession,
    message: Message,
    *,
    agent: Agent,
    role: str,
    target: TargetProject,
    intent_type: str,
    priority: int,
    depends_on: list[str],
    auto_start: bool = False,
    planner: str = "direct_assignment_v1",
    routing: str = "direct_mention",
    extra_plan: Optional[dict] = None,
) -> Task:
    allowed_path = _primary_allowed_path(target)
    files = _external_task_files(target)
    plan = {
        "planner": planner,
        "routing": routing,
        "assignedRole": role,
        "target": "external_target_request",
        "targetId": target.target_id,
        "safeTarget": allowed_path,
        "allowedPaths": list(target.allowed_paths),
        "deniedPaths": list(target.denied_paths),
        "files": files,
        "projectType": target.project_type,
        "detectedFramework": target.detected_framework,
        "packageManager": target.package_manager,
        "devCommand": target.dev_command,
        "testCommand": target.test_command,
        "checkCommand": target.check_command,
        "buildCommand": target.build_command,
        "previewCommand": target.preview_command,
        "originalRequest": message.content_md,
        "expectedArtifactTypes": ["diff", "review"],
        "autoStart": auto_start,
        **(extra_plan or {}),
    }
    if role == "frontend":
        plan["frontendTargetId"] = target.target_id
    if role == "backend":
        plan["backendTargetId"] = target.target_id
    return _create_single_task(
        db,
        message,
        agent=agent,
        title=_task_title(role.title(), message.content_md),
        intent_type=intent_type,
        priority=priority,
        depends_on=depends_on,
        plan=plan,
    )


def _create_platform_maintenance_task(
    db: DbSession,
    message: Message,
    *,
    depends_on: Optional[list[str]] = None,
    priority: int = 0,
    llm_fallback: Optional[dict] = None,
) -> list[Task]:
    backend = _enabled_agent_or_raise(db, "backend")
    platform_target = get_target(AGENTHUB_PLATFORM_TARGET_ID)
    task = _create_single_task(
        db,
        message,
        agent=backend,
        title=_task_title("Platform maintenance", message.content_md),
        intent_type="platform_maintenance",
        priority=priority,
        depends_on=depends_on or [],
        plan={
            "planner": "platform_maintenance_v1",
            "routing": "explicit_platform_mode",
            "assignedRole": "backend",
            "target": "agenthub_platform_maintenance",
            "targetId": platform_target.target_id,
            "platformMode": True,
            "requiresApproval": True,
            "safeTarget": "apps/api",
            "allowedPaths": list(platform_target.allowed_paths),
            "deniedPaths": list(platform_target.denied_paths),
            "validationExpectations": ["pnpm check", "pnpm test"],
            "originalRequest": message.content_md,
            "expectedArtifactTypes": ["diff", "review"],
            "autoStart": False,
            **_fallback_plan_metadata(llm_fallback),
        },
    )
    _create_orchestrator_boundary_message(
        db,
        message,
        "I created a platform maintenance task targeting agenthub-platform. It requires approval before adapter execution.",
    )
    return [task]


def _create_single_task(
    db: DbSession,
    message: Message,
    *,
    agent: Agent,
    title: str,
    intent_type: str,
    priority: int,
    depends_on: list[str],
    plan: dict,
) -> Task:
    task = Task(
        session_id=message.session_id,
        created_by_message_id=message.id,
        title=title,
        intent_type=intent_type,
        status="pending",
        priority=priority,
        plan_json=json.dumps(plan, separators=(",", ":")),
        depends_on_task_ids=json.dumps(depends_on, separators=(",", ":")),
        assigned_agent_id=agent.id,
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


def _enabled_agent_or_raise(db: DbSession, role: str) -> Agent:
    agent = db.exec(select(Agent).where(Agent.role == role)).first()
    if agent is None or not agent.enabled:
        raise MentionParseError(f"Mention @{role} is disabled or unavailable.")
    return agent


def _next_priority(existing_tasks: list[Task]) -> int:
    return max((task.priority for task in existing_tasks), default=-1) + 1


def _task_title(prefix: str, content: str) -> str:
    request = MENTION_PATTERN.sub("", content).strip()
    request = re.sub(r"\s+", " ", request)
    if len(request) > 90:
        request = f"{request[:87].rstrip()}..."
    return f"{prefix}: {request or 'Handle requested task'}"


def _is_safe_demo_frontend_request(content: str) -> bool:
    normalized = MENTION_PATTERN.sub("", content).lower()
    if _is_unsupported_broad_request(normalized):
        return False
    safe_signals = [
        "demo app",
        "apps/demo",
        "current demo",
        "当前 demo",
        "演示应用",
        "frontend",
        "前端",
        "dashboard",
        "统计卡片",
        "最近活动",
        "hero",
    ]
    return any(signal in normalized for signal in safe_signals)


def _is_passthrough_frontend_request(content: str) -> bool:
    normalized = MENTION_PATTERN.sub("", content).lower()
    implementation_signals = [
        "implement",
        "build",
        "create",
        "make",
        "add",
        "实现",
        "构建",
        "创建",
        "做一个",
        "做成",
        "添加",
        "新增",
    ]
    frontend_scope_signals = [
        "current frontend",
        "frontend project",
        "当前前端",
        "前端项目",
        "当前项目",
        "demo app",
        "apps/demo",
        "dashboard",
        "game",
        "游戏",
        "页面",
    ]
    demo_template_signals = [
        "login page",
        "登录页",
        "button text",
        "按钮文案",
    ]
    return (
        any(signal in normalized for signal in implementation_signals)
        and any(signal in normalized for signal in frontend_scope_signals)
        and not any(signal in normalized for signal in demo_template_signals)
    )


def _is_safe_external_frontend_request(content: str) -> bool:
    normalized = MENTION_PATTERN.sub("", content).lower()
    if _is_unsupported_broad_request(normalized):
        return False
    safe_signals = [
        "frontend",
        "ui",
        "page",
        "dashboard",
        "hero",
        "copy",
        "button",
        "layout",
        "前端",
        "页面",
        "仪表盘",
        "按钮",
        "文案",
    ]
    return any(signal in normalized for signal in safe_signals)


def _active_external_target_for_role(
    db: DbSession,
    message: Message,
    role: str,
) -> Optional[TargetProject]:
    session = _session_for_message(db, message)
    target_id = (
        session.active_frontend_target_id
        if role == "frontend"
        else session.active_backend_target_id
    )
    if not target_id:
        return None
    try:
        target = get_target_for_workspace(db, session.workspace_id, target_id)
    except TargetRegistryError:
        return None
    if not target.target_id.startswith("external-"):
        return None
    if role == "frontend" and target.type != "frontend":
        return None
    if role == "backend" and target.type != "backend":
        return None
    return target


def _external_task_files(target: TargetProject) -> list[str]:
    root = Path(target.root)
    files: list[str] = []
    for allowed_path in target.allowed_paths:
        allowed_root = root / allowed_path
        for candidate in ("App.tsx", "App.jsx", "main.tsx", "main.jsx", "main.py", "server.ts"):
            if (allowed_root / candidate).exists():
                files.append(f"{allowed_path}/{candidate}")
                break
        if not files:
            files.append(allowed_path)
    return files[:4]


def _maybe_handle_explicit_memory_write(
    db: DbSession,
    message: Message,
    content: str,
) -> bool:
    session = db.get(AgentHubSession, message.session_id)
    if session is None:
        return False
    memory_write = maybe_create_explicit_user_memory(
        db,
        session=session,
        content=content,
    )
    if memory_write is None:
        return False
    _create_orchestrator_boundary_message(
        db,
        message,
        memory_write.reply,
    )
    return True


def _demo_frontend_task_files(target: TargetProject, content: str) -> list[str]:
    safe_root = _primary_allowed_path(target)
    files = [
        f"{safe_root}/App.tsx",
        f"{safe_root}/styles.css",
    ]
    for match in re.finditer(r"apps/demo/src/[A-Za-z0-9_./-]+", content):
        path = match.group(0).rstrip(".,，。:：;；)")
        if target.allows_path(path) and not target.denies_path(path) and path not in files:
            files.append(path)
    return files[:6]


def _is_unsupported_broad_request(content: str) -> bool:
    blocked_signals = [
        "whole app",
        "entire app",
        "full app",
        "agenthub platform",
        "apps/api",
        "production deploy",
        "payment",
        "multi-tenant",
        "多租户",
        "生产部署",
    ]
    return any(signal in content for signal in blocked_signals)


def _is_pure_chat_request(content: str) -> bool:
    normalized = MENTION_PATTERN.sub("", content).strip().lower()
    normalized = normalized.strip(" ?!。！？")
    greetings = {"你好", "您好", "hello", "hi", "hey"}
    capability_questions = {
        "你能做什么",
        "你可以做什么",
        "what can you do",
        "what can agenthub do",
    }
    return normalized in greetings or normalized in capability_questions


def _friendly_chat_fallback_reply(llm_fallback: Optional[dict] = None) -> str:
    if llm_fallback and llm_fallback.get("reason") == "provider_failed":
        detail = _planner_fallback_detail(llm_fallback)
        return f"抱歉，{detail}。你可以通过 @frontend 或 @backend 直接指派编码 Agent。"
    if llm_fallback and llm_fallback.get("reason") == "invalid_provider":
        return "抱歉，LLM 路由配置无效。你可以通过 @frontend 或 @backend 直接指派编码 Agent。"
    return "你好，有什么我可以帮你的？你可以提出具体的代码需求，或通过 @frontend 直接让 Agent 开始工作。"


def _unsupported_or_unregistered_target_reply(llm_fallback: Optional[dict] = None) -> str:
    prefix = ""
    if llm_fallback and llm_fallback.get("reason") in {"provider_failed", "invalid_provider"}:
        prefix = f"Planner LLM 未能完成本次路由：{_planner_fallback_detail(llm_fallback)}\n\n"
    elif llm_fallback:
        prefix = "当前 LLM 路由不可用。\n\n"
    return (
        f"{prefix}"
        "我还不能安全地把这条消息直接变成可执行任务。"
        "如果要写入桌面或其他本地目录，请先把对应目录注册为外部工作区/目标；"
        "如果只是想改当前 demo，请提出一个限定在 demo app 内的前端/后端变更，"
        "或显式使用 @frontend / @backend 指派。"
    )


def _planner_fallback_detail(llm_fallback: dict) -> str:
    summary = llm_fallback.get("errorSummary")
    code = llm_fallback.get("errorCode")
    provider = llm_fallback.get("providerId") or llm_fallback.get("providerType")
    parts = []
    if provider:
        parts.append(f"provider={provider}")
    if code:
        parts.append(f"code={code}")
    if isinstance(summary, str) and summary.strip():
        parts.append(_safe_error_excerpt(summary))
    return "；".join(parts) if parts else "请检查 Planner 配置、模型名、baseUrl 和后端环境变量。"


def _safe_error_excerpt(value: str) -> str:
    redacted = value.replace("\n", " ").strip()
    return redacted[:240] + ("..." if len(redacted) > 240 else "")


def _safe_planner_error_summary(value: str) -> str:
    redacted = re.sub(
        r"(?i)(secret|token|password|api[_-]?key)\s*[:=]\s*[^\s;]+",
        "[protected]",
        value,
    )
    redacted = re.sub(
        r"/[^\s]*?(?:\.env|/\.git|/node_modules|/\.venv|/secrets)(?:[^\s]*)?",
        "[protected]",
        redacted,
    )
    return _safe_error_excerpt(redacted)


def _is_explicit_platform_mode_request(content: str) -> bool:
    normalized = MENTION_PATTERN.sub("", content).lower()
    return (
        "platform mode" in normalized
        or "platform maintenance" in normalized
        or "平台维护模式" in normalized
        or "平台维护" in normalized
    )


def _demo_backend_target_exists() -> bool:
    backend_target = get_target(DEMO_BACKEND_TARGET_ID)
    return (_repo_root() / backend_target.root / "app/main.py").exists()


def _fallback_tasks_for_non_task_llm_outcome(
    db: DbSession,
    message: Message,
    content: str,
    outcome: dict[str, Any],
    planner_provider,
) -> list[Task]:
    if str(outcome.get("outcomeType") or "") != "assistant_reply":
        return []
    if _is_pure_chat_request(content):
        return []
    if list_session_tasks(db, message.session_id):
        return []
    active_frontend_target = _active_external_target_for_role(db, message, "frontend")
    if active_frontend_target is None:
        return []
    if not _is_safe_external_frontend_request(content):
        return []
    llm_fallback = llm_planner_fallback_metadata(
        "non_task_coding_outcome",
        provider=planner_provider,
    )
    llm_fallback["originalOutcomeType"] = str(outcome.get("outcomeType") or "")
    llm_fallback["originalValidationResult"] = str(
        outcome.get("validationResult") or ""
    )
    llm_fallback["deterministicExecutable"] = True
    llm_fallback["errorCode"] = "LLM_NON_TASK_CODING_OUTCOME"
    llm_fallback["errorSummary"] = (
        "LLM router returned assistant_reply for a safe external frontend coding request."
    )
    tasks = _create_orchestrator_external_frontend_task(
        db,
        message,
        active_frontend_target,
        llm_fallback=llm_fallback,
    )
    _record_fallback_created_task_ids(db, tasks)
    return tasks


def _should_request_target_setup_for_non_task_llm_outcome(
    db: DbSession,
    message: Message,
    content: str,
    outcome: dict[str, Any],
) -> bool:
    if str(outcome.get("outcomeType") or "") != "assistant_reply":
        return False
    if _is_pure_chat_request(content):
        return False
    if list_session_tasks(db, message.session_id):
        return False
    if _active_external_target_for_role(db, message, "frontend") is not None:
        return False
    return _is_safe_external_frontend_request(content)


def _record_fallback_created_task_ids(db: DbSession, tasks: list[Task]) -> None:
    created_task_ids = [task.id for task in tasks]
    for task in tasks:
        try:
            plan = json.loads(task.plan_json)
        except json.JSONDecodeError:
            continue
        if not isinstance(plan, dict):
            continue
        fallback = plan.get("plannerFallback")
        if not isinstance(fallback, dict):
            continue
        fallback["createdTaskIds"] = created_task_ids
        plan["plannerFallback"] = fallback
        planner_evidence = plan.get("plannerEvidence")
        if not isinstance(planner_evidence, dict):
            planner_evidence = {}
        planner_evidence["createdTaskIds"] = created_task_ids
        plan["plannerEvidence"] = planner_evidence
        task.plan_json = json.dumps(plan, separators=(",", ":"))
        db.add(task)
    db.commit()
    for task in tasks:
        db.refresh(task)


def _primary_allowed_path(target: TargetProject) -> str:
    return target.allowed_paths[0] if target.allowed_paths else target.root


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _create_orchestrator_boundary_message(
    db: DbSession,
    message: Message,
    content: str,
) -> None:
    orchestrator = db.exec(select(Agent).where(Agent.role == "orchestrator")).first()
    summary = Message(
        session_id=message.session_id,
        sender_type="orchestrator",
        sender_id=orchestrator.id if orchestrator is not None else None,
        content_md=content,
        message_kind="chat",
        parent_message_id=message.id,
    )
    create_session_message(db, _session_for_message(db, message), summary)


def _create_conversation_outcome_message(
    db: DbSession,
    message: Message,
    outcome: dict,
) -> None:
    reply = outcome.get("reply")
    if not isinstance(reply, str) or not reply.strip():
        reply = _default_reply_for_conversation_outcome(
            str(outcome.get("outcomeType") or "unsupported")
        )
    orchestrator = db.exec(select(Agent).where(Agent.role == "orchestrator")).first()
    response = Message(
        session_id=message.session_id,
        sender_type="orchestrator",
        sender_id=orchestrator.id if orchestrator is not None else None,
        content_md=reply.strip(),
        message_kind="chat",
        parent_message_id=message.id,
    )
    create_session_message(db, _session_for_message(db, message), response)


def _default_reply_for_conversation_outcome(outcome_type: str) -> str:
    if outcome_type == "clarification":
        return "我还需要一些细节才能安全地规划这个任务，能再具体描述一下吗？"
    if outcome_type == "refusal":
        return (
            "这个请求涉及我无法操作的范围。我只能修改当前项目工作区内的文件，"
            "无法操作系统文件、桌面、或其他项目目录。你可以在当前项目内提出"
            "一个具体的代码需求，或者通过 @frontend 直接指派前端 Agent。"
        )
    if outcome_type == "approval_required":
        return "这个请求需要审批才能执行，请确认你已了解相关风险。"
    if outcome_type == "unsupported":
        return "这个请求暂时超出我的能力范围。可以试试换个方式描述你的需求？"
    return "我可以帮你规划任务、写代码、做审查、预览和部署。需要我做什么？"


def _coding_title_for(intent: FrontendIntent) -> str:
    labels = {
        "demo_heading_text": "Change demo heading text",
        "primary_action_button_text": "Change primary button text",
        "theme_accent_color": "Change theme accent color",
        "simple_input_field": "Add simple input field",
        "status_help_text": "Add status/help text",
        "layout_copy": "Adjust layout copy",
    }
    label = labels.get(intent.target, "Apply bounded frontend change")
    return f"{label} to {intent.target_text}"


def _graph_metadata(
    *,
    goal: str,
    intent: str,
    planner: str,
    task_specs: list[TaskSpec],
) -> dict:
    return task_graph_metadata(
        goal=goal,
        intent=intent,
        planner=planner,
        task_specs=task_specs,
    )


def _plan_draft_metadata(
    *,
    goal: str,
    intent: str,
    planner: str,
    task_specs: list[TaskSpec],
) -> dict:
    return build_plan_draft(
        goal=goal,
        intent=intent,
        planner=planner,
        task_specs=task_specs,
    ).to_metadata()


def _fallback_plan_metadata(llm_fallback: Optional[dict]) -> dict:
    if not llm_fallback:
        return {}
    return {
        "plannerFallback": llm_fallback,
        "plannerSource": "fallback",
        "plannerEvidence": _planner_evidence_from_fallback(llm_fallback),
    }


def _planner_evidence_from_fallback(llm_fallback: dict) -> dict:
    evidence = {
        "plannerSource": "fallback",
        "fallbackReason": llm_fallback.get("reason"),
        "providerId": llm_fallback.get("providerId"),
        "providerType": llm_fallback.get("providerType"),
        "providerSource": llm_fallback.get("plannerSource"),
        "status": llm_fallback.get("status"),
        "llmOutcomeType": llm_fallback.get("originalOutcomeType"),
        "deterministicExecutable": llm_fallback.get("deterministicExecutable"),
        "validationResult": (
            llm_fallback.get("validationResult")
            or llm_fallback.get("originalValidationResult")
        ),
        "errorCode": llm_fallback.get("errorCode"),
        "errorSummary": llm_fallback.get("errorSummary"),
    }
    for key in ("model", "providerPresetId", "protocol"):
        if key in llm_fallback:
            evidence[key] = llm_fallback[key]
    return {key: value for key, value in evidence.items() if value not in (None, "")}


def _validate_task_graph(task_specs: list[TaskSpec]) -> None:
    try:
        validate_task_graph(task_specs)
    except PlanValidationError as exc:
        raise MentionParseError(str(exc)) from exc


def _session_for_message(db: DbSession, message: Message):
    from app.models import Session

    session = db.get(Session, message.session_id)
    if session is None:
        raise MentionParseError("Session is unavailable for planning.")
    return session
