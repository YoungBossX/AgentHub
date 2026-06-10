import json
from dataclasses import dataclass
from typing import Any, Optional

from sqlmodel import Session as DbSession
from sqlmodel import select

from app.agent_capabilities import validate_capability_tags, validate_supported_modes
from app.agent_profiles import (
    VIRTUAL_AGENT_PROFILE_AGENTS,
    AgentProfile,
    profile_for_agent,
)
from app.agent_target_compatibility import supports_target_id
from app.models import Agent, Task


class AgentSelectionError(ValueError):
    pass


@dataclass(frozen=True)
class AgentSelectionDecision:
    profile: AgentProfile
    target_id: Optional[str]
    required_mode: Optional[str]
    required_capabilities: list[str]
    safe_for_write: bool
    safe_for_review: bool

    def to_metadata(self) -> dict[str, Any]:
        return {
            "role": self.profile.role,
            "targetId": self.target_id,
            "requiredMode": self.required_mode,
            "requiredCapabilities": self.required_capabilities,
            "safeForWrite": self.safe_for_write,
            "safeForReview": self.safe_for_review,
        }


def validate_agent_selection(
    db: DbSession,
    task: Task,
    agent: Agent,
    *,
    explicit_adapter_type: Optional[str] = None,
) -> AgentSelectionDecision:
    plan = _json_dict(task.plan_json)
    profile_agent = _effective_agent_for_selection(
        db,
        task,
        agent,
        plan=plan,
        explicit_adapter_type=explicit_adapter_type,
    )
    profile = profile_for_agent(profile_agent)
    target_id = _target_id_for_plan(plan)
    required_mode = _required_mode_for_task(task, plan)
    required_capabilities = _required_capabilities_for_task(task, plan)
    validate_capability_tags(required_capabilities, source=f"Task:{task.id}")
    if required_mode is not None:
        validate_supported_modes([required_mode], source=f"Task:{task.id}")

    if target_id is not None and not _profile_supports_target(profile, target_id):
        raise AgentSelectionError(
            f"Agent profile `{profile.role}` does not support target `{target_id}`."
        )

    requires_review = task.intent_type in {"review", "qa_review"} or plan.get("readOnly") is True
    requires_write = task.intent_type in {
        "frontend_change",
        "backend_change",
        "platform_maintenance",
    } or plan.get("writeMode") is True

    if requires_write and not profile.safe_for_write:
        raise AgentSelectionError(f"Agent profile `{profile.role}` is not safe for write.")
    if requires_review and not profile.safe_for_review:
        raise AgentSelectionError(f"Agent profile `{profile.role}` is not safe for review.")

    if required_mode is not None and required_mode not in profile.supported_modes:
        raise AgentSelectionError(
            f"Agent profile `{profile.role}` does not support mode `{required_mode}`."
        )

    missing_capabilities = [
        capability
        for capability in required_capabilities
        if capability not in profile.capability_tags
    ]
    if missing_capabilities:
        raise AgentSelectionError(
            "Agent profile "
            f"`{profile.role}` is missing required capability "
            f"`{missing_capabilities[0]}`."
        )

    return AgentSelectionDecision(
        profile=profile,
        target_id=target_id,
        required_mode=required_mode,
        required_capabilities=required_capabilities,
        safe_for_write=profile.safe_for_write,
        safe_for_review=profile.safe_for_review,
    )


def _required_mode_for_task(task: Task, plan: dict[str, Any]) -> Optional[str]:
    assigned_role = plan.get("assignedRole") or plan.get("assigned_role")
    if assigned_role in {"frontend", "backend", "qa", "review", "platform_maintenance"}:
        return str(assigned_role)
    if task.intent_type == "frontend_change":
        return "frontend"
    if task.intent_type == "backend_change":
        return "backend"
    if task.intent_type == "qa_review":
        return "qa"
    if task.intent_type == "review":
        return "review"
    if task.intent_type == "platform_maintenance":
        return "platform_maintenance"
    return None


def _required_capabilities_for_task(task: Task, plan: dict[str, Any]) -> list[str]:
    explicit = plan.get("requiredCapabilities")
    if isinstance(explicit, list):
        return [item for item in explicit if isinstance(item, str) and item]
    explicit_one = plan.get("requiredCapability")
    if isinstance(explicit_one, str) and explicit_one:
        return [explicit_one]
    if task.intent_type == "platform_maintenance":
        return ["code_write", "platform_change"]
    if task.intent_type in {"frontend_change", "backend_change"}:
        return ["code_write"]
    if task.intent_type in {"review", "qa_review"}:
        return ["code_review"]
    return []


def _profile_supports_target(profile: AgentProfile, target_id: str) -> bool:
    return supports_target_id(
        profile.supported_targets,
        target_id,
        role=profile.role,
    )


def _target_id_for_plan(plan: dict[str, Any]) -> Optional[str]:
    target_id = plan.get("targetId") or plan.get("target_id")
    return target_id if isinstance(target_id, str) and target_id else None


def _effective_agent_for_selection(
    db: DbSession,
    task: Task,
    agent: Agent,
    *,
    plan: dict[str, Any],
    explicit_adapter_type: Optional[str],
) -> Agent:
    if (
        explicit_adapter_type == "scripted_mock"
        and task.intent_type in {"frontend_change", "backend_change"}
    ):
        fallback = next(
            profile_agent
            for profile_agent in VIRTUAL_AGENT_PROFILE_AGENTS
            if profile_agent.role == "fallback"
        )
        return fallback

    assigned_role = plan.get("assignedRole") or plan.get("assigned_role")
    if isinstance(assigned_role, str) and assigned_role and assigned_role != agent.role:
        assigned_agent = db.exec(select(Agent).where(Agent.role == assigned_role)).first()
        if assigned_agent is not None:
            return assigned_agent
    return agent


def _json_dict(value: str) -> dict[str, Any]:
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}
