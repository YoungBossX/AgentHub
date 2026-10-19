# 数据库完整性实施文件清单

这是实施计划的范围附件，基于 2026-10-19 主树 `8392b7f` 的源码搜索。
文件名表示必须审阅的调用点；只进行所属任务要求的修改，不把清单当作任意重构授权。
这是实施前冻结的调查范围；实际修改和验证见[验收记录](../../../docs/database-integrity-verification.md)。
独立审阅随后补充 `apps/api/app/dependencies.py` 请求事务边界：
真实创建/重试在事件 guard 前遇到 SQLite 写竞争时回滚并分类，两个真实接口已红绿验证。

## 测试引擎调用点

共 70 个文件。普通业务连接接入实例级外键工厂；
`migration_fixtures.py`、`test_migration_backup.py`、`test_migration_lifecycle.py`、`test_models.py`
中的历史构造/坏库/结构诊断连接须按具体用途区分，不能全部机械替换或用它们关闭业务连接约束。
通过 helper 间接构造数据库的其他测试维持原调用；只有实际失败证实必要时才修复父链。

- `apps/api/tests/migration_fixtures.py`
- `apps/api/tests/test_adapters.py`
- `apps/api/tests/test_agent_creation.py`
- `apps/api/tests/test_agent_directory.py`
- `apps/api/tests/test_agent_profile_drafts.py`
- `apps/api/tests/test_agent_runtime_config.py`
- `apps/api/tests/test_agent_selection_policy.py`
- `apps/api/tests/test_agent_system_prompt.py`
- `apps/api/tests/test_artifact_scope_guards.py`
- `apps/api/tests/test_artifact_workbench_api.py`
- `apps/api/tests/test_artifact_workbench_edit_api.py`
- `apps/api/tests/test_automatic_validation.py`
- `apps/api/tests/test_chat_events.py`
- `apps/api/tests/test_claude_code_adapter.py`
- `apps/api/tests/test_codex_adapter.py`
- `apps/api/tests/test_cross_provider_rehearsal.py`
- `apps/api/tests/test_custom_agents.py`
- `apps/api/tests/test_deployments.py`
- `apps/api/tests/test_diffs.py`
- `apps/api/tests/test_execution_worktrees.py`
- `apps/api/tests/test_external_benchmark.py`
- `apps/api/tests/test_external_evidence.py`
- `apps/api/tests/test_external_memory_scan.py`
- `apps/api/tests/test_external_reviews.py`
- `apps/api/tests/test_external_workspaces.py`
- `apps/api/tests/test_failure_recovery.py`
- `apps/api/tests/test_group_auto_execution.py`
- `apps/api/tests/test_group_planning.py`
- `apps/api/tests/test_guardrails.py`
- `apps/api/tests/test_layered_qa.py`
- `apps/api/tests/test_live_memory_compliance.py`
- `apps/api/tests/test_llm_planner.py`
- `apps/api/tests/test_local_data.py`
- `apps/api/tests/test_memory_evals.py`
- `apps/api/tests/test_memory_rehearsal.py`
- `apps/api/tests/test_memory_retrieval.py`
- `apps/api/tests/test_memory_rule_budget.py`
- `apps/api/tests/test_memory_snapshot_consistency.py`
- `apps/api/tests/test_memory_store.py`
- `apps/api/tests/test_memory_write_policy.py`
- `apps/api/tests/test_message_attachments.py`
- `apps/api/tests/test_message_regeneration.py`
- `apps/api/tests/test_migration_backup.py`
- `apps/api/tests/test_migration_lifecycle.py`
- `apps/api/tests/test_models.py`
- `apps/api/tests/test_native_review_artifacts.py`
- `apps/api/tests/test_p18b_workflow_rehearsal.py`
- `apps/api/tests/test_parallel_dispatcher.py`
- `apps/api/tests/test_pinned_message_context.py`
- `apps/api/tests/test_planner_contracts.py`
- `apps/api/tests/test_planner_message_references.py`
- `apps/api/tests/test_planning.py`
- `apps/api/tests/test_pmo_decisions.py`
- `apps/api/tests/test_previews.py`
- `apps/api/tests/test_project_analyzer.py`
- `apps/api/tests/test_project_provisioning.py`
- `apps/api/tests/test_provider_gateway_contract.py`
- `apps/api/tests/test_recovery.py`
- `apps/api/tests/test_run_diagnostics.py`
- `apps/api/tests/test_scheduler.py`
- `apps/api/tests/test_scripted_mock_adapter.py`
- `apps/api/tests/test_session_organization.py`
- `apps/api/tests/test_session_queue.py`
- `apps/api/tests/test_sessions.py`
- `apps/api/tests/test_skills.py`
- `apps/api/tests/test_target_locks.py`
- `apps/api/tests/test_target_registry.py`
- `apps/api/tests/test_task_runs.py`
- `apps/api/tests/test_transactional_delivery.py`
- `apps/api/tests/test_workflow_evaluation.py`

## 事件生产调用点

共 22 个文件，包含 events.py 自身的定义/包装。
逐项核对父行 flush、事务所有权及竞争错误处理；已有正确边界的文件不改。

- `apps/api/app/adapters.py`
- `apps/api/app/automatic_validation.py`
- `apps/api/app/dag_integration.py`
- `apps/api/app/deployments.py`
- `apps/api/app/diffs.py`
- `apps/api/app/events.py`
- `apps/api/app/external_evidence.py`
- `apps/api/app/group_execution.py`
- `apps/api/app/group_summaries.py`
- `apps/api/app/guardrails.py`
- `apps/api/app/mcp_gateway.py`
- `apps/api/app/preview_deploy_jobs.py`
- `apps/api/app/previews.py`
- `apps/api/app/provider_gateway.py`
- `apps/api/app/recovery.py`
- `apps/api/app/reviews.py`
- `apps/api/app/run_engine.py`
- `apps/api/app/session_queue.py`
- `apps/api/app/skill_runtime.py`
- `apps/api/app/target_locks.py`
- `apps/api/app/task_runs.py`
- `apps/api/app/transactional_delivery.py`

执行前重新比较清单；若出现新增调用点，先说明与本任务的关系并补齐验证，不静默扩大范围。
