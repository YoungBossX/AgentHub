import json
from typing import Any

from sqlmodel import Session as DbSession

from app.agent_runtime_config import resolve_runtime_role_config
from app.config import get_settings
from app.context_items import normalize_context_items
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
from app.models import Message, Task
from app.models import Session as AgentHubSession
from app.planner_providers import PlannerProviderError, resolve_planner_provider
from app.repositories import list_session_tasks
from app.planning_intents import (
    AppContractIntent,
    FollowupChange,
    FrontendIntent,
    MentionParseError,
    ParsedMentions,
    parse_app_contract_intent,
    parse_followup_change,
    parse_frontend_intent,
    parse_mentions,
    _active_external_target_for_role,
    _clean_target_text,
    _demo_backend_target_exists,
    _demo_frontend_task_files,
    _external_task_files,
    _fallback_external_target_for_role,
    _friendly_chat_fallback_reply,
    _has_active_external_targets,
    _is_explicit_platform_mode_request,
    _is_passthrough_frontend_request,
    _is_pure_chat_request,
    _is_safe_demo_frontend_request,
    _is_safe_external_frontend_request,
    _is_unsupported_broad_request,
    _planner_fallback_detail,
    _primary_allowed_path,
    _repo_root,
    _requires_backend_target,
    _safe_error_excerpt,
    _safe_planner_error_summary,
    _session_for_message,
    _unsupported_or_unregistered_target_reply,
    _wildcard_external_task_files,
)

from app.planning_tasks import (
    TaskSpec,
    _active_planning_tasks,
    _app_contract_for,
    _coding_title_for,
    _create_contract_first_plan,
    _create_conversation_outcome_message,
    _create_direct_assignment_tasks,
    _create_dynamic_frontend_tasks,
    _create_external_assignment_task,
    _create_external_fallback_tasks_for_request,
    _create_login_page_plan,
    _create_orchestrator_boundary_message,
    _create_orchestrator_demo_frontend_task,
    _create_orchestrator_external_frontend_task,
    _create_platform_maintenance_task,
    _create_single_task,
    _default_reply_for_conversation_outcome,
    _enabled_agent_or_raise,
    _fallback_plan_metadata,
    _fallback_tasks_for_non_task_llm_outcome,
    _graph_metadata,
    _maybe_handle_explicit_memory_write,
    _next_priority,
    _plan_draft_metadata,
    _planner_evidence_from_fallback,
    _record_fallback_created_task_ids,
    _should_request_target_setup_for_non_task_llm_outcome,
    _task_title,
    _validate_task_graph,
)


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
        context_handoff = _context_handoff_for_task(db, task)
        if context_handoff["itemCount"] > 0:
            planner_evidence["contextHandoff"] = context_handoff
            plan["contextHandoff"] = context_handoff
        plan["plannerEvidence"] = planner_evidence
        task.plan_json = json.dumps(plan, separators=(",", ":"))
        db.add(task)
    db.commit()
    for task in tasks:
        db.refresh(task)


def _context_handoff_for_task(db: DbSession, task: Task) -> dict[str, Any]:
    if task.created_by_message_id is None:
        return {"itemCount": 0, "items": [], "redacted": False}
    message = db.get(Message, task.created_by_message_id)
    if message is None:
        return {"itemCount": 0, "items": [], "redacted": False}
    try:
        context = json.loads(message.context_json)
    except json.JSONDecodeError:
        context = {}
    if not isinstance(context, dict):
        context = {}
    items = normalize_context_items(context)
    evidence_items = [
        {
            "id": item.get("id"),
            "kind": item.get("kind"),
            "valid": item.get("valid"),
            "artifactId": item.get("artifactId"),
            "artifactVersionId": item.get("artifactVersionId"),
            "messageId": item.get("messageId"),
            "deploymentId": item.get("deploymentId"),
            "redacted": item.get("redacted"),
            "source": item.get("source"),
        }
        for item in items
    ]
    return {
        "itemCount": len(items),
        "itemKinds": [str(item.get("kind")) for item in items],
        "items": evidence_items,
        "redacted": any(bool(item.get("redacted")) for item in items),
    }


def plan_for_message(
    db: DbSession,
    message: Message,
    content: str,
) -> list[Task]:
    parsed = parse_mentions(db, content)
    existing_tasks = list_session_tasks(db, message.session_id)
    active_tasks = _active_planning_tasks(existing_tasks)
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
                            _attach_planner_runtime_evidence(db, fallback_tasks, planner_runtime)
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
    if (
        not active_tasks
        and _has_active_external_targets(db, message)
        and bounded_intent is None
    ):
        external_fallback_tasks = _create_external_fallback_tasks_for_request(
            db,
            message,
            content,
            llm_fallback=llm_fallback,
        )
        if external_fallback_tasks:
            return external_fallback_tasks

    if contract_intent is not None and not active_tasks:
        return _create_contract_first_plan(
            db,
            message,
            contract_intent,
            llm_fallback=llm_fallback,
        )
    if contract_intent is not None and active_tasks:
        return []

    if _is_explicit_platform_mode_request(content) and not active_tasks:
        return _create_platform_maintenance_task(
            db,
            message,
            llm_fallback=llm_fallback,
        )

    if bounded_intent is not None and active_tasks:
        return _create_dynamic_frontend_tasks(
            db,
            message,
            bounded_intent,
            existing_tasks=active_tasks,
            auto_start=True,
        )

    if active_tasks:
        return []

    if "login page" not in content.lower() or "demo app" not in content.lower():
        if bounded_intent is None:
            external_fallback_tasks = _create_external_fallback_tasks_for_request(
                db,
                message,
                content,
                llm_fallback=llm_fallback,
            )
            if external_fallback_tasks:
                return external_fallback_tasks
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
