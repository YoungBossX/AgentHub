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

### Outcome

Policy Engine MUST 使用小集合 outcome：

- `allow`：允许继续。
- `deny`：直接拒绝。
- `require_approval`：需要普通审批。
- `require_elevated_approval`：需要高级审批，例如平台维护、破坏性 host 操作。

### Category

首版 category：

- `command`
- `path`
- `network`
- `cost`
- `destructive_change`
- `deploy`
- `platform_maintenance`

### Decision 字段

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

`safeMetadata` 必须脱敏，不包含 secrets、tokens、API keys、`.env` 内容或未授权 host
path。

## 策略规则

### Command Policy

- 复用 `evaluate_project_command()`。
- target/profile 显式配置且命令匹配时 `allow`。
- 未配置命令或命令不匹配时 `deny`。
- `install`、`curl`、`docker`、`git push`、生产 deploy 等高风险命令不因 profile
  存在而默认允许。

### Path Policy

- target allowed paths 内普通路径可 `allow`。
- `.git`、`.env*`、`secrets`、`node_modules`、venv/cache/build 输出、target 外路径
  必须 `deny`。
- AgentHub platform code 在未开启 platform maintenance 时必须 `deny` 或
  `require_elevated_approval`。

### Network Policy

- 默认网络访问不自动允许。
- 明确的本地 preview/dev server 可以由对应 preview/deploy 子系统处理。
- 外部网络访问首版应返回 `require_approval`，除非已有明确配置允许。

### Cost Policy

- 预算超过阈值或未知高成本操作应返回 `require_approval`。
- V2.5 可先实现合同和 helper，不要求接真实计费系统。

### Destructive Change Policy

- 删除大量文件、修改迁移/配置、重写项目结构、`rm -rf` 等应拒绝或高级审批。
- 首版可通过 requestedAction / fileCount / destructive flag 判断。

### Deploy Policy

- mock/local staging 可以按现有部署规则继续。
- 生产部署或第三方 cloud deploy 默认 `deny` 或 `require_approval`，不得伪造成成功。
- V2.5 不接入生产云平台。

### Platform Maintenance

- AgentHub platform target 或 `requires_platform_mode` target 必须返回
  `require_elevated_approval`，除非调用方明确提供已批准上下文。
- 该规则不能被普通 runtime config 或 agent profile 绕过。

## Approval Timeout

Policy Engine 应提供 approval timeout helper：

- 未决审批超时默认 `deny`；
- 不允许因为审批通道失败、SSE 断开或前端未响应而自动放行；
- timeout evidence 应包含 safe reason 和 requestedAction。

## 安全边界

Policy Engine 是统一决策层，不是权限扩张层：

- 不替代 Target Registry；
- 不替代 PlanValidator；
- 不替代 Guardrails；
- 不允许任意 shell command agent；
- 不暴露 secrets；
- 不伪造 provider / deploy 成功。

## 测试策略

V2.5 后续实现应覆盖：

- allow / deny / require_approval / require_elevated_approval 四种 outcome；
- command 匹配、缺失、不匹配；
- allowed path、denied path、target outside path；
- network 默认审批；
- cost threshold；
- destructive action；
- local staging vs production deploy；
- platform maintenance 高级审批；
- approval timeout 默认 deny；
- evidence 脱敏。
