from sqlmodel import Session as DbSession
from sqlmodel import select

from app.models import Agent, User, Workspace

DEMO_USER_EMAIL = "demo@agenthub.local"
DEMO_WORKSPACE_NAME = "AgentHub Demo"
DEMO_WORKSPACE_ROOT = "apps/demo"


def seed_demo_data(db: DbSession) -> None:
    user = db.exec(select(User).where(User.email == DEMO_USER_EMAIL)).first()
    if user is None:
        db.add(
            User(
                email=DEMO_USER_EMAIL,
                name="Demo User",
                avatar_url=None,
            )
        )

    workspace = db.exec(
        select(Workspace).where(Workspace.name == DEMO_WORKSPACE_NAME)
    ).first()
    if workspace is None:
        db.add(
            Workspace(
                name=DEMO_WORKSPACE_NAME,
                repo_url="local://apps/demo",
                root_path=DEMO_WORKSPACE_ROOT,
                default_branch="main",
            )
        )
    else:
        workspace.repo_url = "local://apps/demo"
        workspace.root_path = DEMO_WORKSPACE_ROOT
        workspace.default_branch = "main"
        db.add(workspace)

    agents = [
        {
            "name": "Orchestrator",
            "role": "orchestrator",
            "adapter_type": "scripted_mock",
            "provider": "local",
            "default_model": None,
            "system_prompt": "Create small, visible coding plans for the demo.",
        },
        {
            "name": "Frontend Agent",
            "role": "frontend",
            "adapter_type": "codex",
            "provider": "local",
            "default_model": "codex-local",
            "system_prompt": "Implement focused Vite React UI changes.",
        },
        {
            "name": "Backend Agent",
            "role": "backend",
            "adapter_type": "codex",
            "provider": "local",
            "default_model": "codex-local",
            "system_prompt": "Implement focused FastAPI backend changes.",
        },
        {
            "name": "QA Agent",
            "role": "qa",
            "adapter_type": "scripted_mock",
            "provider": "local",
            "default_model": None,
            "system_prompt": "Verify the demo flow and report concise findings.",
        },
    ]

    for agent_data in agents:
        agent = db.exec(select(Agent).where(Agent.role == agent_data["role"])).first()
        if agent is None:
            db.add(
                Agent(
                    **agent_data,
                    capabilities_json="{}",
                    permission_profile_json="{}",
                    enabled=True,
                )
            )
        else:
            agent.enabled = True
            agent.name = agent_data["name"]
            agent.adapter_type = agent_data["adapter_type"]
            agent.provider = agent_data["provider"]
            agent.default_model = agent_data["default_model"]
            agent.system_prompt = agent_data["system_prompt"]
            db.add(agent)

    db.commit()


if __name__ == "__main__":
    from app.db import create_db_and_tables, engine

    create_db_and_tables()
    with DbSession(engine) as session:
        seed_demo_data(session)
    print("Seeded demo user, workspace, and agents.")
