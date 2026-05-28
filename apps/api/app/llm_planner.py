from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Protocol

from sqlmodel import Session as DbSession
from sqlmodel import select

from app.canonical_context import build_canonical_shared_context, filter_protected_values
from app.models import Agent, Message, Task
from app.models import Session as AgentHubSession
from app.plan_validator import PlanValidationError, validate_task_graph
from app.planner_service import build_plan_draft
from app.planner_providers import (
    PlannerProvider,
    PlannerProviderError,
    PlannerProviderResult,
)
from app.repositories import create_session_message
from app.target_registry import TargetProject, list_targets_for_workspace
from app.task_graph_builder import TaskGraphTaskSpec, task_graph_metadata

LLM_PLANNER_MODE = "llm_v1"
LLM_PLANNER_VERSION = 1


class LLMPlannerError(ValueError):
    pass


class LLMPlannerProvider(PlannerProvider, Protocol):
    pass


@dataclass(frozen=True)
class LLMPlanningOutcome:
    tasks: list[Task]
    planner_input: dict[str, Any]
    raw_output: dict[str, Any]
    plan_draft: dict[str, Any]


def llm_planner_fallback_metadata(
    reason: str,
    *,
    provider: PlannerProvider | None = None,
    provider_result: PlannerProviderResult | None = None,
) -> dict[str, str]:
    metadata = {
        "attemptedPlanner": LLM_PLANNER_MODE,
        "reason": reason,
    }
    if provider_result is not None:
        metadata.update(
            {
                "providerId": provider_result.provider_id,
                "providerType": provider_result.provider_type,
                "plannerSource": provider_result.planner_source,
                "status": provider_result.status,
            }
        )
        return metadata
    if provider is not None:
        metadata.update(
            {
                "providerId": provider.provider_id,
                "providerType": provider.provider_type,
                "plannerSource": provider.planner_source,
                "status": "disabled" if provider.planner_source == "disabled" else "not_started",
            }
        )
    return metadata


def build_llm_planner_input(db: DbSession, message: Message) -> dict[str, Any]:
    session = db.get(AgentHubSession, message.session_id)
    if session is None:
        raise LLMPlannerError("Session is unavailable for LLM planning.")

    targets = list_targets_for_workspace(db, session.workspace_id)
    recent_messages = _recent_messages(db, message.session_id)
    session_context_pack = {
        "sessionId": session.id,
        "workspaceId": session.workspace_id,
        "currentGoal": message.content_md,
        "originalUserRequest": message.content_md,
        "currentTask": {
            "id": None,
            "title": "Planning request",
            "intentType": "planning",
            "description": message.content_md,
            "plan": {
                "planner": LLM_PLANNER_MODE,
                "originalRequest": message.content_md,
            },
        },
        "recentMessages": recent_messages,
        "ledger": {},
        "latestDiff": None,
        "latestReview": None,
        "latestPreview": None,
        "latestDeployment": None,
        "targetProject": None,
        "relatedTargetProjects": [],
        "safeTargetPaths": [
            allowed_path
            for target in targets
            if not target.requires_platform_mode
            for allowed_path in target.allowed_paths
        ],
        "validationExpectations": _validation_expectations(targets),
    }
    canonical_context = build_canonical_shared_context(session_context_pack)
    return {
        "plannerMode": LLM_PLANNER_MODE,
        "version": LLM_PLANNER_VERSION,
        "originalUserRequest": message.content_md,
        "canonicalSharedContext": filter_protected_values(canonical_context),
        "targetRegistry": [_target_summary(target) for target in targets],
        "projectAnalyzer": [_project_analyzer_summary(target) for target in targets],
        "recentMessages": filter_protected_values(recent_messages),
        "artifactReferences": [],
        "guardrails": {
            "protectedPaths": [".git", ".env", ".env.*", "secrets", "node_modules", ".venv"],
            "denyProductionDeploy": True,
            "denyUnapprovedNetworkAccess": True,
            "platformMaintenanceRequiresExplicitMode": True,
        },
    }


def create_llm_plan_tasks(
    db: DbSession,
    message: Message,
    *,
    provider: LLMPlannerProvider,
) -> LLMPlanningOutcome:
    planner_input = build_llm_planner_input(db, message)
    try:
        provider_result = provider.create_plan(planner_input)
    except PlannerProviderError as exc:
        raise LLMPlannerError(f"LLM planner provider failed: {exc.summary}") from exc
    except Exception as exc:
        raise LLMPlannerError(f"LLM planner provider failed: {exc}") from exc

    if provider_result.status != "succeeded":
        raise LLMPlannerError(
            provider_result.error_summary
            or f"LLM planner provider did not succeed: {provider_result.status}"
        )

    raw_output = parse_llm_plan_output(provider_result.raw_output)
    targets = {
        target.target_id: target
        for target in list_targets_for_workspace(
            db,
            _workspace_id_for_message(db, message),
        )
    }
    task_specs = task_specs_from_llm_plan(raw_output)
    try:
        validate_task_graph(task_specs, allowed_targets=targets)
    except PlanValidationError as exc:
        raise LLMPlannerError(str(exc)) from exc

    _validate_llm_targets_and_roles(task_specs, targets)
    plan_draft = _llm_plan_draft_metadata(
        message=message,
        raw_output=raw_output,
        task_specs=task_specs,
    )
    tasks = _persist_llm_plan_tasks(
        db,
        message=message,
        provider_id=provider.provider_id,
        provider_result=provider_result,
        raw_output=raw_output,
        task_specs=task_specs,
        plan_draft=plan_draft,
    )
    return LLMPlanningOutcome(
        tasks=tasks,
        planner_input=planner_input,
        raw_output=raw_output,
        plan_draft=plan_draft,
    )


def parse_llm_plan_output(raw_text: str) -> dict[str, Any]:
    try:
        payload = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise LLMPlannerError("LLM planner returned invalid JSON.") from exc
    if not isinstance(payload, dict):
        raise LLMPlannerError("LLM planner output must be a JSON object.")
    if payload.get("plannerMode") != LLM_PLANNER_MODE:
        raise LLMPlannerError("LLM planner output must use plannerMode llm_v1.")
    if not isinstance(payload.get("tasks"), list) or not payload["tasks"]:
        raise LLMPlannerError("LLM planner output must include tasks.")
    if not isinstance(payload.get("rationale"), str) or not payload["rationale"].strip():
        raise LLMPlannerError("LLM planner output must include rationale.")
    if not isinstance(payload.get("acceptanceCriteria"), list):
        raise LLMPlannerError("LLM planner output must include acceptanceCriteria.")
    if not isinstance(payload.get("validationExpectations"), list):
        raise LLMPlannerError("LLM planner output must include validationExpectations.")
    return payload


def task_specs_from_llm_plan(payload: dict[str, Any]) -> list[TaskGraphTaskSpec]:
    specs: list[TaskGraphTaskSpec] = []
    for index, item in enumerate(payload["tasks"]):
        if not isinstance(item, dict):
            raise LLMPlannerError("LLM planner task entries must be objects.")
        role = _string_value(item.get("assignedAgentRole") or item.get("role"))
        target_id = _string_value(item.get("targetId"))
        expected = _string_list(item.get("expectedArtifactTypes"))
        files = _string_list(item.get("plannedFiles") or item.get("files"))
        intent_type = _string_value(item.get("intentType")) or _intent_type_for_role(role)
        if not role or not target_id or not expected:
            raise LLMPlannerError("LLM planner tasks must include role, target, and artifacts.")
        specs.append(
            TaskGraphTaskSpec(
                title=_string_value(item.get("title")) or f"LLM task {index + 1}",
                intent_type=intent_type,
                role=role,
                priority=int(item.get("priority") or index),
                plan={
                    "planner": LLM_PLANNER_MODE,
                    "plannerMode": LLM_PLANNER_MODE,
                    "targetId": target_id,
                    "target": _string_value(item.get("target")) or "real_coding_request",
                    "files": files,
                    "plannedFiles": files,
                    "dependsOn": _string_list(item.get("dependsOn")),
                    "acceptanceCriteria": _string_list(item.get("acceptanceCriteria")),
                    "validationExpectations": _string_list(item.get("validationExpectations")),
                    "rationale": _string_value(item.get("rationale")),
                },
                expected_artifact_types=expected,
            )
        )
    return specs


def _persist_llm_plan_tasks(
    db: DbSession,
    *,
    message: Message,
    provider_id: str,
    provider_result: PlannerProviderResult,
    raw_output: dict[str, Any],
    task_specs: list[TaskGraphTaskSpec],
    plan_draft: dict[str, Any],
) -> list[Task]:
    agents = {
        agent.role: agent
        for agent in db.exec(select(Agent).where(Agent.role.in_({"orchestrator", "backend", "frontend", "qa"}))).all()
        if agent.enabled
    }
    missing = [spec.role for spec in task_specs if spec.role not in agents]
    if missing:
        raise LLMPlannerError(f"LLM planner selected unavailable agents: {', '.join(sorted(set(missing)))}.")

    graph = task_graph_metadata(
        goal=message.content_md,
        intent=_string_value(raw_output.get("intent")) or "real_coding_request",
        planner=LLM_PLANNER_MODE,
        task_specs=task_specs,
    )
    task_ids_by_key: dict[str, str] = {}
    tasks: list[Task] = []
    for index, spec in enumerate(task_specs):
        key = f"{index + 1}-{spec.role}-{spec.intent_type}"
        depends_on_keys = _string_list(spec.plan.get("dependsOn"))
        depends_on = [
            task_ids_by_key[dependency_key]
            for dependency_key in depends_on_keys
            if dependency_key in task_ids_by_key
        ]
        if not depends_on and index > 0 and not depends_on_keys:
            depends_on = [tasks[index - 1].id]
        plan = {
            **spec.plan,
            "planner": LLM_PLANNER_MODE,
            "plannerMode": LLM_PLANNER_MODE,
            "plannerProviderId": provider_id,
            "goal": message.content_md,
            "originalRequest": message.content_md,
            "intent": _string_value(raw_output.get("intent")) or "real_coding_request",
            "expectedArtifactTypes": spec.expected_artifact_types,
            "taskGraph": graph,
            "planDraft": plan_draft,
            "llmPlanner": {
                "plannerMode": LLM_PLANNER_MODE,
                "providerId": provider_id,
                "providerType": provider_result.provider_type,
                "plannerSource": provider_result.planner_source,
                "status": provider_result.status,
                "rationale": _string_value(raw_output.get("rationale")),
            },
            "plannerProvider": provider_result.to_metadata(),
            "autoStart": False,
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
        task_ids_by_key[key] = task.id

    orchestrator = db.exec(select(Agent).where(Agent.role == "orchestrator")).first()
    summary = Message(
        session_id=message.session_id,
        sender_type="orchestrator",
        sender_id=orchestrator.id if orchestrator is not None else None,
        content_md="I created an llm_v1 plan and validated it before task creation.",
        message_kind="plan",
        parent_message_id=message.id,
    )
    create_session_message(db, _session_for_message(db, message), summary)
    return tasks


def _llm_plan_draft_metadata(
    *,
    message: Message,
    raw_output: dict[str, Any],
    task_specs: list[TaskGraphTaskSpec],
) -> dict[str, Any]:
    return build_plan_draft(
        goal=message.content_md,
        intent=_string_value(raw_output.get("intent")) or "real_coding_request",
        planner=LLM_PLANNER_MODE,
        task_specs=task_specs,
        version=int(raw_output.get("version") or LLM_PLANNER_VERSION),
        rationale=_string_value(raw_output.get("rationale")),
        planner_mode=LLM_PLANNER_MODE,
        acceptance_criteria=_string_list(raw_output.get("acceptanceCriteria")),
        validation_expectations=_string_list(raw_output.get("validationExpectations")),
        guardrail_notes=_string_list(raw_output.get("guardrailNotes")),
    ).to_metadata()


def _validate_llm_targets_and_roles(
    task_specs: list[TaskGraphTaskSpec],
    targets: dict[str, TargetProject],
) -> None:
    for spec in task_specs:
        target_id = _string_value(spec.plan.get("targetId"))
        target = targets.get(target_id)
        if target is None:
            raise LLMPlannerError(f"LLM planner selected unknown target: {target_id}")
        if not target.allows_agent(spec.role):
            raise LLMPlannerError(
                f"LLM planner selected role {spec.role} for unsupported target {target_id}."
            )


def _target_summary(target: TargetProject) -> dict[str, Any]:
    return {
        "targetId": target.target_id,
        "name": target.name,
        "type": target.type,
        "root": target.root,
        "allowedPaths": list(target.allowed_paths),
        "deniedPaths": list(target.denied_paths),
        "allowedAgents": list(target.allowed_agents),
        "requiresPlatformMode": target.requires_platform_mode,
        "requiresApproval": target.requires_approval,
    }


def _project_analyzer_summary(target: TargetProject) -> dict[str, Any]:
    return {
        "targetId": target.target_id,
        "projectType": target.project_type,
        "detectedFramework": target.detected_framework,
        "packageManager": target.package_manager,
        "devCommand": target.dev_command,
        "testCommand": target.test_command,
        "checkCommand": target.check_command,
        "buildCommand": target.build_command,
        "previewCommand": target.preview_command,
    }


def _recent_messages(db: DbSession, session_id: str) -> list[dict[str, Any]]:
    messages = db.exec(
        select(Message)
        .where(Message.session_id == session_id)
        .order_by(Message.created_at.desc(), Message.id.desc())
        .limit(8)
    ).all()
    return [
        {
            "id": message.id,
            "senderType": message.sender_type,
            "messageKind": message.message_kind,
            "contentMd": message.content_md[:700],
            "createdAt": message.created_at.isoformat(),
        }
        for message in reversed(messages)
    ]


def _validation_expectations(targets: tuple[TargetProject, ...]) -> list[str]:
    expectations = [
        "Validate generated PlanDraft before creating tasks.",
        "Do not include protected host paths or secrets in provider-visible context.",
    ]
    for target in targets:
        if target.test_command:
            expectations.append(f"{target.target_id}: {target.test_command}")
        if target.check_command:
            expectations.append(f"{target.target_id}: {target.check_command}")
        if target.build_command:
            expectations.append(f"{target.target_id}: {target.build_command}")
    return expectations


def _workspace_id_for_message(db: DbSession, message: Message) -> str:
    return _session_for_message(db, message).workspace_id


def _session_for_message(db: DbSession, message: Message) -> AgentHubSession:
    session = db.get(AgentHubSession, message.session_id)
    if session is None:
        raise LLMPlannerError("Session is unavailable for LLM planning.")
    return session


def _intent_type_for_role(role: str) -> str:
    if role == "backend":
        return "backend_change"
    if role == "frontend":
        return "frontend_change"
    if role == "qa":
        return "review"
    return "planning"


def _string_value(value: Any) -> str:
    return value if isinstance(value, str) else ""


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str) and item]
