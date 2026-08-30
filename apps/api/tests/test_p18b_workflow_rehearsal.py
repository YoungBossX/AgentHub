import hashlib
import json
from pathlib import Path
import subprocess

from sqlalchemy.pool import StaticPool
from sqlmodel import Session as DbSession
from sqlmodel import SQLModel, create_engine

from app.p18b_workflow_rehearsal import (
    EVIDENCE_SCHEMA_VERSION,
    run_bounded_p18b_workflow_rehearsal,
)


def test_bounded_p18b_rehearsal_uses_saved_memories_in_real_workflow(
    tmp_path: Path,
) -> None:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    worktree = tmp_path / "bounded-worktree"
    worktree.mkdir()
    _initialize_git_worktree(worktree)

    with DbSession(engine) as db:
        evidence = run_bounded_p18b_workflow_rehearsal(
            db,
            worktree_path=str(worktree),
        )

    assert evidence["schemaVersion"] == EVIDENCE_SCHEMA_VERSION
    assert evidence["evidenceSource"] == "bounded_product_workflow"
    assert evidence["liveProviderSuccessClaimed"] is False
    assert set(evidence["expectedMemoryIds"]).issubset(
        evidence["plannerRetrievedMemoryIds"]
    )
    assert set(evidence["expectedMemoryIds"]).issubset(
        evidence["codingRetrievedMemoryIds"]
    )
    assert len(evidence["expectedMemoryIds"]) == 2
    assert (
        evidence["memorySnapshotIds"]["planner"]
        == evidence["memorySnapshotIds"]["coding"]
    )
    workflow = evidence["workflow"]
    assert workflow["messagePersisted"] is True
    assert workflow["plannerInputBuilt"] is True
    assert workflow["taskGraphValidatedAndPersisted"] is True
    assert len(workflow["taskIds"]) == 3
    assert workflow["taskStates"] == {
        "orchestrator": {
            "taskId": workflow["taskIds"][0],
            "status": "completed",
            "schedulerState": "completed",
        },
        "frontend": {
            "taskId": workflow["taskIds"][1],
            "status": "pending",
            "schedulerState": "ready",
        },
        "qa": {
            "taskId": workflow["taskIds"][2],
            "status": "waiting_dependency",
            "schedulerState": "waiting_dependency",
        },
    }
    assert workflow["planner"] == "deterministic_login_v1"
    assert workflow["codingContextBuilt"] is True
    assert workflow["planValidator"] == {
        "validator": "app.plan_validator.validate_task_graph",
        "passed": True,
        "validatedTaskCount": 3,
    }
    assert len(workflow["schedulerRefreshTaskIds"]) == 2
    execution = workflow["executionBoundary"]
    assert execution["schedulerStateBeforeTaskRun"] == "ready"
    assert execution["taskRunState"] == "queued"
    assert execution["adapterType"] == "codex"
    assert execution["adapterExecuted"] is False
    assert evidence["ordinaryChat"] == {
        "sessionId": evidence["ordinaryChat"]["sessionId"],
        "messageId": evidence["ordinaryChat"]["messageId"],
        "request": "你好",
        "createdTaskIds": [],
        "createdTaskRunIds": [],
        "responseMessageId": evidence["ordinaryChat"]["responseMessageId"],
        "responseSenderType": "orchestrator",
        "responseMessageKind": "chat",
        "nonExecuting": True,
    }
    assert evidence["worktree"] == {
        "label": "isolated_temporary_worktree",
        "existedDuringRun": True,
        "absolutePathPersisted": False,
    }

    payload = dict(evidence)
    digest = payload.pop("payloadSha256")
    assert digest == hashlib.sha256(
        json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


def _initialize_git_worktree(worktree: Path) -> None:
    app_dir = worktree / "apps" / "demo" / "src"
    app_dir.mkdir(parents=True)
    (app_dir / "App.tsx").write_text(
        "export default function App() { return <main>demo</main>; }\n",
        encoding="utf-8",
    )
    (app_dir / "styles.css").write_text("main { color: black; }\n", encoding="utf-8")
    commands = [
        ["git", "init", "-b", "main"],
        ["git", "config", "user.name", "AgentHub P18b Rehearsal"],
        ["git", "config", "user.email", "p18b@example.invalid"],
        ["git", "add", "."],
        ["git", "commit", "-m", "p18b bounded baseline"],
    ]
    for command in commands:
        subprocess.run(
            command,
            cwd=worktree,
            check=True,
            capture_output=True,
            text=True,
        )
