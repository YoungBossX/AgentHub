import json
from pathlib import Path
from typing import Any, Optional

from app.models import Agent, Task
from app.target_registry import (
    DEMO_BACKEND_TARGET_ID,
    DEMO_FRONTEND_TARGET_ID,
    TargetProject,
    TargetRegistryError,
    get_related_backend_target,
    get_target,
)


def build_role_instruction(
    task: Task,
    agent: Agent,
    context_pack: dict[str, Any],
) -> str:
    role = _effective_role(task, agent, context_pack)
    plan = _task_plan(context_pack)
    original_request = str(context_pack.get("originalUserRequest") or task.title).strip()
    target = _target_for_role(role, plan, context_pack)
    sections = [
        _role_body(role, task, plan, original_request, target),
        _target_section(role, plan, target),
        _contract_guidance(role, plan, target),
        _context_section(context_pack),
        _guardrails(role, target),
    ]
    return "\n\n".join(section for section in sections if section)


def _role_body(
    role: str,
    task: Task,
    plan: dict[str, Any],
    original_request: str,
    target: TargetProject,
) -> str:
    if target.type == "platform":
        return _platform_body(original_request, target)
    if role == "frontend":
        return _frontend_body(task, plan, original_request, target)
    if role == "backend":
        return _backend_body(original_request, target)
    if role in {"qa", "review"}:
        return _review_body(original_request, target)
    if role == "orchestrator":
        return _manager_body(original_request)
    return (
        f"You are the {role} agent for AgentHub.\n"
        f"Original user request: {original_request}\n"
        "Use the session context pack below and stay within the assigned safe target."
    )


def _frontend_body(
    task: Task,
    plan: dict[str, Any],
    original_request: str,
    target: TargetProject,
) -> str:
    allowed_path = _primary_allowed_path(target)
    if target.target_id != DEMO_FRONTEND_TARGET_ID:
        return _external_frontend_body(original_request, target)

    target_kind = plan.get("target")
    if task.intent_type == "frontend_change" and target_kind == "login_page":
        return (
            "You are the Frontend Agent for AgentHub's demo app.\n"
            f"Original user request: {original_request}\n"
            "In apps/demo/src/App.tsx, find the element with "
            'data-agenthub-target="login-page-slot" and replace only that slot '
            "content with a compact login form containing email and password "
            "fields. Keep the existing deterministic data-agenthub-target "
            "attributes intact, do not edit unrelated files, do not read the "
            "OpenSpec change, and do not run setup or dependency install "
            "commands."
        )

    if task.intent_type == "frontend_change" and target_kind == "primary_action_button_text":
        target_text = str(plan.get("targetText") or "").strip()
        return (
            "You are the Frontend Agent for AgentHub's demo app.\n"
            f"Original user request: {original_request}\n"
            "In apps/demo/src/App.tsx, find the element with "
            'data-agenthub-target="primary-action-button" and change only its '
            f'visible button text to "{target_text}". Keep all deterministic '
            "data-agenthub-target attributes intact, do not edit unrelated "
            "files, do not read the OpenSpec change, and do not run setup or "
            "dependency install commands."
        )

    if task.intent_type == "frontend_change" and target_kind == "demo_heading_text":
        target_text = str(plan.get("targetText") or "").strip()
        return (
            "You are the Frontend Agent for AgentHub's demo app.\n"
            f"Original user request: {original_request}\n"
            "In apps/demo/src/App.tsx, find the h1 with id=\"demo-heading\" "
            f'and change only its visible heading text to "{target_text}". '
            "Keep deterministic data-agenthub-target attributes intact, do "
            "not edit unrelated files, do not read the OpenSpec change, and "
            "do not run setup or dependency install commands."
        )

    if task.intent_type == "frontend_change" and target_kind == "theme_accent_color":
        target_text = str(plan.get("targetText") or "").strip()
        return (
            "You are the Frontend Agent for AgentHub's demo app.\n"
            f"Original user request: {original_request}\n"
            "In apps/demo/src/styles.css, change only the demo app accent color "
            f'to "{target_text}". Keep the change bounded to existing color '
            "values used by the eyebrow, slot label, primary action, hover "
            "state, and soft blue background accent. Do not edit unrelated "
            "files, do not read the OpenSpec change, and do not run setup or "
            "dependency install commands."
        )

    if task.intent_type == "frontend_change" and target_kind == "simple_input_field":
        target_text = str(plan.get("targetText") or "").strip()
        return (
            "You are the Frontend Agent for AgentHub's demo app.\n"
            f"Original user request: {original_request}\n"
            "In apps/demo/src/App.tsx, add exactly one simple labeled input "
            f'field for "{target_text}" inside the element with '
            'data-agenthub-target="login-page-slot". Keep deterministic '
            "data-agenthub-target attributes intact, do not edit unrelated "
            "files, do not read the OpenSpec change, and do not run setup or "
            "dependency install commands."
        )

    if task.intent_type == "frontend_change" and target_kind == "status_help_text":
        target_text = str(plan.get("targetText") or "").strip()
        return (
            "You are the Frontend Agent for AgentHub's demo app.\n"
            f"Original user request: {original_request}\n"
            "In apps/demo/src/App.tsx, add one short status or help text line "
            f'with the copy "{target_text}" inside the mutation card. Keep '
            "deterministic data-agenthub-target attributes intact, do not edit "
            "unrelated files, do not read the OpenSpec change, and do not run "
            "setup or dependency install commands."
        )

    if task.intent_type == "frontend_change" and target_kind == "layout_copy":
        target_text = str(plan.get("targetText") or "").strip()
        return (
            "You are the Frontend Agent for AgentHub's demo app.\n"
            f"Original user request: {original_request}\n"
            "In apps/demo/src/App.tsx, update only one short layout copy block "
            f'to "{target_text}". Prefer the lede or slot copy text, keep the '
            "existing component structure and deterministic targets intact, "
            "do not edit unrelated files, do not read the OpenSpec change, and "
            "do not run setup or dependency install commands."
        )

    files = plan.get("files")
    file_list = ", ".join(files) if isinstance(files, list) else allowed_path
    return (
        "You are the Frontend Agent for AgentHub's demo app.\n"
        f"Original user request: {original_request}\n"
        "Implement a meaningful, bounded frontend change for that request. "
        "Use the session context pack to understand prior changes and follow-up "
        f"intent. Work only inside {allowed_path}, preferably in the existing "
        f"React demo files: {file_list}. Preserve the existing Vite React demo "
        "app boundary. Keep the diff focused and previewable."
    )


def _backend_body(original_request: str, target: TargetProject) -> str:
    if target.target_id != DEMO_BACKEND_TARGET_ID:
        return _external_backend_body(original_request, target)

    target_exists = _target_root_exists(target)
    allowed_path = _primary_allowed_path(target)
    if target_exists:
        availability = (
            f"The safe demo backend target {target.root} exists. Work only inside "
            f"{allowed_path} for backend application code. Current scaffold is a "
            "minimal FastAPI contacts API with GET /health, GET /contacts, and "
            "POST /contacts."
        )
    else:
        availability = (
            f"The safe demo backend target {target.root} is not available yet. "
            f"If {target.root} is missing, do not pretend backend execution is "
            "possible. Report that backend execution is blocked until P6-4 adds "
            "the safe demo backend target."
        )
    return (
        "You are the Backend Agent for AgentHub's demo app.\n"
        f"Original user request: {original_request}\n"
        f"{availability} Do not edit apps/api; that is the AgentHub platform "
        "backend/control plane."
    )


def _review_body(original_request: str, target: TargetProject) -> str:
    if target.target_id.startswith("external-"):
        return (
            "You are the QA / Review Agent for a registered external AgentHub target.\n"
            f"Original user request: {original_request}\n"
            f"Review target `{target.target_id}` at root `{target.root}`. "
            "This task is read-oriented by default. Inspect the latest diff, "
            "changed files, selected artifact, scheduler state, and configured "
            "check/test/build evidence when present. Verify that changes stay "
            "inside allowed paths and do not touch denied paths. Report advisory "
            "findings honestly; do not claim validation success if command "
            "evidence is missing or failed."
        )
    return (
        "You are the QA / Review Agent for AgentHub.\n"
        f"Original user request: {original_request}\n"
        "This task is read-oriented by default. Review the latest diff, changed "
        "files, ledger, preview, deploy, and prior review context. Produce "
        "advisory findings with status passed, warning, or failed; do not block "
        "preview or mock deploy in v1."
    )


def _external_frontend_body(original_request: str, target: TargetProject) -> str:
    command_hint = _command_hint(target)
    return (
        "You are the Frontend Agent for a registered external AgentHub target.\n"
        f"Original user request: {original_request}\n"
        f"Target root: {target.root}\n"
        f"Allowed paths: {', '.join(target.allowed_paths)}\n"
        f"Denied paths: {', '.join(target.denied_paths)}\n"
        f"Project type: {target.project_type or target.type}; "
        f"framework: {target.detected_framework or 'unknown'}; "
        f"package manager: {target.package_manager or 'unknown'}.\n"
        "Implement a meaningful, bounded frontend change for the request inside "
        "the registered external target only. Preserve the existing framework "
        "and project structure. Do not assume apps/demo, apps/demo-api, or any "
        "AgentHub built-in demo path unless the registered target metadata says "
        "so. "
        f"{command_hint}"
    )


def _external_backend_body(original_request: str, target: TargetProject) -> str:
    command_hint = _command_hint(target)
    return (
        "You are the Backend Agent for a registered external AgentHub target.\n"
        f"Original user request: {original_request}\n"
        f"Target root: {target.root}\n"
        f"Allowed paths: {', '.join(target.allowed_paths)}\n"
        f"Denied paths: {', '.join(target.denied_paths)}\n"
        f"Project type: {target.project_type or target.type}; "
        f"framework: {target.detected_framework or 'unknown'}; "
        f"package manager: {target.package_manager or 'unknown'}.\n"
        "Implement backend/API changes only inside the registered external "
        "target. Do not edit AgentHub platform backend `apps/api` unless the "
        "task explicitly targets `agenthub-platform` in platform maintenance "
        "mode. "
        f"{command_hint}"
    )


def _command_hint(target: TargetProject) -> str:
    commands = [
        command
        for command in [
            target.check_command,
            target.test_command,
            target.build_command,
            target.preview_command,
        ]
        if command
    ]
    if not commands:
        return "No validation commands are configured; do not invent successful validation."
    return (
        "Configured validation/evidence commands: "
        f"{', '.join(commands)}. Run only configured commands when validation is requested."
    )


def _manager_body(original_request: str) -> str:
    return (
        "You are the Manager / Orchestrator for AgentHub.\n"
        f"Original user request: {original_request}\n"
        "Use the session context pack to decide whether to answer, create "
        "bounded frontend/backend/QA/review tasks, ask a clarification "
        "question, or reject unsupported requests honestly. Do not execute "
        "unsafe work directly."
    )


def _platform_body(original_request: str, target: TargetProject) -> str:
    validation = target.test_command or "pnpm check && pnpm test"
    return (
        "You are working in AgentHub Platform Maintenance Mode.\n"
        f"Original user request: {original_request}\n"
        f"Target `{target.target_id}` requires explicit platform mode and "
        "approval before adapter execution. Treat this as control-plane work, "
        f"use stricter validation (`{validation}`), and do not route ordinary "
        "application backend work here."
    )


def _target_section(
    role: str,
    plan: dict[str, Any],
    target: TargetProject,
) -> str:
    lines = [
        "Target Project:",
        f"- targetId: {target.target_id}",
        f"- name: {target.name}",
        f"- type: {target.type}",
        f"- root: {target.root}",
        f"- allowedPaths: {', '.join(target.allowed_paths)}",
        f"- deniedPaths: {', '.join(target.denied_paths)}",
    ]
    if target.dev_command:
        lines.append(f"- devCommand: {target.dev_command}")
    if target.test_command:
        lines.append(f"- testCommand: {target.test_command}")
    if target.check_command:
        lines.append(f"- checkCommand: {target.check_command}")
    if target.build_command:
        lines.append(f"- buildCommand: {target.build_command}")
    if target.preview_command:
        lines.append(f"- previewCommand: {target.preview_command}")
    if target.base_url:
        lines.append(f"- baseUrl: {target.base_url}")
    if target.package_manager:
        lines.append(f"- packageManager: {target.package_manager}")
    if target.detected_framework:
        lines.append(f"- detectedFramework: {target.detected_framework}")
    if target.project_type:
        lines.append(f"- projectType: {target.project_type}")
    if target.analysis_status:
        lines.append(f"- analysisStatus: {target.analysis_status}")
    if target.requires_platform_mode:
        lines.append("- requiresPlatformMode: true")
    if target.requires_approval:
        lines.append("- requiresApproval: true")

    if role == "frontend":
        backend_target = _backend_target_for_frontend(plan, target)
        if backend_target.base_url:
            lines.append(f"- relatedBackendTargetId: {backend_target.target_id}")
            lines.append(f"- relatedBackendBaseUrl: {backend_target.base_url}")

    return "\n".join(lines)


def _context_section(context_pack: dict[str, Any]) -> str:
    return (
        "Session Context Pack:\n"
        "```json\n"
        f"{json.dumps(context_pack, ensure_ascii=True, sort_keys=True, indent=2)}\n"
        "```"
    )


def _contract_guidance(
    role: str,
    plan: dict[str, Any],
    target: TargetProject,
) -> str:
    contract = plan.get("appContract")
    if not isinstance(contract, dict):
        return ""
    contract_id = str(contract.get("contractId") or "shared contract")
    app_name = str(contract.get("appName") or "the bounded app")
    backend_target = _backend_target_for_frontend(plan, target)
    demo_api_base_url = backend_target.base_url or str(contract.get("demoApiBaseUrl") or "")
    if role == "backend":
        return (
            f"Shared App Contract: Use `{contract_id}` for {app_name}. "
            "Implement only backend API behavior described by the contract, "
            f"targeting `{target.target_id}` ({_primary_allowed_path(target)})."
        )
    if role == "frontend":
        return (
            f"Shared App Contract: Use `{contract_id}` for {app_name}. "
            "Implement only frontend UI behavior described by the contract, "
            f"targeting `{target.target_id}` ({_primary_allowed_path(target)}) "
            "and integrating with the demo API shape. "
            f"Use the `{backend_target.target_id}` base URL `{demo_api_base_url}` "
            "for app data calls. Do not call the AgentHub platform API at http://localhost:8000 "
            "or http://127.0.0.1:8000 for generated app data."
        )
    if role in {"qa", "review"}:
        return (
            f"Shared App Contract: Review backend and frontend work against "
            f"`{contract_id}` for {app_name}. Treat findings as advisory in v1."
        )
    if role == "orchestrator":
        return (
            f"Shared App Contract: Maintain `{contract_id}` for {app_name} and "
            "keep backend, frontend, and review tasks aligned to it."
        )
    return f"Shared App Contract: Use `{contract_id}` for {app_name}."


def _guardrails(role: str, target: TargetProject) -> str:
    role_specific = []
    if role == "frontend":
        role_specific.append(
            f"Work only inside {', '.join(target.allowed_paths)} unless a later task explicitly expands the safe target."
        )
    if role == "backend":
        role_specific.append("Do not modify apps/api or any AgentHub platform backend files.")
    if role in {"qa", "review"}:
        role_specific.append("Stay read-oriented unless an explicit future task allows write remediation.")
    if target.requires_platform_mode:
        role_specific.append("Platform maintenance requires explicit platform mode and approval.")

    guardrails = [
        "Do not edit .env files, secrets, node_modules, .git, or host paths outside the assigned worktree.",
        "Do not run setup, dependency install, production deploy, or arbitrary host commands.",
        "Do not read or modify OpenSpec files as part of adapter execution.",
        "Do not claim success unless files or review evidence actually support it.",
        *role_specific,
    ]
    return "Guardrails:\n" + "\n".join(f"- {item}" for item in guardrails)


def _effective_role(
    task: Task,
    agent: Agent,
    context_pack: dict[str, Any],
) -> str:
    plan = _task_plan(context_pack)
    assigned_role = plan.get("assignedRole")
    if isinstance(assigned_role, str) and assigned_role in {"frontend", "backend", "qa", "review", "orchestrator"}:
        return assigned_role
    if task.intent_type == "review":
        return "review"
    return agent.role


def _task_plan(context_pack: dict[str, Any]) -> dict[str, Any]:
    current_task = context_pack.get("currentTask")
    if not isinstance(current_task, dict):
        return {}
    plan = current_task.get("plan")
    return plan if isinstance(plan, dict) else {}


def _target_for_role(
    role: str,
    plan: dict[str, Any],
    context_pack: dict[str, Any],
) -> TargetProject:
    explicit_target = _string_value(plan.get("targetId"))
    contract = plan.get("appContract")
    if explicit_target is None and isinstance(contract, dict):
        if role == "frontend":
            explicit_target = _string_value(plan.get("frontendTargetId") or contract.get("frontendTargetId"))
        elif role == "backend":
            explicit_target = _string_value(plan.get("backendTargetId") or contract.get("backendTargetId"))
        elif role in {"qa", "review"}:
            explicit_target = _string_value(plan.get("targetId") or contract.get("frontendTargetId"))

    if explicit_target:
        packed_target = _target_from_context_pack(context_pack, explicit_target)
        if packed_target is not None:
            return packed_target
        try:
            return get_target(explicit_target)
        except TargetRegistryError:
            pass

    if role == "backend":
        return get_target(DEMO_BACKEND_TARGET_ID)
    if role == "frontend":
        return get_target(DEMO_FRONTEND_TARGET_ID)
    if role in {"qa", "review"}:
        return get_target(DEMO_FRONTEND_TARGET_ID)
    if role == "orchestrator":
        return get_target(DEMO_FRONTEND_TARGET_ID)
    return get_target(DEMO_FRONTEND_TARGET_ID)


def _target_from_context_pack(
    context_pack: dict[str, Any],
    target_id: str,
) -> Optional[TargetProject]:
    for key in ("targetProject",):
        value = context_pack.get(key)
        if isinstance(value, dict) and value.get("targetId") == target_id:
            return _target_from_context(value)

    related = context_pack.get("relatedTargetProjects")
    if isinstance(related, list):
        for value in related:
            if isinstance(value, dict) and value.get("targetId") == target_id:
                return _target_from_context(value)
    return None


def _target_from_context(value: dict[str, Any]) -> TargetProject:
    return TargetProject(
        target_id=str(value.get("targetId") or ""),
        name=str(value.get("name") or "External Target"),
        type=str(value.get("type") or "frontend"),
        root=str(value.get("root") or ""),
        allowed_paths=tuple(_string_list(value.get("allowedPaths"))),
        denied_paths=tuple(_string_list(value.get("deniedPaths"))),
        allowed_agents=tuple(_string_list(value.get("allowedAgents"))),
        dev_command=_string_value(value.get("devCommand")),
        test_command=_string_value(value.get("testCommand")),
        check_command=_string_value(value.get("checkCommand")),
        build_command=_string_value(value.get("buildCommand")),
        preview_command=_string_value(value.get("previewCommand")),
        base_url=_string_value(value.get("baseUrl")),
        package_manager=_string_value(value.get("packageManager")),
        detected_framework=_string_value(value.get("detectedFramework")),
        project_type=_string_value(value.get("projectType")),
        analysis_status=_string_value(value.get("analysisStatus")),
        requires_platform_mode=bool(value.get("requiresPlatformMode")),
        requires_approval=bool(value.get("requiresApproval")),
        related_target_ids=tuple(_string_list(value.get("relatedTargetIds"))),
    )


def _backend_target_for_frontend(plan: dict[str, Any], frontend_target: TargetProject) -> TargetProject:
    contract = plan.get("appContract")
    backend_target_id = _string_value(plan.get("backendTargetId"))
    if backend_target_id is None and isinstance(contract, dict):
        backend_target_id = _string_value(contract.get("backendTargetId"))
    if backend_target_id:
        try:
            return get_target(backend_target_id)
        except TargetRegistryError:
            pass
    if frontend_target.target_id == DEMO_FRONTEND_TARGET_ID:
        return get_related_backend_target(frontend_target.target_id)
    return get_target(DEMO_BACKEND_TARGET_ID)


def _primary_allowed_path(target: TargetProject) -> str:
    return target.allowed_paths[0] if target.allowed_paths else target.root


def _target_root_exists(target: TargetProject) -> bool:
    if target.target_id == DEMO_BACKEND_TARGET_ID:
        return (_repo_root() / target.root / "app/main.py").exists()
    return (_repo_root() / target.root).exists()


def _string_value(value: Any) -> Optional[str]:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]
