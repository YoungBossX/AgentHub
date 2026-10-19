# 第一阶段设计与计划核验

实施日期：2026-10-18–19；基线 main `8392b7fb02584ba6b6210705d4c8d4d5513b794e`。
用户已批准 Native 顺序实现，最初后置环境，随后明确授权准备 Docker 并完成资格验收。
本机双镜像正式准备、真实资格18项及最后完整原生API2714通过/19环境跳过，第一阶段本机验收完成。

## 2026-10-19 双镜像修复与真实资格

同一最小 context 的 DEBUG 诊断确认下载可完成，legacy deploy 随后报
`ERR_PNPM_UNUSED_PATCH`。已安装固定 pnpm10.33.4 的源码显示 legacy deploy
还会关闭 frozen/preferFrozen lock。修复只在 deploy 命令选择共享锁文件的离线子集生成，
不删除/放宽全局补丁、不改原 workspace 或依赖锁。固定 Corepack 下载独立缓存，
每次45秒加5秒结束余量、3次；frozen install 每次180秒加5秒、3次，
每个请求30秒/2次重试。固定准备客户端总预算仍为900秒。

正式入口 `pnpm sandbox:prepare --output E:/Docker/AgentHub/images-20261019-07`
退出0，最小输入、镜像 inspect 与构建前后 daemon 绑定全部核对。
完整回执 `E:/Docker/AgentHub/images-20261019-07/images.json`：

| Profile | 实际不可变镜像 ID | Recipe fingerprint |
|---|---|---|
| vite-build-smoke-v1 | sha256:031f9382f1ed5137ad15af0e4ddc45e2576e44a7649971eecff771226d56a15d | 07e982b202550e06387b68159b9c2b87b7b9f62bc523e93b19b2127337a890eb |
| fastapi-contract-v1 | sha256:a54a6dc640cb01f802706811f8ba152f654a1abcaeb7d5e2e8c53e1a45e8733b | bd92d8e8882a5ceb363f245abf37e9394952f98e78051a08c0f41fd3a862cf07 |

doctor退出0、metadata_ready，`runtimeIsolationVerified=false` 不变；doctor不冒充执行验收。
实际不带过滤的 `pnpm sandbox:verify` **18 passed / 0 skipped / 0 failed / 0 errors**，301.11秒，
JUnit `E:/Docker/agenthub-temp/agenthub-pytest-api.mHeiKM/results.xml`，
日志 `E:/Docker/AgentHub/qualification-20261019/verify-final.log`。

- 正确和有缺陷的两类源码、只读root/input、无凭据/socket/宿主sentinel/网络访问通过。
- 实际cgroup v2 CPU限流、PID耗尽及分配进程OOM计数、跨OS进程容量竞争通过。
- 有界日志、缩短的测试超时与总deadline拒绝、5MiB+1前端产物拒绝通过；不把测试探针变成生产命令。
- create响应传输未返回时结束工作进程、check/export容器内探针正在执行时分别崩溃/取消，
  共5个同步窗口通过；精确恢复自有容器/journal/输入，无关真实容器保持不变。
- ScriptedMock真实修改、非空Diff、Docker固定检查、宿主原生浏览器登录契约和健康Vite预览通过。
  模型评审仍为not_run、整体acceptance未建立；这不是实际LLM执行成功。
- 两项独立current测试库分别追加native/Docker任务后，既有行ID/值/附件BLOB、schema/head、
  外键与完整性、旧回执保持不变。产品SQLite未读取、迁移或修改。

失败与修复记录保留：首次6通过/1失败为内存计数输出多余空行；第二次15通过/1失败为
独立临时项目未链接已安装依赖，启动预览找不到vite。补齐测试fixture忽略/依赖链接，
保留ready断言与启动错误后，专项3通过，随后完整18项通过；不改生产预览或安装依赖。
准备超时丢日志先RED，再复用已有自有进程树管理，27项相邻GREEN。

本轮仅5个工程文件相对先前48文件冻结清单变化；一次局部只读审查无Critical/Important。
一项Minor仍保留：客户端只保存每路前12000字节，极长构建日志末尾错误可能丢失；
不改变验证/export输出语义。真实执行和最终套件由实现者验证，审查不代替运行。
原生全量冻结清单与日志位于 `E:/Docker/AgentHub/qualification-20261019`。
本轮首次完整API为 **2711 passed / 3 failed / 19 skipped**，1222.38秒，
JUnit `E:/Docker/agenthub-temp/agenthub-pytest-api.jXXu0O/results.xml`，不记录为全量通过。
两项coordinated-contacts在独立临时Git仓库中产生损坏的pnpm-lock.yaml压缩对象，
git status/fsck均报inflate incorrect data check；一项原生QA恢复在独立后端验收时
Python退出3221225477且无结果日志。底层原因未确认，不借此推断硬件问题或修改业务断言。
主仓库Git连通性检查通过，未删除dangling对象。3项在全新E盘临时目录、未改源码时
全部通过，143.28秒，JUnit `E:/Docker/agenthub-temp/agenthub-pytest-api.cZLi1c/results.xml`。
随后完整复验 **2714 passed / 19 skipped / 0 failed / 0 errors**，1261.91秒，
JUnit `E:/Docker/agenthub-temp/agenthub-pytest-api.Z8ehwu/results.xml`，
日志 `E:/Docker/AgentHub/qualification-20261019/api-final-recheck.log`。
19项跳过为17项真实Docker资格（已由独立强制入口执行）、1项POSIX精确大小写语义、
1项未观察到瞬态属性的Windows探针；2项既有表达式索引SAWarning保留。
这是一次完整成功复验；保留首次失败，不把2711+3拼接为一次全量绿灯。
两份损坏临时对象分别重复读取3次仍CRC失败；主仓库对应blob内容及SHA1正确。
证据 `failed-fixture-object-evidence.json`；不据成功复验宣称底层环境异常已根治。
其余最终全量组成：Web333/44文件、本地工具24、demo-api5、Node控制3、根pnpm check和strict通过。
48个工程文件保持冻结；当前5文件变化由一次局部只读审查覆盖，其余前期实现已有审查。
本机1.3/1.6完成，后续远程交付仍须另行授权。

环境仅验证 Windows Docker Desktop4.95.0/Engine29.8.2、Linux/amd64/cgroup v2。
未验证独立Linux宿主、macOS或真实Codex/Claude模型执行；Provider CLI、预览与浏览器仍为原生。
代码未提交/合并/推送，主工作区服务未切换或重启，默认native不变。远程Actions尚未触发；
按计划独立获授权后才提交推送并检查对应SHA，不能声称本轮远程CI通过。
以下保留此前各阶段的历史快照，不能用旧的延期描述覆盖本节结果。

## 2026-10-19 Docker 环境准备

用户安装并指定 `E:/Docker` 后恢复任务1.3。Desktop4.95.0/Engine29.8.2、
WSL3.0.3、Linux/x86_64、cgroup v2、seccomp 与 CPU/内存/swap/PID 能力已只读核对。
context 为 `desktop-linux`，冻结 endpoint 为 `npipe:////./pipe/dockerDesktopLinuxEngine`。
数据 VHD、WSL 系统盘及新交换 VHD 实际位于 E 盘；本轮 `.wslconfig` 在原文件不存在时独占新建，
未覆盖旧配置。新 TEMP/TMP/TMPDIR 与回执位于 `E:/Docker/agenthub-temp`、`E:/Docker/AgentHub`。
没有发现默认 C 盘 Docker 数据 VHD 或 swap VHD；不承诺 Windows/Docker 零配置/日志写入 C 盘。
只读环境证据保存在 `E:/Docker/AgentHub/environment-20261019.json`。

实际准备发现默认构建退回 legacy，现显式选择配方需要的 BuildKit；另在固定环境白名单下
Windows 插件查找缺少 PROGRAMFILES。改为 `buildx build --load`，仅补该系统路径变量，
不继承代理、注册表认证、API 密钥或 DOCKER_* 覆盖。两项 RED → GREEN 回归与相邻39项通过；
JUnit `E:/Docker/agenthub-temp/agenthub-pytest-api.KkNktx/results.xml`。
一次局部只读审查无 Critical/Important/Minor；未以代码审查代替镜像和隔离验收。

准备01的 corepack 下载中断、02的插件不可见失败记录保留在 `E:/Docker/AgentHub`。
03–05在 corepack 下载阶段长期没有完成，核对各自 argv 后仅停止对应 Buildx 进程；
这三轮是主动中止，不称为成功构建。普通临时 Node/Corepack 容器及最小 cache-only BuildKit
下载均有成功记录，不能据这些记录认定正式镜像已完成或已定位最终网络根因。
本机系统代理开关为0；用户最新说明为未使用 VPN，本轮没有更改全局代理或 DNS。

后端独立准备已成功，实际 image ID 为
`sha256:f8335bf9a925dbb226edac1a8af6bb69bb1ed6c64648de3d81a22597e547b401`；
配方 `bd92d8e8882a5ceb363f245abf37e9394952f98e78051a08c0f41fd3a862cf07`。
只复制5项固定输入，构建 context18.59kB，pip --require-hashes；构建前后 daemon 身份一致，
inspect 验证 Linux/amd64、10001:10001、固定入口/命令和配方标签。
部分回执为 `E:/Docker/AgentHub/backend-image-20261019/partial-image.json`，
明确 completeProfileSet=false，不伪造双镜像 images.json。
前端另以相同纯配方、仅构建网络改为host的一次尝试在360秒超时，日志位于
`E:/Docker/AgentHub/frontend-host-build-20261019/build.log`；客户端自有进程已结束。
两种构建网络均没有取得完整前端镜像，根因尚未确认；正式运行网络策略没有改变。
仅删除来源可在首轮构建日志核对的已退出/无挂载容器85f2f6d1c07b；未全局 prune。

冻结后的完整回归：API **2712 passed / 17 skipped / 0 failed / 0 errors**，1303.92s，
JUnit `E:/Docker/agenthub-temp/agenthub-pytest-api.9bWafq/results.xml`。
17项仍为15项真实资格、1项POSIX语义和1项Windows瞬态属性探针；既有表达式索引2项警告保留。
Web333/44文件、本地工具24、demo-api5、Node控制3、根检查及 strict 全部通过；
48个工程文件全量期间与 `docker-preparation-frozen.json` 完全一致。
汇总 `E:/Docker/AgentHub/native-regression-20261019.json`；相对上轮冻结，
新增源码变化只有已审查的4个准备兼容文件。
只读 doctor 退出1、unavailable/image_missing，`runtimeIsolationVerified=false`，
结果位于 `E:/Docker/AgentHub/doctor-after-partial-images.json`，没有把部分准备记录为 ready。
没有成功双镜像回执，不勾选1.3。
不启动任务1.6、不启用正在运行的产品后端，不改产品库或三个 Adapter，不提交推送。

## 当前实现与证据

2026-10-19 后续修复：目录大小写别名已拒绝（输入和导出写入前共用完整树检查）；
8 项失败回归经修复通过，相邻 72 项通过。新增宿主真实客户端及子进程运行中取消、
工作进程在 create/check/export 调用未返回时被终止后的 OS 锁/journal 恢复与外来资源保留。
专项 87 passed/14 skipped；强制缺环境入口相邻 7 passed/14 skipped，批次重叠。
真实 Docker 入口新增同步探针：create 为实际创建完成但响应未送达（不模拟 daemon 内部调度）；
check/export 为容器内固定测试探针正在 exec 时中断，不等正常阶段返回再注入崩溃。
这些探针尚未在 Docker 上执行，真实隔离和恢复资格保持未完成。

本次两项修复的最终结果：完整 API **2711 passed / 17 skipped / 0 failed / 0 errors**，
1996.77s，JUnit `C:/Users/XCC/AppData/Local/Temp/agenthub-pytest-api.AJbrGR/results.xml`。
17 项跳过为 15 项真实 Docker 资格、1 项 POSIX 精确大小写语义，以及
`test_windows_directory_path_observation_ignores_transient_enumeration_bit`
因本次运行未暴露 0x10000000 属性变化而主动跳过（未改该用例；其余属性守卫测试通过）。
两项既有 schema 表达式索引 SAWarning 保留，不是新增失败。
对比上一轮 2710 个用例，本轮 2728 个：仅原来的 3 个阶段返回后崩溃用例替换为
5 个同步中断用例，另外新增 16 个目录/宿主中断用例，无意外移除。
完整 Web333/44文件、启动工具24、demo-api5、Node控制3、根检查及后续 API 编译均通过。
48 个代码/工程文件在本次最终全量期间与冻结摘要完全一致；产品库、Adapter、迁移、
执行引擎、依赖锁及默认 CI 未改动，未安装、提交、推送、合并或重启服务。

本次局部只读审查发现并修复 1 项 Important（带内容同步标记原子发布）及 2 项 Minor
（外来资源使用独立状态副本断言、消除过期目录延期描述）。修复后专项62 passed/14 skipped，
再运行上述冻结后的完整套件。首次全量在约15%主动中断以纳入测试同步修复，不称为通过或失败。
真实镜像、Docker/资源隔离、Linux 实机进程行为仍未判定，不用当前宿主结果替代。

- 1.3 准备/控制代码单元通过；官方 Docker Hub / PyPI JSON 元数据及依赖哈希已冻结，但没有实际 build/inspect 成功回执。
- 1.4 runtime/归属/导出专项 62 项通过；后续增加中断 journal 更新回归。仅 CLI 替身及真实本机进程/文件锁测试，不是容器隔离证据。
- 1.5 验证/QA/原生浏览器回归 143 passed；Adapter/恢复/生命周期等相邻回归 125 passed；UI18 passed；根 pnpm check 通过。这些批次有重叠，不相加为独立用例。
- 1.6 原生旧数据兼容及强制缺环境失败入口 2 passed，默认模式13个真实环境资格用例明确跳过；不能由这些跳过项确认 Docker 成功。
- 数据验证库在外部临时目录，由 current migration 新建并预置旧值；没有读取、迁移、重置或修改产品数据库。
- 一次独立审查完成；三个 Important 经六条 RED → GREEN 回归修复，专项 138 passed/13 skipped，JUnit `agenthub-pytest-api.tufD44/results.xml`。未调 Docker；测试替身不证明隔离。
- Web333/44文件、本地工具24、demo-api5、Node控制3及根 pnpm check 通过。
- 2026-10-19 首轮完整 API：2688 passed/3 failed/14 skipped，1826.23s，JUnit `agenthub-pytest-api.3qBo0z/results.xml`。两项表达式索引 SAWarning 来自既有拒绝未知 schema 用例。三项失败及诊断均保留，没有把首轮写成通过。
- 原生修复报告策略摘要兼容、准备测试缓存及旧续租测试启动同步等待已修复；126项相邻兼容回归通过，最后46项通过，批次重叠。
- 上一轮冻结后完整 API：2696 passed/14 skipped/0 failed/0 errors，1907.87s，JUnit `C:/Users/XCC/AppData/Local/Temp/agenthub-pytest-api.5Z2qhE/results.xml`。14项跳过为13项显式真实 Docker 资格与1项 POSIX 精确大小写语义，不能当作 Docker 成功。
- 最终根检查通过；完整 Web333/44文件（单 worker）、本地工具24、demo-api5、Node控制3通过。相应证据保留在本计划忽略工作区 final-* 日志；第一轮失败与诊断记录没有覆盖。
- 1.3/1.6 总复选框保留未完成。未安装、提交、推送或触发远程工作流。

## 最终独立审查与边界

审查针对基线 8392b7f 到整个工作树（含未跟踪文件），文件与 manifest 一致。
该整体审查只读，不执行测试或 Docker；修复后由实现者按失败回归和完整套件核验。
2026-10-19 新增两项修复另做一次局部审查，未重复审查整个阶段或派发第二意见。

- 已修复：context 核对与实际操作之间的重定向窗口，改为冻结 endpoint；所有 daemon 操作使用 --host 和临时空客户端配置。
- 已修复：Docker 用户 config.json 可注入代理凭据，改为隔离配置并核对实际 Env；回归仅使用虚构代理/凭据，没有读取用户真实配置。
- 已修复：create 结果未知时空查询错误删除恢复凭据，改为调用前持久化 creating/createAttempted 并保留未知结果，覆盖容器延迟可见后的严格恢复。
- 已修复（2026-10-19）：`Assets/a.js` 与 `assets/b.js` 的目录组件大小写别名现由完整路径树检查拒绝，输入与导出写入前均核验；允许共享完全相同拼写的目录。不是自动改名或业务 import 修复，也不代表已完成 Linux/Docker 跨平台资格。
- 尚未判断：真实镜像可构建性、Docker Desktop 挂载表示、资源/隔离 enforcement；用户明确环境后置，1.3/1.6 保持未完成。
- 尚未判断：真实 Codex/Claude Provider 成功；本次只是后置固定验证，不扩大模型执行结论。
- 范围外：恶意宿主管理员、被攻陷 daemon、内核逃逸、完整语言运行时反射抵抗；设计只面向受信本地 daemon。
- 尚未判断：macOS 宿主；接受 Unix socket 不是兼容验收。
- 真实资格脚本仍未运行；原先预先置位取消、阶段返回后崩溃的覆盖不足已由后续同步探针替换/补充。真实进行中窗口必须执行后才能完成 1.6，宿主进程及 CLI 替身结果不等于真实容器结果。

完整回归追加修复：绑定执行信息的新原生回执同时保存 nativePolicyFingerprint，
读取时与原生当前策略及服务器事件逐项核验；主策略仍包含执行包装和代次。修复历史只有在
相同 profile、新结果为 native 且旧原生检查摘要完全相同时才使用该兼容路径，不允许 Docker
或不同策略借用。准备测试在前后清空配置缓存。旧续租用例的一秒启动等待在全量中超时，
单独复跑通过；调度延迟1.1秒负例复现，改为五秒启动同步等待后正反延迟都通过，
原续租/到期/精确锁代次断言不变。首次在 Adapter.createRun 内插入延迟的诊断会改变持锁
阶段，因此舍弃该模拟，最终只在执行任务调度前插入延迟，不改生产行为。


## 本轮实施取舍与代价

按执行台账顺序保留全部取舍，便于后续环境准备和集成时复核。

| 序号 | 取舍 | 代价或限制 |
|---|---|---|
| 1 | 按批准的顺序完成无 Docker 环境可验证的实现，实际环境后置 | 环境准备后仍可能暴露问题，不能标记第一阶段完成 |
| 2 | 复用已安装依赖，不安装 Docker/WSL、不改产品库、不提交推送 | 当前运行环境不会自动采用改动；开发依赖链接不能用于容器挂载 |
| 3 | 保留未提交工作的忽略台账 | 台账尚无 Git 恢复保障，需要随工作区保留 |
| 4 | 无代码变化时直接记录刚完成的成功测试，不为 task-done 重跑同一命令 | 结论依赖所保留的原始日志/JUnit |
| 5 | 镜像/控制接口单测通过后继续 runtime，1.3 整体仍未完成 | 真实构建仍可能发现配方或平台缺陷 |
| 6 | 按 daemon ID 而非 context 别名限制容量 | daemon 身份无法核实时拒绝执行 |
| 7 | 导出接口强制传 expected_files 全量摘要表 | 调用方需提供完整快照，不能只凭 sourceFingerprint |
| 8 | 原生验证和 Docker 客户端共用自有进程管理 | 不支持 Windows Job 绑定时返回 unavailable，不启动失控子进程 |
| 9 | 无启动元数据的原生直接调用保留旧回执形式 | 该历史兼容路径证据较弱，不补造执行环境或代次；Docker 必须有绑定 |
| 10 | 先独立审查，再运行昂贵的完整原生回归 | 全量兼容问题会较晚暴露，但修复后仍须完整重跑 |
| 11 | create 结果未知且查不到 ID 时保留 journal/输入并阻断 | 可能需要操作员排查；不以可用性换取丢失恢复依据 |
| 12 | 镜像构建、Desktop 挂载与资源隔离保持未判断 | 1.3/1.6 未完成，不能声称容器隔离已通过 |
| 13 | 本次不判断真实 Codex/Claude 执行效果 | Adapter 回归不能代表新增真实模型成功证据 |
| 14 | 宿主管理员、被攻陷 daemon、内核逃逸和完整反射抵抗范围外 | 只面向受信本地 daemon，不能称为敌对多租户安全隔离 |
| 15 | macOS 保持未验收 | Unix socket 可解析不等于宿主兼容 |
| 16 | 已补运行中中断同步探针，真实 Docker 执行继续后置 | 未执行的资格脚本不能证明真实容器进行中窗口的恢复 |
| 17 | 保留隔离分支与工作区，不进入提交/合并菜单 | 改动未提交，也未加载到主工作区的现行服务 |
| 18 | 对 review_repairs 增加严格的旧原生策略比较兼容 | 错误比较可能误报检查恢复；以同 profile/原生策略、执行版本和负例约束 |
| 19 | 只将租约测试的启动同步等待由1秒调到5秒，增加调度延迟样本 | 挂起测试最多晚4秒报错；续租/锁代次/到期断言与生产超时不变 |

原延期目录大小写 Minor 已在 2026-10-19 修复；实际 Linux/Docker 资格仍待环境。

## 1.2 本地实现检查

- 新旧验证测试合计 96 passed / 0 failed；基线旧测试 67 passed，新测试红灯 29 failed 后绿灯 29 passed。
- 外部 JUnit：`C:/Users/XCC/AppData/Local/Temp/agenthub-pytest-api.QsLlJ5/results.xml`。
- `pnpm sandbox:doctor`：退出 1，unavailable/context_missing，runtimeIsolationVerified=false；独立子进程检查没有 app.db 导入或数据库文件产生。
- 没有产品库、Adapter、models/migrations/seed 改动，没有依赖安装、提交或推送。

以下保留 1.1 的文档核验快照。

## 源码核对

- automatic_validation.py：两个固定 profile、源码捕获、超时/输出预算及事件/currentness。
- backend_validation.py：只运行受信语法/ASGI harness；当前策略含宿主依赖，Docker 路径须分离。
- scripts/demo-validation-build.mjs、demo-build-smoke.test.mjs、demo-backend-check.py、
  demo-requirement-check.mjs：固定命令及浏览器/构建产物衔接。
- task_runs.py：taskRunExecutionAccessBinding 的 executionAttemptId、runnerId 等启动身份；
  不能拿后来可能变化的 runner_id 当永久验收代次。
- run_engine.py、events.py、qa_assessment.py：已有租约/最终写入围栏、线程/数据库与旧回执边界。
- models.py、config.py、qa-evidence.tsx、lib/api.ts：不改结构或种子，增量 JSON 和最小环境标签。

## 只读环境核对

当前 PATH 未找到 docker，默认 Docker Desktop 文件不存在。没有调用构建、拉取、
运行、安装、daemon 启停或数据库命令；未重新检查此前 WSL 状态。
设计引用的 Docker flags、tmpfs/cp、exec、网络与权限事实核对了官方文档。
没有 Docker/镜像/容器隔离成功证据；不能以本文件替代实际资格测试。

## 自查修正

- 两个独立镜像，避免混合 Node/Python 镜像的 ABI 与依赖复杂度；摘要在真实准备时冻结。
- Docker 必须显式选本机 context 和实际 image ID；native 路径不探测 Docker。
- tmpfs 不直接 docker cp；采用固定 exec 导出受限 JSON/base64，主机独占物化。
- 补充重复键、NFC/大小写、Windows 设备名/ADS、尾点空格及 --mount 逗号语法负例。
- 冻结 dataclass 中的映射也做只读包装；工作线程不持有 DbSession/ownership_guard。
- 区分请求 Docker 与真正执行、Docker 命令与原生浏览器；旧环境缺失不补造。
- 旧回执遇新 Docker 策略只读过期，不重写数据；类型/接口和五个 Review Focus 对齐到任务。
- 不暂停容器；keeper 到期、私有 journal 和容量锁覆盖崩溃/重启，不凭前缀删除未知资源。
- 真实容器资格 job 缺条件必须失败；默认 native CI 可明确 skip，不冒充第一阶段验收。

## 文档检查

已通过：

- `openspec validate agenthub-container-validation --strict`。
- `git diff --check`。
- 六份专项文档 UTF-8、代码围栏配对、占位词及相对链接检查；首次八个链接有效，
  完成任务核验记录后新增的 verification 链接再次检查。
- 十项变更仅为 docs/OpenSpec 和精确 .gitignore 白名单；计划文件未被忽略。
- `git diff --exit-code HEAD -- apps scripts containers .github package.json pnpm-lock.yaml pnpm-workspace.yaml AGENTS.md`
  退出 0；运行源码、Adapter、模型、固定迁移和依赖均无变化。

完成 1.1 只表示文档交付，不代表书面设计/计划已获批准或实施已开始。
本轮未执行运行测试、安装、Docker 构建/运行或数据库读写；没有提交、推送或新远程 CI。
文档核验不代表运行测试、数据库保留实验或容器隔离已经通过。
