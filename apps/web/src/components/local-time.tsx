"use client"

import { useSyncExternalStore } from "react"
import { formatCompactDateTime, parseApiTimestamp, timestampDetails } from "@/lib/date-format"

const subscribe = () => () => {}
const serverTimeZone = () => null
function browserTimeZone() {
  try { return Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC" }
  catch { return "UTC" }
}

export function useLocalTimeZone(): string | null {
  return useSyncExternalStore(subscribe, browserTimeZone, serverTimeZone)
}

export function TimeZoneLabel({ className }: { className?: string }) {
  const zone = useLocalTimeZone()
  return <span className={className} title={zone ? `时间按浏览器时区 ${zone} 显示；悬停时间可查看 UTC 和原始值。` : "客户端时区尚未就绪，暂按 UTC 显示。"}>{zone ? "本地时间" : "时间"} · {zone ?? "UTC"}</span>
}

export function LocalTime({ value, emptyLabel = "暂无时间", className }: { value: string | null; emptyLabel?: string; className?: string }) {
  const zone = useLocalTimeZone() ?? "UTC"
  const date = parseApiTimestamp(value)
  if (!value) return <span className={className}>{emptyLabel}</span>
  if (!date) return <span className={className} title={timestampDetails(value)}>{value}</span>
  return <time className={className} dateTime={date.toISOString()} data-time-zone={zone} title={timestampDetails(value, zone)}>{formatCompactDateTime(value, zone)}</time>
}
