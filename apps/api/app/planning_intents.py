import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from sqlmodel import Session as DbSession
from sqlmodel import select

from app.models import Agent, Message
from app.models import Session as AgentHubSession
from app.repositories import list_session_tasks
from app.target_registry import (
    DEMO_BACKEND_TARGET_ID,
    TargetProject,
    TargetRegistryError,
    get_target,
    get_target_for_workspace,
    list_targets_for_workspace,
)


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
        "app",
        "application",
        "system",
        "login",
        "management",
        "前端",
        "页面",
        "系统",
        "应用",
        "软件",
        "登录",
        "管理",
        "登记",
        "健康",
        "仪表盘",
        "按钮",
        "文案",
    ]
    return any(signal in normalized for signal in safe_signals)


def _requires_backend_target(content: str) -> bool:
    normalized = MENTION_PATTERN.sub("", content).lower()
    return any(
        signal in normalized
        for signal in (
            "backend",
            "api",
            "database",
            "server",
            "后端",
            "前后端",
            "数据库",
            "服务端",
            "接口",
        )
    )


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


def _fallback_external_target_for_role(
    db: DbSession,
    message: Message,
    role: str,
) -> Optional[TargetProject]:
    active = _active_external_target_for_role(db, message, role)
    if active is not None:
        return active
    session = _session_for_message(db, message)
    expected_type = "frontend" if role == "frontend" else "backend"
    targets = [
        target
        for target in list_targets_for_workspace(db, session.workspace_id)
        if target.target_id.startswith("external-")
        and target.type == expected_type
        and target.allows_agent(role)
        and not target.requires_platform_mode
        and not target.requires_approval
    ]
    preferred_ids = (
        ["external-agenthub-rehearsals", "external-frontend-agenthub-rehearsals"]
        if role == "frontend"
        else ["external-backend-agenthub-rehearsals"]
    )
    for preferred in preferred_ids:
        match = next((target for target in targets if target.target_id == preferred), None)
        if match is not None:
            return match
    return next(
        (
            target
            for target in targets
            if "agenthub-rehearsals" in target.target_id
            or "agenthub-rehearsals" in target.root
        ),
        targets[0] if targets else None,
    )


def _has_active_external_targets(
    db: DbSession,
    message: Message,
) -> bool:
    return (
        _active_external_target_for_role(db, message, "frontend") is not None
        or _active_external_target_for_role(db, message, "backend") is not None
    )


def _external_task_files(target: TargetProject) -> list[str]:
    root = Path(target.root)
    files: list[str] = []
    for allowed_path in target.allowed_paths:
        if allowed_path == "*":
            wildcard_files = _wildcard_external_task_files(target)
            files.extend(wildcard_files)
            continue
        allowed_root = root / allowed_path
        if allowed_root.is_file():
            files.append(allowed_path)
            continue
        for candidate in ("App.tsx", "App.jsx", "main.tsx", "main.jsx", "main.py", "server.ts"):
            if (allowed_root / candidate).exists():
                files.append(f"{allowed_path}/{candidate}")
                break
        else:
            files.append(allowed_path)
    return files[:4]


def _wildcard_external_task_files(target: TargetProject) -> list[str]:
    root = Path(target.root)
    candidates = (
        ("src/App.tsx", "src/main.tsx", "src/App.jsx", "src/main.jsx", "package.json")
        if target.type == "frontend"
        else ("app/main.py", "main.py", "requirements.txt", "pyproject.toml")
    )
    files = [path for path in candidates if (root / path).exists()]
    return files or ["*"]


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


def _primary_allowed_path(target: TargetProject) -> str:
    return target.allowed_paths[0] if target.allowed_paths else target.root


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _session_for_message(db: DbSession, message: Message):
    from app.models import Session

    session = db.get(Session, message.session_id)
    if session is None:
        raise MentionParseError("Session is unavailable for planning.")
    return session
