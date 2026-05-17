import json
import re
from dataclasses import dataclass
from typing import Optional

from sqlmodel import Session as DbSession
from sqlmodel import select

from app.models import Agent, Message, Task
from app.repositories import create_session_message, list_session_tasks

SUPPORTED_MENTION_ROLES = {"orchestrator", "frontend", "backend", "qa"}
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


class MentionParseError(ValueError):
    pass


@dataclass(frozen=True)
class ParsedMentions:
    roles: list[str]


@dataclass(frozen=True)
class FollowupChange:
    target: str
    target_text: str


def parse_mentions(db: DbSession, content: str) -> ParsedMentions:
    roles: list[str] = []
    for raw_role in MENTION_PATTERN.findall(content):
        role = raw_role.lower()
        mention = f"@{raw_role}"
        if role not in SUPPORTED_MENTION_ROLES:
            raise MentionParseError(f"Unknown mention {mention}. Supported mentions are @orchestrator, @frontend, @backend, and @qa.")

        agent = db.exec(select(Agent).where(Agent.role == role)).first()
        if agent is None or not agent.enabled:
            raise MentionParseError(f"Mention {mention} is disabled or unavailable.")

        if role not in roles:
            roles.append(role)

    return ParsedMentions(roles=roles)


def plan_for_message(
    db: DbSession,
    message: Message,
    content: str,
) -> list[Task]:
    parsed = parse_mentions(db, content)
    existing_tasks = list_session_tasks(db, message.session_id)

    followup = parse_followup_change(content)
    if followup is not None and existing_tasks:
        return _create_followup_task(db, message, followup, existing_tasks)

    if "orchestrator" not in parsed.roles:
        return []

    if "login page" not in content.lower() or "demo app" not in content.lower():
        return []

    if existing_tasks:
        return []

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
        {
            "title": "Plan the login page change",
            "intent_type": "planning",
            "role": "orchestrator",
            "priority": 0,
            "plan": {
                "target": "login_page",
                "summary": "Confirm the demo login-page scope and execution order.",
                "parallelGroup": None,
            },
        },
        {
            "title": "Build the Vite React login page",
            "intent_type": "frontend_change",
            "role": "frontend",
            "priority": 1,
            "plan": {
                "target": "login_page",
                "files": ["apps/demo/src/App.tsx", "apps/demo/src/styles.css"],
                "parallelGroup": None,
            },
        },
        {
            "title": "Review the login page demo path",
            "intent_type": "qa_review",
            "role": "qa",
            "priority": 2,
            "plan": {
                "target": "login_page",
                "checks": ["page renders", "button target remains deterministic"],
                "parallelGroup": None,
            },
        },
    ]

    tasks: list[Task] = []
    for index, spec in enumerate(task_specs):
        depends_on = [tasks[index - 1].id] if index > 0 else []
        task = Task(
            session_id=message.session_id,
            created_by_message_id=message.id,
            title=spec["title"],
            intent_type=spec["intent_type"],
            status="pending",
            priority=spec["priority"],
            plan_json=json.dumps(spec["plan"], separators=(",", ":")),
            depends_on_task_ids=json.dumps(depends_on, separators=(",", ":")),
            assigned_agent_id=agents[spec["role"]].id,
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


def _create_followup_task(
    db: DbSession,
    message: Message,
    followup: FollowupChange,
    existing_tasks: list[Task],
) -> list[Task]:
    frontend = db.exec(select(Agent).where(Agent.role == "frontend")).first()
    orchestrator = db.exec(select(Agent).where(Agent.role == "orchestrator")).first()
    if frontend is None or not frontend.enabled:
        raise MentionParseError("Follow-up planning requires the enabled frontend agent.")

    latest_task = existing_tasks[-1]
    priority = max(task.priority for task in existing_tasks) + 1
    target_label = (
        "primary button text"
        if followup.target == "primary_action_button_text"
        else "demo heading text"
    )
    task = Task(
        session_id=message.session_id,
        created_by_message_id=message.id,
        title=f"Change {target_label} to {followup.target_text}",
        intent_type="frontend_change",
        status="pending",
        priority=priority,
        plan_json=json.dumps(
            {
                "target": followup.target,
                "targetText": followup.target_text,
                "files": ["apps/demo/src/App.tsx"],
                "summary": f"Change only the {target_label}.",
                "parallelGroup": None,
            },
            separators=(",", ":"),
        ),
        depends_on_task_ids=json.dumps([latest_task.id], separators=(",", ":")),
        assigned_agent_id=frontend.id,
    )
    db.add(task)
    db.commit()
    db.refresh(task)

    if orchestrator is not None and orchestrator.enabled:
        summary = Message(
            session_id=message.session_id,
            sender_type="orchestrator",
            sender_id=orchestrator.id,
            content_md=f"I created a focused follow-up task to change the {target_label}.",
            message_kind="plan",
            parent_message_id=message.id,
        )
        create_session_message(db, _session_for_message(db, message), summary)

    return [task]


def _session_for_message(db: DbSession, message: Message):
    from app.models import Session

    session = db.get(Session, message.session_id)
    if session is None:
        raise MentionParseError("Session is unavailable for planning.")
    return session
