import asyncio
import hashlib
import json
import os
import subprocess
from pathlib import Path

import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import Session as DbSession, SQLModel, create_engine, select

from app.claude_code_adapter import ClaudeCodeAdapter
from app.custom_agents import CustomAgentInput, save_custom_agent
from app.models import Agent, Artifact, ArtifactVersion, Message, Review, Session, Task, TaskRunEvent, Workspace
from app.native_reviews import (
    NATIVE_REVIEW_BINDING_KEY, NativeReadEvidence, NativeReviewError,
    capture_native_review_binding, require_native_review_input_current, validate_native_assessment,
)
from app.reviews import create_scripted_review_for_task_run, list_task_run_reviews, ReviewError
from app.routes.task_artifacts import review_response
from app.run_engine import execute_task_run, finalize_completed_task_run
from app.run_supervisor import RunSupervisor
from app.task_runs import create_task_run, metrics_for_run
from test_claude_code_adapter import FakeClaudeCodeProcess


SOURCE = "apps/demo/src/App.tsx"


@pytest.fixture
def fixture(tmp_path):
    root = tmp_path / "review-root"
    source = root / SOURCE
    source.parent.mkdir(parents=True)
    source.write_text('export const title = "review input"\n', encoding="utf-8")
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    # An empty Git repository is not a usable Diff baseline. This commit belongs
    # only to the disposable test repository, never the development checkout.
    subprocess.run(["git", "-C", str(root), "add", SOURCE], check=True)
    subprocess.run(["git", "-C", str(root), "-c", "user.name=Test", "-c", "user.email=test@example.invalid",
                    "-c", "core.hooksPath=", "commit", "-qm", "fixture"], check=True)
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)
    with DbSession(engine) as db:
        workspace = Workspace(name="Review", root_path="apps/demo", repo_url="local://apps/demo", default_branch="main")
        session = Session(workspace_id=workspace.id, title="Native review", bound_branch="main", worktree_path=str(root))
        agent = Agent(name="QA", role="qa", adapter_type="scripted_mock", provider="local")
        db.add_all([workspace, session, agent]); db.commit()
        profile = save_custom_agent(db, workspace_id=workspace.id, value=CustomAgentInput(
            display_name="Native reviewer", mention_alias="native-reviewer", role="review",
            provider_id="local-claude-code-cli", tool_policy="claude_read_only",
            supported_targets=["demo-frontend"], capability_tags=["code_review"],
            system_prompt="Review actual code in Chinese.", description="Read only",
        ))
        task = Task(session_id=session.id, title="Review source", intent_type="review", assigned_agent_id=agent.id,
                    plan_json=json.dumps({"targetId": "demo-frontend", "assignedRole": "review",
                                          "agentProfileId": profile.id, "files": [SOURCE]}))
        db.add(task); db.commit()
        run = create_task_run(db, task.id)
        yield db, run, root, source
    engine.dispose()


def assessment(binding, **changes):
    value = {"schemaVersion": "agenthub.native_review.v1", "taskRunId": binding["taskRunId"],
             "inputFingerprint": binding["inputFingerprint"], "status": "warning", "riskLevel": "low",
             "summary": "发现一个可改进项。", "filesReviewed": [SOURCE],
             "findings": [{"severity": "low", "file": SOURCE, "line": 1, "message": "建议补充可访问性说明。"}],
             "suggestedChanges": ["补充说明。"], "validation": "not_run"}
    value.update(changes)
    return value


def read_events(root, text, *, error=False, partial=False, wrong_file=False):
    path = str(root / SOURCE)
    return [
        {"type": "assistant", "message": {"content": [{"type": "tool_use", "name": "Read", "id": "read-1",
                                                        "input": {"file_path": path}}]}},
        {"type": "user", "message": {"content": [{"type": "tool_result", "tool_use_id": "read-1", "is_error": error}]},
         "tool_use_result": {"type": "text", "file": {"filePath": str(root / "other.tsx") if wrong_file else path,
                                                       "content": text, "startLine": 2 if partial else 1,
                                                       "numLines": 1, "totalLines": 1}}},
    ]


@pytest.mark.parametrize("changes", [
    {"taskRunId": "other"}, {"inputFingerprint": "other"}, {"schemaVersion": "other"},
    {"status": "passed"}, {"riskLevel": "high"}, {"validation": "passed"}, {"summary": " "},
    {"filesReviewed": []}, {"filesReviewed": [SOURCE, SOURCE]}, {"filesReviewed": [".env"]},
    {"findings": [{"severity": "low", "file": "outside.ts", "message": "invalid"}]},
    {"findings": [{"severity": "low", "file": SOURCE, "line": 2, "message": "invalid"}]},
    {"suggestedChanges": [42]}, {"suggestedChanges": ["x" * 2001]}, {"testEvidence": "passed"},
])
def test_invalid_or_unbound_assessment_rejected(fixture, changes):
    db, run, _, _ = fixture
    binding = capture_native_review_binding(db, run)
    with pytest.raises(NativeReviewError, match="bound JSON"):
        validate_native_assessment(json.dumps(assessment(binding, **changes)), binding,
                                   {SOURCE: binding["files"][SOURCE]["textSha256"]})


@pytest.mark.parametrize("mode", ["success", "error", "partial", "wrong_file", "different_content", "missing_call"])
def test_read_evidence_requires_matching_complete_native_read(fixture, mode):
    db, run, root, source = fixture
    binding = capture_native_review_binding(db, run)
    recorder = NativeReadEvidence(binding)
    events = read_events(root, "other" if mode == "different_content" else source.read_text(encoding="utf-8"),
                         error=mode == "error", partial=mode == "partial", wrong_file=mode == "wrong_file")
    for event in events[1:] if mode == "missing_call" else events:
        recorder.observe(event)
    if mode == "success":
        assert validate_native_assessment(json.dumps(assessment(binding)), binding, recorder.reads)["status"] == "warning"
    else:
        with pytest.raises(NativeReviewError):
            validate_native_assessment(json.dumps(assessment(binding)), binding, recorder.reads)


def test_missing_prose_and_duplicate_keys_cannot_substitute_final_json(fixture):
    db, run, _, _ = fixture
    binding = capture_native_review_binding(db, run)
    for output in [None, "Looks good", '{"status":"passed","status":"failed"}', "x" * 65537]:
        with pytest.raises(NativeReviewError):
            validate_native_assessment(output, binding, {})


@pytest.mark.parametrize("fence", ["```json", "```"])
def test_whole_output_json_fence_preserves_bound_assessment(fixture, fence):
    db, run, _, _ = fixture
    binding = capture_native_review_binding(db, run)
    payload = json.dumps(assessment(binding))
    reads = {SOURCE: binding["files"][SOURCE]["textSha256"]}
    assert validate_native_assessment(f"{fence}\n{payload}\n```", binding, reads) == validate_native_assessment(payload, binding, reads)
    for output in [f"Explanation\n{fence}\n{payload}\n```", f"{fence}\n{payload}\n```\nMore text", f"{fence}\n{payload}\n{payload}\n```"]:
        with pytest.raises(NativeReviewError):
            validate_native_assessment(output, binding, reads)


@pytest.mark.parametrize("change", ["edit", "add", "delete", "target"])
def test_version_and_target_changes_invalidate_review(fixture, change):
    db, run, root, source = fixture
    binding = capture_native_review_binding(db, run)
    if change == "edit": source.write_text("changed", encoding="utf-8")
    if change == "add": (source.parent / "new.tsx").write_text("new", encoding="utf-8")
    if change == "delete": source.unlink()
    if change == "target":
        task = db.get(Task, run.task_id); plan = json.loads(task.plan_json); plan["targetId"] = "demo-backend"
        task.plan_json = json.dumps(plan); db.add(task); db.commit()
        (root / "apps/demo-api").mkdir(); (root / "apps/demo-api/main.py").write_text("source", encoding="utf-8")
    with pytest.raises(NativeReviewError) as exc:
        require_native_review_input_current(db, run, binding)
    assert exc.value.error_code == ("NATIVE_REVIEW_INPUT_UNVERIFIABLE" if change == "delete" else "NATIVE_REVIEW_INPUT_CHANGED")


@pytest.mark.parametrize("unsafe", ["hardlink", "oversize", "reparse"])
def test_unsafe_or_unbounded_inputs_fail_closed(fixture, monkeypatch, unsafe):
    db, run, root, source = fixture
    if unsafe == "hardlink": os.link(source, source.parent / "alias.tsx")
    if unsafe == "oversize": source.write_bytes(b"x" * (512 * 1024 + 1))
    if unsafe == "reparse":
        import app.native_reviews as module
        original = module._no_link
        def reject(path):
            if path == source.parent: raise ValueError("Reparse fixture")
            return original(path)
        monkeypatch.setattr(module, "_no_link", reject)
    with pytest.raises(NativeReviewError) as exc:
        capture_native_review_binding(db, run)
    assert exc.value.error_code == "NATIVE_REVIEW_INPUT_UNVERIFIABLE"


def test_protected_files_never_enter_native_binding(fixture):
    db, run, _, source = fixture
    (source.parent / ".env").write_text("private", encoding="utf-8")
    secret = source.parent / "secrets"; secret.mkdir(); (secret / "token").write_text("private", encoding="utf-8")
    binding = capture_native_review_binding(db, run)
    assert list(binding["files"]) == [SOURCE]
    run.metrics_json = json.dumps({NATIVE_REVIEW_BINDING_KEY: binding})
    assert NATIVE_REVIEW_BINDING_KEY not in metrics_for_run(run)
    assert str(source.parent) not in json.dumps(metrics_for_run(run))


def test_single_custom_native_review_mention_freezes_selected_target(fixture):
    from app.planning import plan_for_message
    db, run, _, _ = fixture
    original = db.get(Task, run.task_id)
    message = Message(session_id=original.session_id, sender_type="user",
                      content_md="@native-reviewer Review the demo source without editing.")
    db.add(message); db.commit()
    planned = plan_for_message(db, message, message.content_md)
    assert len(planned) == 1
    plan = json.loads(planned[0].plan_json)
    assert plan["targetId"] == "demo-frontend" and plan["readOnly"] is True
    assert plan["safeTarget"] == "apps/demo/src"


class ReviewRunner:
    def __init__(self, mode="valid"):
        self.mode = mode

    def start(self, command, cwd):
        shape = json.loads(command[-1].splitlines()[-1])
        output = dict(shape)
        output.update(assessment(shape))
        text = (cwd / SOURCE).read_text(encoding="utf-8")
        events = read_events(cwd, text)
        if self.mode == "missing_read": events = []
        if self.mode == "outside_read": events[0]["message"]["content"][0]["input"]["file_path"] = str(cwd / ".env")
        if self.mode == "write_tool": events[0]["message"]["content"][0]["name"] = "Write"
        if self.mode == "invalid": output["validation"] = "passed"
        if self.mode == "changed": (cwd / SOURCE).write_text("changed after Read", encoding="utf-8")
        events.append({"type": "result", "subtype": "success", "is_error": False,
                       "result": json.dumps(output, ensure_ascii=False)})
        self.process = FakeClaudeCodeProcess(stdout="\n".join(json.dumps(event, ensure_ascii=False) for event in events),
                                            returncode=1 if self.mode == "exit_error" else 0)
        return self.process


@pytest.mark.parametrize("mode,code", [("valid", None), ("invalid", "NATIVE_REVIEW_OUTPUT_INVALID"),
    ("missing_read", "NATIVE_REVIEW_OUTPUT_INVALID"), ("changed", "NATIVE_REVIEW_INPUT_CHANGED"),
    ("exit_error", "CLAUDE_CODE_EXIT_ERROR"), ("outside_read", "NATIVE_REVIEW_SCOPE_VIOLATION"),
    ("write_tool", "NATIVE_REVIEW_SCOPE_VIOLATION")])
def test_native_execution_artifact_and_failure_boundaries(fixture, mode, code):
    db, run, _, source = fixture
    before = source.read_bytes()
    runner = ReviewRunner(mode)
    completed = asyncio.run(execute_task_run(db, run, adapter_type="claude_code",
                                             adapter=ClaudeCodeAdapter(process_runner=runner, read_only=True),
                                             supervisor=RunSupervisor()))
    db.expire_all()
    reviews = list_task_run_reviews(db, run.id)
    assert runner.process.waited
    if code:
        assert completed.state == "failed" and completed.error_code == code
        assert reviews == []
        with pytest.raises(ReviewError, match="fresh native run"):
            create_scripted_review_for_task_run(db, run.id)
        return
    assert completed.state == "completed" and source.read_bytes() == before
    assert len(reviews) == 1 and reviews[0].status == "warning"  # assessment != execution
    review = reviews[0]
    assert review.adapter_type == "claude_code" and review.summary == "发现一个可改进项。"
    assert review.findings[0]["file"] == SOURCE
    assert review.native_receipt["validation"] == "not_run"
    assert review.native_receipt["files"][SOURCE]["sha256"] == hashlib.sha256(before).hexdigest()
    assert review_response(review).model_dump(by_alias=True)["nativeReceipt"] == review.native_receipt
    assert db.exec(select(ArtifactVersion).where(ArtifactVersion.artifact_id == review.artifact_id)).one().editor_source == "agent"
    assert len(db.exec(select(Review)).all()) == 1
    assert create_scripted_review_for_task_run(db, run.id).id == review.id
    asyncio.run(finalize_completed_task_run(db, completed))
    assert [x.id for x in list_task_run_reviews(db, run.id)] == [review.id]
    events = db.exec(select(TaskRunEvent).where(TaskRunEvent.task_run_id == run.id)).all()
    assert sum(event.event_type == "artifact.review.ready" for event in events) == 1
    assert not any('"claudeEventType":"user"' in event.payload_json for event in events)


def test_review_and_version_roll_back_if_terminal_commit_cannot_finish(fixture, monkeypatch):
    import app.run_engine as engine
    db, run, _, _ = fixture
    original = engine.transition_task_run
    def rejected(db, run_id, state, **kwargs):
        if state == "completed":
            raise NativeReviewError("NATIVE_REVIEW_INPUT_CHANGED", "Simulated last-boundary rejection")
        return original(db, run_id, state, **kwargs)
    monkeypatch.setattr(engine, "transition_task_run", rejected)
    completed = asyncio.run(execute_task_run(db, run, adapter_type="claude_code",
                                             adapter=ClaudeCodeAdapter(process_runner=ReviewRunner(), read_only=True),
                                             supervisor=RunSupervisor()))
    assert completed.state == "failed"
    assert db.exec(select(Artifact).where(Artifact.artifact_type == "review")).all() == []
    assert db.exec(select(Review)).all() == []
    assert db.exec(select(ArtifactVersion).where(ArtifactVersion.editor_source == "agent")).all() == []
    assert db.exec(select(TaskRunEvent).where(TaskRunEvent.event_type == "artifact.review.ready")).all() == []
