"""Bounded, atomic coordination for explicitly selected execution roles."""

import json

from sqlmodel import Session as DbSession

from app.agent_profiles import profile_for_draft
from app.agent_selection_policy import AgentSelectionError, validate_agent_selection
from app.custom_agents import CustomAgentError, require_custom_agent
from app.group_planner import apply_native_group_plan
from app.llm_planner import LLMPlannerError
from app.models import Message, Task
from app.plan_validator import PlanValidationError, validate_task_graph
from app.planning_intents import (
    MentionParseError, ParsedMentions, _demo_backend_target_exists,
    _is_explicit_platform_mode_request, _is_safe_demo_frontend_request,
    _primary_allowed_path, _session_for_message,
    parse_frontend_intent,
)
from app.planning_tasks import _create_direct_assignment_tasks, _enabled_agent_or_raise
from app.repositories import create_session_message
from app.target_registry import (
    DEMO_BACKEND_TARGET_ID, DEMO_FRONTEND_TARGET_ID, TargetRegistryError,
    get_target_for_workspace,
)
from app.task_graph_builder import TaskGraphTaskSpec, task_graph_metadata, task_key


GROUP_PLANNER = "explicit_group_v1"


def create_explicit_group_tasks(
    db: DbSession,
    message: Message,
    parsed: ParsedMentions,
    *,
    existing_tasks: list[Task],
) -> list[Task]:
    session = _session_for_message(db, message)
    coordinator = _enabled_agent_or_raise(db, "orchestrator")
    context = json.loads(message.context_json)
    execution = context.get("groupExecution", "automatic")
    if not isinstance(execution, str) or execution not in {"automatic", "manual"}:
        raise MentionParseError("groupExecution must be automatic or manual.")
    if _is_explicit_platform_mode_request(message.content_md):
        raise MentionParseError("Group assignments do not allow platform maintenance; use a separate approved task.")

    writers = [role for role in parsed.roles if role in {"frontend", "backend"}]
    reviewers = [role for role in parsed.roles if role in {"qa", "review"}]
    targets = {}
    writer_targets = {}
    try:
        # Resolve every target before calling factories which may emit boundary replies.
        for role in writers:
            target_id = (
                session.active_frontend_target_id or DEMO_FRONTEND_TARGET_ID
                if role == "frontend" else
                session.active_backend_target_id or DEMO_BACKEND_TARGET_ID
            )
            target = get_target_for_workspace(db, session.workspace_id, target_id)
            if target.requires_platform_mode or target.requires_approval or not target.allows_agent(role):
                raise MentionParseError(f"Group Agent {role} cannot use target {target_id}.")
            if role == "frontend" and target_id == DEMO_FRONTEND_TARGET_ID and not _is_safe_demo_frontend_request(message.content_md):
                raise MentionParseError("Bound the group frontend assignment to the demo app UI.")
            if role == "backend" and target_id == DEMO_BACKEND_TARGET_ID and not _demo_backend_target_exists():
                raise MentionParseError("Group backend assignment needs a safe demo backend target.")
            writer_targets[role] = target
            targets[target_id] = target
        review_targets = list(writer_targets.values())
        if reviewers and not review_targets:
            target_id = session.active_frontend_target_id or session.active_backend_target_id or DEMO_FRONTEND_TARGET_ID
            review_targets = [get_target_for_workspace(db, session.workspace_id, target_id)]
        for target in review_targets:
            if target.requires_platform_mode or target.requires_approval:
                raise MentionParseError("Group review cannot use an unapproved platform target.")
            targets[target.target_id] = target

        profiles = {
            role: require_custom_agent(db, session.workspace_id, profile_id)
            for role, profile_id in parsed.profile_ids.items()
        }
        tasks = []
        write_ids = []
        previous = existing_tasks[-1].id if existing_tasks else None
        assignments = [(role, writer_targets[role]) for role in writers]
        assignments.extend((role, target) for role in reviewers for target in review_targets)
        for role, target in assignments:
            if not target.allows_agent(role):
                raise MentionParseError(f"Group Agent {role} cannot use target {target.target_id}.")
            task = _create_direct_assignment_tasks(
                db, message, role, existing_tasks=[*existing_tasks, *tasks], persist=False,
            )[0]
            plan = json.loads(task.plan_json)
            if role in writers and plan.get("targetId") != target.target_id:
                raise MentionParseError("Group task factory did not preserve the selected target.")
            if role in writers and target.target_id.startswith("external-"):
                # Factory file hints include manifests even for src-only targets.
                # Keep only permitted hints; execution retains the target policy.
                plan["files"] = [path for path in plan.get("files", []) if target.permits_path(path)]
            if role == "frontend" and target.target_id == DEMO_FRONTEND_TARGET_ID:
                intent = parse_frontend_intent(message.content_md, include_login_creation=True)
                if intent is not None:
                    plan.update({"target": intent.target, "targetText": intent.target_text})
            if role in reviewers:
                plan.update({
                    "targetId": target.target_id, "safeTarget": _primary_allowed_path(target),
                    "target": "explicit_group_review", "readOnly": True,
                    "allowedPaths": list(target.allowed_paths), "deniedPaths": list(target.denied_paths),
                    "files": [],
                })
                task.title += f" [{target.name}]"
            plan.update({"planner": GROUP_PLANNER, "plannerSource": "deterministic", "routing": "multiple_mentions", "autoStart": execution == "automatic"})
            profile = profiles.get(role)
            if profile is not None:
                plan.update({"agentProfileId": profile.id, "agentProfileDisplayName": profile.display_name, "agentMentionAlias": profile.mention_alias})
            task.plan_json = json.dumps(plan, separators=(",", ":"))
            dependencies = list(write_ids) if role in reviewers else []
            if previous and previous not in dependencies:
                dependencies.append(previous)
            task.depends_on_task_ids = json.dumps(dependencies, separators=(",", ":"))
            agent = _enabled_agent_or_raise(db, "qa" if role == "review" else role)
            validate_agent_selection(db, task, agent, selected_profile=profile_for_draft(profile) if profile else None)
            tasks.append(task)
            previous = task.id
            if role in writers:
                write_ids.append(task.id)

        native = apply_native_group_plan(db, message, session, tasks, targets)
        from app.group_summaries import STATE_KEY, SUMMARY_SCHEMA, deterministic_summary_policy

        summary_policy = native.pop("_summaryPolicy") if native else deterministic_summary_policy(db, session, coordinator)
        summary_policy.update({"agentId": coordinator.id, "workspaceId": session.workspace_id,
                               "displayName": (summary_policy.get("selection") or {}).get("displayName") or coordinator.name})
        # Revalidate all execution selections and target bindings after the call.
        db.expire_all()
        db.refresh(coordinator)
        if not coordinator.enabled:
            raise MentionParseError("Group coordinator was disabled during planning.")
        for role, profile in profiles.items():
            db.refresh(profile)
            require_custom_agent(db, session.workspace_id, profile.id)
        for task in tasks:
            plan = json.loads(task.plan_json)
            role = plan["assignedRole"]
            target = get_target_for_workspace(db, session.workspace_id, plan["targetId"])
            if target != targets[target.target_id]:
                raise MentionParseError("Group target policy changed during planning.")
            agent = _enabled_agent_or_raise(db, "qa" if role == "review" else role)
            db.refresh(agent)
            if not agent.enabled:
                raise MentionParseError("Group execution Agent was disabled during planning.")
            validate_agent_selection(db, task, agent, selected_profile=profile_for_draft(profiles[role]) if role in profiles else None)

        specs = []
        keys = {}
        for index, task in enumerate(tasks):
            plan = json.loads(task.plan_json)
            role = plan["assignedRole"]
            spec = TaskGraphTaskSpec(
                title=task.title, intent_type=task.intent_type, role="qa" if role == "review" else role,
                priority=task.priority, plan={**plan, "dependsOn": [keys[dep] for dep in json.loads(task.depends_on_task_ids) if dep in keys]},
                expected_artifact_types=plan["expectedArtifactTypes"],
            )
            keys[task.id] = task_key(index, spec)
            specs.append(spec)
        validate_task_graph(specs, allowed_targets=targets, max_tasks=6)
        graph = task_graph_metadata(goal=message.content_md, intent="explicit_group", planner=GROUP_PLANNER, task_specs=specs)
        for node, task in zip(graph["tasks"], tasks):
            node["assignedAgentRole"] = json.loads(task.plan_json)["assignedRole"]
        participants = [
            {"role": role, "profileId": profiles[role].id if role in profiles else None,
             "mentionAlias": profiles[role].mention_alias if role in profiles else role,
             "displayName": profiles[role].display_name if role in profiles else _enabled_agent_or_raise(db, "qa" if role == "review" else role).name}
            for role in parsed.roles
        ]
        group = {"id": message.id, "participants": participants, "coordinationSource": native["plannerSource"] if native else "deterministic", "execution": execution}
        reply_id = Message(session_id=message.session_id, sender_type="orchestrator", content_md="").id
        group["coordinatorMessageId"] = reply_id
        if native:
            group["plannerEvidence"] = native
        for index, task in enumerate(tasks):
            plan = json.loads(task.plan_json)
            plan.update({"taskGraph": graph, "taskKey": task_key(index, specs[index]), "groupAssignment": group})
            task.plan_json = json.dumps(plan, separators=(",", ":"))
            db.add(task)
        labels = "、".join(f"{item['displayName']} (@{item['mentionAlias']})" for item in participants if item["role"] != "orchestrator")
        coordination = f"原生 Planner 已完成规划：{native['rationale']}" if native else "使用确定性协调"
        execution_hint = (
            "就绪任务将自动启动；失败、中断或审批阻塞时暂停后续任务，重试成功后继续。"
            if execution == "automatic" else "请依次启动就绪任务。"
        )
        reply = Message(
            id=reply_id,
            session_id=message.session_id, sender_type="orchestrator", sender_id=coordinator.id,
            message_kind="plan", parent_message_id=message.id,
            content_md=f"已为 {labels} 创建 {len(tasks)} 个任务。{coordination}。写任务依次执行，评审等待全部写任务完成，并分别绑定对应目标。{execution_hint}",
            context_json=json.dumps({STATE_KEY: {"schemaVersion": SUMMARY_SCHEMA, "taskIds": [task.id for task in tasks],
                "policy": summary_policy, "execution": execution, "status": "waiting"}}, ensure_ascii=False),
        )
        # The repository commits tasks and coordinator reply in the same transaction.
        create_session_message(db, session, reply)
        for task in tasks:
            db.refresh(task)
        return tasks
    except (CustomAgentError, AgentSelectionError, TargetRegistryError, PlanValidationError, LLMPlannerError) as exc:
        db.rollback()
        raise MentionParseError(str(exc)) from exc
    except Exception:
        db.rollback()
        raise
