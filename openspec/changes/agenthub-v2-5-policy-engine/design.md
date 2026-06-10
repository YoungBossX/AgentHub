## 总体设计

V2.5 新增一个独立的 Policy Engine 投影层。它不直接执行命令，不创建审批按钮，
也不替换现有 guardrails；它负责把不同安全输入统一为可审计决策。

目标形态：
```text
Target Registry + ProjectProfile + Guardrails + Command Policy + Runtime Context
  -> Policy Engine
  -> PolicyDecision(outcome, reason, risk, approval, evidence)
  -> Run Engine / Transactional Delivery / Deploy / Diagnostics
```
## 决策模型

### 结果

Policy Engine MUST 使用小集合结果：

- `allow`：允许继续。
- `deny`：直接拒绝。
- `require_approval`：需要普通审批。
- `require_elevated_approval`：需要高级审批，例如平台维护、破坏性主机操作。

### 类别

首版类别：

- `command`
- `path`
- `network`
- `cost`
- `destructive_change`
- `deploy`
- `platform_maintenance`

### 决策字段

建议 `PolicyDecision` 包含：

- `category`
- `outcome`
- `reason`
- `riskLevel`
- `approvalType`
- `targetId`
- `commandType`
- `requestedAction`
- `safeMetadata`

`safeMetadata` 必须脱敏，不包含 secrets、tokens、API keys、`.env` 内容或未授权主机路径。

## 策略规则

### 命令策略

- 复用 `evaluate_project_command()`。
- target/profile 显式配置且命令匹配时 `allow`。
- 未配置命令或命令不匹配时 `deny`。
- `install`、`curl`、`docker`、`git push`、生产部署等高风险命令不因配置文件存在而默认允许。

### 路径策略

- 目标允许路径内的普通路径可 `allow`。
- `.git`、`.env*`、`secrets`、`node_modules`、venv/cache/build 输出、目标外路径必须 `deny`。
- AgentHub 平台代码在未开启平台维护时必须 `deny` 或 `require_elevated_approval`。

### 网络策略

- 默认网络访问不自动允许。
- 明确的本地 preview/dev 服务器可由对应 preview/deploy 子系统处理。
- 外部网络访问首版应返回 `require_approval`，除非已有明确配置允许。

### 成本策略

- 预算超过阈值或未知高成本操作应返回 `require_approval`。
- V2.5 可先实现合同和辅助函数，不要求接入真实计费系统。

### 破坏性变更策略

- 删除大量文件、修改迁移/配置、重写项目结构、`rm -rf` 等应拒绝或高级审批。
- 首版可通过 requestedAction / fileCount / destructive flag 判断。

### 部署策略

- mock/local 预发布环境可按现有部署规则继续。
- 生产部署或第三方云部署默认 `deny` 或 `require_approval`，不得伪造成成功。
- V2.5 不接入生产云平台。

### 平台维护

- AgentHub 平台目标或 `requires_platform_mode` 目标必须返回 `require_elevated_approval`，除非调用方明确提供已批准上下文。
- 该规则不能被普通运行时配置或代理配置文件绕过。

## 审批超时

Policy Engine 应提供审批超时辅助函数：

- 未决审批超时默认 `deny`；
- 不允许因为审批通道失败、SSE 断开或前端未响应而自动放行；
- 超时证据应包含安全原因和 requestedAction。

## 安全边界

Policy Engine 是统一决策层，不是权限扩张层：

- 不替代目标注册表；
- 不替代计划验证器；
- 不替代防护栏；
- 不允许任意 shell 命令代理；
- 不暴露 secrets；
- 不伪造提供者/部署成功。

## 测试策略

V2.5 后续实现应覆盖：

- allow / deny / require_approval / require_elevated_approval 四种结果；
- 命令匹配、缺失、不匹配；
- 允许路径、拒绝路径、目标外路径；
- 网络默认审批；
- 成本阈值；
- 破坏性操作；
- 本地预发布环境 vs 生产部署；
- 平台维护高级审批；
- 审批超时默认拒绝；
- 证据脱敏。
