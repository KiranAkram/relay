import { useSuspenseQuery } from "@tanstack/react-query"
import { createFileRoute, Link } from "@tanstack/react-router"
import { Suspense, useState } from "react"

import type { PatientPublic } from "@/client"
import AddPatient from "@/components/Patients/AddPatient"
import { getCensusQueryOptions } from "@/components/Patients/CensusPicker"
import { PatientActionsMenu } from "@/components/Patients/PatientActionsMenu"
import PendingTable from "@/components/Pending/PendingTable"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import { Label } from "@/components/ui/label"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import useAuth from "@/hooks/useAuth"

export const Route = createFileRoute("/_layout/patients/")({
  component: Patients,
  head: () => ({
    meta: [{ title: "Patients - Relay" }],
  }),
})

const isAdmin = (
  user: { role?: string; is_superuser?: boolean } | null | undefined,
) => user?.role === "admin" || user?.is_superuser === true

function CensusTable({ includeDischarged }: { includeDischarged: boolean }) {
  const { data } = useSuspenseQuery(getCensusQueryOptions(includeDischarged))
  const { user } = useAuth()
  const admin = isAdmin(user)

  return (
    <Table>
      <TableHeader>
        <TableRow className="hover:bg-transparent">
          <TableHead>Bed</TableHead>
          <TableHead>Patient</TableHead>
          <TableHead>MRN</TableHead>
          <TableHead>Diagnosis</TableHead>
          <TableHead>Attending</TableHead>
          <TableHead>
            <span className="sr-only">Actions</span>
          </TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {data.data.map((p: PatientPublic) => (
          <TableRow key={p.id}>
            <TableCell className="font-medium">
              {p.bed ?? "—"}
              {!p.active && (
                <Badge variant="outline" className="ml-2">
                  Discharged
                </Badge>
              )}
            </TableCell>
            <TableCell>
              <Link
                to="/patients/$patientId"
                params={{ patientId: p.id }}
                className="hover:underline"
              >
                {p.family_name}, {p.given_name}
              </Link>
            </TableCell>
            <TableCell className="font-mono text-xs">{p.mrn}</TableCell>
            <TableCell className="max-w-xs truncate text-muted-foreground">
              {p.admitting_diagnosis ?? "—"}
            </TableCell>
            <TableCell className="text-muted-foreground">
              {p.attending_name ?? "—"}
            </TableCell>
            <TableCell>
              <div className="flex justify-end gap-1">
                <Button asChild variant="outline" size="sm">
                  <Link to="/patients/$patientId" params={{ patientId: p.id }}>
                    Record
                  </Link>
                </Button>
                {admin && <PatientActionsMenu patient={p} />}
              </div>
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  )
}

function Patients() {
  const { user } = useAuth()
  const [includeDischarged, setIncludeDischarged] = useState(false)

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Patients</h1>
          <p className="text-muted-foreground">The ward census, by bed</p>
        </div>
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2">
            <Checkbox
              id="include-discharged"
              checked={includeDischarged}
              onCheckedChange={(v) => setIncludeDischarged(v === true)}
            />
            <Label htmlFor="include-discharged" className="font-normal">
              Show discharged
            </Label>
          </div>
          {isAdmin(user) && <AddPatient />}
        </div>
      </div>
      <Suspense fallback={<PendingTable />}>
        <CensusTable includeDischarged={includeDischarged} />
      </Suspense>
    </div>
  )
}
