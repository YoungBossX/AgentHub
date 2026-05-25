export function statusClasses(status: string) {
  if (status === "completed") {
    return {
      badge: "bg-green-50 text-green-700 border-green-200",
      border: "border-l-green-600",
    }
  }
  if (status === "failed" || status === "blocked") {
    return {
      badge: "bg-red-50 text-red-700 border-red-200",
      border: "border-l-red-600",
    }
  }
  if (
    status === "waiting_approval" ||
    status === "waiting_dependency" ||
    status === "waiting_target_lock"
  ) {
    return {
      badge: "bg-amber-50 text-amber-700 border-amber-200",
      border: "border-l-amber-500",
    }
  }
  if (status === "retryable" || status === "fallback_available") {
    return {
      badge: "bg-purple-50 text-purple-700 border-purple-200",
      border: "border-l-purple-500",
    }
  }
  if (status === "running" || status === "active") {
    return {
      badge: "bg-blue-50 text-blue-700 border-blue-200",
      border: "border-l-blue-600",
    }
  }

  return {
    badge: "bg-slate-50 text-slate-600 border-slate-200",
    border: "border-l-slate-300",
  }
}

export function statusLabel(status: string) {
  const labels: Record<string, string> = {
    active: "运行中",
    applying_changes: "应用变更",
    collecting_diff: "收集 Diff",
    completed: "已完成",
    created: "已创建",
    failed: "失败",
    fallback_available: "可兜底",
    interrupted: "已中断",
    pending: "待处理",
    queued: "排队中",
    retryable: "可重试",
    running: "运行中",
    starting_preview: "启动预览",
    streaming: "执行中",
    waiting_approval: "等待审批",
    waiting_dependency: "等待依赖",
    waiting_target_lock: "等待目标锁",
    blocked: "已阻塞",
  }
  return labels[status] ?? status
}

export function healthLabel(health: string) {
  const labels: Record<string, string> = {
    healthy: "健康",
    pending: "等待中",
    starting: "启动中",
    stopped: "已停止",
    unhealthy: "异常",
  }
  return labels[health] ?? health
}

export function reviewLabel(status: string) {
  const labels: Record<string, string> = {
    failed: "未通过",
    passed: "通过",
    warning: "警告",
  }
  return labels[status] ?? status
}
