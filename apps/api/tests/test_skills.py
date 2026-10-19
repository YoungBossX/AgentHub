import copy
import json
import threading
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi import BackgroundTasks
from sqlmodel import select, SQLModel, Session as DbSession
from app.db_engine import create_runtime_engine as create_engine

from app.models import Agent, Message, Session, Task, TaskRun, Workspace, WorkspaceSkill
from app.skills import (SkillError, BINDING, catalog, capture_binding, instruction, message_selection,
    receipt, rebind_message_selection, save_package, validate_package, verify_binding)
from app.routes.skills import SkillSaveRequest
from app.routes.messages import create_message
from app.schemas import MessageCreateRequest
from app.task_runs import create_task_run, metrics_for_run
from test_task_runs import client, db_from_override, task_id
from test_native_review_artifacts import fixture as native_fixture


def request(**changes):
    package = catalog_stub()
    return SkillSaveRequest(markdown=changes.get("markdown", package["markdown"]),
        references=changes.get("references", {}), roles=changes.get("roles", ["frontend"]),
        defaultAgents=changes.get("defaultAgents", ["frontend"]), enabled=changes.get("enabled", True),
        expectedRevision=changes.get("expectedRevision", 0))


def catalog_stub():
    from app.skills import builtin_packages
    return builtin_packages()["react-form"]


def workspace(db):
    return db.exec(select(Workspace)).first()


@pytest.mark.parametrize("path", ["../escape.md", "/host.md", "references/../escape.md", "references/.env",
    "scripts/run.py", "assets/run.js", "references\\file.md", "references//file.md"])
def test_skill_resources_cannot_be_scripts_or_escape_paths(path):
    with pytest.raises(SkillError):
        validate_package(catalog_stub()["markdown"], {path: "text"}, ["frontend"], [], True)


@pytest.mark.parametrize("markdown", ["No frontmatter", "---\nname: Bad_Name\ndescription: x\n---\nbody",
    "---\nname: valid\ndescription: 123\n---\nbody", "---\nname: !!python/object/apply:os.system ['echo unsafe']\ndescription: x\n---\nbody",
    "---\nname: valid\ndescription: x\n---\n[missing](references/missing.md)", "x" * 16001])
def test_invalid_skill_packages_are_rejected(markdown):
    with pytest.raises(SkillError):
        validate_package(markdown, {}, ["frontend"], [], True)


def test_yaml_multiline_metadata_and_only_linked_references_are_loaded():
    markdown = "---\nname: api-guide\ndescription: >\n  Guide to API changes\nallowed-tools: Bash\n---\n[contract](references/api.md)\n"
    p = validate_package(markdown, {"references/api.md": "expected contract", "references/unused.md": "unused"}, ["frontend"], [], True)
    binding = {"role": "frontend", "packages": [p]}
    text = instruction(binding, "codex")
    assert "expected contract" in text and "unused" not in text and "allowed-tools" not in text


@pytest.mark.parametrize("budget", ["count", "bytes"])
@pytest.mark.parametrize("existing_rows", [False, True])
def test_concurrent_default_saves_cannot_overfill_aggregate(tmp_path, budget, existing_rows):
    engine = create_engine(f"sqlite:///{(tmp_path / 'race.sqlite').as_posix()}", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    def value(name, size=30, enabled=True):
        return request(markdown=f"---\nname: {name}\ndescription: Budget fixture\n---\n" + "x" * size, enabled=enabled)
    try:
        with DbSession(engine) as db:
            w = Workspace(name="Concurrent", root_path="unused", repo_url="local://unused", default_branch="main")
            db.add(w); db.commit(); workspace_id = w.id
            save_package(db, workspace_id, value("base-one", 10000 if budget == "bytes" else 30), 0)
            if budget == "count": save_package(db, workspace_id, value("base-two"), 0)
            if existing_rows:
                for name in ["candidate-one", "candidate-two"]:
                    save_package(db, workspace_id, value(name, enabled=False), 0)
        ready = threading.Barrier(2, timeout=10)
        def save(name):
            with DbSession(engine) as db:
                ready.wait()
                try:
                    save_package(db, workspace_id, value(name, 8000 if budget == "bytes" else 30), 1 if existing_rows else 0)
                    return "saved"
                except SkillError as exc:
                    assert "budget" in str(exc)
                    return "rejected"
        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = list(pool.map(save, ["candidate-one", "candidate-two"]))
        assert sorted(outcomes) == ["rejected", "saved"]
        with DbSession(engine) as db:
            binding = capture_binding(db, workspace_id=workspace_id, agent_id="agent", role="frontend")
            assert len(binding["packages"]) == (3 if budget == "count" else 2)
        # Prove the rolled-back connection leaves future configuration saves usable.
        with DbSession(engine) as db:
            save_package(db, workspace_id, value("base-one", enabled=False), 1)
    finally:
        engine.dispose()


def test_workspace_persistence_builtin_override_and_conflict(client):
    with db_from_override() as db:
        first = workspace(db)
        second = Workspace(name="Other", root_path="apps/demo", repo_url="local://apps/demo", default_branch="main")
        db.add(second); db.commit()
        saved = save_package(db, first.id, request(), 0)
        assert saved["revision"] == 1 and saved["source"] == "workspace"
        db.expire_all()
        assert catalog(db, first.id)[0]["defaultAgents"] == ["frontend"]
        assert catalog(db, second.id)[0]["revision"] == 0
        with pytest.raises(SkillError, match="changed"):
            save_package(db, first.id, request(), 0)
        updated = save_package(db, first.id, request(enabled=False, expectedRevision=1), 1)
        assert updated["revision"] == 2 and not updated["enabled"]


def test_unknown_or_cross_workspace_agent_binding_is_rejected(client):
    with db_from_override() as db:
        with pytest.raises(SkillError):
            save_package(db, workspace(db).id, request(defaultAgents=["unknown-profile"]), 0)
        with pytest.raises(SkillError):
            save_package(db, workspace(db).id, request(defaultAgents=["review"]), 0)


def test_real_run_freezes_defaults_and_request_uses_old_content(client):
    from app.run_engine import agent_run_request_for
    with db_from_override() as db:
        w = workspace(db)
        save_package(db, w.id, request(), 0)
        run = create_task_run(db, task_id())
        frozen = json.loads(run.metrics_json)[BINDING]
        assert frozen["packages"][0]["revision"] == 1
        save_package(db, w.id, request(markdown=catalog_stub()["markdown"] + "\nNEW POLICY", expectedRevision=1), 1)
        actual = agent_run_request_for(db, run, adapter_type="codex")
        assert "Skill: react-form" in actual.instruction and "NEW POLICY" not in actual.instruction
        assert "skillBinding" not in metrics_for_run(run)
        retry = capture_binding(db, workspace_id=w.id, agent_id=run.agent_id, role="frontend",
            task=db.get(Task, run.task_id), previous_run=run.id)
        assert retry == frozen
        assert instruction(frozen, "scripted_mock") == ""
        assert receipt(frozen, "scripted_mock")["skills"][0]["status"] == "unsupported_adapter"


def test_explicit_message_selection_freezes_before_planning_and_regeneration(client, monkeypatch):
    import app.routes.messages as routes
    monkeypatch.setattr(routes, "dispatch_message", lambda *_args: None)
    with db_from_override() as db:
        w = workspace(db); session = db.exec(select(Session)).first(); agent = db.exec(select(Agent).where(Agent.role == "frontend")).first()
        selected = create_message(session.id, MessageCreateRequest(contentMd="hello", skillIds=["react-form"]), BackgroundTasks(), db)
        original = db.get(Message, selected.id)
        save_package(db, w.id, request(markdown=catalog_stub()["markdown"] + "\nLATER", enabled=False), 0)
        frozen = capture_binding(db, workspace_id=w.id, agent_id=agent.id, role="frontend", message=original)
        assert "LATER" not in instruction(frozen, "codex")
        regenerated = Message(session_id=session.id, sender_type="user", content_md="hello")
        rebind_message_selection(original, regenerated)
        db.add(regenerated); db.commit()
        again = capture_binding(db, workspace_id=w.id, agent_id=agent.id, role="frontend", message=regenerated)
        assert again["packages"] == frozen["packages"] and again["messageId"] == regenerated.id
        empty = create_message(session.id, MessageCreateRequest(contentMd="hello", skillIds=[], context={"skillSelection": {"forged": True}}), BackgroundTasks(), db)
        assert capture_binding(db, workspace_id=w.id, agent_id=agent.id, role="frontend", message=db.get(Message, empty.id))["packages"] == []


def test_snapshot_identity_digest_and_role_compatibility(client):
    with db_from_override() as db:
        w = workspace(db); session = db.exec(select(Session)).first()
        message = Message(session_id=session.id, sender_type="user", content_md="hello")
        message.context_json = json.dumps({"skillSelection": message_selection(db, w.id, session.id, message.id, ["react-form"])})
        db.add(message); db.commit()
        binding = capture_binding(db, workspace_id=w.id, agent_id="a", role="review", message=message)
        assert instruction(binding, "claude_code") == ""
        assert receipt(binding, "claude_code")["skills"][0]["status"] == "incompatible_role"
        with pytest.raises(SkillError): verify_binding(binding, workspace_id="other", agent_id="a")
        tampered = copy.deepcopy(binding); tampered["packages"][0]["markdown"] += "changed"
        with pytest.raises(SkillError): verify_binding(tampered, workspace_id=w.id, agent_id="a")


def test_skills_api_rejects_invalid_selection_and_updates(client):
    with db_from_override() as db:
        w = workspace(db); session = db.exec(select(Session)).first()
        url = f"/workspaces/{w.id}/skills"
    assert client.get(url).status_code == 200
    assert len(client.get(url).json()) == 3
    assert client.put(url, json=request().model_dump(by_alias=True)).status_code == 200
    assert client.put(url, json=request().model_dump(by_alias=True)).status_code == 409
    assert client.post(f"/sessions/{session.id}/messages", json={"contentMd": "hello", "skillIds": ["unknown"]}).status_code == 400
    assert client.get("/workspaces/unknown/skills").status_code == 404


def test_packages_survive_sqlite_close_and_reopen(tmp_path):
    path = f"sqlite:///{(tmp_path / 'skills.sqlite').as_posix()}"
    engine = create_engine(path); SQLModel.metadata.create_all(engine)
    with DbSession(engine) as db:
        w = Workspace(name="Persist", root_path="apps/demo", repo_url="local://apps/demo", default_branch="main")
        db.add(w); db.commit(); workspace_id = w.id
        save_package(db, workspace_id, request(), 0)
    engine.dispose()
    engine = create_engine(path)
    with DbSession(engine) as db:
        assert catalog(db, workspace_id)[0]["revision"] == 1
        assert db.exec(select(WorkspaceSkill)).one().workspace_id == workspace_id
    engine.dispose()


def test_native_execution_receives_skill_and_persists_loading_event(native_fixture):
    import asyncio
    from app.claude_code_adapter import ClaudeCodeAdapter
    from app.models import TaskRunEvent
    from app.run_engine import execute_task_run
    from app.run_supervisor import RunSupervisor
    from app.task_runs import transition_task_run
    from app.skills import builtin_packages
    from test_native_review_artifacts import ReviewRunner

    db, old_run, root, _ = native_fixture
    task = db.get(Task, old_run.task_id); session = db.get(Session, task.session_id)
    profile_id = json.loads(task.plan_json)["agentProfileId"]
    transition_task_run(db, old_run.id, "interrupted")
    save_package(db, session.workspace_id, SkillSaveRequest(markdown=builtin_packages()["code-review"]["markdown"],
        roles=["review"], defaultAgents=[profile_id]), 0)
    task = Task(session_id=session.id, title="New review with Skill", intent_type="review",
        assigned_agent_id=task.assigned_agent_id, plan_json=task.plan_json)
    db.add(task); db.commit()
    run = create_task_run(db, task.id)
    received = []
    class CapturingRunner(ReviewRunner):
        def start(self, command, cwd, **kwargs):
            received.append(json.loads(kwargs["input_text"])["message"]["content"][0]["text"] if kwargs.get("input_text") else command[-1])
            return super().start(command, cwd, **kwargs)
    completed = asyncio.run(execute_task_run(db, run, adapter_type="claude_code",
        adapter=ClaudeCodeAdapter(process_runner=CapturingRunner(), read_only=True), supervisor=RunSupervisor()))
    assert completed.state == "completed", completed.error_message
    assert "Skill: code-review" in received[0]
    assert metrics_for_run(completed)["skills"]["skills"][0]["status"] == "loaded"
    events = db.exec(select(TaskRunEvent).where(TaskRunEvent.task_run_id == run.id, TaskRunEvent.event_type == "skills.loaded")).all()
    assert len(events) == 1


def test_planner_receives_compatible_guidance_and_only_public_receipt(client):
    from app.llm_planner import build_llm_planner_request
    with db_from_override() as db:
        w = workspace(db); session = db.exec(select(Session)).first()
        guide = "---\nname: planning-guide\ndescription: Planner guide\n---\nPLANNER_GUIDANCE_MARKER"
        save_package(db, w.id, request(markdown=guide, roles=["planner"], defaultAgents=["planner"]), 0)
        message = Message(session_id=session.id, sender_type="user", content_md="Build a page")
        db.add(message); db.commit()
        actual = build_llm_planner_request(db, message).to_provider_payload()
        assert "PLANNER_GUIDANCE_MARKER" in actual["agentSystemPrompt"]
        assert actual["skillEvidence"]["skills"][0]["name"] == "planning-guide"
        assert "markdown" not in json.dumps(actual["skillEvidence"])
