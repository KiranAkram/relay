import { useQuery } from "@tanstack/react-query"

import { PatientsService } from "@/client"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"

export function getCensusQueryOptions(includeDischarged = false) {
  return {
    queryFn: async () =>
      (
        await PatientsService.readPatients({
          query: { include_discharged: includeDischarged },
        })
      ).data,
    queryKey: ["patients", { includeDischarged }],
  }
}

interface CensusPickerProps {
  onPick: (patientId: string) => void
  disabled?: boolean
}

/** Dropdown of the active census, for assigning a card by hand. */
export function CensusPicker({ onPick, disabled }: CensusPickerProps) {
  const { data, isPending } = useQuery(getCensusQueryOptions())

  return (
    <Select onValueChange={onPick} disabled={disabled || isPending}>
      <SelectTrigger className="w-full md:w-96">
        <SelectValue
          placeholder={isPending ? "Loading census…" : "Choose a patient"}
        />
      </SelectTrigger>
      <SelectContent>
        {data?.data.map((p) => (
          <SelectItem key={p.id} value={p.id}>
            {p.bed ? `Bed ${p.bed} · ` : ""}
            {p.given_name} {p.family_name} · MRN {p.mrn}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  )
}
