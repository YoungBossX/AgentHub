## ADDED Requirements
### Requirement: Vite React 预览运行器
系统 MUST 支持为恰好一个 P0 演示应用栈启动预览：Vite React。

#### Scenario: Vite React 演示应用预览启动
- **GIVEN** 一个 TaskRun 已在 Vite React 演示应用中产生变更
- **WHEN** 预览启动开始
- **THEN** 后端在会话工作树中运行固定的 Vite 预览命令
- **并且** 记录预览端口和 URL

### Requirement: 设置时依赖安装
系统 MUST 在设置期间安装演示应用依赖，并且 MUST 不在代理执行期间运行依赖安装。

#### Scenario: 预览启动时无需安装依赖
- **GIVEN** Vite React 演示仓库的依赖已在设置期间安装
- **WHEN** 代理任务完成，预览启动
- **THEN** 预览运行器不执行 `pnpm install`
- **并且** 使用已有的设置时依赖

### Requirement: 固定预览命令
系统 MUST 使用 `pnpm dev --host 127.0.0.1 --port <port>` 启动预览。

#### Scenario: 后端启动预览命令
- **GIVEN** 分配一个预览端口
- **WHEN** 预览运行器启动 Vite React 应用
- **THEN** 它运行 `pnpm dev --host 127.0.0.1 --port <port>`
- **并且** 存储命令、端口、URL、进程信息和健康状态

### Requirement: 预览卡片
系统 MUST 在预览 URL 健康时显示预览卡片。

#### Scenario: 用户打开预览面板
- **GIVEN** 存在一个健康的预览
- **WHEN** 用户打开预览卡片
- **THEN** UI 在右侧面板或 iframe 中显示预览

### Requirement: 第二次变更后预览刷新
系统 MUST 允许演示流程在同一会话工作树中进行第二次小幅变更后显示更新后的预览。

#### Scenario: 按钮文本变更后刷新预览
- **GIVEN** 用户之前已打开预览
- **WHEN** 用户要求让按钮文本更友好，代理修改了 Vite React 演示仓库
- **THEN** 系统更新了差异
- **并且** 预览反映了最新的会话工作树状态

### Requirement: 预览成功后部署卡片
系统 MUST 在预览成功后显示后端创建的部署卡片。

#### Scenario: 预览成功创建部署卡片
- **GIVEN** 预览制品状态正常
- **WHEN** 部署卡片创建流程执行
- **THEN** 后端存储一条部署记录
- **并且** 界面展示提供商、环境、状态、URL、提交或引用信息，以及日志引用（若可用）

### Requirement: Mock 部署兜底
系统 MUST 在真实部署不可用时保持演示路径正常工作。

#### Scenario: 真实部署被禁用或失败
- **GIVEN** 真实部署不可用或不稳定
- **WHEN** 演示进入部署阶段
- **THEN** 后端创建模拟部署记录
- **并且** UI 显示模拟部署卡片，但不声称真实提供商部署成功
