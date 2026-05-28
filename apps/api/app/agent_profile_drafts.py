from __future__ import annotations

import json
import re
from dataclasses import dataclass

from sqlmodel import Session as DbSession
from sqlmodel import select

from app.agent_capabilities import validate_capability_tags, validate_supported_modes
from app.models import AgentProfileDraft, utc_now
from app.provider_configs import list_provider_configs


class AgentProfileDraftError(ValueError):
    pass


@dataclass(frozen=True)
class AgentProfileDraftInput:
    display_name: str
    role: str
    adapter_type: str
    provider_id: str
    capability_tags: list[str]
    supported_targets: list[str]
    supported_modes: list[str]
    description: str
    avatar_initials: str | None = None
    safe_for_write: bool = False
    safe_for_review: bool = True
    status: str = "draft_only"
    shell_commands: list[str] | None = None
    tool_permissions: list[str] | None = None
    unrestricted_filesystem_access: bool = False


DRAFT_STATUSES = {"draft_only", "disabled"}
UNSAFE_TOOL_PERMISSIONS = {
    "arbitrary_shell",
    "host_shell",
    "shell",
    "unrestricted_filesystem",
    "filesystem_unrestricted",
    "secrets",
    "production_deploy",
    "docker",
    "network_unrestricted",
}
_SAFE_ID_PATTERN = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_-]{1,63}$")


def create_agent_profile_draft(
    db: DbSession,
    *,
    workspace_id: str,
    draft_input: AgentProfileDraftInput,
) -> AgentProfileDraft:
    _validate_safe_draft(draft_input)
    draft = AgentProfileDraft(
        workspace_id=workspace_id,
        display_name=draft_input.display_name.strip(),
        avatar_initials=_avatar_initials(draft_input),
        role=draft_input.role.strip(),
        adapter_type=draft_input.adapter_type,
        provider_id=draft_input.provider_id,
        capability_tags_json=json.dumps(draft_input.capability_tags),
        supported_targets_json=json.dumps(draft_input.supported_targets),
        supported_modes_json=json.dumps(draft_input.supported_modes),
        safe_for_write=False,
        safe_for_review=draft_input.status == "draft_only",
        description=draft_input.description.strip(),
        status=draft_input.status,
    )
    db.add(draft)
    db.commit()
    db.refresh(draft)
    return draft


def list_agent_profile_drafts(
    db: DbSession,
    *,
    workspace_id: str,
) -> list[AgentProfileDraft]:
    return list(
        db.exec(
            select(AgentProfileDraft)
            .where(AgentProfileDraft.workspace_id == workspace_id)
            .order_by(AgentProfileDraft.created_at)
        )
    )


def capability_tags_for_draft(draft: AgentProfileDraft) -> list[str]:
    return _json_list(draft.capability_tags_json)


def supported_targets_for_draft(draft: AgentProfileDraft) -> list[str]:
    return _json_list(draft.supported_targets_json)


def supported_modes_for_draft(draft: AgentProfileDraft) -> list[str]:
    return _json_list(draft.supported_modes_json)


def _validate_safe_draft(draft_input: AgentProfileDraftInput) -> None:
    if not draft_input.display_name.strip():
        raise AgentProfileDraftError("Draft agent displayName is required.")
    if not _SAFE_ID_PATTERN.fullmatch(draft_input.role.strip()):
        raise AgentProfileDraftError("Draft agent role must be a safe identifier.")

    provider = _provider_for(draft_input.provider_id)
    if provider is None:
        raise AgentProfileDraftError(f"Unknown providerId: {draft_input.provider_id}")
    if provider.adapter_type != draft_input.adapter_type:
        raise AgentProfileDraftError(
            "Draft agent adapterType must match the selected provider."
        )

    capability_tags = validate_capability_tags(
        draft_input.capability_tags,
        source="AgentProfileDraft",
    )
    supported_modes = validate_supported_modes(
        draft_input.supported_modes,
        source="AgentProfileDraft",
    )
    if "code_write" in capability_tags or draft_input.safe_for_write:
        raise AgentProfileDraftError("Draft agents are not write-enabled by default.")
    if draft_input.status not in DRAFT_STATUSES:
        raise AgentProfileDraftError("Draft agent status must be draft_only or disabled.")
    if draft_input.status == "draft_only" and not draft_input.safe_for_review:
        raise AgentProfileDraftError("Draft-only agents must remain review-safe.")
    if not set(supported_modes).issubset({"review", "read_only", "debug"}):
        raise AgentProfileDraftError("Draft agents may only use review/read_only/debug modes.")
    if not draft_input.supported_targets:
        raise AgentProfileDraftError("Draft agents must declare at least one supported target.")
    for target in draft_input.supported_targets:
        if not _SAFE_ID_PATTERN.fullmatch(target):
            raise AgentProfileDraftError("Draft agent supportedTargets must be target IDs.")

    if draft_input.shell_commands:
        raise AgentProfileDraftError("Draft agents cannot define shell commands.")
    unsafe_permissions = set(draft_input.tool_permissions or []) & UNSAFE_TOOL_PERMISSIONS
    if unsafe_permissions:
        raise AgentProfileDraftError("Draft agents cannot request unsafe tool permissions.")
    if draft_input.unrestricted_filesystem_access:
        raise AgentProfileDraftError(
            "Draft agents cannot request unrestricted filesystem access."
        )


def _provider_for(provider_id: str):
    return next(
        (provider for provider in list_provider_configs() if provider.provider_id == provider_id),
        None,
    )


def _avatar_initials(draft_input: AgentProfileDraftInput) -> str:
    if draft_input.avatar_initials and draft_input.avatar_initials.strip():
        return draft_input.avatar_initials.strip()[:3].upper()
    words = re.findall(r"[A-Za-z0-9]+", draft_input.display_name)
    if len(words) >= 2:
        return f"{words[0][0]}{words[1][0]}".upper()
    if words:
        return words[0][:2].upper()
    return draft_input.role[:2].upper()


def _json_list(raw: str) -> list[str]:
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        return []
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if isinstance(item, str)]
