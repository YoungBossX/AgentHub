# V2.7 运行诊断冻结审查

**日期：** 2026-06-09

## 范围

V2.7 在 TaskRun、TaskRunEvent、提供商网关、队列、锁、预览、部署和制品证据之上新增了安全的诊断投影。

已实现：

- RunDiagnostics 响应模型。
- 失败类别分类器和 primary/contributing 因子选择。
- 运行时间线构建器。
- provider/queue/lock/preview/deploy 健康摘要。
- 下一步建议模型。
- `GET /task-runs/{task_run_id}/diagnostics`。
- `GET /sessions/{session_id}/run-diagnostics-summary`。
- 使用 TaskRun provider/queue/lock/job 证据的任务面板诊断摘要。

## 安全性

- 诊断不会改变执行语义。
- 未新增适配器、WebSocket、Docker 沙箱、外部 IM、PR 或部署行为。
- 元数据和证据在暴露前已进行脱敏处理。
- 缺失的证据显示为 unknown/limited，而非推断为成功。
- ScriptedMock 仍明显显示为 mock/fallback 证据。

## 验证

| 命令 | 结果 |
|---|---|
| `cd apps/api && ../../.venv/bin/python -m pytest tests/test_run_diagnostics.py -q` | 通过 |
| `pnpm --filter @agenthub/web test -- mission-panel.test.tsx` | 通过 |
| `pnpm check` | 通过 |
| `pnpm test` | 通过 |
| `pnpm demo:api:test` | 通过 |
| `openspec validate agenthub-v2-7-run-diagnostics --strict` | 通过 |
| `git diff --check` | 通过 |

## 限制

- 首次 UI 迭代有意保持简洁，在任务面板中展示诊断信息，而非添加完整的详情抽屉。
- 建议操作按钮仍绑定到现有的 retry/settings/artifact 流程；新的自动修复功能已推迟。
- 时间线显示可通过 API 获取，并在 UI 中汇总展示，更丰富的可视化时间线留待后续迭代。

## 后续工作

建议后续工作：在 V2.4/V2.5 稳定 ProjectProfile 和 Policy Engine 信号后，添加专用的运行诊断抽屉。
