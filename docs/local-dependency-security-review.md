# 本地依赖安全更新验收

日期：2026-10-08—09。范围：`agenthub-local-dependency-security-refresh` 1.1。
本地未提交；未推送。证据索引：[validation-index.json](evidence/local-dependency-security/validation-index.json)。

## 问题与修复

新鲜审计发现生产依赖 12 条告警，完整树 19 条。此前零告警是历史快照。
按公告修复范围更新 Next/eslint-config-next 16.3.8、DOMPurify 3.4.16、sharp 0.35.5、
source-map-js 1.2.2、baseline-browser-mapping 2.11.0 和 brace-expansion 1.1.21/5.0.12。
安装过程的 `^16.3.8` 一度解析到 16.4.0，最终改为 `~16.3.8`，按最终锁文件重新验证。
所有安装禁用生命周期脚本，没有改动后端依赖或 Agent 执行权限。

本地源码检查发现两层运行依赖偏差：React Monaco loader 默认下载 CDN Monaco
0.55.1；安装的 Monaco 0.56.0 又在 ESM 文件中内嵌 DOMPurify 3.4.8。因此单改
锁文件不足以改变浏览器实际使用的净化器。现在由客户端按需加载本地编辑器和 worker，
pnpm 补丁把 ESM 净化器改为导入包依赖。实际浏览器脚本包含 3.4.16、不含 3.4.8，
阻断外网时仍可显示 Diff。未使用的 AMD/预打包副本没有被宣称已经重写。

切换视图实测暴露 Monaco 0.56 的模型释放顺序兼容错误：React wrapper 先销毁模型，
编辑器还持有该模型。由本地组件管理匿名模型，在卸载时先解绑再释放，随后让 wrapper
释放编辑器。加载失败保留代码补丁与重试，实际拦截本地编辑器分块后恢复加载通过。

## braces 的有界缓解

截至本次核查，[GHSA-vfj7-8cjw-p6xm](https://github.com/advisories/GHSA-vfj7-8cjw-p6xm)
没有发布修复版；实际路径是
`eslint-config-next → @next/eslint-plugin-next → fast-glob → micromatch → braces 3.0.3`。
开发工具输入可到达它，不属于生产依赖树。上游复现说明见
[braces issue 70](https://github.com/micromatch/braces/issues/70)。

以 4,500 层、9,001 字符的成对括号在原始包复现：compile/stringify 的两类输入及
expand 的花括号输入发生原生栈溢出，expand 的圆括号样本正常返回。它们均未超过
已有 10,000 字符限制。最初使用的超长样本只触发长度校验，不计为漏洞复现证据。

跟踪补丁将 AST 根到叶深度限制为 128，解析器最多允许 127 层同时打开的容器，
为叶节点保留一层；三个递归遍历器也检查调用方直接传入的 AST。上述六个样本现在
均受控拒绝。11 组正常文件匹配、范围、转义、引号和不完整输入的结果与补丁前一致；
回归另覆盖边界深度、混合/未闭合嵌套、循环 AST、实际 micromatch/fast-glob 调用。

这不是上游修复版，也不宣称解决任意组合展开规模或伪造 AST 父指针循环问题。
无效输入仍需调用方处理异常。维护与移除条件见 [patches/README.md](../patches/README.md)。

## 最终验证

| 检查 | 结果与边界 |
|---|---|
| `pnpm audit --prod --json` | exit 0，12→0；审计输出无屏蔽项 |
| `pnpm audit --json` | exit 1，19→1 high，仅 braces 已知上游告警；保留原始结果，不伪称全树归零 |
| 冻结安装 | `pnpm install --frozen-lockfile --ignore-scripts` exit 0，两个补丁及哈希受 lockfile 管理 |
| 本地回归 | `pnpm test:local`：17 passed（12 启动器 + 5 依赖测试节点） |
| Web 全量 | 28 文件、237 passed；包含新增加载/失败恢复/过期响应/模型清理覆盖 |
| 根静态检查 | `pnpm check` exit 0，Web lint/types、API 语法、demo 类型和 demo-api 语法通过 |
| 生产构建 | Next 16.3.8 `pnpm --filter @agenthub/web build` exit 0 |
| 规范与空白 | strict OpenSpec 与 `git diff --check` 通过 |
| 开发模式浏览器 | Edge：已有原生 Diff 内容、本地 worker、实际净化器版本、外网阻断、只读、亮暗、反复切换、加载失败后重试、实际 Vite iframe 通过，无未捕获 JS 错误 |
| 聊天兼容 | 原样本 Markdown、复制/失败反馈、引用/置顶、图片显式加载与刷新；1440/390/320px 无页面横向溢出 |
| 后端与数据 | 26 个后端基线文件哈希不变；Session/Message/TaskRun/Diff/Artifact 完整行哈希不变；Task 逐字段复核仅旧任务 `d9e6e037-46d1-42ef-984e-a473b6bb9e2b.updated_at` 被既有逻辑刷新 |

构建时发现 JSON 注册路径与安装版本不匹配，已改用该版本的 features/json 路径；
测试 hook 返回 mock 函数和测试替身类型断言问题均在最终检查前修正。
额外的 3002 端口本地生产模式浏览器服务启动被自动审批拦截，仅返回 `blocked by policy`；
未绕过拦截，也未宣称完成该模式浏览器验收。最终运行页面仍是 3000 开发服务，连接原
8006 API。后端未改动，本轮未重跑全量 API 或调用新模型；复用此前原生 TaskRun
`3f6b828b-39d3-4aa2-97dc-5bc5f4a020b3` 的真实 Diff 和健康 Vite 结果进行兼容验证。

参考核查：[Next RCE 公告](https://github.com/vercel/next.js/security/advisories/GHSA-vcvr-r3jv-pc5j)、
[Next 图片优化公告](https://github.com/vercel/next.js/security/advisories/GHSA-cjq9-62q9-8jv4)、
[DOMPurify 公告](https://github.com/cure53/DOMPurify/security/advisories/GHSA-p98j-92pf-mc4p)。
安装版本命中公告不等于当前应用已被利用；未将静态审计作为实际攻击成功证明。
完整项目仍有附件输入、重新生成、对话创建 Agent 等独立缺口，见
[交付表](local-project-delivery.md)。
