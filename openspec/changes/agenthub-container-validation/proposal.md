# Fixed validation containers, phase 1

## Why

用户要求先完成固定检查和测试容器化的设计与实施计划，兼容现有 Adapter，
保留已有数据库及数据。当前两个内置验证配置使用宿主 Node/Python 和临时副本；
工作树隔离、CLI 工具限制和 Python audit guard 不能等同于容器隔离。

## What Changes

- 可选、服务器管理的 Docker 验证后端；默认 native，Docker 不可用不静默降级。
- 固定前端 check/build/test 和后端 check/test；两类可信镜像、受限输入、
  无网络执行、资源预算、受控产物导出、取消和归属清理。
- 在既有 TaskRunEvent JSON 中追加执行环境证据，并保持旧回执可读。
- 复用现有 Adapter、范围控制、队列/锁、Diff、QA 和原生浏览器需求检查。
- 开发者只读 doctor、显式镜像准备及真实容器验证；不在任务执行时安装依赖或拉镜像。

## Scope and Status

架构变更。用户已批准设计和 Native 顺序实现，随后准备 Docker 并授权真实资格验收。
2026-10-19 双镜像正式准备、本机真实Docker资格18项和最后完整原生回归2714通过/19环境跳过，
第一阶段本机验收完成，未提交/合并或启用主工作区；
精确环境及交付边界见 tasks/verification。
本期不容器化 Provider CLI、预览、数据库、API 或浏览器，不新增 Adapter、
表/列、Alembic revision、通用命令工具、网络权限或 Docker socket 挂载。
未经用户后续授权不安装环境、不提交或推送。

设计：[design.md](design.md)。
实施计划：[2026-10-18-container-validation.md](../../../docs/superpowers/plans/2026-10-18-container-validation.md)。
