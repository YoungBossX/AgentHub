import { Disclosure } from "./disclosure"

import type { ReviewArtifact } from "@/lib/api"

const labels: Record<string, string> = {
  passed: "通过", failed: "未通过", warning: "有待处理问题",
  unknown: "证据不足", not_run: "未运行",
  recorded_passed: "记录通过", recorded_failed: "记录失败",
  expired: "已过期", timeout: "超时", cancelled: "已取消",
  not_configured: "未覆盖此需求", unavailable: "验证环境不可用",
  not_applicable: "此验证配置不需要",
}

export function qaLabel(review: ReviewArtifact): string {
  if (review.qaAssessment?.status === "expired") return "QA 证据已过期"
  if (review.qaAssessment?.status === "passed") return review.qaAssessment.acceptance === "requirement_checks_passed" ? "本版本指定需求验收通过" : "本版本已配置验证通过"
  if (review.qaAssessment?.status === "blocked") return "QA 有阻塞问题"
  if (review.qaAssessment) return "QA 待验证"
  return `${review.nativeReceipt ? "模型" : "规则"}评审${labels[review.status] ?? review.status}`
}

export function QaEvidence({ review }: { review: ReviewArtifact }) {
  const qa = review.qaAssessment
  const backend = qa?.validation?.profile === "fastapi-contract-v1"
  const execution = qa?.validation?.execution
  if (!qa) return (
    <p className="mt-3 rounded-md border border-[var(--border)] p-3 text-xs text-[var(--muted-foreground)]">
      历史报告缺少分项 QA 证据，不能据此确认功能验收通过。
    </p>
  )
  return (
    <section aria-label="QA 分项证据" className="mt-3 min-w-0 rounded-md border border-[var(--border)] p-3 text-xs">
      <p className="font-semibold">{qaLabel(review)}</p>
      {qa.validation ? <div className="mt-2 space-y-1 text-[var(--muted-foreground)]">
        <p>{!execution ? "历史验证（环境未记录）" : execution.commandsBackend === "docker" ? "Docker 固定验证"
          : execution.commandsBackend === "native" ? "原生固定验证"
          : execution.backend === "docker" ? "请求 Docker · 未运行/环境不可用" : "请求原生验证 · 未运行/环境不可用"}</p>
        <p>{backend ? "验证范围：Python 语法、FastAPI 健康检查、联系人接口、输入校验、重复拦截、CORS 与 OpenAPI" : "验证范围：类型检查、构建、构建产物冒烟测试"}</p>
        <p>版本状态：{{ current: "与当前源码一致", expired: "源码或验证策略已变化，需重新运行", unverifiable: "无法核对，需重新运行" }[qa.currentness ?? "unverifiable"]}</p>
        {qa.validation.sourceFingerprint ? <p>源码指纹：<code>{qa.validation.sourceFingerprint.slice(0, 12)}</code></p> : null}
      </div> : null}
      <dl className="mt-3 grid gap-2 sm:grid-cols-2">
        <div><dt className="text-[var(--muted-foreground)]">规则检查</dt><dd>{labels[qa.rules.status] ?? "证据不足"}</dd></div>
        <div><dt className="text-[var(--muted-foreground)]">模型评审</dt><dd>{labels[qa.model.status] ?? "证据不足"}</dd></div>
        {qa.commands.map((item) => (
          <div key={item.kind}>
            <dt className="text-[var(--muted-foreground)]">{{ check: "静态检查", test: "测试", build: "构建" }[item.kind]}</dt>
            <dd>{labels[item.status]}{item.versionBound ? " · 已绑定版本" : !item.configured && item.status !== "not_applicable" ? " · 未配置命令" : ""}</dd>
          </div>
        ))}
      </dl>
      {qa.functional && !backend ? <div className="mt-3 border-t border-[var(--border)] pt-3">
        {qa.functional.execution ? <p className="text-[var(--muted-foreground)]">原生浏览器检查</p> : null}
        <p className="font-medium">需求交互验收：{labels[qa.functional.status]}</p>
        {qa.functional.contract ? <p className="mt-1 text-[var(--muted-foreground)]">
          {({ login_page: "登录表单校验与提交", demo_heading_text: "标题文案", primary_action_button_text: "按钮文案与点击" } as Record<string, string>)[qa.functional.contract.target] ?? "指定需求"}
          {qa.functional.contract.expectedText ? ` · 期望：${qa.functional.contract.expectedText}` : ""}
        </p> : <p className="mt-1 text-[var(--muted-foreground)]">当前结构化任务未配置交互验收，构建通过不能替代需求验收。</p>}
        {qa.functional.status === "unavailable" ? <p className="mt-1">请检查已安装的浏览器与验证环境，再发起新运行。</p> : null}
        {qa.functional.checks.length > 0 ? <Disclosure className="mt-2"  summary={<>桌面与窄屏检查（{qa.functional.checks.length}）</>}>
          <ul className="mt-1 space-y-1">{qa.functional.checks.map((check) => <li key={check.id}>
            {check.id.startsWith("desktop.") ? "桌面" : "窄屏"} · {({ fields: "表单输入", empty: "空值拦截", invalid_email: "邮箱格式校验", submit: "有效输入提交", text: "文案一致", click: "按钮可点击", runtime: "运行与资源检查" } as Record<string, string>)[check.id.split(".")[1]] ?? check.id}：{labels[check.status]}
            {check.detail ? <p className="break-words text-[var(--muted-foreground)]">{check.detail}</p> : null}
          </li>)}</ul>
        </Disclosure> : null}
        <p className="mt-2 text-[var(--muted-foreground)]">仅验证上列交互，不包含真实账号认证或完整应用验收。过期报告中的分项结果为历史记录。</p>
      </div> : null}
      {qa.rules.violations.length > 0 ? (
        <p className="mt-2 break-all">范围违规：{qa.rules.violations.join("、")}</p>
      ) : null}
      {qa.rules.findings.length > 0 ? (
        <Disclosure className="mt-2"  summary={<>规则发现（{qa.rules.findings.length}）</>}>
          <ul className="mt-1 space-y-1">{qa.rules.findings.map((finding, index) => (
            <li className="break-words" key={index}>{String(finding.message ?? "")}</li>
          ))}</ul>
        </Disclosure>
      ) : null}
      {qa.commands.some((item) => item.evidence.length > 0) ? (
        <Disclosure className="mt-2"  summary={<>命令执行记录</>}>
          <ul className="mt-1 space-y-2">{qa.commands.flatMap((item) => item.evidence.map((entry) => (
            <li className="break-all" key={`${item.kind}-${entry.eventId ?? entry.artifactId}`}>
              <code>{entry.command}</code> · 退出码 {entry.exitCode}
              <p className="text-[var(--muted-foreground)]">运行 {entry.taskRunId.slice(0, 8)} · 证据 {(entry.eventId ?? entry.artifactId ?? "").slice(0, 8)}</p>
              {entry.log ? <pre className="mt-1 max-h-48 overflow-auto whitespace-pre-wrap rounded bg-[var(--muted)] p-2">{entry.log}</pre> : null}
            </li>
          )))}</ul>
        </Disclosure>
      ) : null}
      <p className="mt-3 leading-5 text-[var(--muted-foreground)]">
        {qa.model.status === "not_run" ? (qa.validation ? "尚未完成模型评审，自动验证结果见上方。" : "此报告仅完成规则审查，未完成模型评审。") : "模型结论仅供静态评审参考，不能覆盖规则失败。"}
        {qa.validation ? (backend ? "自动验证仅覆盖固定后端接口契约，不包含新增接口、真实数据库或完整前后端联调。" : qa.functional?.contract ? "自动验证范围以已配置检查和上列需求为准，不代表完整业务功能验收。" : "自动验证仅覆盖已配置检查和构建产物，不代表完整业务功能验收。") : "执行完成不等于 QA 通过。命令记录未绑定源码版本，不能证明当前代码已通过功能验收。"}
      </p>
      <p className="mt-1 text-[var(--muted-foreground)]">证据截至本报告生成时；后续改动需重新验证。</p>
    </section>
  )
}
