# 工作树依赖链接与 Git 干净状态修复

2026-10-07：单任务 `agenthub-worktree-dependency-ignore` 1.1 已完成（本地未提交）。

## 修复范围

实际只读检查旧演示 Session 工作树，Git 报告 `?? node_modules` 和
`?? apps/demo/node_modules`；原 `node_modules/` 规则不能匹配符号链接。

- 版本化 `.gitignore` 的 `node_modules` 规则覆盖目录和符号链接。
- WorktreeService 在创建/复用链接前核对 Session 与源仓库的 Git common directory
  身份，再向其 `info/exclude` 追加缺少的 `/node_modules` 和
  `/apps/demo/node_modules` 固定规则，保留已有字节，重复初始化不再追加。
- 这两个排除项属于该 Git 仓库，影响其所有 linked worktrees，不修改全局 Git 配置。
  因为 Session 从 HEAD 创建，运行时排除也兼容旧 HEAD 的目录规则。
- 不删除/替换链接，不安装依赖，不改 tracked 文件或 Session 持久路径。
  未修改 Scheduler、Target Lock、隔离分支/合并、Adapter 或作用域检查。
- 不同仓库或重定向的 exclude 元数据拒绝初始化，防止写入未分配仓库/宿主位置。
  Git 命令使用既有净化环境，忽略继承的 `GIT_DIR`；符号链接或多个硬链接的 exclude
  文件均拒绝追加规则。

## 真实文件与控制验收

新增回归先复现两项失败：历史规则的链接仍出现在 Git status，错误仓库没有被拒绝。
修复后在独立临时 Git 仓库及内存 SQLite 中验证：

1. HTTP 创建会话，链接指向 setup 时准备的依赖，Git status 为空；旧 tracked
   `.gitignore` 保持不变，原 exclude 内容保留。
2. 重复初始化保持路径、链接 inode 和 exclude 字节不变。
3. 手动构造旧式工作树和既有依赖链接，初始化后 Git 从未跟踪链接变为空，链接未替换。
4. Frontend 任务真实 Scheduler 判定 runnable；新增无关文件后 dirty conflict 仍阻塞。
5. Git 忽略链接时完整 scope snapshot 仍可用；修改受保护链接后 protected digest
   变化，依赖路径的 guardrail 仍拒绝写入。没有跟随链接去读取依赖内容。
6. 错误仓库、exclude 符号链接/硬链接和继承 `GIT_DIR` 负例保留未分配元数据与外部内容。

## 验证记录

- 会话、调度、隔离工作树、DAG 合并和完整 scope 回归 **230 passed / 1 skipped**；
  跳过项为 POSIX 专用用例，耗时约 8 分 29 秒。
- 收尾加入 Git 环境净化/硬链接拒绝控制后，最终 Session 和 process environment
  回归 **18 passed**（其中 13 项 Session 用例，含前一组的 11 项复验，不重复累计）。
  其他模块代码未改，前一组结果保留其实际验证范围。
- `pnpm check` 通过 Web ESLint/TypeScript、API compileall、Demo TypeScript 和
  Demo API compileall；收尾控制后再跑 `pnpm check:api` 通过。
- strict OpenSpec 与 Git 空白检查通过。未运行 API/Web 全量，未安装依赖或永久修改 PATH。

复跑：在 `apps/api` 用根目录 `.venv/Scripts/python.exe` 执行，下列每组提供独立可写
`--basetemp=<临时目录>`：

```text
python -m pytest tests/test_sessions.py tests/test_scheduler.py tests/test_execution_worktrees.py tests/test_dag_integration.py tests/test_task_run_scope.py -q
python -m pytest tests/test_sessions.py tests/test_process_environment.py -q
```

## 使用与剩余边界

加载新服务代码后，新建会话会建立仓库局部的排除规则；它也对同仓库的旧工作树
生效。直接复用 WorktreeService 初始化同样支持旧链接。没有为旧 Task plan 自动迁移
目标绑定，也没有修改用户已有数据库或运行服务。

本轮在开发仓库只读核对旧工作树，写入和控制验收均在独立测试夹具进行；没有
删除之前被自动审批阻止清理的两个依赖链接，也没有绕过该审批。

本轮没有真实 Provider 调用、登录表单功能验收、健康 Preview、build 或部署验收。
ScriptedMock 的完整指令关键词误选脚本仍是下一项独立任务。相关历史边界见
[目标绑定修复](login-plan-target-binding-review.md) 和 [UI 验收](conversation-workbench-ui-review.md)。
未提交或推送开发工作区。
