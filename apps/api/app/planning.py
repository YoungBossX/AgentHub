import json
import re
from dataclasses import dataclass

from sqlmodel import Session as DbSession
from sqlmodel import select

from app.models import Agent, Message, Task
from app.repositories import create_session_message, list_session_tasks

SUPPORTED_MENTION_ROLES = {"orchestrator", "frontend", "backend", "qa"}
MENTION_PATTERN = re.compile(r"@([A-Za-z][A-Za-z0-9_-]*)")


class MentionParseError(ValueError):
    pass


@dataclass(frozen=True)
class ParsedMentions:
    roles: list[str]


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
    if "orchestrator" not in parsed.roles:
        return []

    if "login page" not in content.lower() or "demo app" not in content.lower():
        return []

    if list_session_tasks(db, message.session_id):
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


def _session_for_message(db: DbSession, message: Message):
    from app.models import Session

    session = db.get(Session, message.session_id)
    if session is None:
        raise MentionParseError("Session is unavailable for planning.")
    return session
