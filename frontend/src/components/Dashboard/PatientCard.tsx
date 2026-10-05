import { useMutation, useQueryClient } from "@tanstack/react-query"
import { Link } from "@tanstack/react-router"
import {
  AlertTriangle,
  BellRing,
  Check,
  CircleDashed,
  Clock,
  FileText,
} from "lucide-react"

import {
  type DashboardPatientPublic,
  type FlagPublic,
  FlagsService,
  type TaskPublic,
  TasksService,
} from "@/client"
import { SeverityBadge } from "@/components/Common/SeverityBadge"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import useCustomToast from "@/hooks/useCustomToast"
import { cn } from "@/lib/utils"
import { handleError } from "@/utils"
import { formatClock, formatCountdown } from "./countdown"

/** Flags whose alert time has passed and nobody has acknowledged yet. */
const firedFlags = (flags: FlagPublic[]) =>
  flags.filter((f) => f.status === "active" && f.fired_at !== null)

function useAcknowledge() {
  const queryClient = useQueryClient()
  const { showSuccessToast, showErrorToast } = useCustomToast()
  const settle = () =>
    queryClient.invalidateQueries({ queryKey: ["dashboard"] })

  const task = useMutation({
    mutationFn: (id: string) => TasksService.acknowledgeTask({ path: { id } }),
    onSuccess: () => showSuccessToast("Task acknowledged"),
    onError: handleError.bind(showErrorToast),
    onSettled: settle,
  })
  const flag = useMutation({
    mutationFn: (id: string) => FlagsService.acknowledgeFlag({ path: { id } }),
    onSuccess: () => showSuccessToast("Alert acknowledged"),
    onError: handleError.bind(showErrorToast),
    onSettled: settle,
  })
  return { task, flag }
}

interface PatientCardProps {
  row: DashboardPatientPublic
  now: Date
}

export function PatientCard({ row, now }: PatientCardProps) {
  if (row.handover_status === "no_handover") {
    return <NoHandoverCard row={row} />
  }
  return <HandedOverCard row={row} now={now} />
}

/** A census patient nobody mentioned: shown so the gap is visible, not hidden. */
function NoHandoverCard({ row }: { row: DashboardPatientPublic }) {
  const { patient } = row
  return (
    <Card className="border-dashed">
      <CardHeader>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <CardTitle className="text-base">
              {patient.bed ? `Bed ${patient.bed}` : "No bed"}
              <span className="ml-3 font-normal text-muted-foreground">
                {patient.given_name} {patient.family_name}
              </span>
            </CardTitle>
            <CardDescription className="font-mono text-xs">
              MRN {patient.mrn}
            </CardDescription>
          </div>
          <div className="flex items-center gap-2">
            <Badge variant="outline" className="text-muted-foreground">
              <CircleDashed />
              No handover this shift
            </Badge>
            <Button asChild variant="ghost" size="sm">
              <Link
                to="/patients/$patientId"
                params={{ patientId: patient.id }}
              >
                <FileText />
                View record
              </Link>
            </Button>
          </div>
        </div>
      </CardHeader>
    </Card>
  )
}

function HandedOverCard({ row, now }: PatientCardProps) {
  const { patient } = row
  const ack = useAcknowledge()
  const alerts = firedFlags(row.flags)
  const unstableAlert = alerts.find((f) => f.category === "unstable_patient")
  const hasAlert = alerts.length > 0

  return (
    <Card className={cn(hasAlert && "border-red-500/60")}>
      <CardHeader>
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <CardTitle className="text-xl">
              {patient.bed ? `Bed ${patient.bed}` : "No bed"}
              <span className="ml-3 font-normal text-muted-foreground">
                {patient.given_name} {patient.family_name}
              </span>
            </CardTitle>
            <CardDescription className="font-mono text-xs">
              MRN {patient.mrn}
              {patient.admitting_diagnosis && (
                <span className="ml-2 font-sans">
                  · {patient.admitting_diagnosis}
                </span>
              )}
            </CardDescription>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <SeverityBadge severity={row.illness_severity} />
            {unstableAlert && (
              <Button
                size="sm"
                variant="destructive"
                onClick={() => ack.flag.mutate(unstableAlert.id)}
                disabled={ack.flag.isPending}
              >
                <AlertTriangle />
                Unstable · acknowledge
              </Button>
            )}
          </div>
        </div>
      </CardHeader>

      <CardContent className="flex flex-col gap-4">
        {row.patient_summary && (
          <p className="text-sm">{row.patient_summary}</p>
        )}
        {row.situation_awareness && (
          <p className="text-sm text-muted-foreground">
            {row.situation_awareness}
          </p>
        )}
        {row.contingencies.length > 0 && (
          <ul className="text-sm list-disc pl-5 space-y-1">
            {row.contingencies.map((c, i) => (
              <li key={i}>
                <span className="font-medium">If {String(c.condition)}</span>
                {" → "}
                {String(c.action)}
              </li>
            ))}
          </ul>
        )}
        {row.tasks.length > 0 && (
          <ul className="divide-y rounded-md border">
            {row.tasks.map((task) => (
              <TaskRow
                key={task.id}
                task={task}
                flags={alerts.filter((f) => f.task_id === task.id)}
                now={now}
                onAcknowledge={() => ack.task.mutate(task.id)}
                pending={ack.task.isPending}
              />
            ))}
          </ul>
        )}
      </CardContent>

      <CardFooter className="justify-between text-xs text-muted-foreground">
        <span>
          {row.confirmed_at
            ? `Handed over at ${formatClock(row.confirmed_at)}`
            : ""}
        </span>
        <Button asChild variant="ghost" size="sm">
          <Link to="/patients/$patientId" params={{ patientId: patient.id }}>
            <FileText />
            View record
          </Link>
        </Button>
      </CardFooter>
    </Card>
  )
}

interface TaskRowProps {
  task: TaskPublic
  flags: FlagPublic[]
  now: Date
  onAcknowledge: () => void
  pending: boolean
}

function TaskRow({ task, flags, now, onAcknowledge, pending }: TaskRowProps) {
  const countdown = task.due_at ? formatCountdown(task.due_at, now) : null
  const dueSoon = flags.some((f) => f.category === "task_due_soon")
  const overdue = countdown?.overdue ?? false
  const acknowledged = task.status === "accepted"

  return (
    <li className="flex flex-wrap items-center justify-between gap-3 p-3">
      <div className="flex flex-col gap-1">
        <div className="flex items-center gap-2">
          <span className="font-medium">{task.description}</span>
          {task.priority !== "routine" && (
            <Badge variant="destructive">{task.priority}</Badge>
          )}
        </div>
        {task.due_at && countdown ? (
          <div
            className={cn(
              "flex items-center gap-1.5 text-sm",
              overdue && "text-red-600 dark:text-red-400 font-medium",
              !overdue && dueSoon && "text-amber-600 dark:text-amber-400",
              !overdue && !dueSoon && "text-muted-foreground",
            )}
          >
            {overdue || dueSoon ? (
              <BellRing className="size-4" />
            ) : (
              <Clock className="size-4" />
            )}
            <span className="font-mono tabular-nums">{countdown.label}</span>
            <span>
              · {task.due_phrase ?? formatClock(task.due_at)} (
              {formatClock(task.due_at)})
            </span>
          </div>
        ) : (
          <span className="text-sm text-muted-foreground">No time given</span>
        )}
      </div>
      {acknowledged ? (
        <span className="flex items-center gap-1 text-sm text-muted-foreground">
          <Check className="size-4" /> Acknowledged
        </span>
      ) : (
        <Button
          size="sm"
          variant={overdue || dueSoon ? "destructive" : "outline"}
          onClick={onAcknowledge}
          disabled={pending}
        >
          Acknowledge
        </Button>
      )}
    </li>
  )
}
