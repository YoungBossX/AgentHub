# V2.2 提供商网关冻结审查

**日期：** 2026-06-09

## 范围

V2.2 在持久化运行引擎与现有 ClaudeCodeAdapter、CodexAdapter 和 ScriptedMockAdapter 之间新增了一个编码提供商网关。

已实现：

- 编码提供商合约与安全证据模型
- 仅用于编码适配器的 ProviderRegistry / ProviderResolver
- 针对 Claude Code、Codex 和 ScriptedMock 的提供商健康探针
- 具有幂等释放功能的提供商容量限制器
- 速率限制证据占位符
- 具有 closed/open/half_open 种状态的提供商断路器
- ProviderErrorClassifier 和 FallbackPolicy
- 提供商解析、健康、容量、断路器、错误和兜底事件
- 在适配器启动前进行提供商解析的持久化运行引擎集成

## 安全性

- 规划器提供商与编码提供商保持分离。
- 未新增适配器、市场、云端 Codex 封装器、Docker 沙箱、WebSocket 或生产部署。
- ScriptedMock 证据仍标记为 fallback/mock.
- 提供商证据会针对密钥、令牌、受保护路径和主机路径进行脱敏处理。
- 提供商故障不会转换为真实的提供商成功。

## 验证

| 命令 | 结果 |
|---|---|
| `cd apps/api && ../../.venv/bin/python -m pytest tests/test_provider_gateway_contract.py tests/test_task_runs.py -q` | 通过 |
| `pnpm check` | 通过 |
| `pnpm demo:api:test` | 通过 |
| `openspec validate agenthub-v2-2-provider-gateway --strict` | 通过 |
| `git diff --check` | 通过 |

## 限制

- 断路器和容量状态在本地 SQLite 演示路径中为进程内处理。
- 完整的分布式提供商 quota/budget 核算已推迟。
- 兜底策略会记录证据和选择，但更深入的自动提供商重试链应在后续阶段加强。
- 提供商健康探针是启动路径检查，而非完整的交互式身份验证烟雾测试。

## 后续工作

建议后续工作：完成 V2.3 冻结审查，然后完成 V2.7 UI，以便用户能直接查看提供商网关故障和下一步建议。
