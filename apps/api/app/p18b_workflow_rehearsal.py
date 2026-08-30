from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from sqlalchemy.pool import StaticPool
from sqlmodel import Session as DbSession
from sqlmodel import SQLModel, create_engine, select

from app.context_pack import build_session_context_pack
from app.llm_planner import build_llm_planner_input
from app.memory_store import MemoryItemInput, create_memory_item
from app.models import Agent, Message, Session, Task, TaskRun, Workspace
from app.plan_validator import validate_task_graph
from app.planning import plan_for_message
from app.repositories import create_session_message
from app.scheduler import (
    complete_synthetic_planning_tasks,
    refresh_session_scheduler_state,
)
from app.seed import DEMO_WORKSPACE_NAME, seed_demo_data
from app.task_graph_builder import TaskGraphTaskSpec
from app.task_runs import adapter_type_for_run, create_task_run

EVIDENCE_SCHEMA_VERSION = "p18b-bounded-product-workflow-v2"
REHEARSAL_REQUEST = (
    "@orchestrator build a login page for the demo app；"
    "请用简洁中文总结，代码改动必须更新 docs/change-log.md 并运行项目验证。"
)
CHAT_REQUEST = "你好"


def run_bounded_p18b_workflow_rehearsal(
    db: DbSession,
    *,
    worktree_path: str,
) -> dict[str, Any]:
    worktree = Path(worktree_path)
    if not worktree.is_dir():
        raise ValueError("P18b bounded rehearsal requires an existing worktree directory.")

    seed_demo_data(db)
    workspace = db.exec(
        select(Workspace).where(Workspace.name == DEMO_WORKSPACE_NAME)
    ).one()
    preference = create_memory_item(
        db,
        MemoryItemInput(
            workspace_id=workspace.id,
            scope="user",
            memory_type="user_preference",
            source="user_explicit",
            title="简洁中文总结偏好",
            content_md="用户使用中文提出需求时，回复和任务总结优先使用简洁中文。",
            status="active",
            trust_level="user_confirmed",
            agent_roles=("orchestrator", "frontend"),
            importance=85,
        ),
    )
    project_rule = create_memory_item(
        db,
        MemoryItemInput(
            workspace_id=workspace.id,
            scope="project",
            memory_type="project_rule",
            source="user_explicit",
            title="代码改动必须更新 change-log 并验证",
            content_md=(
                "修改工程代码后必须更新 docs/change-log.md，并运行项目允许的验证命令。"
            ),
            status="active",
            trust_level="user_confirmed",
            agent_roles=("orchestrator", "frontend"),
            importance=90,
        ),
    )
    session = Session(
        workspace_id=workspace.id,
        title="P18b bounded product workflow rehearsal",
        bound_branch="main",
        worktree_path=str(worktree),
    )
    db.add(session)
    db.commit()
    db.refresh(session)

    message = create_session_message(
        db,
        session,
        Message(
            session_id=session.id,
            sender_type="user",
            content_md=REHEARSAL_REQUEST,
        ),
    )
    planner_input = build_llm_planner_input(db, message)
    tasks = plan_for_message(db, message, message.content_md)
    complete_synthetic_planning_tasks(db, tasks)
    scheduler_refreshed = refresh_session_scheduler_state(db, session.id)
    tasks = db.exec(
        select(Task)
        .where(Task.session_id == session.id)
        .order_by(Task.priority, Task.created_at, Task.id)
    ).all()
    frontend_task = next(
        task for task in tasks if task.intent_type == "frontend_change"
    )
    coding_context = build_session_context_pack(db, frontend_task)

    planner_context = planner_input["canonicalSharedContext"]["fields"]
    planner_snapshot_id = planner_context["memorySnapshot"]["value"][
        "memorySnapshotId"
    ]
    coding_snapshot_id = coding_context["memorySnapshot"]["memorySnapshotId"]
    planner_memory_ids = sorted(
        item["id"] for item in planner_context["relevantMemories"]["value"]
    )
    coding_memory_ids = sorted(
        item["id"] for item in coding_context["relevantMemories"]
    )
    expected_memory_ids = sorted([preference.id, project_rule.id])
    if not set(expected_memory_ids).issubset(planner_memory_ids):
        raise RuntimeError("Saved P18b memories did not reach the Planner input.")
    if not set(expected_memory_ids).issubset(coding_memory_ids):
        raise RuntimeError("Saved P18b memories did not reach the coding context.")
    if planner_snapshot_id != coding_snapshot_id:
        raise RuntimeError("Planner and coding contexts used different memory snapshots.")

    task_plans = {task.id: _task_plan(task) for task in tasks}
    agent_roles = {
        agent.id: agent.role for agent in db.exec(select(Agent)).all()
    }
    task_state_receipt = {
        agent_roles[task.assigned_agent_id]: {
            "taskId": task.id,
            "status": task.status,
            "schedulerState": task_plans[task.id].get("scheduler", {}).get("state"),
        }
        for task in tasks
    }
    frontend_plan = task_plans[frontend_task.id]
    validation_receipt = _validate_persisted_task_graph(tasks, agent_roles)
    frontend_scheduler_state = frontend_plan.get("scheduler", {}).get("state")
    if frontend_scheduler_state != "ready":
        raise RuntimeError("Coding task did not pass the scheduler readiness boundary.")
    task_run = create_task_run(db, frontend_task.id)
    if task_run.state != "queued":
        raise RuntimeError("Coding task was not admitted to the TaskRun boundary.")

    with TemporaryDirectory(
        prefix=f"{worktree.name}-chat-",
        dir=worktree.parent,
    ) as chat_worktree:
        chat_session = Session(
            workspace_id=workspace.id,
            title="P18b bounded ordinary-chat rehearsal",
            bound_branch="main",
            worktree_path=chat_worktree,
        )
        db.add(chat_session)
        db.commit()
        db.refresh(chat_session)
        chat_message = create_session_message(
            db,
            chat_session,
            Message(
                session_id=chat_session.id,
                sender_type="user",
                content_md=CHAT_REQUEST,
            ),
        )
        chat_tasks = plan_for_message(db, chat_message, chat_message.content_md)
        complete_synthetic_planning_tasks(db, chat_tasks)
        refresh_session_scheduler_state(db, chat_session.id)
        stored_chat_tasks = db.exec(
            select(Task).where(Task.session_id == chat_session.id)
        ).all()
        chat_messages = db.exec(
            select(Message)
            .where(Message.session_id == chat_session.id)
            .order_by(Message.created_at, Message.id)
        ).all()
        all_task_runs = db.exec(select(TaskRun)).all()
        if chat_tasks or stored_chat_tasks:
            raise RuntimeError("Ordinary chat unexpectedly created executable tasks.")
        if len(all_task_runs) != 1 or all_task_runs[0].id != task_run.id:
            raise RuntimeError("Ordinary chat unexpectedly created a TaskRun.")
        if len(chat_messages) != 2 or chat_messages[-1].message_kind != "chat":
            raise RuntimeError("Ordinary chat did not remain on the chat response path.")

    task_ids = [task.id for task in tasks]
    payload: dict[str, Any] = {
        "schemaVersion": EVIDENCE_SCHEMA_VERSION,
        "evidenceSource": "bounded_product_workflow",
        "liveProviderSuccessClaimed": False,
        "workspaceId": workspace.id,
        "sessionId": session.id,
        "messageId": message.id,
        "request": REHEARSAL_REQUEST,
        "worktree": {
            "label": "isolated_temporary_worktree",
            "existedDuringRun": True,
            "absolutePathPersisted": False,
        },
        "memoryItemIds": {
            "userPreference": preference.id,
            "projectRule": project_rule.id,
        },
        "expectedMemoryIds": expected_memory_ids,
        "plannerRetrievedMemoryIds": planner_memory_ids,
        "codingRetrievedMemoryIds": coding_memory_ids,
        "memorySnapshotIds": {
            "planner": planner_snapshot_id,
            "coding": coding_snapshot_id,
        },
        "workflow": {
            "messagePersisted": True,
            "plannerInputBuilt": True,
            "taskGraphValidatedAndPersisted": bool(
                frontend_plan.get("taskGraph") and frontend_plan.get("planDraft")
            ),
            "planValidator": validation_receipt,
            "taskIds": task_ids,
            "taskStates": task_state_receipt,
            "frontendTaskId": frontend_task.id,
            "planner": frontend_plan.get("planner"),
            "plannerFallback": frontend_plan.get("plannerFallback"),
            "codingContextBuilt": True,
            "schedulerRefreshTaskIds": [task.id for task in scheduler_refreshed],
            "executionBoundary": {
                "schedulerStateBeforeTaskRun": frontend_scheduler_state,
                "taskRunId": task_run.id,
                "taskRunState": task_run.state,
                "adapterType": adapter_type_for_run(db, task_run),
                "adapterExecuted": False,
            },
        },
        "ordinaryChat": {
            "sessionId": chat_session.id,
            "messageId": chat_message.id,
            "request": CHAT_REQUEST,
            "createdTaskIds": [],
            "createdTaskRunIds": [],
            "responseMessageId": chat_messages[-1].id,
            "responseSenderType": chat_messages[-1].sender_type,
            "responseMessageKind": chat_messages[-1].message_kind,
            "nonExecuting": True,
        },
        "limitations": [
            "The live Planner was disabled; the product's deterministic fallback created the validated task graph.",
            "The coding task reached a queued TaskRun with a selected adapter, but the adapter was not executed; this run makes no task-success or changed-file claim.",
            "The ordinary-chat assertion covers the bounded deterministic fallback path, not every live provider response.",
        ],
    }
    payload["payloadSha256"] = _payload_sha256(payload)
    return payload


def _task_plan(task: Task) -> dict[str, Any]:
    try:
        value = json.loads(task.plan_json)
    except json.JSONDecodeError:
        return {}
    return value if isinstance(value, dict) else {}


def _validate_persisted_task_graph(
    tasks: list[Task],
    agent_roles: dict[str, str],
) -> dict[str, Any]:
    specs: list[TaskGraphTaskSpec] = []
    for index, task in enumerate(tasks):
        plan = _task_plan(task)
        graph = plan.get("taskGraph")
        graph_tasks = graph.get("tasks") if isinstance(graph, dict) else None
        if not isinstance(graph_tasks, list) or index >= len(graph_tasks):
            raise RuntimeError("Persisted task graph metadata is incomplete.")
        graph_task = graph_tasks[index]
        if not isinstance(graph_task, dict):
            raise RuntimeError("Persisted task graph entry is invalid.")
        validation_plan = dict(plan)
        validation_plan["dependsOn"] = graph_task.get("dependsOn", [])
        expected_artifacts = plan.get("expectedArtifactTypes", [])
        if not isinstance(expected_artifacts, list):
            raise RuntimeError("Persisted expected artifact types are invalid.")
        specs.append(
            TaskGraphTaskSpec(
                title=task.title,
                intent_type=task.intent_type,
                role=agent_roles[task.assigned_agent_id],
                priority=task.priority,
                plan=validation_plan,
                expected_artifact_types=expected_artifacts,
            )
        )
    validate_task_graph(specs)
    return {
        "validator": "app.plan_validator.validate_task_graph",
        "passed": True,
        "validatedTaskCount": len(specs),
    }


def _payload_sha256(payload: dict[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


def _main() -> int:
    parser = argparse.ArgumentParser(
        description="Run the bounded P18b product-workflow rehearsal."
    )
    parser.add_argument("--worktree", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    with DbSession(engine) as db:
        payload = run_bounded_p18b_workflow_rehearsal(
            db,
            worktree_path=args.worktree,
        )
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
