# P18c 实时内存合规性冻结评审

**冻结日期：** 2026-08-29

**结论：** P18c 5.1 已通过新的 Windows 有界演练闭合。完整机器可读证据保存在
[`p18c-bounded-rehearsal-evidence.json`](p18c-bounded-rehearsal-evidence.json)。本评审保留
所有失败与恢复步骤，不把最终 TaskRun 的后处理失败误报成 `completed`。

## 演练边界

- 外部目标：`external-p18c-library-app`
- 项目目录：`C:\Users\XCC\Desktop\agenthub-rehearsals\p18c-library-app`
- 初始空仓库提交：`9a5178716e5df1ee632d1e314d3734e2aa43105e`
- 前端边界：Vite + React + TypeScript；数据只使用 `localStorage`
- 依赖策略：未安装依赖；通过本轮临时验证镜像复用 AgentHub 已有依赖缓存
- 真实 provider：`local-codex-cli` / `codex`
- Planner：配置的 LLM planner 未启用，使用受审计的外部目标 fallback planner

用户提示原文如下；其中没有重复项目目录、技术栈、持久化、变更日志、平台边界或 provider
证据规则：

```text
帮我在桌面开发一个简单的图书管理系统。有登录页面，初始账户和密码是 18088888888 / 888888。登录后进入管理页面，只需要有图书管理功能：加入图书、删除图书、修改图书、查询图书。
```

提示 SHA-256：
`05c1a2c76180ddeb728829e1488674659ab14f78b869d0eae173105679aaf97d`。

## 会话、快照与哈希

| 字段 | 值 |
|---|---|
| Session | `e65ba76a-5abe-440b-a34d-f0b7dca8ed0c` |
| Task | `71811fb2-276a-41b9-ae01-c66b5829a947` |
| `memorySnapshotId` | `b884d8c2-4042-45b2-9af7-d057c63294a5` |
| `agentsMdHash` | `2b74cf4bea8ce3c2ccfde8f7a61184396585c037740317646c358e4d5c2c22ce` |
| `claudeMdHash` | `73fe70bd9bc5e556730f6a4bf257a43ab92052a91df1de30ac1b766cba24da8c` |
| target registry version | `d7d0f67d74ddbf2c4cfc0794b5e9d100b15172c6c1d0b0b35d7f8efc54c2c95e` |
| runtime config version | `2c9bf9a484309146265bcbfa854130ce91d41f42e812a37a9027012443a1f2fa` |
| context-pack hash | `44269c3f5d09e1d24eb8c1ac4523e6e821b58f9e326fdadc03dfb6a6884061b3` |

六条活跃规则对应的实际 `MemoryItem.id` 为：

1. `dbc396fa-af9d-4b0e-8808-a4fe4b453896`
2. `56010ca5-85cc-4d5c-b995-96f88c5c4041`
3. `7f08b339-1c74-403a-a7bf-b36bfb55f2e2`
4. `01c0e2f5-762f-452c-bf15-317d8d90a10f`
5. `58d60769-f466-431a-892e-1c29464f9273`
6. `2394f1ce-afce-4466-9b9c-6a84af3ead78`

逻辑规则顺序依次为项目位置、Vite/React/TypeScript、`localStorage`、变更日志、平台边界和
provider 证据要求。Planner、coding agent、review、TaskRun 与 task trace 的一致性检查均使用
同一 `memorySnapshotId`，snapshot consistency 为 `1.0`。

## Provider 与恢复链

| 顺序 | TaskRun | 结果 | 证据解释 |
|---:|---|---|---|
| 1 | `e933edce-b7c2-4f0b-8b04-fd6296e20a74` | `TASK_RUN_TIMEOUT` | 真实 Codex 已生成应用；Corepack 签名 key 不匹配使 check/test/build 阻塞到 600 秒超时 |
| 2 | `ad06c60b-e288-4edb-a61b-4d3c81299cf9` | `TASK_RUN_SCOPE_UNVERIFIABLE` | 临时依赖联接进入受保护目标树，作用域 fail-closed；未启动 provider |
| 3 | `aab84938-ab59-45a9-acd2-2c26897bc14a` | `TASK_RUN_SCOPE_UNVERIFIABLE` | 同一恢复问题的第二次 fail-closed；未启动 provider |
| 4 | `1c83525d-2488-4772-8d0b-2cc293a4163c` | provider turn 完成；TaskRun 后处理失败 | Codex adapter run `codex-3f1b6528-7816-4fd7-b5b4-0e9fa360fb53` 产生 `turn.completed`；作用域 `passed`，但 pre-fix Git 文本收集使用 GBK，`collecting_diff` 抛出解码错误，持久化 TaskRun 保持 `ADAPTER_EXECUTION_ERROR` |

最终 provider 运行的作用域验证 schema 为 `agenthub.task_run_scope_validation.v2`，状态
`passed`，受保护类别为 `.git` 和 `node_modules`，基线有 52 个受保护条目。外部验证镜像位于
本轮临时目录，不写入目标树，不绕过 Target Registry、PlanValidator 或作用域校验。

本轮修复了两个 Windows UTF-8 缺口：Codex JSONL stdout 与 Git diff/行数收集均显式使用
UTF-8，并以 replacement 处理不可解码字节。最终 Diff 是在修复后从同一 Session、同一 Task、
同一外部 Git 基线补采；没有把 TaskRun 状态改写为 `completed`。

## Diff 与 changed-files

| 字段 | 值 |
|---|---|
| Diff | `0ed19075-f53e-4706-a3b4-8cfbe4da2a70` |
| Diff artifact | `bc542c97-0761-4e52-8ff4-367d694b83aa` |
| base | `9a5178716e5df1ee632d1e314d3734e2aa43105e` |
| head | `9a5178716e5df1ee632d1e314d3734e2aa43105e+worktree` |
| patch SHA-256 | `33d771fe9c00c105b9efdea901d5abf7e852c0120f769006bb73f9957064cd9f` |

精确 changed-files 共 13 个：

1. `index.html`
2. `package.json`
3. `src/App.tsx`
4. `src/library.d.ts`
5. `src/library.js`
6. `src/library.test.mjs`
7. `src/main.tsx`
8. `src/styles.css`
9. `src/vite-env.d.ts`
10. `tsconfig.app.json`
11. `tsconfig.json`
12. `tsconfig.node.json`
13. `vite.config.ts`

没有 AgentHub `apps/api`、`apps/web`、平台脚本、后端或数据库文件进入该外部应用 Diff。

## 功能、验证、Preview 与 Staging

应用源码包含固定凭据 `18088888888 / 888888`、登录页、管理页、图书 add/delete/edit/search，
以及 `localStorage` 读写。独立验证制品为
`4a17b1b6-e755-4c7b-b802-aa0bce1c2337`：

| 命令 | 结果 |
|---|---:|
| `pnpm test` | exit 0；3 tests passed |
| `pnpm check` | exit 0 |
| `pnpm build` | exit 0；Vite 生成 3 个 staging 文件 |

缓存中的 Vite 7.3.3 提示 Node 22.11.0 低于其建议的 22.12+，但 build、preview 与 staging
均实际成功；没有把 warning 省略或当作失败。

| 制品 | ID | 结果 |
|---|---|---|
| Preview smoke | `9904ad87-0cda-498e-8f6b-697e75c22d7b` | HTTP 200，健康，进程已停止 |
| Local staging smoke | `73b1c068-db1e-4a99-9cb8-ea960e73edaf` | HTTP 200，健康，进程已停止 |

## Review 与合规性

脚本化 Review ID 为 `15904c56-ec8c-44cd-8749-88ac9ca0c5b5`，artifact 为
`1d961fd1-db5b-4346-a300-76e710ac6f3d`，状态 `warning / medium`。三个 advisory 均是
Review collector 没有读取本轮 generic validation artifact，因而声称 check/test/build 未记录；
实际三项命令及其 stdout/stderr SHA-256 已保存在 validation artifact 和机器可读 JSON 中。

合规 artifact 为 `c6d5d1c7-336d-4c85-929b-a547120893e8`，结果 `passed`，违规列表为空：

| 指标 | 值 |
|---|---:|
| 偏好召回率 | `1.0` |
| 项目记忆召回率 | `0.8333333333333334` |
| 跨 Agent 一致性率 | `1.0` |
| 快照一致性率 | `1.0` |
| 变更日志缺失率 | `0.0` |
| 目标边界违规次数 | `0` |
| 持久化记忆违规次数 | `0` |
| provider 证据违规次数 | `0` |
| 任务成功增量 | unknown |

完整 provider evidence 为：TaskRun `1c83525d-...`、Diff artifact `bc542c97-...`、validation
artifact `4a17b1b6-...`。任务成功增量保持 unknown，因为没有可比较的实时无记忆 control run。

## 冻结限制与决定

- 原 2026-06-07 冻结稿仍不可恢复；本文件是一次新的有界演练，不是旧稿恢复。
- 最终真实 provider turn 完成且作用域通过，但持久化 TaskRun 因后处理 UTF-8 缺陷保持 failed；
  本评审明确区分 provider 完成、作用域结果、TaskRun 终态和后续补采制品。
- fallback planner 的成功不能当作 LLM planner 成功。
- Review 的三个 warning 是命令证据集成缺口，不是三项命令实际失败。
- preview/staging 是本机有界 smoke，进程均已停止，不代表生产部署。
- 没有新增生产 backend/database、云部署、身份验证加固、检索算法、provider 市场或安全边界绕过。

上述限制均已冻结，且 5.1 要求的 provider、session、task/run、snapshot、内存哈希、活跃
MemoryItem、Diff、changed-files、Review、build/check/test、preview/staging、合规性、follow-up
与限制证据已完整保存。因此 P18c 5.1 可以勾选，P18c 为 **24/24 tasks**。
