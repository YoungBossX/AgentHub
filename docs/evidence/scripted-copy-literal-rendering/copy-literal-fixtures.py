import asyncio
import hashlib
import json
import runpy
import sys
from pathlib import Path

repo = Path("X:/Git_Clone/AgentHub")
temp = Path(__file__).parent
dest = temp / "copy-literal-fixtures"
dest.mkdir()
sys.path.insert(0, str(repo / "apps/api"))
test = runpy.run_path(str(repo / "apps/api/tests/test_scripted_mock_adapter.py"))
from sqlmodel import Session, SQLModel, create_engine
from app.models import TaskRun
from app.scripted_mock import ScriptedMockAdapter

engine = create_engine("sqlite://")
SQLModel.metadata.create_all(engine)
worktree = dest / "fixture-worktree"
app = worktree / "apps/demo/src/App.tsx"
app.parent.mkdir(parents=True)
original = (repo / "apps/demo/src/App.tsx").read_bytes()
styles = (repo / "apps/demo/src/styles.css").read_bytes()
app.with_name("styles.css").write_bytes(styles)
cases = []

async def generate():
    with Session(engine) as db:
        first = test["create_task_run"](db, worktree)
        values = [*test["COPY_LITERAL_VALUES"], r"C:\demo\1", "普通文案"]
        for target in ["primary_action_button_text", "demo_heading_text"]:
            for value in values:
                app.write_bytes(original)
                run = TaskRun(task_id=first.task_id, agent_id=first.agent_id, state="created", worktree_path=str(worktree))
                db.add(run); db.commit(); db.refresh(run)
                events = await test["run_adapter_event_stream"](db, ScriptedMockAdapter(), test["run_request"](
                    db, run, "Structured rendering fixture", {"target": target, "targetText": value},
                ))
                assert events[-1].event_type == "completed"
                assert app.with_name("styles.css").read_bytes() == styles
                data = app.read_bytes()
                cases.append({"target": target, "value": value, "source": data.decode("utf-8"),
                              "sourceSha256": hashlib.sha256(data).hexdigest()})

asyncio.run(generate())
(dest / "fixture-sources.json").write_text(json.dumps({
    "boundary": "Structured adapter fixtures with test ownership guard; not production route/lease evidence",
    "adapterSha256": hashlib.sha256((repo / "apps/api/app/scripted_mock.py").read_bytes()).hexdigest(),
    "generatorSha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    "cases": cases,
}, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
print(f"Prepared {len(cases)} actual adapter source fixtures")
