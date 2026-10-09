import json
import asyncio
import shutil
import subprocess
from dataclasses import replace
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session as DbSession, SQLModel, create_engine, select

from app.custom_agents import CustomAgentInput, save_custom_agent
from app.external_workspaces import ExternalWorkspaceRegistration, register_external_project_target
from app.main import app, get_db
from app.models import Agent, Artifact, Diff, Message, Session, Task, TaskRun, Workspace
from app.planning import MentionParseError, plan_for_message
from app.run_engine import complete_ready_session_review_tasks, execute_task_run_background
from app.session_queue import entry_for_task_run
from app.scripted_mock import ScriptedMockAdapter
from app.scheduler import complete_synthetic_planning_tasks, evaluate_dependency_readiness, refresh_session_scheduler_state
from app.task_runs import create_task_run, retry_with_scripted_mock


@pytest.fixture
def db(monkeypatch):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    # HTTP BackgroundTasks use app.db.engine independently of get_db overrides.
    # Keep the dispatcher/summary scan in this fixture, never the developer DB.
    monkeypatch.setattr("app.db.engine", engine)
    SQLModel.metadata.create_all(engine)
    with DbSession(engine) as db:
        workspace = Workspace(name="Group", root_path="apps/demo", repo_url="local://apps/demo", default_branch="main")
        session = Session(workspace_id=workspace.id, title="Group", bound_branch="main", worktree_path=".worktrees/group-test")
        agents = [Agent(name=role, role=role, adapter_type="scripted_mock" if role in {"qa", "orchestrator"} else "codex", provider="local") for role in ["orchestrator", "frontend", "backend", "qa"]]
        db.add_all([workspace, session, *agents]); db.commit()
        yield db
    engine.dispose()


def message(db, content):
    result = Message(session_id=db.exec(select(Session)).one().id, sender_type="user", content_md=content, context_json='{"groupExecution":"manual"}')
    db.add(result); db.commit()
    return result


def plan(db, content):
    result = message(db, content)
    return plan_for_message(db, result, content)


def custom(db, **kwargs):
    value = CustomAgentInput(display_name="界面工程师", mention_alias="ui-expert", role="frontend", provider_id="local-codex-cli", tool_policy="codex_coding", supported_targets=["demo-frontend"], capability_tags=["code_write", "diff_analysis"], system_prompt="Use bounded changes", description="")
    return save_custom_agent(db, workspace_id=db.exec(select(Workspace)).one().id, value=replace(value, **kwargs))


@pytest.mark.parametrize("content", [
    "@qa @frontend update demo app button", "@frontend @qa update demo app button",
    "@orchestrator @qa @frontend update demo app button", "@frontend @qa @orchestrator update demo app button",
    "@frontend @frontend @qa @QA update demo app button",
])
def test_group_routes_every_role_reviews_after_writes_and_discloses_source(db, content):
    tasks = plan(db, content)
    assert [task.intent_type for task in tasks] == ["frontend_change", "qa_review"]
    assert json.loads(tasks[1].depends_on_task_ids) == [tasks[0].id]
    refresh_session_scheduler_state(db, tasks[0].session_id)
    assert [task.status for task in tasks] == ["pending", "waiting_dependency"]
    plans = [json.loads(task.plan_json) for task in tasks]
    assert all(item["planner"] == "explicit_group_v1" and item["autoStart"] is False for item in plans)
    assert all(item["targetId"] == "demo-frontend" for item in plans)
    assert plans[1]["readOnly"] is True
    assert plans[0]["groupAssignment"]["id"] == tasks[0].created_by_message_id
    assert len(plans[0]["taskGraph"]["tasks"]) == 2
    response = db.exec(select(Message).where(Message.sender_type == "orchestrator")).one()
    assert "确定性协调" in response.content_md and "@frontend" in response.content_md and "@qa" in response.content_md
    assert db.exec(select(TaskRun)).all() == []


def test_two_writers_and_two_review_roles_bind_each_target_and_all_dependencies(db):
    tasks = plan(db, "@review @backend @qa @frontend update demo app and backend contacts")
    assert len(tasks) == 6
    plans = [json.loads(task.plan_json) for task in tasks]
    assert [item["assignedRole"] for item in plans] == ["backend", "frontend", "review", "review", "qa", "qa"]
    assert [item["targetId"] for item in plans] == ["demo-backend", "demo-frontend"] * 3
    assert json.loads(tasks[1].depends_on_task_ids) == [tasks[0].id]
    for task in tasks[2:]:
        assert set([tasks[0].id, tasks[1].id]).issubset(json.loads(task.depends_on_task_ids))
    tasks[0].status = "completed"; db.add(tasks[0]); db.commit()
    assert not evaluate_dependency_readiness(db, tasks[2]).runnable
    tasks[1].status = "failed"; db.add(tasks[1]); db.commit()
    assert not evaluate_dependency_readiness(db, tasks[2]).runnable


def test_custom_participant_binding_is_frozen_in_own_run(db):
    profile = custom(db)
    tasks = plan(db, "@qa @ui-expert update demo app button")
    assert json.loads(tasks[0].plan_json)["agentProfileId"] == profile.id
    run = create_task_run(db, tasks[0].id)
    selection = json.loads(run.metrics_json)["agentSelection"]["customProfile"]
    assert selection["id"] == profile.id and selection["mentionAlias"] == "ui-expert"
    assert json.loads(tasks[1].plan_json).get("agentProfileId") is None


@pytest.mark.parametrize("content", [
    "@frontend @qa update payment whole app", "@backend @qa platform maintenance",
    "@frontend @missing update demo app", "@frontend @ui-expert @qa update demo app",
    "@ui-expert @frontend @qa update demo app",
])
def test_invalid_group_has_no_partial_tasks_or_response(db, content):
    custom(db)
    with pytest.raises(MentionParseError): plan(db, content)
    assert db.exec(select(Task)).all() == []
    assert db.exec(select(Message).where(Message.sender_type == "orchestrator")).all() == []


def test_disabled_agent_and_missing_active_target_do_not_fall_back_or_persist(db):
    qa = db.exec(select(Agent).where(Agent.role == "qa")).one()
    qa.enabled = False; db.add(qa); db.commit()
    with pytest.raises(MentionParseError, match="disabled"): plan(db, "@frontend @qa update demo app")
    qa.enabled = True; db.add(qa)
    session = db.exec(select(Session)).one()
    session.active_backend_target_id = "external-missing"; db.add(session); db.commit()
    with pytest.raises(MentionParseError): plan(db, "@frontend @backend update demo app")
    assert db.exec(select(Task)).all() == []


def test_late_custom_scope_failure_rolls_back_earlier_tasks_and_flushes(db):
    custom(db, display_name="评审", mention_alias="read-expert", role="review", provider_id="local-claude-code-cli", tool_policy="claude_read_only", capability_tags=["code_review", "diff_analysis"])
    with pytest.raises(MentionParseError, match="does not support target"):
        plan(db, "@frontend @backend @read-expert update demo app and backend contacts")
    assert db.exec(select(Task)).all() == []
    assert db.exec(select(Message).where(Message.sender_type == "orchestrator")).all() == []
    assert len(plan(db, "@frontend @qa update demo app button")) == 2


def test_custom_planner_group_failure_has_no_substitution(db, monkeypatch):
    from app.planner_providers import PlannerProviderResult
    class Unavailable:
        planner_source = "real_llm"
        def create_plan(self, payload):
            return PlannerProviderResult("claude-cli-planner", "claude_cli", "real_llm", "failed", error_summary="Provider unavailable")
    monkeypatch.setattr("app.group_planner.resolve_planner_provider", lambda *args, **kwargs: Unavailable())
    custom(db, display_name="规划", mention_alias="team-planner", role="orchestrator", provider_id="claude-cli-planner", tool_policy="planner_no_tools", capability_tags=["code_review", "diff_analysis"])
    with pytest.raises(MentionParseError, match="Provider unavailable"):
        plan(db, "@team-planner @frontend update demo app")
    assert db.exec(select(Task)).all() == []


def native_provider(db, monkeypatch, mutate=None, callback=None):
    from app.planner_providers import PlannerProviderResult
    captured = []
    class NativeTest:
        planner_source = "fake_test"
        def create_plan(self, payload):
            captured.append(payload)
            # Factories must not flush tasks while the provider is running.
            assert db.exec(select(Task)).all() == []
            items = []
            for index, assignment in enumerate(payload["explicitGroupAssignments"]):
                role = assignment["role"]
                target = next(target for target in payload["targetRegistry"] if target["targetId"] == assignment["targetId"])
                file = next((path for path in target["allowedPaths"] if path.endswith((".tsx", ".py"))), None)
                items.append({
                    "title": f"Native {index + 1} {role}", "role": role, "targetId": assignment["targetId"],
                    "intentType": assignment["intentType"], "plannedFiles": [file] if file and not assignment["readOnly"] else [],
                    "dependsOn": [], "expectedArtifactTypes": ["review" if assignment["readOnly"] else "diff"],
                    "acceptanceCriteria": [f"Actual acceptance {role}"], "riskLevel": "low", "requiresApproval": False,
                    "validationExpectations": [], "rationale": f"Actual task rationale {role}",
                })
            value = {"outcomeType": "task_plan", "planDraft": {
                "planId": "native-group-test", "planner": "llm_v1", "plannerMode": "llm_v1", "rationale": "Actual group rationale",
                "tasks": items, "acceptanceCriteria": ["All requested actors complete"], "validationExpectations": [],
            }}
            if mutate: mutate(value)
            if callback: callback(payload)
            return PlannerProviderResult("controlled-group-planner", "fake_test", "fake_test", "succeeded", raw_output=json.dumps(value), duration_ms=12)
    monkeypatch.setattr("app.group_planner.resolve_planner_provider", lambda *args, **kwargs: NativeTest())
    return captured


def custom_planner(db, **kwargs):
    return custom(db, display_name="规划", mention_alias="team-planner", role="orchestrator", provider_id="claude-cli-planner", tool_policy="planner_no_tools", capability_tags=["code_review", "diff_analysis"], **kwargs)


def test_native_custom_planner_group_uses_actual_content_prompt_scope_and_atomic_persistence(db, monkeypatch):
    import hashlib
    planner = custom_planner(db, system_prompt="NATIVE_GROUP_PROMPT_MARKER")
    writer = custom(db)
    captured = native_provider(db, monkeypatch)
    tasks = plan(db, "@ui-expert @qa @team-planner for demo app change button to Planned")
    assert len(tasks) == 2
    assert tasks[0].title == "Native 1 frontend"
    payload = captured[0]
    assert payload["agentSystemPrompt"] == "NATIVE_GROUP_PROMPT_MARKER"
    assert payload["agentToolPolicy"] == "planner_no_tools"
    assert payload["agentProfileSelection"]["id"] == planner.id
    assert payload["explicitGroupAssignments"][0]["profileId"] == writer.id
    assert [target["targetId"] for target in payload["targetRegistry"]] == ["demo-frontend"]
    assert [target["targetId"] for target in payload["projectAnalyzer"]] == ["demo-frontend"]
    first = json.loads(tasks[0].plan_json)
    assert first["acceptanceCriteria"] == ["Actual acceptance frontend"]
    assert first["description"] == "Actual task rationale frontend"
    assert first["instructionMode"] == "llm_v1"
    from app.instruction_builder import _passthrough_body
    from app.target_registry import get_target_for_workspace
    instruction = _passthrough_body("qa", tasks[1], json.loads(tasks[1].plan_json), "User request", get_target_for_workspace(db, planner.workspace_id, "demo-frontend"))
    assert "Actual acceptance qa" in instruction
    assert "Do not edit files" in instruction
    assert "Implement meaningful coding" not in instruction
    assert first["agentProfileId"] == writer.id
    assert first["groupAssignment"]["coordinationSource"] == "fake_test"
    assert first["plannerEvidence"]["agentInstruction"]["sha256"] == hashlib.sha256(b"NATIVE_GROUP_PROMPT_MARKER").hexdigest()
    assert first["plannerEvidence"]["createdTaskIds"] == [task.id for task in tasks]
    assert json.loads(tasks[1].depends_on_task_ids) == [tasks[0].id]
    assert "NATIVE_GROUP_PROMPT_MARKER" not in tasks[0].plan_json
    reply = db.exec(select(Message).where(Message.sender_type == "orchestrator")).one()
    assert "Actual group rationale" in reply.content_md
    assert not complete_ready_session_review_tasks(db, tasks[0].session_id)
    db.expire_all()
    assert db.get(Task, tasks[0].id).title == "Native 1 frontend"


@pytest.mark.parametrize("violation", [
    "omit", "extra", "swap", "target", "intent", "files", "artifacts", "high-risk", "approval", "empty-title", "empty-acceptance", "command", "global-command", "unknown-dependency", "forward-dependency", "duplicate-dependency", "project-setup", "planner-identity", "non-task",
])
def test_invalid_native_group_is_atomic_and_never_substitutes_roles(db, monkeypatch, violation):
    custom_planner(db)
    def mutate(value):
        output = value["planDraft"]; item = output["tasks"][0]
        if violation == "omit": output["tasks"].pop()
        elif violation == "extra": output["tasks"].append(dict(item))
        elif violation == "swap": output["tasks"].reverse()
        elif violation == "target": item["targetId"] = "demo-backend"
        elif violation == "intent": item["intentType"] = "review"
        elif violation == "files": item["plannedFiles"] = [".env"]
        elif violation == "artifacts": item["expectedArtifactTypes"] = ["review"]
        elif violation == "high-risk": item["riskLevel"] = "high"
        elif violation == "approval": item["requiresApproval"] = True
        elif violation == "empty-title": item["title"] = " "
        elif violation == "empty-acceptance": item["acceptanceCriteria"] = []
        elif violation == "command": item["validationExpectations"] = ["pnpm install"]
        elif violation == "global-command": output["validationExpectations"] = ["python -m pytest /host"]
        elif violation == "unknown-dependency": item["dependsOn"] = ["not-a-task"]
        elif violation == "forward-dependency": item["dependsOn"] = ["2-qa-review"]
        elif violation == "duplicate-dependency": output["tasks"][1]["dependsOn"] = ["1-frontend-frontend_change"] * 2
        elif violation == "project-setup": output["projectSetup"] = {"projectKind": "new", "plannedProjectRoot": "other"}
        elif violation == "planner-identity": output["planner"] = "deterministic"
        elif violation == "non-task": value.clear(); value.update({"outcomeType": "clarification", "reply": "Need details"})
    native_provider(db, monkeypatch, mutate)
    with pytest.raises(MentionParseError): plan(db, "@team-planner @frontend @qa update demo app")
    assert db.exec(select(Task)).all() == []
    assert db.exec(select(Message).where(Message.sender_type == "orchestrator")).all() == []


def test_native_group_checks_planner_target_scope_before_call(db, monkeypatch):
    custom_planner(db)
    captured = native_provider(db, monkeypatch)
    with pytest.raises(MentionParseError, match="every group target"):
        plan(db, "@team-planner @frontend @backend update demo app and backend contacts")
    assert captured == []
    assert db.exec(select(Task)).all() == []


@pytest.mark.parametrize("disabled_role", ["orchestrator", "frontend", "qa"])
def test_native_group_rechecks_disabled_participant_after_provider(db, monkeypatch, disabled_role):
    planner = custom_planner(db)
    writer = custom(db)
    def disable(_payload):
        profile = planner if disabled_role == "orchestrator" else writer if disabled_role == "frontend" else db.exec(select(Agent).where(Agent.role == "qa")).one()
        if disabled_role == "qa": profile.enabled = False
        else: profile.status = "disabled"
        db.add(profile); db.commit()
    native_provider(db, monkeypatch, callback=disable)
    with pytest.raises(MentionParseError, match="disabled"):
        plan(db, "@team-planner @ui-expert @qa update demo app")
    assert db.exec(select(Task)).all() == []


def test_native_six_task_group_preserves_review_role_targets_and_server_dependencies(db, monkeypatch):
    custom_planner(db, supported_targets=["demo-frontend", "demo-backend"])
    native_provider(db, monkeypatch)
    tasks = plan(db, "@team-planner @frontend @backend @qa @review update demo app and backend contacts")
    assert len(tasks) == 6
    roles = [json.loads(task.plan_json)["assignedRole"] for task in tasks]
    assert roles == ["frontend", "backend", "qa", "qa", "review", "review"]
    assert json.loads(tasks[1].depends_on_task_ids) == [tasks[0].id]
    for task in tasks[2:]:
        assert {tasks[0].id, tasks[1].id}.issubset(json.loads(task.depends_on_task_ids))
        assert json.loads(task.plan_json)["readOnly"]
    assert all(node["assignedAgentRole"] == role for node, role in zip(json.loads(tasks[0].plan_json)["taskGraph"]["tasks"], roles))


def test_configured_custom_planner_participates_without_explicit_mention(db, monkeypatch):
    from app.agent_runtime_config import default_runtime_config, upsert_runtime_config
    planner = custom_planner(db)
    role = replace(default_runtime_config(None).roles["planner"], enabled=True, agent_profile_id=planner.id, provider_id=planner.provider_id, adapter_type=planner.adapter_type)
    upsert_runtime_config(db, planner.workspace_id, {"planner": role})
    captured = native_provider(db, monkeypatch)
    tasks = plan(db, "@qa @frontend update demo app button")
    assert captured[0]["agentProfileSelection"]["id"] == planner.id
    assert json.loads(tasks[0].plan_json)["groupAssignment"]["coordinationSource"] == "fake_test"


def test_native_review_dependency_keys_and_readonly_scripted_execution_mode(db, monkeypatch):
    from app.task_runs import is_scripted_group_review
    custom_planner(db)
    def dependencies(value):
        value["planDraft"]["tasks"][1]["dependsOn"] = ["1-frontend-frontend_change"]
        value["planDraft"]["tasks"][2]["dependsOn"] = ["2-review-review"]
    native_provider(db, monkeypatch, mutate=dependencies)
    tasks = plan(db, "@team-planner @frontend @review @qa update demo app button")
    # Server orders reviewers by explicit mention, preserving native backward edges.
    assert is_scripted_group_review(tasks[1], "scripted_mock")
    assert is_scripted_group_review(tasks[2], "scripted_mock")
    assert json.loads(tasks[2].depends_on_task_ids) == [tasks[0].id, tasks[1].id]


def test_native_group_http_history_and_validation_provenance(db, monkeypatch):
    custom_planner(db)
    native_provider(db, monkeypatch)
    app.dependency_overrides[get_db] = lambda: db
    try:
        client = TestClient(app)
        session = db.exec(select(Session)).one()
        response = client.post(f"/sessions/{session.id}/messages", json={"contentMd": "@team-planner @frontend @qa update demo app button", "context": {"groupExecution": "manual"}})
        assert response.status_code == 201
        tasks = client.get(f"/sessions/{session.id}/tasks").json()
        assert len(tasks) == 2 and tasks[1]["status"] == "waiting_dependency"
        assert tasks[0]["planJson"]["plannerEvidence"]["validationResult"] == "passed"
        assert all(task["taskRuns"] == [] for task in tasks)
        db.expire_all()
        assert client.get(f"/sessions/{session.id}/tasks").json()[0]["title"] == "Native 1 frontend"
    finally:
        app.dependency_overrides.clear()


def test_native_group_provider_resolution_failure_is_explicit_and_atomic(db, monkeypatch):
    from app.planner_providers import PlannerProviderError
    def unavailable(*args, **kwargs):
        raise PlannerProviderError(code="UNAVAILABLE", summary="Missing provider configuration", provider_id="unknown")
    monkeypatch.setattr("app.group_planner.resolve_planner_provider", unavailable)
    with pytest.raises(MentionParseError, match="Missing provider configuration"):
        plan(db, "@frontend @qa update demo app button")
    assert db.exec(select(Task)).all() == []


def test_native_group_rechecks_planner_identity_change_after_call(db, monkeypatch):
    planner = custom_planner(db)
    def change(_payload):
        planner.tool_policy = "codex_coding"; db.add(planner); db.commit()
    native_provider(db, monkeypatch, callback=change)
    with pytest.raises(MentionParseError, match="identity or tool policy changed"):
        plan(db, "@team-planner @frontend @qa update demo app button")
    assert db.exec(select(Task)).all() == []


def test_explicit_review_is_not_satisfied_by_generated_report(db, monkeypatch):
    tasks = plan(db, "@frontend @review update demo app button")
    tasks[0].status = "completed"; db.add(tasks[0]); db.commit()
    # Even valid reports cannot stand in for the user's explicitly selected reviewer.
    monkeypatch.setattr("app.run_engine._dependency_review_evidence", lambda *_: [{"status": "passed"}])
    assert complete_ready_session_review_tasks(db, tasks[0].session_id) == []
    assert tasks[1].status == "pending"


def test_group_preserves_previous_session_dependency(db):
    previous = Task(session_id=db.exec(select(Session)).one().id, title="Prior", intent_type="frontend_change", priority=7)
    db.add(previous); db.commit()
    tasks = plan(db, "@frontend @qa update demo app button")
    assert tasks[0].priority == 8
    assert json.loads(tasks[0].depends_on_task_ids) == [previous.id]
    assert not evaluate_dependency_readiness(db, tasks[0]).runnable


def test_registered_external_target_and_foreign_workspace_rejection(db, tmp_path):
    project = tmp_path / "ui"; (project / "src").mkdir(parents=True)
    (project / "src/App.tsx").write_text("export default function App() { return null }", encoding="utf-8")
    (project / "package.json").write_text('{"name":"group-ui"}', encoding="utf-8")
    workspace = db.exec(select(Workspace)).one()
    register_external_project_target(db, workspace, ExternalWorkspaceRegistration(target_id="external-group-ui", name="UI", root_path=str(project), allowed_paths=["src"], project_type="vite-react"))
    session = db.exec(select(Session)).one()
    session.active_frontend_target_id = "external-group-ui"; db.add(session); db.commit()
    tasks = plan(db, "@frontend @review update heading")
    assert all(json.loads(task.plan_json)["targetId"] == "external-group-ui" for task in tasks)
    assert json.loads(tasks[0].plan_json)["files"] == ["src/App.tsx"]
    # The target ID alone must not make a different workspace's project usable.
    other = Workspace(name="Other", root_path="apps/demo", repo_url="local://apps/demo", default_branch="main")
    db.add(other); db.commit()
    session.workspace_id = other.id; session.memory_snapshot_id = None; db.add(session); db.commit()
    with pytest.raises(MentionParseError): plan(db, "@frontend @qa update heading")
    assert len(db.exec(select(Task)).all()) == 2


def test_http_group_round_trip_and_rejected_message_retains_no_partial_tasks(db):
    app.dependency_overrides[get_db] = lambda: db
    try:
        client = TestClient(app)
        session = db.exec(select(Session)).one()
        response = client.post(f"/sessions/{session.id}/messages", json={"contentMd": "@qa @frontend update demo app button", "context": {"groupExecution": "manual"}})
        assert response.status_code == 201
        tasks = client.get(f"/sessions/{session.id}/tasks").json()
        assert len(tasks) == 2 and tasks[1]["status"] == "waiting_dependency"
        response = client.post(f"/sessions/{session.id}/messages", json={"contentMd": "@backend @frontend platform maintenance"})
        assert response.status_code == 400
        assert len(client.get(f"/sessions/{session.id}/tasks").json()) == 2
        assert len(db.exec(select(Message).where(Message.sender_type == "user")).all()) == 2
    finally:
        app.dependency_overrides.clear()


def test_real_scripted_group_write_then_own_readonly_review_preserves_files(db, tmp_path):
    worktree = tmp_path / "group-worktree"
    demo = worktree / "apps/demo/src"; demo.mkdir(parents=True)
    source = Path(__file__).resolve().parents[3] / "apps/demo/src"
    for filename in ["App.tsx", "styles.css"]:
        shutil.copyfile(source / filename, demo / filename)
    for command in [
        ["git", "init"], ["git", "config", "user.email", "test@example.com"],
        ["git", "config", "user.name", "Group Test"], ["git", "add", "."],
        ["git", "commit", "-m", "Fixture baseline"],
    ]:
        subprocess.run(command, cwd=worktree, check=True, capture_output=True)
    session = db.exec(select(Session)).one()
    session.worktree_path = str(worktree); db.add(session); db.commit()
    tasks = plan(db, "@frontend @qa for demo app change button to Group Reviewed")
    write = create_task_run(db, tasks[0].id, adapter_type="scripted_mock")
    assert asyncio.run(execute_task_run_background(db, write.id, "scripted_mock"))
    db.refresh(write)
    assert write.state == "completed", (write.error_code, write.error_message)
    baseline = (demo / "App.tsx").read_bytes()
    assert b"Group Reviewed" in baseline
    db.refresh(tasks[1]); assert tasks[1].status != "completed"
    review = create_task_run(db, tasks[1].id)
    assert entry_for_task_run(db, review.id).access_mode == "readonly"
    assert entry_for_task_run(db, review.id).target_lock_key is None
    assert asyncio.run(execute_task_run_background(db, review.id, "scripted_mock"))
    db.refresh(review)
    assert review.state == "completed", (review.error_code, review.error_message)
    assert (demo / "App.tsx").read_bytes() == baseline
    assert db.exec(select(Artifact).where(Artifact.task_run_id == review.id, Artifact.artifact_type == "review")).one().status in {"passed", "warning", "failed"}
    assert ScriptedMockAdapter(read_only=True).getCapabilities().supports_file_edit is False


@pytest.mark.parametrize("mentions", ["@frontend", "@frontend @qa"])
@pytest.mark.parametrize("prompt,target,text", [
    ("build a login page for the demo app", "login_page", ""),
    ("for demo app change button text to Sign in", "primary_action_button_text", "Sign in"),
    ("build a login page for the demo app with OAuth", "demo_frontend_request", None),
])
def test_direct_and_group_persist_specific_supported_targets(db, mentions, prompt, target, text):
    tasks = plan(db, f"{mentions} {prompt}")
    value = json.loads(tasks[0].plan_json)
    assert value["target"] == target
    assert value.get("targetText") == text
    assert value["targetId"] == value["frontendTargetId"] == "demo-frontend"
    assert value["safeTarget"] == "apps/demo/src"
    assert value["originalRequest"] == f"{mentions} {prompt}"
    if len(tasks) == 2:
        review = json.loads(tasks[1].plan_json)
        assert review["target"] == "explicit_group_review" and review["readOnly"]
        assert json.loads(tasks[1].depends_on_task_ids) == [tasks[0].id]


@pytest.mark.parametrize("mentions", ["@frontend", "@frontend @qa", "@orchestrator"])
def test_login_request_does_not_override_selected_external_target(db, tmp_path, mentions):
    project = tmp_path / "login-external"
    (project / "src").mkdir(parents=True)
    (project / "src/App.tsx").write_text("export default function App() { return null }", encoding="utf-8")
    workspace = db.exec(select(Workspace)).one()
    register_external_project_target(db, workspace, ExternalWorkspaceRegistration(
        target_id="external-login-ui", name="Login UI", root_path=str(project),
        allowed_paths=["src"], project_type="vite-react",
    ))
    session = db.exec(select(Session)).one()
    session.active_frontend_target_id = "external-login-ui"
    db.add(session); db.commit()
    tasks = plan(db, f"{mentions} build a login page for the demo app")
    complete_synthetic_planning_tasks(db, tasks)
    assert tasks
    values = [json.loads(task.plan_json) for task in tasks]
    assert all(value["targetId"] == "external-login-ui" for value in values)
    assert all(value["target"] != "login_page" for value in values)


@pytest.mark.parametrize("mentions", ["@frontend", "@frontend @qa", "@orchestrator"])
def test_login_failure_fallback_and_followup_with_real_engine(db, tmp_path, mentions):
    worktree = tmp_path / "login-fallback"
    demo = worktree / "apps/demo/src"; demo.mkdir(parents=True)
    source = Path(__file__).resolve().parents[3] / "apps/demo/src"
    for name in ["App.tsx", "styles.css"]:
        shutil.copyfile(source / name, demo / name)
    for command in [
        ["git", "init"], ["git", "config", "user.email", "test@example.invalid"],
        ["git", "config", "user.name", "Login Fixture"], ["git", "add", "."],
        ["git", "-c", "core.hooksPath=", "commit", "-m", "Fixture"],
    ]:
        subprocess.run(command, cwd=worktree, check=True, capture_output=True)
    session = db.exec(select(Session)).one()
    session.worktree_path = str(worktree); db.add(session); db.commit()
    baseline = (demo / "App.tsx").read_bytes()
    tasks = plan(db, f"{mentions} build a login page for the demo app")
    complete_synthetic_planning_tasks(db, tasks)
    task = next(task for task in tasks if task.intent_type == "frontend_change")
    assert json.loads(task.plan_json)["target"] == "login_page"
    failed = create_task_run(db, task.id, adapter_type="codex", retry_metadata={"forceFailure": True})
    assert asyncio.run(execute_task_run_background(db, failed.id, "codex"))
    db.refresh(failed)
    assert failed.state == "failed" and failed.error_code == "CODEX_DEMO_FORCED_FAILURE"
    assert (demo / "App.tsx").read_bytes() == baseline
    frozen_failed = failed.metrics_json
    fallback = retry_with_scripted_mock(db, failed.id)
    assert asyncio.run(execute_task_run_background(db, fallback.id, "scripted_mock"))
    db.refresh(fallback); db.refresh(failed)
    assert fallback.state == "completed", (fallback.error_code, fallback.error_message)
    assert failed.state == "failed" and failed.metrics_json == frozen_failed
    assert json.loads(fallback.metrics_json)["fallbackFromRunId"] == failed.id
    diff = db.exec(select(Diff).join(Artifact).where(Artifact.task_run_id == fallback.id)).one()
    assert diff.patch_text.strip() and 'type="password"' in diff.patch_text
    login = (demo / "App.tsx").read_text(encoding="utf-8")
    assert '<form className="login-form"' in login and 'type="email"' in login
    if mentions == "@frontend @qa":
        review = create_task_run(db, tasks[1].id)
        assert entry_for_task_run(db, review.id).access_mode == "readonly"
        assert asyncio.run(execute_task_run_background(db, review.id, "scripted_mock"))
        db.refresh(review); assert review.state == "completed"
        assert (demo / "App.tsx").read_text(encoding="utf-8") == login
    # Direct/group creation must leave a normal supported follow-up runnable.
    if mentions != "@orchestrator":
        followup = plan(db, f"{mentions} for demo app change button text to Login Verified")[0]
        assert json.loads(followup.plan_json)["target"] == "primary_action_button_text"
        run = create_task_run(db, followup.id, adapter_type="scripted_mock")
        assert asyncio.run(execute_task_run_background(db, run.id, "scripted_mock"))
        db.refresh(run); assert run.state == "completed", (run.error_code, run.error_message)
        assert (demo / "App.tsx").read_text(encoding="utf-8") == login.replace(
            "            Continue\n", "            Login Verified\n",
        )
