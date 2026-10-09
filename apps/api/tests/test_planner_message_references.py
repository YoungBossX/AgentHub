import json
from contextlib import contextmanager

from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, Session as DbSession, create_engine

from app.context_pack import build_session_context_pack
from app.llm_planner import build_llm_planner_input, build_llm_planner_request
from app.models import Agent, Artifact, Message, Session, Task, TaskRun, Workspace


@contextmanager
def conversation():
    engine = create_engine("sqlite://", poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)
    with DbSession(engine) as db:
        workspace = Workspace(name="References", root_path="apps/demo", repo_url="local://apps/demo", default_branch="main")
        session = Session(workspace_id=workspace.id, title="References", bound_branch="main", worktree_path=".worktrees/references")
        agent = Agent(name="Frontend", role="frontend", adapter_type="codex", provider="local")
        task = Task(session_id=session.id, title="Previous code", intent_type="frontend_change", assigned_agent_id=agent.id)
        run = TaskRun(task_id=task.id, agent_id=agent.id, state="completed", worktree_path=session.worktree_path)
        artifact = Artifact(task_run_id=run.id, artifact_type="diff", title="Previous diff", status="ready")
        db.add_all([workspace, session, agent, task, run, artifact])
        db.commit()
        yield db, session, agent, artifact
    engine.dispose()


def test_selected_code_reaches_ordinary_and_group_planner_before_execution():
    with conversation() as (db, session, agent, artifact):
        text = "  const title = 'SELECTION_ONLY_VALUE';\n"
        message = Message(session_id=session.id, sender_type="user", content_md="Use the selected code", context_json=json.dumps({
            "contextItems": [{"kind": "selected_text", "artifactId": artifact.id, "selectedText": text,
                              "metadata": {"path": "apps/demo/src/App.tsx", "source": "editor_draft"}}],
        }))
        task = Task(session_id=session.id, title="Continue", intent_type="frontend_change", assigned_agent_id=agent.id,
                    created_by_message_id=message.id, plan_json=json.dumps({"targetId": "demo-frontend"}))
        db.add_all([message, task]); db.commit()
        ordinary = build_llm_planner_input(db, message)
        group = build_llm_planner_request(db, message, target_ids={"demo-frontend"}).to_provider_payload()
        execution = build_session_context_pack(db, task)
        for request in (ordinary, group):
            field = request["canonicalSharedContext"]["fields"]["relevantArtifacts"]
            item = field["value"]["contextItems"][0]
            assert item == execution["contextItems"][0]
            assert item["selectedText"] == text
            assert item["metadata"] == {"path": "apps/demo/src/App.tsx", "source": "editor_draft"}
            assert request["artifactReferences"][0]["selectedText"] == text
            assert "metadata" not in request["artifactReferences"][0]
            assert field["trustLevel"] != "system"


def test_planner_does_not_attribute_selected_text_to_another_session_artifact():
    with conversation() as (db, session, _, artifact):
        other = Session(workspace_id=session.workspace_id, title="Other", bound_branch="main", worktree_path=".worktrees/other")
        message = Message(session_id=other.id, sender_type="user", content_md="Inspect reference", context_json=json.dumps({
            "contextItems": [{"kind": "selected_text", "artifactId": artifact.id, "selectedText": "FORGED_SOURCE"}],
        }))
        db.add_all([other, message]); db.commit()
        request = build_llm_planner_input(db, message)
        references = request["canonicalSharedContext"]["fields"]["relevantArtifacts"]["value"]
        assert not references["contextItems"][0]["valid"]
        assert "FORGED_SOURCE" not in json.dumps(references)
        assert request["artifactReferences"] == []


def test_planner_reference_budgets_redaction_and_malformed_context():
    with conversation() as (db, session, _, artifact):
        message = Message(session_id=session.id, sender_type="user", content_md="Inspect bounded reference", context_json=json.dumps({
            "contextItems": [{"kind": "selected_text", "artifactId": artifact.id, "selectedText": "x" * 2500},
                             {"kind": "note", "summary": "api_key=private_value"}] + [{"kind": "note", "summary": "note"}] * 10,
        }))
        db.add(message); db.commit()
        request = build_llm_planner_input(db, message)
        items = request["canonicalSharedContext"]["fields"]["relevantArtifacts"]["value"]["contextItems"]
        assert len(items) == 8
        assert len(items[0]["selectedText"]) == 2400
        assert items[0]["redacted"]
        assert "private_value" not in json.dumps(request)
        for bad in ("null", "[]", "broken"):
            message.context_json = bad
            request = build_llm_planner_input(db, message)
            assert request["artifactReferences"] == []
