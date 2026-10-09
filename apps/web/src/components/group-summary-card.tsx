"use client"

import type { GroupSummary } from "@/lib/api"

const outcomes: Record<string, string> = {
  completed: "任务组执行已完成", partial_failure: "任务组部分失败",
  failed: "任务组未完成", awaiting_action: "任务组等待继续",
}
const states: Record<string, string> = { completed: "已完成", failed: "失败", interrupted: "已中断", not_started: "未启动", waiting_approval: "等待审批" }

export function GroupSummaryCard({ summary, onRetry }: { summary: GroupSummary; onRetry?: (groupId: string) => void }) {
  const evidence = summary.evidence
  return (
    <section aria-label="任务组结果汇总" className="min-w-0 space-y-3 [overflow-wrap:anywhere]">
      <div className="flex flex-wrap items-center gap-2">
        <strong>{outcomes[evidence?.outcome ?? ""] ?? "任务组结果汇总"}</strong>
        <span className="rounded bg-[var(--primary-soft)] px-2 text-xs text-[var(--primary)]">
          {summary.source === "native_model" ? "原生协调模型" : "确定性执行记录"}
        </span>
        {!summary.current ? <span className="text-xs text-[var(--text-muted)]">历史汇总 · 已非最新结果</span> : null}
      </div>
      {summary.state === "calling" ? <p role="status">协调 Agent 正在根据执行证据汇总…</p> : null}
      {summary.state === "superseded" ? <p>输入已过期，请查看最新运行或后续汇总。</p> : null}
      {summary.state === "failed" ? <div className="rounded border border-amber-300 p-2"><p>模型汇总失败；任务运行结果未改变。</p><code className="text-xs">{summary.errorCode}</code>
        {summary.current && onRetry ? <button type="button" onClick={() => onRetry(summary.groupId)} className="ml-3 rounded border border-[var(--border)] px-2 py-1 text-xs">重试汇总</button> : null}
      </div> : null}
      {summary.state === "completed" ? <p className="whitespace-pre-wrap">{summary.interpretation?.summary ?? "未配置原生协调模型，以下为确定性执行记录。"}</p> : null}
      {summary.interpretation?.nextSteps.length ? <ul className="list-disc pl-5">{summary.interpretation.nextSteps.map((step, index) => <li key={index}>{step}</li>)}</ul> : null}
      <p className="text-xs text-[var(--text-muted)]">本次汇总未运行测试；评审通过仅表示静态评审结论。</p>
      <details className="rounded border border-[var(--border)] p-2">
        <summary className="cursor-pointer text-xs font-medium">运行与制品依据 · {evidence?.tasks.length ?? 0} 个任务</summary>
        <div className="mt-2 space-y-2">
          {evidence?.tasks.map((task) => <div key={task.taskId} className="rounded bg-[var(--surface-muted)] p-2 text-xs">
            <p className="font-medium">{task.displayName} · {task.title}</p>
            <p>{states[task.state] ?? task.state} · {task.attemptCount} 次运行 · {task.adapterType ?? "尚无适配器运行"}</p>
            {task.errorCode ? <p>{task.errorCode}</p> : null}
            {task.missingEvidence.length ? <p>缺少完成证据：{task.missingEvidence.join("、")}</p> : null}
            <p className="break-all text-[var(--text-muted)]">Task {task.taskId} · Run {task.runId ?? "无"}</p>
            {task.artifacts.map((artifact) => <p key={artifact.artifactId} className="break-all">{artifact.type} v{artifact.version} · {artifact.artifactId}{artifact.readOnlySnapshot ? " · 只读 Diff 快照（非评审修改）" : ""}</p>)}
            {task.reviews.map((review) => <p key={review.artifactId}>评审 {review.status} · {review.source === "user_edited" ? "用户编辑的评审" : review.source === "native_model" ? "原生模型评审" : "脚本参考评审"} · {review.summary}</p>)}
          </div>)}
          <p className="break-all text-xs text-[var(--text-muted)]">输入指纹 {evidence?.inputFingerprint}</p>
          {summary.agentInstruction ? <p className="break-all text-xs text-[var(--text-muted)]">提示词 SHA-256 {summary.agentInstruction.sha256}</p> : null}
          {summary.providerEvidence?.outputSha256 ? <p className="break-all text-xs text-[var(--text-muted)]">输出 SHA-256 {summary.providerEvidence.outputSha256}</p> : null}
        </div>
      </details>
    </section>
  )
}
