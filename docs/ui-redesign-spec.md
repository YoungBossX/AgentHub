# AgentHub UI Redesign Specification

> 适用阶段：P3 UI Redesign / AgentHub Command Center  
> 目标读者：Codex / 前端实现者 / 项目维护者  
> 来源：三张 Stitch UI 设计图 + 三份 Design.md 的统一整理  
> 实现原则：前端优先、保持现有后端 API、分阶段落地、每阶段独立验证
> 三张stitch ui设计图在 agenthub文件夹下

---

## 0. 结论摘要

AgentHub 前端重构不应被实现为三套互不相关的页面，而应被整理成一个统一产品中的三个状态：

| 设计来源 | 最终定位 | 实现方式 |
|---|---|---|
| 主工作台图 | AgentHub 主页面 | 默认页面：左侧 Session，中间 Chat + Task Timeline，右侧 Artifact Panel |
| 执行详情图 | Task Detail / Execution Trace | 任务详情态、展开态或详情面板，不作为默认首页 |
| Preview / Deploy 图 | Artifact Panel 完成态 | 右侧面板中 Preview / Deploy tab 的完成态 |

最终产品定位：

> AgentHub 是一个 **IM-style Coding Agent Command Center**。  
> 它不是普通聊天机器人，也不是完整 IDE。  
> 它的核心价值是把需求、规划、Agent 执行、真实 diff、preview、mock deploy 组织成一条可验证的工程链路。

核心演示链路：

```text
Requirement -> Plan -> Run -> Diff -> Preview -> Deploy
```

---

## 1. 产品定位

### 1.1 产品定义

AgentHub 是一个面向开发任务的 Agent 协作工作台。用户以 IM/Chat 的方式提出需求，Orchestrator 生成任务计划，不同 Agent 执行任务，系统产出真实工程证据，包括：

- TaskRun 执行状态；
- fallback recovery 轨迹；
- diff artifact；
- Vite preview；
- mock deploy card；
- approval / second-change / adapter selection 等辅助能力。

### 1.2 不是什么

AgentHub 不应被设计成：

| 不应定位为 | 原因 |
|---|---|
| 通用聊天机器人 | 核心不是闲聊，而是工程任务执行链路 |
| 完整 IDE | 当前没有完整文件树、编辑器、终端、调试器 |
| Provider Marketplace | 当前只需要 Codex / Claude / ScriptedMock 的运行时路径，不做 marketplace |
| 生产部署平台 | 当前是 mock deploy，production deploy 明确 out of scope |
| 多人实时协作平台 | 当前没有多人协作后端支持 |
| PR / GitHub 自动化平台 | 当前没有 PR 创建闭环 |

---

## 2. 设计系统

### 2.1 视觉风格

采用 **Corporate Modern / Developer Tool** 风格：

- 专业；
- 克制；
- 可扫描；
- 高信息密度但不拥挤；
- 以清晰状态和工程证据为核心；
- 少用大面积炫酷渐变，多用边框、状态条、语义色和清晰层级。

### 2.2 色彩系统

建议统一使用以下色板，避免不同页面出现三套颜色体系。

#### Base

| Token | Color | 用途 |
|---|---|---|
| `--background` | `#F8FAFC` | 页面背景 |
| `--surface` | `#FFFFFF` | 主卡片、侧栏、面板 |
| `--surface-muted` | `#F1F5F9` | 次级区域、输入背景 |
| `--border-subtle` | `#E2E8F0` | 面板边框 |
| `--border-strong` | `#CBD5E1` | 强分隔线 |
| `--text-primary` | `#0F172A` | 主文字 |
| `--text-secondary` | `#475569` | 次级文字 |
| `--text-muted` | `#94A3B8` | 辅助文字 |

#### Brand / Primary

| Token | Color | 用途 |
|---|---|---|
| `--primary` | `#3525CD` | 主按钮、品牌、active tab |
| `--primary-strong` | `#1E00A9` | 强强调、按钮 hover |
| `--primary-soft` | `#E2DFFF` | 选中背景、soft chip |
| `--primary-border` | `#C3C0FF` | 选中边框 |

> 注意：Design.md 中 YAML 的 `primary` 是 `#1e00a9`，正文说明 Primary Indigo 是 `#3525cd`。实现时建议以 `#3525cd` 作为默认主按钮色，`#1e00a9` 用作 hover/strong 状态。

#### Semantic

| 状态 | Color | Soft Background | 用途 |
|---|---|---|---|
| Running / Active | `#2563EB` | `#DBEAFE` | streaming、running、active process |
| Success / Completed | `#059669` | `#D1FAE5` | completed、healthy |
| Error / Failed | `#BA1A1A` | `#FEE2E2` | failed、error |
| Fallback / Recovered | `#7E22CE` | `#EDE9FE` | fallback recovery、recovered |
| Warning / Approval | `#D97706` | `#FEF3C7` | approval、pending human decision |
| Diff Ready | `#0891B2` | `#CFFAFE` | diff artifact |
| Deploy Ready | `#3525CD` | `#E2DFFF` | mock deploy ready |

#### Code / Log

| Token | Color | 用途 |
|---|---|---|
| `--code-bg` | `#0F172A` | 代码预览、日志面板 |
| `--code-text` | `#E2E8F0` | 代码正文 |
| `--code-muted` | `#94A3B8` | 行号、注释、时间戳 |
| `--code-success` | `#34D399` | 成功日志 |
| `--code-error` | `#F87171` | 错误日志 |

### 2.3 字体系统

推荐字体栈：

```css
--font-heading: Geist, Inter, system-ui, sans-serif;
--font-body: Inter, system-ui, sans-serif;
--font-code: "JetBrains Mono", ui-monospace, SFMono-Regular, Menlo, monospace;
```

不要强制引入本地字体文件；优先使用现有 Web 环境和 fallback。

| Type | Size | Weight | 用途 |
|---|---:|---:|---|
| Display / Page title | 30px | 600 | Execution Details 等大标题 |
| Headline | 20px | 600 | Section 标题 |
| Title | 16px | 600 | Task title / card title |
| Body | 14px | 400 | 正文 |
| Small body | 13px | 400 | 辅助说明 |
| Label caps | 11px | 700 | badge / meta label |
| Code | 13px | 450 | code、adapter name、artifact id |

### 2.4 布局和间距

采用 **Fixed - Fluid - Fixed** 结构：

```text
┌───────────────┬──────────────────────────────┬──────────────────┐
│ Sidebar 280px │ Central Workspace fluid      │ Artifact 400px   │
└───────────────┴──────────────────────────────┴──────────────────┘
```

| 区域 | 宽度 |
|---|---:|
| Sidebar | 280px |
| Artifact Panel | 400px |
| Central Workspace | fluid，内容建议 720px-800px 可读宽度 |
| Desktop margin | 24px |
| Mobile margin | 16px |
| Gutter | 16px |
| Stack gap | 8px / 16px / 24px |

### 2.5 圆角和阴影

| 元素 | Radius | 说明 |
|---|---:|---|
| Small tags / inputs | 4px |
| Timeline cards | 8px |
| Chat bubble / modal | 12px |
| Avatar / icon button | full |

阴影应克制。优先使用：

- 1px border；
- subtle shadow；
- 左侧状态边框；
- tonal surface；

不要大量使用发光阴影。

---

## 3. 信息架构

### 3.1 主页面结构

```text
Top Header / Demo Pipeline
├── Brand
├── Requirement -> Plan -> Run -> Diff -> Preview -> Deploy
└── Primary action / notification / settings / profile

Main Area
├── Left Sidebar
│   ├── Workspace summary
│   ├── New Session
│   ├── Recent Sessions
│   └── Docs / API / Support
├── Center Workspace
│   ├── Session title
│   ├── Requirement message
│   ├── Orchestrator plan
│   ├── Agent task timeline
│   └── Composer
└── Right Artifact Panel
    ├── Tabs: Diff / Preview / Deploy
    ├── Diff tab
    ├── Preview tab
    └── Deploy tab
```

### 3.2 页面 / 状态关系

不要将三张设计图做成互相无关的 route。推荐：

| 状态 | 展示方式 |
|---|---|
| 主工作台 | `/` 默认工作台 |
| Execution Details | task card 展开、drawer、detail state，或后续路由 |
| Preview/Deploy | 右侧 Artifact Panel tab state |

---

## 4. Header / Demo Pipeline

### 4.1 目标

顶部不只是导航，而是 demo 进度条，表达系统当前从需求到部署的进度。

Pipeline：

```text
Requirement -> Plan -> Run -> Diff -> Preview -> Deploy
```

### 4.2 状态显示

| 阶段 | 状态示例 |
|---|---|
| Requirement | completed |
| Plan | completed |
| Run | running / completed / recovered |
| Diff | ready |
| Preview | healthy |
| Deploy | mock ready |

### 4.3 交互要求

- 当前阶段使用 primary 下划线或 active pill；
- completed 使用绿色 check；
- running 使用蓝色 spinner / sync icon；
- recovered 使用紫色 recovery icon；
- pending 使用灰色；
- Deploy 按钮不要写 `Deploy All`，避免误解为生产部署。推荐：
  - `Create Mock Deploy`
  - `Show Deploy Card`
  - `Mock Deploy`

---

## 5. Sidebar

### 5.1 内容

Sidebar 应包含：

- AgentHub logo / product title；
- workspace name：`AgentHub Demo`；
- repo/path：`apps/demo`；
- New Session；
- Recent Sessions；
- session summary；
- bottom links：Docs / API / Support / Profile。

### 5.2 Session item

每个 session item 应展示：

```text
AgentHub Demo
3 tasks
Preview: Healthy
Updated: 2m ago
```

状态点语义：

| 状态 | 颜色 |
|---|---|
| preview healthy | green |
| running | blue |
| failed | red |
| idle | gray |

当前 session：

- 使用 primary soft 背景；
- 使用左侧 4px primary border；
- 不使用过强大面积实心紫。

---

## 6. Central Workspace

### 6.1 Session header

展示当前 session / task context：

```text
Login Page Dev
```

可选 subtitle：

```text
apps/demo · 3 tasks · preview healthy
```

### 6.2 Requirement message

用户消息应保持 IM 感，但不要让聊天压过任务流。

示例：

```text
@orchestrator build a login page for the demo app
```

### 6.3 Orchestrator plan card

Orchestrator 卡片应展示：

- agent identity；
- planning status chip；
- 生成了多少任务；
- 可选的 plan summary。

示例：

```text
@orchestrator    PLANNING
I've generated a plan with 3 tasks to build the login page.
```

---

## 7. Task Timeline

### 7.1 视觉结构

每个 Task Card 应使用：

- 4px left status border；
- header；
- body；
- run history；
- artifact chips / metadata footer；
- primary action。

状态边框：

| 状态 | 左边框 |
|---|---|
| Pending | gray |
| Running | blue |
| Completed | green |
| Failed | red |
| Recovered | purple |
| Waiting approval | amber |

### 7.2 Task card 信息

每张 task card 应尽量包括：

- task number；
- task title；
- assigned agent；
- status badge；
- adapter / run history；
- artifact chips；
- action buttons。

示例结构：

```text
T2: Setup Authentication Logic          Recovered
@backend

Run history
- Run 1 · CodexAdapter · Failed
- Run 2 · ScriptedMockAdapter · Completed

[Retry] [Force Codex failure] [Diff ready · 2 files]
```

### 7.3 Agent Tags

Agent tag 使用 monospace：

```text
@frontend
@backend
@orchestrator
```

样式：

- small;
- background tint;
- border;
- monospace text.

---

## 8. Fallback Recovery Visualization

这是 AgentHub 的核心演示亮点之一，必须比普通日志更醒目。

### 8.1 推荐展示

```text
Execution Trace

Run 1 · CodexAdapter                     14:02:10
Error: CODEX_DEMO_FORCED_FAILURE

↓ Triggering fallback logic...

Run 2 · ScriptedMockAdapter              14:02:15
Execution completed successfully via fallback.
```

### 8.2 视觉要求

| 事件 | 样式 |
|---|---|
| failed run | red soft background + red left border |
| fallback arrow | purple icon/text |
| successful fallback | green soft background + green left border |
| recovered status | purple badge |

### 8.3 可交互

在主卡片中可使用简化版本。点击 `View details` 后可展示完整 Execution Details。

---

## 9. Artifact Evidence Chips

Completed / Recovered task 底部展示 evidence chips：

```text
[Diff ready · 1 file]
[Changed file: apps/demo/src/App.tsx]
[Preview healthy]
[Deploy mock ready]
```

颜色：

| Chip | 色彩 |
|---|---|
| Diff ready | cyan |
| Changed file | slate / mono |
| Preview healthy | green |
| Deploy mock ready | indigo |
| Recovered | purple |

目的：强调系统产生了真实可验证产物，而不是只生成聊天文本。

---

## 10. Artifact Panel

### 10.1 定位

右侧不应只是 Preview Panel，而应是统一的 Artifact Panel：

```text
Tabs: Diff | Preview | Deploy
```

### 10.2 Diff Tab

展示：

- changed files；
- patch summary；
- code/diff preview；
- View Diff / Open details；
- 可选 file tabs。

示例：

```text
auth.ts
package.json

- Old logic removed
+ Fallback logic executed
```

代码区域使用深色 code/log style，但不要变成完整 IDE。

### 10.3 Preview Tab

展示：

- browser mockup；
- URL；
- port；
- health status；
- refresh/open actions；
- iframe preview。

Browser mockup 包含：

- traffic-light dots；
- address bar；
- refresh icon；
- external open icon。

空态：

```text
Preview not started yet.
Start preview after a diff artifact is ready.
[Start Preview]
```

健康态：

```text
Preview Environment: healthy
Port: 5173
Protocol: HTTP
```

### 10.4 Deploy Tab

展示 mock deploy card：

```text
Mock Deployment Ready
Provider: Internal Mock Adapter
Environment: Preview-Environment-01
URL: demo-app-deploy-v1.mock.local
Status: ready

[14:05:01] Building assets...
[14:05:03] Uploading to mock storage...
[14:05:05] Deployment successful.

[Open Deployment]
```

注意：

- 不要暗示 production deploy；
- 按钮可写 `Open Mock Deployment`；
- deploy status 使用 indigo / green；
- log 区使用 code background。

---

## 11. Composer / Input

### 11.1 输入框

Placeholder：

```text
Type your instruction or @mention an agent...
```

或：

```text
@orchestrator build a login page for the demo app
```

### 11.2 Mention chips

```text
@orchestrator
@frontend
@backend
@qa
```

### 11.3 Demo shortcut

可选增加：

```text
Build login page demo
```

但如果当前后端没有 shortcut API，不要实现为新功能；只可作为 placeholder / chip 视觉。

---

## 12. Approval UI

P2 已补充 approval card 的最小闭环。UI redesign 中应保留或增强：

- waiting_approval 状态；
- product_confirmation；
- security_approval；
- approve / deny 按钮；
- 不要实现 enterprise RBAC；
- 不要暗示 production deploy approval。

Approval card 颜色建议：

- amber soft background；
- warning icon；
- primary approve；
- ghost/outline deny。

---

## 13. Claude / Codex Adapter 表达

当前 P2 支持：

- CodexAdapter；
- ClaudeCodeAdapter；
- ScriptedMockAdapter；
- 默认 code adapter 可通过 `AGENTHUB_DEFAULT_CODE_ADAPTER=claude_code` 切换。

UI 中不要做 provider marketplace。

可在 task run history 里显示 adapter：

```text
Run 1 · ClaudeCodeAdapter · Completed
Run 1 · CodexAdapter · Failed
Run 2 · ScriptedMockAdapter · Completed
```

不要新增复杂 provider picker。

---

## 14. 当前可前端实现的内容

以下内容应以前端为主实现，不需要改后端：

| 功能 | 说明 |
|---|---|
| Fixed-fluid-fixed 主布局 | CSS / component layout |
| Sidebar visual hierarchy | frontend-only |
| Top pipeline | 可由现有 task/run/artifact 状态推导，初版也可静态/弱推导 |
| Task card visual redesign | frontend-only |
| Run history visualization | 使用现有 runs/events |
| Artifact chips | 从现有 diff/preview/deploy state 推导 |
| Artifact Panel tabs | frontend-only state |
| Browser mockup | frontend-only |
| Deploy card visual polish | frontend-only |
| Empty/loading/error states | frontend-only |

---

## 15. 需要后端支持或应延期的内容

| 需求 | 处理 |
|---|---|
| 完整文件树 IDE | defer |
| Provider marketplace | defer |
| Production deploy | out of scope |
| PR creation | out of scope |
| Docker sandbox UI | defer |
| 多人协作头像/状态 | defer |
| 全量任意自然语言代码编辑 | out of current scope |
| 真实 Claude browser full path 自动演练状态 | 文档 caveat，不在 UI 重构中解决 |

---

## 16. 推荐实施阶段

### Phase 1: Shell layout and visual tokens

目标：

- 统一颜色、字体、背景、卡片、按钮；
- fixed-fluid-fixed layout；
- sidebar；
- top pipeline；
- main surface。

预期文件：

```text
apps/web/src/app/globals.css
apps/web/src/app/page.tsx
apps/web/src/components/workspace-shell.tsx
apps/web/src/components/ui/button.tsx
docs/change-log.md
```

验收：

- 页面结构更接近 Command Center；
- 不改后端；
- 现有测试通过。

### Phase 2: Task timeline and fallback recovery

目标：

- 重构 task card；
- 加强 run history；
- fallback recovery 叙事；
- artifact chips。

预期文件：

```text
apps/web/src/components/task-card-list.tsx
apps/web/src/components/task-card-list.test.tsx
apps/web/src/components/diff-card.tsx
apps/web/src/components/preview-card.tsx
apps/web/src/components/deploy-card.tsx
docs/change-log.md
```

验收：

- 用户能一眼看到 Codex failed -> fallback recovered；
- Diff / Preview / Deploy 证据更明显；
- 不改变现有 task action 行为。

### Phase 3: Artifact Panel

目标：

- 右侧统一 Diff / Preview / Deploy；
- preview browser mockup；
- deploy card completion state；
- diff tab。

预期文件：

```text
apps/web/src/components/workspace-shell.tsx
apps/web/src/components/diff-card.tsx
apps/web/src/components/preview-card.tsx
apps/web/src/components/deploy-card.tsx
apps/web/src/components/health-card.tsx
apps/web/src/components/*test.tsx
docs/change-log.md
```

验收：

- 右侧从 Preview Panel 升级为 Artifact Panel；
- 三个 artifact 类型都有清晰位置；
- 保持 API 不变。

### Phase 4: Polish states

目标：

- empty；
- loading；
- failed；
- waiting approval；
- stale preview；
- no artifact selected；
- responsive fallback。

验收：

- 低数据状态不显空；
- demo 更稳；
- 不扩大功能范围。

---

## 17. Codex 实现要求

Codex 实现时必须遵守：

1. 每个 phase 单独实现、单独验证、单独提交。
2. 不要一次性全量重构。
3. 不要改后端 API。
4. 不要引入未实现功能。
5. 不要新增 provider marketplace。
6. 不要影响 P2 已验证路径：
   - approval card；
   - second-change orchestration；
   - preview refresh；
   - ClaudeCodeAdapter config；
   - fallback demo。
7. 每次修改更新 `docs/change-log.md`。
8. 每次验证：
   ```bash
   pnpm check
   pnpm test
   git diff --check
   ```

---

## 18. 推荐 Codex 开发提示词

### 18.1 诊断阶段

```text
Use AGENTS.md and docs/codex-task-template.md.

Task:
Diagnose implementation plan for docs/ui-redesign-spec.md.

Do not modify files yet.

Scope:
- Map the redesign spec to current frontend components.
- Identify frontend-only changes.
- Defer backend-dependent items.
- Propose Phase 1 / 2 / 3 / 4 implementation plan.
- List exact files to modify.
- List tests to update.

Final response:
- feasible changes
- deferred items
- phases
- expected files
- tests
- risks
```

### 18.2 Phase 1

```text
Use AGENTS.md and docs/codex-task-template.md.

Task:
Implement UI redesign Phase 1: shell layout and visual system.

Scope:
- Frontend-only.
- Apply docs/ui-redesign-spec.md layout and visual tokens.
- Preserve APIs and behavior.
- Update docs/change-log.md.
- Run pnpm check, pnpm test, git diff --check.

Do not commit or push.
```

### 18.3 Phase 2

```text
Use AGENTS.md and docs/codex-task-template.md.

Task:
Implement UI redesign Phase 2: task timeline and fallback recovery visualization.

Scope:
- Frontend-only.
- Improve task cards, run history, fallback recovery, and artifact chips.
- Preserve existing actions and APIs.
- Update tests and docs/change-log.md.
- Run pnpm check, pnpm test, git diff --check.

Do not commit or push.
```

### 18.4 Phase 3

```text
Use AGENTS.md and docs/codex-task-template.md.

Task:
Implement UI redesign Phase 3: Artifact Panel for Diff / Preview / Deploy.

Scope:
- Frontend-only unless tiny API-client adjustment is strictly necessary.
- Implement Diff / Preview / Deploy tabs.
- Preserve preview/deploy APIs.
- Update tests and docs/change-log.md.
- Run pnpm check, pnpm test, git diff --check.

Do not commit or push.
```

---

## 19. 最终验收标准

UI redesign 完成后应满足：

| 验收项 | 标准 |
|---|---|
| 主页面定位 | 一眼看出是 coding-agent command center |
| 核心链路 | Requirement -> Plan -> Run -> Diff -> Preview -> Deploy 明确 |
| Fallback | Codex/Claude failure -> ScriptedMock recovery 清晰 |
| Artifacts | Diff / Preview / Deploy 都有明确位置 |
| 真实证据 | changed file、diff ready、preview healthy、mock deploy ready 可见 |
| 不跑偏 | 没有新增 unsupported features |
| 测试 | pnpm check / pnpm test / git diff --check 通过 |
| P2 路径 | 不破坏 P2 已验证能力 |

---

## 20. 当前设计矛盾和处理建议

### 20.1 三张图 sidebar 不完全一致

处理：

- 以主工作台 sidebar 为准；
- Execution Details / Artifact 状态不应引入另一套 navigation 模式；
- 如果实现详情页面，也复用同一个 AppShell。

### 20.2 Deploy All 文案风险

处理：

- 不使用 `Deploy All`；
- 改为 `Create Mock Deploy` / `Show Deploy Card`；
- 文档和 UI 都要避免暗示 production deploy。

### 20.3 代码预览像 IDE

处理：

- 保留 code preview；
- 不增加完整文件树、编辑器、终端；
- 文案用 `Artifact Preview` 而不是 `Editor`。

### 20.4 紫色过强

处理：

- primary 用于主操作；
- 状态用语义色；
- 不要所有 badge 和按钮都用 primary。

---

## 21. 推荐文件命名

建议将本文件保存为：

```text
docs/ui-redesign-spec.md
```

设计源文件可保留在：

```text
docs/ui-redesign/01-main-workspace.md
docs/ui-redesign/02-execution-details.md
docs/ui-redesign/03-artifact-preview-deploy.md
```

实现过程中如发现设计与现有代码冲突，应更新本 spec，而不是临时改散在 prompt 中。

