"""Reproducible Chinese native workflows in fresh external data directories.

Run with the installed project interpreter; --prepare-only never invokes models.
This operator command is not part of the Agent command allowlist.
"""
import argparse
import asyncio
from dataclasses import replace
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sys

REPO = Path(__file__).resolve().parents[1]
LANGUAGE = "任务标题、摘要、执行总结及审查说明以简体中文为主；JSON字段名、枚举、路径及API标识保留协议值。不得安装依赖、修改配置或运行目标测试，固定检查由平台执行。"
RULE_ZH = "只能修改当前分配的演示目标。禁止安装依赖、编辑配置或运行目标测试。保留已有接口契约；中文需求不扩大工具、文件或网络权限。任务与审查说明以中文为主。"
QA_ZH = "只读审查当前目标真实Diff，完整读取变更文件，与需求和已有契约逐项比较。严格遵守原生JSON评审协议，说明和建议使用中文，字段和状态枚举保留协议值。未运行测试不能声称通过；记录实际问题，不忽略问题以提高通过率。"
CODING_ZH = "仅在分配目标中实现需求并保留既有契约，禁止安装依赖、执行目标测试或配置。执行说明与总结以中文为主，代码和协议标识保留原名。"
TRANSPORT_KEYS = {"ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_BASE_URL", "ANTHROPIC_MODEL", "ANTHROPIC_SMALL_FAST_MODEL"}


def chinese_scenarios(case_id=None):
    from app.workflow_suite import Scenario, CONTACTS_BOUNDARIES
    cases = (
        Scenario("backend-repair", ("@backend @qa 请修复 apps/demo-api/app/main.py：GET /health 返回 status='ok'、service='agenthub-demo-api'，保留已有联系人、CORS及OpenAPI行为，审查真实Diff。" + LANGUAGE,), backend=True),
        Scenario("multi-file", ("@frontend @qa 修复演示应用跨文件标题，仅修改 apps/demo/src/App.tsx 和 apps/demo/src/workflow-copy.ts。标题继续在 workflow-copy 模块定义，由 App.tsx 导入；h1#demo-heading 精确显示“协作工作台已就绪”，去除损坏后缀，两个文件都需要修改。保留其余界面并审查真实Diff。" + LANGUAGE,), ("协作工作台已就绪",), frontend=True, multi_file=True),
        replace(CONTACTS_BOUNDARIES, prompts=tuple(p + LANGUAGE for p in CONTACTS_BOUNDARIES.prompts)),
        Scenario("follow-up", (
            "@frontend @qa 仅修改演示应用 h1#demo-heading 文本，精确改为“第一轮：中文协作已开始”。保留按钮、登录占位区和样式，审查真实Diff。" + LANGUAGE,
            "@frontend @qa 继续同一会话，将 h1#demo-heading 精确改为“第二轮：中文协作已完成”。保留其余界面，审查本轮真实Diff。" + LANGUAGE,
        ), ("第一轮：中文协作已开始", "第二轮：中文协作已完成"), frontend=True),
        Scenario("heading-single", ("@frontend @qa 仅修改演示应用 h1#demo-heading 文本，精确改为“单轮：中文界面已更新”。保留按钮、登录占位区、样式及其余界面，审查真实Diff。" + LANGUAGE,), ("单轮：中文界面已更新",), frontend=True),
    )
    selected = [case for case in cases if case_id is None or case.id == case_id]
    if not selected:
        raise ValueError("不支持的中文评测场景")
    return selected


def provider_environment(settings_path):
    """Operator-owned local settings; never return unrelated process/tool config."""
    if not settings_path.is_file():
        return {}
    if settings_path.stat().st_size > 1024 * 1024:
        raise ValueError("本地模型配置文件超过读取上限")
    data = json.loads(settings_path.read_text(encoding="utf-8-sig"))
    if not isinstance(data, dict):
        raise ValueError("本地模型配置必须为对象")
    env = data.get("env", {})
    if not isinstance(env, dict):
        raise ValueError("本地模型配置中的 env 必须为对象")
    return {key: value for key, value in env.items()
            if isinstance(value, str) and (key in TRANSPORT_KEYS or key.startswith("ANTHROPIC_DEFAULT_"))}


def product_hashes(settings_path):
    paths = [REPO / "apps/api/data/agenthub.sqlite3", REPO / "data/agenthub.sqlite3",
             REPO / "apps/api/.env", REPO / "apps/web/.env.local", settings_path]
    paths += [p.with_name(p.name + "-wal") for p in paths[:2]]
    return {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths if p.is_file()}


def reserve_operator_output(output):
    # This model-only module does not import the engine or freeze runtime settings.
    # Temp/config paths must exist before importing the full evaluation runtime.
    from app.external_workspaces import is_system_path
    if output.expanduser().is_symlink():
        raise ValueError("评测输出不能是符号链接")
    root = output.expanduser().resolve()
    if root == REPO or REPO in root.parents or is_system_path(root):
        raise ValueError("评测输出必须位于仓库外的新非系统目录")
    root.mkdir(parents=True, exist_ok=False)
    return root


def configure_profiles(db, workspace_id, *, adapter, qa_adapter):
    from app.custom_agents import CustomAgentInput, save_custom_agent
    assert adapter == qa_adapter == "claude_code"
    rows = []
    for role, targets in [("frontend", ["demo-frontend"]), ("backend", ["demo-backend"]), ("qa", ["demo-frontend", "demo-backend"])]:
        review = role == "qa"
        profile = save_custom_agent(db, workspace_id=workspace_id, value=CustomAgentInput(
            display_name={"frontend": "前端开发智能体", "backend": "后端开发智能体", "qa": "代码审查智能体"}[role],
            mention_alias="workflow-" + role, role="review" if review else role,
            provider_id="local-claude-code-cli", tool_policy="claude_read_only" if review else "claude_file_edit",
            supported_targets=targets, capability_tags=["code_review", "diff_analysis"] if review else ["code_write", "diff_analysis"],
            system_prompt=QA_ZH if review else CODING_ZH))
        rows.append({"id": profile.id, "role": profile.role, "alias": profile.mention_alias,
                     "adapterType": profile.adapter_type, "toolPolicy": profile.tool_policy,
                     "targets": targets, "language": "zh-CN"})
    return rows


def localized_prepare(original, directory, scenario):
    from app.external_benchmark import git
    target = original(directory, scenario)
    source = target / "apps/demo/src/App.tsx"
    text = source.read_text(encoding="utf-8")
    replacements = {
        "Create a focused login page in the empty slot": "在指定区域完成小范围功能",
        "Keep the change small enough for a readable diff": "保留清晰可审查的代码差异",
        "Refresh the preview after the follow-up button copy change": "追问修改后重新验证并刷新预览",
        "AgentHub demo workspace": "AgentHub 中文协作演示",
        "Launchpad for a visible coding-agent change": "让协作过程可见，让执行结果可验证",
        "This baseline Vite React app gives future agents a stable place to\n            add a login page and then adjust button copy without changing the\n            rest of the product scaffold.": "在独立演示项目中协作修改代码，记录任务过程、真实差异与验证结果。",
        "Ready for adapter changes": "已准备好接收协作任务", "Login page target": "功能展示区域",
        "Build the login page here during the first demo request.": "此处为基线占位区，仅在需求明确要求时实现登录功能。", "Continue": "继续",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    source.write_text(text, encoding="utf-8")
    git(target, "add", "apps/demo/src/App.tsx")
    git(target, "-c", "user.name=AgentHub Chinese Evaluation", "-c", "user.email=workflow@example.invalid", "commit", "-m", "Frozen Chinese display baseline")
    return target


def finalize_evidence(root, *, before, settings_path, policy, frozen, report, workflow, phase):
    check_errors = []
    try:
        after = product_hashes(settings_path)
    except (OSError, ValueError) as error:
        after = None
        check_errors.append(type(error).__name__)
    try:
        source_unchanged = policy() == frozen if policy is not None and frozen is not None else None
    except (OSError, ValueError) as error:
        source_unchanged = False
        check_errors.append(type(error).__name__)
    returned = report is not None
    partial = root / "cohort/report.json"
    if report is None and partial.is_file():
        try:
            report = json.loads(partial.read_text(encoding="utf-8"))
        except (OSError, ValueError) as error:
            check_errors.append(type(error).__name__)
    unchanged = before is not None and after == before
    valid = returned and unchanged and source_unchanged is True
    if report is not None and not valid and workflow is not None:
        reason = "preservation_or_policy_unverifiable" if check_errors else "product_data_or_config_changed" if not unchanged else "evaluation_policy_changed" if source_unchanged is not True else "evaluation_entrypoint_failed"
        workflow.invalidate(report, reason=reason, index=len(report["cases"]))
        report["status"] = "invalidated"
        workflow.save_report(root / "cohort", report)
    preservation = {"unchanged": unchanged, "before": before, "after": after,
                    "frozenSourceUnchanged": source_unchanged, "checkErrors": check_errors}
    (root / "preserved-after.json").write_text(json.dumps(preservation, indent=2), encoding="utf-8")
    state = {"state": "verified" if valid else "preparation_failed" if phase == "preparing" else "invalidated",
             "cohortValid": valid, "phase": phase, "pythonBytecodeDisabled": sys.dont_write_bytecode,
             "databaseConfiguredInsideOutput": os.environ.get("AGENTHUB_DATABASE_URL") == "sqlite:///" + (root / "operator-runtime.sqlite3").as_posix()}
    (root / "execution-state.json").write_text(json.dumps(state, indent=2), encoding="utf-8")
    if returned and not valid:
        raise RuntimeError("保全校验未通过，本轮报告已标为无效，观察结果保留且不得作为有效通过率")


def main(argv=None):
    sys.dont_write_bytecode = True
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="五类中文真实任务验收；结果保存到新的仓库外目录")
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--repetitions", type=int, default=2)
    parser.add_argument("--timeout", type=int, default=900)
    parser.add_argument("--max-retries", type=int, default=1)
    parser.add_argument("--prepare-only", action="store_true")
    parser.add_argument("--claude-settings", type=Path, default=Path.home() / ".claude/settings.json")
    args = parser.parse_args(argv)
    if not 1 <= args.repetitions <= 10 or not 60 <= args.timeout <= 1800 or not 0 <= args.max_retries <= 2:
        parser.error("重复次数须为 1–10，超时为 60–1800 秒，显式重试次数为 0–2")
    args.claude_settings = args.claude_settings.expanduser().resolve()
    sys.path.insert(0, str(REPO / "apps/api"))
    private = provider_environment(args.claude_settings)
    if not args.prepare_only and not any(private.get(k) or os.environ.get(k) for k in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN")):
        parser.error("未配置真实 Claude 兼容 API；请设置 ANTHROPIC_AUTH_TOKEN/API_KEY 或指定 --claude-settings")
    root = reserve_operator_output(args.output)
    before = frozen = report = workflow = policy = None
    phase = "preparing"
    try:
        before = product_hashes(args.claude_settings)
        (root / "preserved-before.json").write_text(json.dumps(before, indent=2), encoding="utf-8")
        for name in ("tmp", "claude-config"):
            (root / name).mkdir()
        os.environ.update(private)
        os.environ.update(TEMP=str(root / "tmp"), TMP=str(root / "tmp"), TMPDIR=str(root / "tmp"),
            CLAUDE_CONFIG_DIR=str(root / "claude-config"), PYTHONDONTWRITEBYTECODE="1", PYTHONIOENCODING="utf-8",
            AGENTHUB_DATABASE_URL="sqlite:///" + (root / "operator-runtime.sqlite3").as_posix(),
            AGENTHUB_LLM_PLANNER_ENABLED="true", AGENTHUB_LLM_PLANNER_PROVIDER="claude_cli", AGENTHUB_DEFAULT_CODE_ADAPTER="claude_code")
        os.chdir(REPO / "apps/api")
        from app import workflow_evaluation as workflow
        from app.process_environment import redact_process_evidence
        original_policy, original_prepare = workflow.source_policy, workflow.prepare_source
        def policy():
            extra = list((REPO / "apps/web/src").rglob("*")) + list((REPO / "apps/web/public").rglob("*"))
            extra += [REPO / "apps/web" / name for name in ("package.json", "next.config.ts", "tsconfig.json", "postcss.config.mjs")]
            return {**original_policy(), **{p.relative_to(REPO).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                                         for p in extra if p.is_file() and p.suffix in {".ts", ".tsx", ".css", ".json", ".mjs", ".png", ".svg", ".ico", ".webp", ".jpg"}}}
        workflow.source_policy, workflow.select_scenarios = policy, chinese_scenarios
        workflow.prepare_source = lambda directory, scenario: localized_prepare(original_prepare, directory, scenario)
        workflow.configure_profiles, workflow.QA_PROMPT, workflow.RULE = configure_profiles, QA_ZH, RULE_ZH
        frozen = policy()
        archive = root / "frozen-source"
        for name, expected in frozen.items():
            raw = (REPO / name).read_bytes()
            assert hashlib.sha256(raw).hexdigest() == expected, name
            destination = archive / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(raw)
        (archive / "manifest.json").write_text(json.dumps(frozen, indent=2), encoding="utf-8")
        metadata = {"recordedAt": datetime.now(timezone.utc).isoformat(), "language": "zh-CN",
                "prepareOnly": args.prepare_only,
                "tasks": 5 * args.repetitions, "scenarioCount": 5, "repetitions": args.repetitions,
                "faultInjection": False, "adapter": "claude_code", "qaAdapter": "claude_code", "planner": "claude_cli",
                "configuredModelAlias": redact_process_evidence(os.environ.get("ANTHROPIC_MODEL", "default")),
                "upstreamModelIdentityVerified": False, "actualBillingVerified": False,
                "productDataUsed": False, "credentialValuesInEvidence": False, "fixtureLocalizationBeforeBaseline": True,
                "entrypoint": "production_message_route_and_dispatch_with_isolated_db", "httpTransportTested": False,
                "timeoutSeconds": args.timeout, "maxRetries": args.max_retries}
        (root / "environment.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
        phase = "evaluating"
        report = asyncio.run(workflow.run_benchmark(root / "cohort", repetitions=args.repetitions,
            prepare_only=args.prepare_only, adapter="claude_code", qa_adapter="claude_code",
            timeout=args.timeout, max_retries=args.max_retries))
        phase = "evaluated"
    finally:
        finalize_evidence(root, before=before, settings_path=args.claude_settings, policy=policy,
                          frozen=frozen, report=report, workflow=workflow, phase=phase)
    print(json.dumps({"status": report["status"], "summary": report["summary"]}, ensure_ascii=False), flush=True)
    expected_verdict = "prepared" if args.prepare_only else "passed"
    return 0 if all(case["verdict"] == expected_verdict for case in report["cases"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
