import type { SessionTask, TaskRun } from "@/lib/api"

function object(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" && !Array.isArray(value)
    ? value as Record<string, unknown> : {}
}

function text(value: unknown): string | null {
  return typeof value === "string" && value.length > 0 ? value : null
}

// API timestamps without an offset are UTC, not the browser's local time.
function timestamp(value: string | null) {
  if (!value) return NaN
  return Date.parse(/[zZ]|[+-]\d{2}:\d{2}$/.test(value) ? value : `${value}Z`)
}

export function overlappingRuns(tasks: SessionTask[]) {
  const runs = tasks.flatMap((task) => task.taskRuns)
  const pairs: Array<[TaskRun, TaskRun]> = []
  for (let i = 0; i < runs.length; i++) {
    for (const right of runs.slice(i + 1)) {
      const left = runs[i]
      if (left.taskId === right.taskId) continue
      const start = Math.max(timestamp(left.startedAt), timestamp(right.startedAt))
      const end = Math.min(timestamp(left.endedAt), timestamp(right.endedAt))
      if (Number.isFinite(start) && Number.isFinite(end) && start < end) pairs.push([left, right])
    }
  }
  return pairs
}

export function DagSummary({ tasks }: { tasks: SessionTask[] }) {
  const children = (id: string) => tasks.filter((task) => task.dependsOnTaskIds.includes(id))
  const hasFork = tasks.some((task) => children(task.id).length > 1) ||
    tasks.filter((task) => task.dependsOnTaskIds.length === 0).length > 1
  const hasJoin = tasks.some((task) => task.dependsOnTaskIds.length > 1)
  const overlaps = overlappingRuns(tasks)
  const label = (id: string) => tasks.find((task) => task.id === id)?.title ?? id

  return (
    <section aria-label="DAG execution summary" className="mb-4 rounded-lg border border-slate-200 bg-slate-50 p-3 text-xs">
      <h3 className="font-semibold text-slate-900">任务依赖图 · {hasFork || hasJoin ? "Fork / Join" : "串行依赖链"}</h3>
      <p className="mt-1 text-slate-600">依赖就绪不等于已并发；并行组仅为提示，执行仍受队列、锁、审批和 provider 容量约束。</p>
      <ul className="mt-2 grid gap-2">
        {tasks.map((task, index) => {
          const run = task.taskRuns.at(-1)
          const binding = object(run?.metricsJson.executionWorktree)
          const fallback = object(run?.metricsJson.executionIsolationFallback)
          const group = text(task.planJson.parallelGroup)
          const scheduler = object(task.planJson.scheduler)
          const waiting = run && !["completed", "failed", "interrupted", "cancelled"].includes(run.state)
            ? text(run.sessionQueue?.waitReason) : null
          return (
            <li key={task.id} className="rounded border border-slate-200 bg-white p-2">
              <p className="font-medium">{index + 1}. {task.title}</p>
              <p className="mt-1 text-slate-600">
                {task.dependsOnTaskIds.length > 1 ? "Join 汇合" : task.dependsOnTaskIds.length ? "依赖" : "Root 起点"}
                {task.dependsOnTaskIds.length ? `：${task.dependsOnTaskIds.map(label).join(" + ")} → 本任务` : "：无上游"}
                {children(task.id).length > 1 ? ` · Fork 分叉 → ${children(task.id).map((child) => child.title).join(" / ")}` : ""}
              </p>
              {group ? <p className="mt-1">并行组（提示）：{group}</p> : null}
              <p className="mt-1 break-all">
                {binding.mode === "isolated_write" ? `已分配隔离写分支：${text(binding.branch) ?? run?.id}`
                  : fallback.reason ? "共享工作树 · 已回退串行"
                  : task.planJson.executionMode === "isolated_write" && !run ? "请求隔离写 · 尚未分配"
                  : "默认共享执行 · 写入串行"}
              </p>
              {text(fallback.reason) ? <p className="mt-1 text-amber-800">隔离回退原因：{text(fallback.reason)}</p> : null}
              {scheduler.runnable === false && !["completed", "cancelled"].includes(task.status) && text(scheduler.reason) ? <p className="mt-1 text-amber-800">安全门禁：{text(scheduler.reason)}</p> : null}
              {waiting ? <p className="mt-1 text-slate-600">队列：{waiting}</p> : null}
              {run?.errorCode ? <p className="mt-1 text-red-700">{run.errorCode}：{run.errorMessage}</p> : null}
              {run?.metricsJson.executionRetry ? <p className="mt-1">独立分支重试 · 保留此前运行与成功分支</p> : null}
              {(task.integrationArtifacts ?? []).map((record) => (
                <details key={record.artifactId} className="mt-2 rounded border border-slate-200 p-2">
                  <summary className="cursor-pointer font-medium">
                    {record.artifactType === "conflict" ? "合并冲突记录"
                      : record.verified ? "已验证集成"
                      : record.status === "prepared" ? "集成已准备 · 等待恢复确认"
                      : "历史或未验证集成"} · {record.artifactId.slice(0, 8)}
                  </summary>
                  <p className="mt-1 break-all">Artifact：{record.artifactId} · {record.status}</p>
                  {record.mergeCommit ? <p className="break-all">合并 commit：{record.mergeCommit}</p> : null}
                  <p className="break-all">来源 Run：{record.sourceRunIds?.join(", ") || "未记录"}</p>
                  {record.reason ? <p className="text-amber-800">原因：{record.reason}</p> : null}
                  {record.changedFiles?.length ? <p>合并文件：{record.changedFiles.join(", ")}</p> : null}
                  {record.conflictingFiles?.length ? <p>冲突文件：{record.conflictingFiles.join(", ")}</p> : null}
                  {record.artifactType === "conflict" ? <p>先处理冲突，再重试此 join 的 integration；无需重跑成功分支。</p> : null}
                </details>
              ))}
            </li>
          )
        })}
      </ul>
      <p className="mt-2 text-slate-600">
        {overlaps.length ? `已记录 TaskRun 生命周期重叠：${overlaps.map(([a, b]) => `${a.id.slice(0, 8)} / ${b.id.slice(0, 8)}`).join("；")}`
          : "尚无完整时间区间可证明运行重叠。"}
        {" 生命周期时间戳不是 provider 内部执行或性能加速证明。"}
      </p>
    </section>
  )
}
