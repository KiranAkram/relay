import { useSuspenseQuery } from "@tanstack/react-query"
import { createFileRoute, Link } from "@tanstack/react-router"
import { Check, FileAudio } from "lucide-react"
import { Suspense } from "react"

import {
  type PatientRecordCardPublic,
  PatientsService,
  type TaskPublic,
} from "@/client"
import { SeverityBadge } from "@/components/Common/SeverityBadge"
import PendingDashboard from "@/components/Pending/PendingDashboard"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"

export const Route = createFileRoute("/_layout/patients/$patientId")({
  component: PatientRecordPage,
  head: () => ({
    meta: [{ title: "Patient record - Relay" }],
  }),
})

const when = (iso: string) =>
  new Date(iso).toLocaleString([], { dateStyle: "medium", timeStyle: "short" })

function RecordContent({ patientId }: { patientId: string }) {
  const { data } = useSuspenseQuery({
    queryKey: ["patients", patientId, "record"],
    queryFn: async () =>
      (await PatientsService.readPatientRecord({ path: { id: patientId } }))
        .data,
  })
  const { patient } = data
  const openTasks = data.tasks.filter(
    (t) => t.status === "requested" || t.status === "accepted",
  )

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">
            {patient.family_name}, {patient.given_name}
            {!patient.active && (
              <Badge variant="outline" className="ml-3 align-middle">
                Discharged
              </Badge>
            )}
          </h1>
          <p className="text-muted-foreground">
            {patient.bed ? `Bed ${patient.bed} · ` : ""}MRN {patient.mrn}
            {patient.birth_date ? ` · born ${patient.birth_date}` : ""}
            {patient.admitting_diagnosis
              ? ` · ${patient.admitting_diagnosis}`
              : ""}
            {patient.attending_name ? ` · ${patient.attending_name}` : ""}
          </p>
        </div>
        <Button asChild variant="outline">
          <Link to="/patients">Back to census</Link>
        </Button>
      </div>

      <section className="grid gap-4 md:grid-cols-3">
        <Stat label="Handovers" value={data.cards.length} />
        <Stat label="Open tasks" value={openTasks.length} />
        <Stat
          label="Alerts fired"
          value={data.flags.filter((f) => f.fired_at).length}
        />
      </section>

      <section className="flex flex-col gap-4">
        <h2 className="text-lg font-semibold">Handover history</h2>
        {data.cards.length === 0 && (
          <p className="text-muted-foreground">
            No confirmed handover mentions this patient yet.
          </p>
        )}
        {data.cards.map((entry) => (
          <HistoryCard key={entry.card.id} entry={entry} tasks={data.tasks} />
        ))}
      </section>

      {data.documents.length > 0 && (
        <section className="flex flex-col gap-2">
          <h2 className="text-lg font-semibold">Recordings</h2>
          <ul className="divide-y rounded-md border text-sm">
            {data.documents.map((d) => (
              <li key={d.id} className="flex items-center gap-3 p-3">
                <FileAudio className="size-4 text-muted-foreground" />
                <span>{when(d.authored_at)}</span>
                <span className="text-muted-foreground">
                  {d.type} · {d.content_type}
                  {d.size_bytes
                    ? ` · ${Math.round(d.size_bytes / 1024)} kB`
                    : ""}
                </span>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  )
}

function Stat({ label, value }: { label: string; value: number }) {
  return (
    <Card>
      <CardHeader>
        <CardDescription>{label}</CardDescription>
        <CardTitle className="text-3xl tabular-nums">{value}</CardTitle>
      </CardHeader>
    </Card>
  )
}

function HistoryCard({
  entry,
  tasks,
}: {
  entry: PatientRecordCardPublic
  tasks: TaskPublic[]
}) {
  const { card } = entry
  const cardTasks = tasks.filter((t) => t.handover_patient_id === card.id)

  return (
    <Card>
      <CardHeader>
        <div className="flex flex-wrap items-center justify-between gap-2">
          <CardTitle className="text-base">
            {when(entry.confirmed_at)}
            {entry.shift_label ? ` · ${entry.shift_label}` : ""}
          </CardTitle>
          <div className="flex items-center gap-2">
            <SeverityBadge severity={card.illness_severity} />
            <Button asChild variant="ghost" size="sm">
              <Link
                to="/handovers/$handoverId"
                params={{ handoverId: entry.handover_id }}
              >
                Open handover
              </Link>
            </Button>
          </div>
        </div>
        <CardDescription>Said as “{card.mention_verbatim}”</CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-3 text-sm">
        {card.patient_summary && <p>{card.patient_summary}</p>}
        {card.situation_awareness && (
          <p className="text-muted-foreground">{card.situation_awareness}</p>
        )}
        {card.contingencies.length > 0 && (
          <ul className="list-disc pl-5">
            {card.contingencies.map((c, i) => (
              <li key={i}>
                If {String(c.condition)} → {String(c.action)}
              </li>
            ))}
          </ul>
        )}
        {cardTasks.length > 0 && (
          <ul className="divide-y rounded-md border">
            {cardTasks.map((t) => (
              <li
                key={t.id}
                className="flex flex-wrap items-center justify-between gap-2 p-2"
              >
                <span>
                  {t.description}
                  {t.due_at && (
                    <span className="ml-2 text-muted-foreground">
                      due {when(t.due_at)}
                    </span>
                  )}
                  {t.cancel_reason && (
                    <span className="ml-2 italic text-muted-foreground">
                      — cancelled: {t.cancel_reason}
                    </span>
                  )}
                </span>
                <Badge variant="outline" className="capitalize">
                  {t.status === "accepted" && <Check />}
                  {t.status}
                </Badge>
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  )
}

function PatientRecordPage() {
  const { patientId } = Route.useParams()
  return (
    <Suspense fallback={<PendingDashboard />}>
      <RecordContent patientId={patientId} />
    </Suspense>
  )
}
