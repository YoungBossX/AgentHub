const MONTH_NAMES = [
  "Jan",
  "Feb",
  "Mar",
  "Apr",
  "May",
  "Jun",
  "Jul",
  "Aug",
  "Sep",
  "Oct",
  "Nov",
  "Dec",
]

const ISO_DATE_TIME_RE = /^(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):(\d{2})/

export function formatCompactDateTime(value: string): string {
  const match = value.match(ISO_DATE_TIME_RE)
  if (match) {
    const [, , month, day, hour, minute] = match
    const monthIndex = Number(month) - 1
    const monthName = MONTH_NAMES[monthIndex] ?? month
    return `${monthName} ${Number(day)}, ${hour}:${minute}`
  }

  return value
}
