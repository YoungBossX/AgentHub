# 固定检查与测试容器

此功能为服务器固定验证增加可选 Docker 后端，默认仍是 native。Provider CLI、
预览和浏览器检查在宿主运行；不代表 Agent 或整个平台已经容器化。
2026-10-19 两类镜像已通过正式准备入口构建并 inspect；真实资格 **18 passed，零跳过/失败**。
已验证前后端正确/错误源码、只读与网络边界、CPU/PID/OOM、容量竞争、超限导出、
运行中取消及 create/check/export 崩溃恢复、旧数据保留和真实写文件/Diff/验证/预览闭环。
环境为 Windows Docker Desktop 4.95.0 / Engine 29.8.2 的 Linux/amd64、cgroup v2；
不推广为 macOS、独立 Linux 宿主或真实模型执行的验收结论。
最后完整原生API **2714 passed / 19 skipped / 0 failed**，Web333、本地工具24、
demo-api5、Node控制3、根检查和专项strict通过。首次全量3项临时环境异常及后续成功记录均保留。
产品库和三个 Adapter 未修改；代码保留在 `codex/container-validation`，未提交或合并，
主工作区服务仍使用原来的 native 配置。远程手动 Actions 尚未触发。

## 操作员准备

本机 Docker Desktop 已安装在 `E:/Docker/DockerDesktop`，Linux/amd64 daemon 已启动。
Docker 数据盘为 `E:/Docker/wsl-data/disk/docker_data.vhdx`；WSL 系统盘和交换盘
也位于 `E:/Docker/wsl-data`，崩溃目录已配置到该目录。用户 `.wslconfig` 只保存 E 盘路径；Docker/Windows 少量配置和日志
仍可能由系统保存在 C 盘，不代表镜像、容器和卷数据位于 C 盘。

日常在 PowerShell 使用以下命令；已运行时无需重复启动：

```powershell
docker desktop start --timeout 60
docker version
docker ps
docker system df
```

`version` 同时出现 Client/Server 才表示已连接引擎；`ps` 只列运行中容器，
临时检查结束后为空是正常情况。`system df` 用于查看 Docker 镜像、容器及构建缓存占用。

以下命令在 `codex/container-validation` 隔离工作区使用；当前主工作区尚未集成这些命令。
每次新开操作终端先设置临时目录，避免准备、客户端私有配置和测试证据落入默认 C 盘临时目录：

```powershell
$env:TEMP = "E:/Docker/agenthub-temp"
$env:TMP = $env:TEMP
$env:TMPDIR = $env:TEMP
$env:PYTHONDONTWRITEBYTECODE = "1"
```

`E:/Docker/agenthub-temp` 和回执父目录 `E:/Docker/AgentHub` 已由本轮创建。
其他机器由操作员另行准备本机 Linux/amd64 Docker daemon 和已安装的平台依赖。
真实资源资格测试使用 cgroup v2；默认 CI 不要求 Docker，不会安装或启动 daemon。
显式选择本机 context，拒绝 TCP/SSH 和继承的 DOCKER_* 覆盖：

```powershell
$env:AGENTHUB_VALIDATION_DOCKER_CONTEXT = "desktop-linux"
pnpm sandbox:prepare --output E:/Docker/AgentHub/images-new
```

context 名称须使用本机实际存在的值；输出必须为尚不存在的外部绝对目录。
prepare 是唯一下载基础镜像/依赖的步骤，不能在任务执行中调用。它只发送固定清单，
输出 `images.json`、构建输入摘要和有界日志，不自动修改 `.env` 或当前 Adapter。
Node 22.23.2 / Python 3.12.15 的 linux/amd64 manifest 与 Python wheel 哈希来源记录于
[recipe-lock.json](../containers/validation/recipe-lock.json)。这两个基础 digest 不是最终验证镜像的 image ID。

按真实准备回执设置服务器环境变量：

```powershell
$receipt = Get-Content E:/Docker/AgentHub/images-20261019-07/images.json -Raw | ConvertFrom-Json
$env:AGENTHUB_VALIDATION_FRONTEND_IMAGE_ID = $receipt.profiles.'vite-build-smoke-v1'.imageId
$env:AGENTHUB_VALIDATION_BACKEND_IMAGE_ID = $receipt.profiles.'fastapi-contract-v1'.imageId
pnpm sandbox:doctor
pnpm sandbox:verify
```

上例使用本机已完成的准备回执；其他机器必须使用其实际准备目录，不能照搬镜像 ID。
doctor 只读检查元数据，`metadata_ready` 不等于隔离测试通过，
`runtimeIsolationVerified` 始终 false。verify 使用新外部 SQLite/JUnit 目录；
环境或镜像缺失必须失败。默认测试会明确跳过 real-container 用例，不可据此宣称通过。
手动 Actions 工作流 `Fixed validation containers (manual)` 只由 workflow_dispatch 触发；
它不改变默认 CI，也不会自动触发或发布镜像。

本机已通过真实资格；需要启用时，再设置 `AGENTHUB_VALIDATION_BACKEND=docker` 并按正常启动流程重启服务。
此处没有自动切换或重启。回退为 native 仅影响新的验证，不删除数据和旧报告。

## 执行与证据

仅支持 vite-build-smoke-v1 和 fastapi-contract-v1；执行不 pull、不安装，不运行目标配置或测试。
固定 non-root/init/read-only/network-none、1 CPU、1024 MiB、128 PID、tmpfs 和 60/180 秒预算。
只能挂载服务器重捕获的只读快照；没有项目目录、数据库、Provider 凭据或 Docker socket。
容量为每用户/daemon 一次；上下文漂移、未知归属或清理失败会拒绝新运行，不清理外部容器。
私有状态位于用户临时目录的 agenthub-container-validation-* 子树，不能通过任务指定路径。
context 只用于最初解析；所有 daemon 操作绑定已核验的本机 socket/npipe，并使用临时空
Docker 客户端配置，避免读取用户代理或注册表凭据。实际容器环境还需与镜像及固定变量一致。
create 超时/断连后即使暂时查不到容器，也保留 journal 和输入并报告 cleanup_required；
后续发现资源才按原归属恢复。持续查不到时需要操作员核实，不能删除 journal 绕过门禁。

UI 区分实际原生/Docker 命令、请求但未运行、历史环境未记录，以及原生浏览器检查。
回执绑定源码/策略、不可变镜像、配方和冻结启动代次；打开报告不访问 daemon，不补写旧数据。
源码、配置镜像或验证策略变化会使旧证据过期。Docker 命令通过不覆盖模型未运行、规则失败
或浏览器环境缺失。Windows Job Object 只管理验证自有子进程，不称为安全沙箱。

资格记录、已知限制和本地结果见
[verification](../openspec/changes/agenthub-container-validation/verification.md)。
镜像和 JUnit 原始回执保存在 `E:/Docker/AgentHub`、`E:/Docker/agenthub-temp`。
准备日志有界保留已捕获输出；超长构建输出可能丢失末尾诊断，不能把日志缺少错误当作成功。
