const ISO_DATE_TIME_RE = /^(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):(\d{2})/

export function formatCompactDateTime(value: string): string {
  const match = value.match(ISO_DATE_TIME_RE)
  if (match) {
    const [, , month, day, hour, minute] = match
    return `${Number(month)}月${Number(day)}日 ${hour}:${minute}`
  }

  return value
}
