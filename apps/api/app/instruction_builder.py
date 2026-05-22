import json
from pathlib import Path
from typing import Any

from app.models import Agent, Task


def build_role_instruction(
    task: Task,
    agent: Agent,
    context_pack: dict[str, Any],
) -> str:
    role = _effective_role(task, agent, context_pack)
    plan = _task_plan(context_pack)
    original_request = str(context_pack.get("originalUserRequest") or task.title).strip()
    sections = [
        _role_body(role, task, plan, original_request),
        _context_section(context_pack),
        _guardrails(role),
    ]
    return "\n\n".join(section for section in sections if section)


def _role_body(
    role: str,
    task: Task,
    plan: dict[str, Any],
    original_request: str,
) -> str:
    if role == "frontend":
        return _frontend_body(task, plan, original_request)
    if role == "backend":
        return _backend_body(original_request)
    if role in {"qa", "review"}:
        return _review_body(original_request)
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
) -> str:
    target = plan.get("target")
    if task.intent_type == "frontend_change" and target == "login_page":
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

    if task.intent_type == "frontend_change" and target == "primary_action_button_text":
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

    if task.intent_type == "frontend_change" and target == "demo_heading_text":
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

    if task.intent_type == "frontend_change" and target == "theme_accent_color":
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

    if task.intent_type == "frontend_change" and target == "simple_input_field":
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

    if task.intent_type == "frontend_change" and target == "status_help_text":
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

    if task.intent_type == "frontend_change" and target == "layout_copy":
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
    file_list = ", ".join(files) if isinstance(files, list) else "apps/demo/src"
    return (
        "You are the Frontend Agent for AgentHub's demo app.\n"
        f"Original user request: {original_request}\n"
        "Implement a meaningful, bounded frontend change for that request. "
        "Use the session context pack to understand prior changes and follow-up "
        "intent. Work only inside apps/demo/src, preferably in the existing "
        f"React demo files: {file_list}. Preserve the existing Vite React demo "
        "app boundary. Keep the diff focused and previewable."
    )


def _backend_body(original_request: str) -> str:
    target_exists = Path("apps/demo-api").exists()
    availability = (
        "The safe demo backend target apps/demo-api exists."
        if target_exists
        else "The safe demo backend target apps/demo-api is not available yet."
    )
    return (
        "You are the Backend Agent for AgentHub's demo app.\n"
        f"Original user request: {original_request}\n"
        f"{availability} Do not edit apps/api; that is the AgentHub platform "
        "backend/control plane. If apps/demo-api is missing, do not pretend "
        "backend execution is possible. Report that backend execution is "
        "blocked until P6-4 adds the safe demo backend target."
    )


def _review_body(original_request: str) -> str:
    return (
        "You are the QA / Review Agent for AgentHub.\n"
        f"Original user request: {original_request}\n"
        "This task is read-oriented by default. Review the latest diff, changed "
        "files, ledger, preview, deploy, and prior review context. Produce "
        "advisory findings with status passed, warning, or failed; do not block "
        "preview or mock deploy in v1."
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


def _context_section(context_pack: dict[str, Any]) -> str:
    return (
        "Session Context Pack:\n"
        "```json\n"
        f"{json.dumps(context_pack, ensure_ascii=True, sort_keys=True, indent=2)}\n"
        "```"
    )


def _guardrails(role: str) -> str:
    role_specific = []
    if role == "frontend":
        role_specific.append("Work only inside apps/demo/src unless a later task explicitly expands the safe target.")
    if role == "backend":
        role_specific.append("Do not modify apps/api or any AgentHub platform backend files.")
    if role in {"qa", "review"}:
        role_specific.append("Stay read-oriented unless an explicit future task allows write remediation.")

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
