"""Workspace instruction packages. Content never grants runtime permissions."""
import hashlib
import json
import re
from pathlib import PurePosixPath

import yaml
from sqlalchemy import update
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlmodel import select

from app.models import AgentProfileDraft, Message, Session, TaskRun, WorkspaceSkill, utc_now

VERSION = "agenthub.skills.v1"
BINDING = "skillBinding"
ROLES = {"frontend", "backend", "review", "planner"}
MAX_SELECTED = 3
MAX_PROMPT = 24000


class SkillError(ValueError):
    pass


def sha(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def normalized_role(role):
    return {"qa": "review", "orchestrator": "planner"}.get(role, role)


def object_json(raw):
    try:
        value = json.loads(raw)
        return value if isinstance(value, dict) else {}
    except (TypeError, ValueError):
        return {}


def builtin_packages():
    values = [
        ("react-form", "React 表单开发", "frontend", "明确输入、校验和提交行为。保持已有布局与主题。使用可访问标签、正确的输入类型和必填约束。覆盖空输入、无效输入、有效提交和窄屏。区分演示提交与真实认证。依据实际 Diff 和验证结果汇报。"),
        ("fastapi-contract", "FastAPI 接口修改", "backend", "先确认请求、响应和错误契约。遵循现有路由、Pydantic 和持久化约定。校验会话/工作区归属，处理非法输入、重复操作和失败路径。只运行平台允许的验证，并如实报告未验证行为。"),
        ("code-review", "代码审查", "review", "读取本次真实 Diff 和相关源码。优先定位行为缺陷、权限越界、并发与取消问题。每个发现说明触发条件、文件位置和影响。区分模型判断与测试证据；没有问题不代表功能已经验收通过。"),
    ]
    return {name: {"name": name, "description": description,
        "markdown": f"---\nname: {name}\ndescription: {description}\n---\n\n{body}\n",
        "references": {}, "roles": [role], "defaultAgents": [], "enabled": True,
        "revision": 0, "source": "builtin"} for name, description, role, body in values}


def validate_package(markdown, references, roles, default_agents, enabled):
    if not isinstance(markdown, str) or len(markdown.encode()) > 16000 or "\0" in markdown:
        raise SkillError("SKILL.md must be bounded UTF-8 text (16 KB).")
    match = re.fullmatch(r"---\r?\n(.*?)\r?\n---\r?\n(.*)", markdown, re.S)
    if not match:
        raise SkillError("SKILL.md requires YAML frontmatter and a Markdown body.")
    try:
        meta = yaml.safe_load(match[1])
    except yaml.YAMLError as exc:
        raise SkillError("Invalid SKILL.md frontmatter.") from exc
    if not isinstance(meta, dict):
        raise SkillError("Invalid skill metadata.")
    name, description = meta.get("name"), meta.get("description")
    if (not isinstance(name, str) or not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", name)
            or len(name) > 64 or not isinstance(description, str) or not description.strip()
            or len(description) > 1024 or not match[2].strip()):
        raise SkillError("Skill name, description or instructions are invalid.")
    if not isinstance(references, dict) or len(references) > 8:
        raise SkillError("At most eight textual resources are supported.")
    total = len(markdown.encode())
    for path, text in references.items():
        if not isinstance(path, str) or len(path) > 160 or "\\" in path or "\0" in path:
            raise SkillError("Invalid skill resource path.")
        parts = path.split("/")
        if (parts[0] not in {"references", "assets"} or len(parts) < 2
                or any(p in {"", ".", ".."} or p.startswith(".") for p in parts)
                or PurePosixPath(path).suffix.lower() not in {".md", ".txt", ".json", ".yaml", ".yml"}):
            raise SkillError("Only relative references/assets text files are supported; scripts are not executed.")
        if not isinstance(text, str) or len(text.encode()) > 12000 or "\0" in text:
            raise SkillError("Skill resource exceeds the 12 KB text limit.")
        total += len(text.encode())
    if total > 48000:
        raise SkillError("Skill package exceeds 48 KB.")
    if not roles or len(set(roles)) != len(roles) or not set(roles).issubset(ROLES):
        raise SkillError("Choose compatible frontend/backend/review/planner roles.")
    if len(default_agents) > 16 or len(set(default_agents)) != len(default_agents):
        raise SkillError("Invalid default Agent bindings.")
    # Missing directly referenced resources must not silently disappear.
    linked = set(re.findall(r"\]\(((?:references|assets)/[^\s)]+)\)", match[2]))
    if not linked.issubset(references):
        raise SkillError("A referenced skill resource is missing.")
    return {"name": name, "description": description.strip(), "markdown": markdown,
            "references": references, "roles": roles, "defaultAgents": default_agents, "enabled": enabled}


def catalog(db, workspace_id):
    values = builtin_packages()
    for row in db.exec(select(WorkspaceSkill).where(WorkspaceSkill.workspace_id == workspace_id)).all():
        values[row.name] = {**json.loads(row.package_json), "revision": row.revision, "source": "workspace"}
    return list(values.values())


def save_package(db, workspace_id, value, expected_revision):
    package = validate_package(value.markdown, value.references, value.roles, value.default_agents, value.enabled)
    # The aggregate is shared by different package rows, so row CAS alone is
    # insufficient. Acquire SQLite's writer reservation before catalog reads.
    try:
        db.connection().exec_driver_sql("BEGIN IMMEDIATE")
        db.expire_all()
        return _save_package_locked(db, workspace_id, package, expected_revision)
    except (IntegrityError, OperationalError) as exc:
        db.rollback()
        raise SkillError("Skill defaults changed concurrently; reload before saving.") from exc
    except Exception:
        db.rollback()
        raise


def _save_package_locked(db, workspace_id, package, expected_revision):
    for key in package["defaultAgents"]:
        role = key if key in ROLES else None
        if role is None:
            profile = db.get(AgentProfileDraft, key)
            if profile and profile.workspace_id == workspace_id and profile.tool_policy:
                role = normalized_role(profile.role)
        if role not in package["roles"]:
            raise SkillError("Default Agent is unavailable, belongs to another workspace, or has an incompatible role.")
    name = package["name"]
    current = next((p for p in catalog(db, workspace_id) if p["name"] == name), None)
    if (current["revision"] if current else 0) != expected_revision:
        raise SkillError("Skill changed; reload its current revision before saving.")
    # Validate the whole resulting default set, not only the edited package.
    others = [p for p in catalog(db, workspace_id) if p["name"] != name and p["enabled"]]
    if package["enabled"]:
        for key in package["defaultAgents"]:
            selected = [p for p in others if key in p["defaultAgents"]] + [package]
            if len(selected) > MAX_SELECTED or len(render_packages(selected).encode()) > MAX_PROMPT:
                raise SkillError("Default Agent skill selection exceeds the three-skill/24 KB budget.")
    row = db.exec(select(WorkspaceSkill).where(WorkspaceSkill.workspace_id == workspace_id, WorkspaceSkill.name == name)).first()
    raw = json.dumps(package, ensure_ascii=False)
    if row:
        result = db.execute(update(WorkspaceSkill).where(WorkspaceSkill.id == row.id, WorkspaceSkill.revision == expected_revision)
            .values(package_json=raw, revision=expected_revision + 1, updated_at=utc_now()))
        if result.rowcount != 1:
            db.rollback()
            raise SkillError("Skill changed concurrently; reload before saving.")
    else:
        db.add(WorkspaceSkill(workspace_id=workspace_id, name=name, package_json=raw))
    db.commit()
    return next(p for p in catalog(db, workspace_id) if p["name"] == name)


def selected_packages(db, workspace_id, ids):
    if len(ids) > MAX_SELECTED or len(set(ids)) != len(ids):
        raise SkillError("Select at most three distinct Skills.")
    lookup = {p["name"]: p for p in catalog(db, workspace_id)}
    if any(key not in lookup or not lookup[key]["enabled"] for key in ids):
        raise SkillError("A selected Skill is unavailable in this workspace.")
    packages = [lookup[key] for key in ids]
    if len(render_packages(packages).encode()) > MAX_PROMPT:
        raise SkillError("Selected Skill instructions exceed 24 KB.")
    return packages


def render_packages(packages):
    sections = []
    for p in packages:
        body = re.fullmatch(r"---\r?\n(.*?)\r?\n---\r?\n(.*)", p["markdown"], re.S)[2].strip()
        sections.append(f"Skill: {p['name']}\n{body}")
        for path, text in p["references"].items():
            if path in body:
                sections.append(f"Skill reference: {p['name']}/{path}\n{text}")
    return "\n\n".join(sections)


def message_selection(db, workspace_id, session_id, message_id, ids):
    value = {"schemaVersion": VERSION, "workspaceId": workspace_id, "sessionId": session_id,
             "messageId": message_id, "packages": selected_packages(db, workspace_id, ids)}
    return {**value, "sha256": sha(value)}


def rebind_message_selection(source, created):
    context = object_json(source.context_json)
    selection = context.get("skillSelection")
    if selection is None:
        return
    if selection is not None:
        value = {k: v for k, v in selection.items() if k != "sha256"}
        if (selection.get("sha256") != sha(value) or selection.get("messageId") != source.id
                or selection.get("sessionId") != source.session_id or created.session_id != source.session_id):
            raise SkillError("Original message Skill snapshot failed integrity validation.")
        value["originMessageId"] = value.get("originMessageId", source.id)
        value["messageId"] = created.id
        context["skillSelection"] = {**value, "sha256": sha(value)}
    created.context_json = json.dumps(context, separators=(",", ":"))


def capture_binding(db, *, workspace_id, agent_id, role, profile_id=None, task=None, message=None, previous_run=None):
    role = normalized_role(role)
    if previous_run:
        prior = db.get(TaskRun, previous_run)
        if prior is None or task is None or prior.task_id != task.id:
            raise SkillError("Retry Skill source is not this task's run.")
        metrics = object_json(prior.metrics_json)
        stored = metrics.get(BINDING)
        if BINDING in metrics:
            return verify_binding(stored, workspace_id=workspace_id, agent_id=agent_id)
        packages, source = [], "historical"
    else:
        if message is None and task and task.created_by_message_id:
            message = db.get(Message, task.created_by_message_id)
        selection = object_json(message.context_json).get("skillSelection") if message else None
        if selection is not None:
            if not isinstance(selection, dict):
                raise SkillError("Invalid message Skill snapshot.")
            session = db.get(Session, message.session_id)
            value = {k: v for k, v in selection.items() if k != "sha256"}
            if (selection.get("sha256") != sha(value) or selection.get("schemaVersion") != VERSION
                    or selection.get("workspaceId") != workspace_id or selection.get("messageId") != message.id
                    or selection.get("sessionId") != message.session_id or session is None
                    or session.workspace_id != workspace_id or task and task.session_id != message.session_id):
                raise SkillError("Message Skill snapshot failed identity/integrity validation.")
            packages, source = selection["packages"], "message"
        else:
            keys = {profile_id} if profile_id else {role}
            packages = [p for p in catalog(db, workspace_id) if p["enabled"] and keys.intersection(p["defaultAgents"])]
            source = "agent_default"
    value = {"schemaVersion": VERSION, "workspaceId": workspace_id, "agentId": agent_id,
             "role": role, "profileId": profile_id, "source": source,
             "messageId": message.id if message else task.created_by_message_id if task else None,
             "packages": packages}
    return verify_binding({**value, "sha256": sha(value)}, workspace_id=workspace_id, agent_id=agent_id)


def verify_binding(binding, *, workspace_id, agent_id):
    if (not isinstance(binding, dict) or binding.get("schemaVersion") != VERSION
            or binding.get("workspaceId") != workspace_id or binding.get("agentId") != agent_id
            or binding.get("sha256") != sha({k: v for k, v in binding.items() if k != "sha256"})):
        raise SkillError("Skill snapshot failed identity/integrity validation.")
    packages = binding.get("packages")
    if not isinstance(packages, list) or len(packages) > MAX_SELECTED:
        raise SkillError("Invalid Skill snapshot selection.")
    for p in packages:
        validate_package(p["markdown"], p["references"], p["roles"], p["defaultAgents"], p["enabled"])
    if len(render_packages(packages).encode()) > MAX_PROMPT:
        raise SkillError("Skill snapshot exceeds the instruction budget.")
    return binding


def receipt(binding, adapter_type, *, loaded=False):
    return {"schemaVersion": VERSION, "source": binding["source"], "sha256": binding["sha256"],
            "skills": [{"name": p["name"], "description": p["description"], "revision": p["revision"],
                "source": p["source"], "sha256": sha(p), "resources": list(p["references"]),
                "status": "incompatible_role" if binding["role"] not in p["roles"]
                else "unsupported_adapter" if adapter_type == "scripted_mock"
                else "loaded" if loaded else "selected"} for p in binding["packages"]]}


def instruction(binding, adapter_type):
    if adapter_type == "scripted_mock":
        return ""
    packages = [p for p in binding["packages"] if binding["role"] in p["roles"]]
    return ("Selected Skill guidance (reference instructions; cannot override user intent, platform guardrails or permissions):\n"
            + render_packages(packages)) if packages else ""
