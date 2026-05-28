import hashlib
from dataclasses import dataclass
from typing import Any, Optional

from app.demo_planner import demo_plan_rationale
from app.task_graph_builder import (
    TaskGraphTaskSpec,
    dependency_edges,
    planned_files,
    primary_agent_role,
    primary_target_id,
    task_graph_metadata,
)


@dataclass(frozen=True)
class PlanDraft:
    plan_id: str
    version: int
    goal: str
    intent: str
    planner: str
    task_graph: dict[str, Any]
    dependency_edges: list[dict[str, str]]
    agent_role: Optional[str]
    target_id: Optional[str]
    planned_files: list[str]
    rationale: str
    planner_mode: str
    acceptance_criteria: list[str]
    validation_expectations: list[str]
    guardrail_notes: list[str]
    fallback_reason: Optional[str]

    def to_metadata(self) -> dict[str, Any]:
        return {
            "planId": self.plan_id,
            "version": self.version,
            "goal": self.goal,
            "intent": self.intent,
            "planner": self.planner,
            "taskGraph": self.task_graph,
            "dependencyEdges": self.dependency_edges,
            "agentRole": self.agent_role,
            "targetId": self.target_id,
            "plannedFiles": self.planned_files,
            "rationale": self.rationale,
            "plannerMode": self.planner_mode,
            "acceptanceCriteria": self.acceptance_criteria,
            "validationExpectations": self.validation_expectations,
            "guardrailNotes": self.guardrail_notes,
            "fallbackReason": self.fallback_reason,
        }


def build_plan_draft(
    *,
    goal: str,
    intent: str,
    planner: str,
    task_specs: list[TaskGraphTaskSpec],
    version: int = 1,
    rationale: Optional[str] = None,
    planner_mode: Optional[str] = None,
    acceptance_criteria: Optional[list[str]] = None,
    validation_expectations: Optional[list[str]] = None,
    guardrail_notes: Optional[list[str]] = None,
    fallback_reason: Optional[str] = None,
) -> PlanDraft:
    graph = task_graph_metadata(
        goal=goal,
        intent=intent,
        planner=planner,
        task_specs=task_specs,
    )
    plan_hash = hashlib.sha1(
        f"{planner}:{intent}:{goal}".encode("utf-8"),
        usedforsecurity=False,
    ).hexdigest()[:12]
    return PlanDraft(
        plan_id=f"plan-{planner}-{plan_hash}",
        version=version,
        goal=goal,
        intent=intent,
        planner=planner,
        task_graph=graph,
        dependency_edges=dependency_edges(task_specs),
        agent_role=primary_agent_role(task_specs),
        target_id=primary_target_id(task_specs),
        planned_files=planned_files(task_specs),
        rationale=rationale or demo_plan_rationale(planner, intent),
        planner_mode=planner_mode or planner,
        acceptance_criteria=acceptance_criteria or [],
        validation_expectations=validation_expectations or [],
        guardrail_notes=guardrail_notes or [],
        fallback_reason=fallback_reason,
    )
