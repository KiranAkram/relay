import { EllipsisVertical } from "lucide-react"
import { useState } from "react"

import type { PatientPublic } from "@/client"
import { Button } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import DischargePatient from "./DischargePatient"
import EditPatient from "./EditPatient"

export const PatientActionsMenu = ({ patient }: { patient: PatientPublic }) => {
  const [open, setOpen] = useState(false)

  return (
    <DropdownMenu open={open} onOpenChange={setOpen}>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" size="icon" aria-label="Patient actions">
          <EllipsisVertical />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        <EditPatient patient={patient} onSuccess={() => setOpen(false)} />
        {patient.active && (
          <DischargePatient
            patient={patient}
            onSuccess={() => setOpen(false)}
          />
        )}
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
