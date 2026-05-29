import json
import os
from dataclasses import dataclass
from typing import Any, Optional

from app.models import Agent, Task

PROVIDER_ASSIGNMENT_MATRIX_ENV = "AGENTHUB_PROVIDER_ASSIGNMENT_MATRIX"
SUPPORTED_PROVIDER_ADAPTERS = {"codex", "claude_code", "scripted_mock"}

BUILT_IN_ROLE_PROVIDER_DEFAULTS: dict[str, dict[str, str]] = {
    "orchestrator": {
        "adapterType": "scripted_mock",
        "providerId": "local-scripted-mock",
    },
    "frontend": {
        "adapterType": "codex",
        "providerId": "local-codex-cli",
    },
    "backend": {
        "adapterType": "codex",
        "providerId": "local-codex-cli",
    },
    "qa": {
        "adapterType": "scripted_mock",
        "providerId": "local-scripted-review",
    },
    "review": {
        "adapterType": "scripted_mock",
        "providerId": "local-scripted-review",
    },
}

ROLE_SUPPORTED_MODES: dict[str, str] = {
    "orchestrator": "planning",
    "frontend": "write",
    "backend": "write",
    "qa": "review",
    "review": "review",
}


class ProviderAssignmentError(ValueError):
    pass


@dataclass(frozen=True)
class ProviderAssignment:
    role: str
    adapter_type: str
    provider_id: str
    source: str
    target_id: Optional[str]
    supported_mode: str
    fallback_policy: str

    def to_metadata(self) -> dict[str, Any]:
        return {
            "role": self.role,
            "adapterType": self.adapter_type,
            "providerId": self.provider_id,
            "source": self.source,
            "targetId": self.target_id,
            "supportedMode": self.supported_mode,
            "fallbackPolicy": self.fallback_policy,
        }


def resolve_provider_assignment(
    task: Task,
    agent: Agent,
    *,
    selected_adapter: str,
    explicit_adapter_type: Optional[str] = None,
    runtime_adapter_type: Optional[str] = None,
    runtime_provider_id: Optional[str] = None,
    runtime_fallback_policy: Optional[str] = None,
) -> ProviderAssignment:
    plan = _plan_json(task)
    role = _role_for_task(plan, agent)
    target_id = _target_id_for_task(plan)
    matrix = _configured_matrix()

    if explicit_adapter_type is not None:
        return _assignment_from_adapter(
            role=role,
            adapter_type=explicit_adapter_type,
            provider_id=_provider_id_for_adapter(explicit_adapter_type, agent),
            source="explicit",
            target_id=target_id,
            fallback_policy="explicit_only",
        )

    if runtime_adapter_type is not None:
        return _assignment_from_adapter(
            role=role,
            adapter_type=runtime_adapter_type,
            provider_id=runtime_provider_id or _provider_id_for_adapter(
                runtime_adapter_type,
                agent,
            ),
            source="runtime_config",
            target_id=target_id,
            fallback_policy=runtime_fallback_policy or "explicit_only",
        )

    configured = _configured_assignment(matrix, role=role, target_id=target_id)
    if configured is not None:
        return configured

    return _assignment_from_adapter(
        role=role,
        adapter_type=selected_adapter,
        provider_id=_provider_id_for_adapter(selected_adapter, agent),
        source="legacy_default",
        target_id=target_id,
        fallback_policy="legacy_default_adapter",
    )


def resolve_profile_provider_assignment(
    role: str,
    agent: Agent,
) -> ProviderAssignment:
    matrix = _configured_matrix()
    raw_role_assignment = matrix.get("roles", {}).get(role)
    if isinstance(raw_role_assignment, dict):
        return _assignment_from_raw(
            raw_role_assignment,
            role=role,
            target_id=None,
            source="role_default",
        )

    raw_default = BUILT_IN_ROLE_PROVIDER_DEFAULTS.get(role)
    if isinstance(raw_default, dict):
        return _assignment_from_raw(
            raw_default,
            role=role,
            target_id=None,
            source="built_in_default",
        )

    return _assignment_from_adapter(
        role=role,
        adapter_type=agent.adapter_type,
        provider_id=agent.provider,
        source="agent_metadata",
        target_id=None,
        fallback_policy="agent_metadata",
    )


def _configured_assignment(
    matrix: dict[str, Any],
    *,
    role: str,
    target_id: Optional[str],
) -> Optional[ProviderAssignment]:
    if target_id:
        target_assignments = matrix.get("targets", {}).get(target_id)
        if isinstance(target_assignments, dict):
            raw_target_assignment = target_assignments.get(role)
            if isinstance(raw_target_assignment, dict):
                return _assignment_from_raw(
                    raw_target_assignment,
                    role=role,
                    target_id=target_id,
                    source="target_override",
                )

    raw_role_assignment = matrix.get("roles", {}).get(role)
    if isinstance(raw_role_assignment, dict):
        return _assignment_from_raw(
            raw_role_assignment,
            role=role,
            target_id=target_id,
            source="role_default",
        )
    return None


def _assignment_from_raw(
    raw: dict[str, Any],
    *,
    role: str,
    target_id: Optional[str],
    source: str,
) -> ProviderAssignment:
    adapter_type = raw.get("adapterType") or raw.get("adapter_type")
    if not isinstance(adapter_type, str) or not adapter_type:
        raise ProviderAssignmentError(
            f"Provider assignment for role `{role}` must include adapterType."
        )
    provider_id = raw.get("providerId") or raw.get("provider_id")
    if not isinstance(provider_id, str) or not provider_id:
        provider_id = _provider_id_for_adapter(adapter_type)
    fallback_policy = raw.get("fallbackPolicy") or raw.get("fallback_policy")
    if not isinstance(fallback_policy, str) or not fallback_policy:
        fallback_policy = "explicit_only"
    return _assignment_from_adapter(
        role=role,
        adapter_type=adapter_type,
        provider_id=provider_id,
        source=source,
        target_id=target_id,
        fallback_policy=fallback_policy,
    )


def _assignment_from_adapter(
    *,
    role: str,
    adapter_type: str,
    provider_id: str,
    source: str,
    target_id: Optional[str],
    fallback_policy: str,
) -> ProviderAssignment:
    if adapter_type not in SUPPORTED_PROVIDER_ADAPTERS:
        raise ProviderAssignmentError(
            f"Unsupported provider assignment adapterType: {adapter_type}"
        )
    return ProviderAssignment(
        role=role,
        adapter_type=adapter_type,
        provider_id=provider_id,
        source=source,
        target_id=target_id,
        supported_mode=ROLE_SUPPORTED_MODES.get(role, "write"),
        fallback_policy=fallback_policy,
    )


def _configured_matrix() -> dict[str, Any]:
    raw = os.environ.get(PROVIDER_ASSIGNMENT_MATRIX_ENV, "").strip()
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ProviderAssignmentError(
            f"Invalid {PROVIDER_ASSIGNMENT_MATRIX_ENV}: {exc.msg}"
        ) from exc
    if not isinstance(parsed, dict):
        raise ProviderAssignmentError(
            f"Invalid {PROVIDER_ASSIGNMENT_MATRIX_ENV}: expected JSON object."
        )
    return parsed


def _role_for_task(plan: dict[str, Any], agent: Agent) -> str:
    assigned_role = plan.get("assignedRole") or plan.get("assigned_role")
    if isinstance(assigned_role, str) and assigned_role:
        return assigned_role
    return agent.role


def _target_id_for_task(plan: dict[str, Any]) -> Optional[str]:
    target_id = plan.get("targetId") or plan.get("target_id")
    return target_id if isinstance(target_id, str) and target_id else None


def _provider_id_for_adapter(
    adapter_type: str,
    agent: Optional[Agent] = None,
) -> str:
    if adapter_type == "codex":
        return "local-codex-cli"
    if adapter_type == "claude_code":
        return "local-claude-code-cli"
    if adapter_type == "scripted_mock":
        return "local-scripted-mock" if agent is None else agent.provider
    return agent.provider if agent is not None else adapter_type


def _plan_json(task: Task) -> dict[str, Any]:
    try:
        parsed = json.loads(task.plan_json)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}
