import json

import pytest

from app.external_evidence import record_command_evidence
from app.models import Artifact, Task, TaskRun, TaskRunEvent
from app.qa_assessment import build_qa_assessment
from app.reviews import create_scripted_review_for_diff, list_task_run_reviews
from app.routes.task_artifacts import review_response
from sqlmodel import Session as DbSession, SQLModel, create_engine, select
from test_external_reviews import create_external_diff_fixture, db_fixture


def setup(db, tmp_path, files=None):
    diff_id = create_external_diff_fixture(db, tmp_path, changed_files=files or ["src/App.tsx"])
    return db.get(Artifact, diff_id)


def assess(db, artifact, *, model="passed", files=None):
    run = db.get(TaskRun, artifact.task_run_id)
    task = db.get(Task, run.task_id)
    return build_qa_assessment(db, artifact, plan=json.loads(task.plan_json),
                               files=files or ["src/App.tsx"], patch="patch",
                               findings=[], model_status=model)


@pytest.mark.parametrize("path", [".env", "../other.ts", "README.md", "src/secrets/token", "src/node_modules/pkg.js"])
def test_model_cannot_override_rule_violation(tmp_path, path):
    with next(db_fixture()) as db:
        artifact = setup(db, tmp_path)
        qa = assess(db, artifact, files=[path])
        assert qa["status"] == "blocked"
        assert qa["rules"]["status"] == "failed"
        assert qa["model"]["status"] == "passed"
        assert qa["rules"]["violations"] == [path]


def test_scripted_report_persists_incomplete_snapshot_and_event(tmp_path):
    with next(db_fixture()) as db:
        artifact = setup(db, tmp_path)
        review = create_scripted_review_for_diff(db, artifact.id)
        qa = review.qa_assessment
        assert qa["model"]["status"] == "not_run"
        assert qa["status"] == "incomplete"
        assert all(item["status"] == "not_run" for item in qa["commands"])
        record_command_evidence(db, artifact.task_run_id, command_type="test", command="pnpm test", exit_code=0)
        db.expire_all()
        reloaded = list_task_run_reviews(db, artifact.task_run_id)[0]
        assert reloaded.qa_assessment == qa  # later receipts cannot rewrite history
        assert review_response(reloaded).model_dump(by_alias=True)["qaAssessment"] == qa
        event = db.exec(select(TaskRunEvent).where(TaskRunEvent.event_type == "artifact.review.ready")).one()
        assert json.loads(event.payload_json)["qaAssessment"] == qa


def test_command_failure_is_not_hidden_by_model_or_later_success(tmp_path):
    with next(db_fixture()) as db:
        artifact = setup(db, tmp_path)
        for code in [1, 0]:
            record_command_evidence(db, artifact.task_run_id, command_type="test", command="pnpm test", exit_code=code)
        record_command_evidence(db, artifact.task_run_id, command_type="build", command="pnpm build", exit_code=0)
        qa = assess(db, artifact)
        assert qa["status"] == "blocked"
        assert qa["commands"][1]["status"] == "recorded_failed"
        assert [e["exitCode"] for e in qa["commands"][1]["evidence"]] == [1, 0]
        assert qa["commands"][2]["status"] == "recorded_passed"


def test_passed_receipts_without_file_version_do_not_establish_acceptance(tmp_path):
    with next(db_fixture()) as db:
        artifact = setup(db, tmp_path)
        for kind in ("check", "test", "build"):
            record_command_evidence(db, artifact.task_run_id, command_type=kind, command=f"pnpm {kind}", exit_code=0)
        qa = assess(db, artifact)
        assert qa["rules"]["status"] == "passed" and qa["model"]["status"] == "passed"
        assert all(c["status"] == "recorded_passed" and not c["versionBound"] for c in qa["commands"])
        assert qa["status"] == "incomplete" and qa["acceptance"] == "not_established"


@pytest.mark.parametrize("mismatch", ["run", "target", "command"])
def test_unrelated_receipts_are_not_borrowed(tmp_path, mismatch):
    with next(db_fixture()) as db:
        artifact = setup(db, tmp_path)
        receipt = record_command_evidence(db, artifact.task_run_id, command_type="test", command="pnpm test", exit_code=0)
        stored = db.get(Artifact, receipt.id)
        if mismatch == "run":
            original = db.get(TaskRun, artifact.task_run_id)
            other = TaskRun(task_id=original.task_id, agent_id=original.agent_id,
                            state="completed", worktree_path=original.worktree_path)
            db.add(other)
            stored.task_run_id = other.id
        else:
            meta = json.loads(stored.meta_json)
            meta["targetId" if mismatch == "target" else "command"] = "unrelated"
            stored.meta_json = json.dumps(meta)
        db.add(stored); db.commit()
        assert assess(db, artifact)["commands"][1]["status"] == "not_run"


def test_legacy_report_and_missing_target_remain_unknown(tmp_path):
    with next(db_fixture()) as db:
        artifact = setup(db, tmp_path)
        review = create_scripted_review_for_diff(db, artifact.id)
        stored = db.get(Artifact, review.artifact_id)
        meta = json.loads(stored.meta_json); meta.pop("qaAssessment")
        stored.meta_json = json.dumps(meta); db.add(stored); db.commit()
        assert list_task_run_reviews(db, artifact.task_run_id)[0].qa_assessment is None
        run = db.get(TaskRun, artifact.task_run_id)
        task = db.get(Task, run.task_id); task.plan_json = "{}"; db.add(task); db.commit()
        assert assess(db, artifact)["rules"]["status"] == "unknown"


def test_model_failure_blocks_even_with_clean_rules(tmp_path):
    with next(db_fixture()) as db:
        artifact = setup(db, tmp_path)
        qa = assess(db, artifact, model="failed")
        assert qa["rules"]["status"] == "passed"
        assert qa["status"] == "blocked"


def test_snapshot_survives_sqlite_reopen(tmp_path):
    engine = create_engine(f"sqlite:///{(tmp_path / 'qa.sqlite3').as_posix()}")
    SQLModel.metadata.create_all(engine)
    with DbSession(engine) as db:
        artifact = setup(db, tmp_path)
        run_id = artifact.task_run_id
        expected = create_scripted_review_for_diff(db, artifact.id).qa_assessment
    engine.dispose()
    with DbSession(engine) as db:
        assert list_task_run_reviews(db, run_id)[0].qa_assessment == expected
    engine.dispose()
