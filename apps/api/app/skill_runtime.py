"""Load a frozen run package into an actual provider request."""
import json

from app.events import append_task_run_event
from app.skills import BINDING, instruction, receipt, verify_binding


def load_instruction(db, run, workspace_id, agent_id, adapter_type):
    metrics = json.loads(run.metrics_json)
    stored = metrics.get(BINDING)
    if stored is None:
        return ""
    binding = verify_binding(stored, workspace_id=workspace_id, agent_id=agent_id)
    return instruction(binding, adapter_type)


def record_loaded(db, run, workspace_id, agent_id, adapter_type):
    metrics = json.loads(run.metrics_json)
    stored = metrics.get(BINDING)
    if stored is None:
        return
    binding = verify_binding(stored, workspace_id=workspace_id, agent_id=agent_id)
    evidence = receipt(binding, adapter_type, loaded=True)
    if metrics.get("skills") == evidence:
        return
    metrics["skills"] = evidence
    run.metrics_json = json.dumps(metrics, separators=(",", ":"))
    db.add(run)
    db.commit()
    if evidence["skills"]:
        event = "skills.loaded" if any(s["status"] == "loaded" for s in evidence["skills"]) else "skills.skipped"
        append_task_run_event(db, task_run_id=run.id, event_type=event, payload_json=json.dumps(evidence))
