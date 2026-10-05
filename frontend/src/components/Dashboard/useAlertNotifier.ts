import { useEffect, useRef } from "react"
import { toast } from "sonner"

import type { DashboardPublic, FlagCategory } from "@/client"

const LABELS: Record<FlagCategory, string> = {
  task_due_soon: "due soon",
  task_overdue: "overdue",
  unstable_patient: "unstable",
}

/** Short beep without an audio asset. Silent if the browser blocks audio. */
function beep() {
  try {
    const ctx = new AudioContext()
    const osc = ctx.createOscillator()
    const gain = ctx.createGain()
    osc.frequency.value = 880
    gain.gain.value = 0.15
    osc.connect(gain).connect(ctx.destination)
    osc.start()
    osc.stop(ctx.currentTime + 0.25)
    osc.onended = () => ctx.close()
  } catch {
    // no audio: the toast is still shown
  }
}

/**
 * Flags fire on the server when the dashboard is read. This notices flags
 * that fired since the previous read and announces them, so an alert is not
 * just a badge somebody has to scroll to.
 */
export function useAlertNotifier(data: DashboardPublic) {
  const seen = useRef<Set<string> | null>(null)

  useEffect(() => {
    const fired = new Map<string, string>()
    for (const row of data.patients) {
      for (const flag of row.flags) {
        if (flag.status === "active" && flag.fired_at) {
          const task = row.tasks.find((t) => t.id === flag.task_id)
          const where = row.patient.bed
            ? `Bed ${row.patient.bed}`
            : `${row.patient.given_name} ${row.patient.family_name}`
          fired.set(
            flag.id,
            task
              ? `${where}: ${task.description} is ${LABELS[flag.category]}`
              : `${where} is ${LABELS[flag.category]}`,
          )
        }
      }
    }
    if (seen.current === null) {
      // First load: everything already fired is on screen; do not re-announce.
      seen.current = new Set(fired.keys())
      return
    }
    const fresh = [...fired].filter(([id]) => !seen.current?.has(id))
    for (const [, message] of fresh) {
      toast.error("Alert", { description: message, duration: 15_000 })
    }
    if (fresh.length > 0) beep()
    seen.current = new Set(fired.keys())
  }, [data])
}
