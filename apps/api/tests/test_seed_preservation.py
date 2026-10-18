from sqlalchemy import text
from sqlmodel import Session, select
from migration_fixtures import memory_engine, current_unversioned
from app.models import Agent, Workspace
from app.seed import seed_demo_data


def test_repeated_seed_inserts_only_missing_records():
    engine = memory_engine()
    current_unversioned(engine)
    with Session(engine) as db:
        seed_demo_data(db)
        agent = db.exec(select(Agent).where(Agent.role == 'frontend')).one()
        agent.name, agent.enabled = '我的前端', False
        agent.adapter_type, agent.provider = 'claude_code', 'custom'
        agent.system_prompt = '保留用户提示词'
        workspace = db.exec(select(Workspace)).one()
        workspace.root_path, workspace.default_branch = 'my-project', 'feature/preserve'
        db.add(agent); db.add(workspace); db.commit()
        before_agent = tuple(db.execute(text('SELECT * FROM agent WHERE id=:id'), {'id': agent.id}).one())
        before_workspace = tuple(db.execute(text('SELECT * FROM workspace')).one())
        seed_demo_data(db)
        seed_demo_data(db)
        assert tuple(db.execute(text('SELECT * FROM agent WHERE id=:id'), {'id': agent.id}).one()) == before_agent
        assert tuple(db.execute(text('SELECT * FROM workspace')).one()) == before_workspace
        assert len(db.exec(select(Agent)).all()) == 4
