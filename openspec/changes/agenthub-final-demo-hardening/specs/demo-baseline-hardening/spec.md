## ADDED Requirements
### Requirement: 基线治理一致性
项目文档 MUST 将 AgentHub 描述为本地单用户 Agent 编码工作区 / 强演示 MVP，且 MUST 未将其呈现为完整的多用户 IM 协作平台。

#### Scenario: 基线文档已评审
- **WHEN** 最终演示基线文档已评审
- **THEN** 它们明确了本地单用户 Agent 编码工作区的定位
- **并且** 它们保留了已验证的 P0/P1/P2/P3/P4 路径，未夸大未经验证的平台功能

### Requirement: 当前适配器现状
项目文档 MUST 将 `CodexAdapter`、`ClaudeCodeAdapter` 和 `ScriptedMockAdapter` 识别为当前适配器，并 MUST 保留基于兜底的 P0 演示路径。

#### Scenario: 适配器指南被审阅
- **WHEN** 在最终演示任务前阅读适配器指南
- **THEN** 该指南将 Codex、Claude Code 和脚本化模拟执行视为当前基线路径
- **并且** 它不指示代理移除或重新推迟现有适配器

### Requirement: 最终演示证据规范
最终演示加固工作 MUST 需在文档和检查表中区分已验证、兜底、部分验证和未验证的行为。

#### Scenario: 最终证据已记录
- **WHEN** 最终演示检查清单或摘要已更新
- **THEN** 真实代理、兜底、跟进、差异、预览、模拟部署和浏览器覆盖声明均根据实际验证证据进行标注
- **且** 模拟部署未被描述为真实生产部署
