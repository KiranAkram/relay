export type Countdown = {
  label: string
  overdue: boolean
}

/** "due in 12m 05s" / "overdue by 1h 03m", relative to `now`. */
export function formatCountdown(dueAt: string, now: Date): Countdown {
  const diffMs = new Date(dueAt).getTime() - now.getTime()
  const overdue = diffMs < 0
  const total = Math.floor(Math.abs(diffMs) / 1000)
  const hours = Math.floor(total / 3600)
  const minutes = Math.floor((total % 3600) / 60)
  const seconds = total % 60
  const pad = (n: number) => String(n).padStart(2, "0")

  let span: string
  if (hours > 0) {
    span = `${hours}h ${pad(minutes)}m`
  } else if (minutes > 0) {
    span = `${minutes}m ${pad(seconds)}s`
  } else {
    span = `${seconds}s`
  }
  return { label: overdue ? `overdue by ${span}` : `due in ${span}`, overdue }
}

export function formatClock(iso: string): string {
  return new Date(iso).toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
  })
}
