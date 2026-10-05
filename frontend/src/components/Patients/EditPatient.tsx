import { zodResolver } from "@hookform/resolvers/zod"
import { useMutation, useQueryClient } from "@tanstack/react-query"
import { Pencil } from "lucide-react"
import { useState } from "react"
import { useForm } from "react-hook-form"

import { type PatientPublic, PatientsService } from "@/client"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { DropdownMenuItem } from "@/components/ui/dropdown-menu"
import { Form } from "@/components/ui/form"
import { LoadingButton } from "@/components/ui/loading-button"
import useCustomToast from "@/hooks/useCustomToast"
import { handleError } from "@/utils"
import {
  type PatientFormData,
  PatientFormFields,
  patientSchema,
  toApi,
} from "./PatientFormFields"

interface EditPatientProps {
  patient: PatientPublic
  onSuccess: () => void
}

const EditPatient = ({ patient, onSuccess }: EditPatientProps) => {
  const [isOpen, setIsOpen] = useState(false)
  const queryClient = useQueryClient()
  const { showSuccessToast, showErrorToast } = useCustomToast()

  const form = useForm<PatientFormData>({
    resolver: zodResolver(patientSchema),
    mode: "onBlur",
    defaultValues: {
      mrn: patient.mrn,
      family_name: patient.family_name,
      given_name: patient.given_name,
      birth_date: patient.birth_date ?? "",
      sex: patient.sex ?? "unknown",
      bed: patient.bed ?? "",
      unit: patient.unit ?? "",
      admitting_diagnosis: patient.admitting_diagnosis ?? "",
      attending_name: patient.attending_name ?? "",
    },
  })

  const mutation = useMutation({
    mutationFn: (data: PatientFormData) =>
      PatientsService.updatePatient({
        path: { id: patient.id },
        body: toApi(data),
      }),
    onSuccess: () => {
      showSuccessToast("Patient updated")
      setIsOpen(false)
      onSuccess()
    },
    onError: handleError.bind(showErrorToast),
    onSettled: () => queryClient.invalidateQueries({ queryKey: ["patients"] }),
  })

  return (
    <Dialog open={isOpen} onOpenChange={setIsOpen}>
      <DropdownMenuItem
        onSelect={(e) => {
          e.preventDefault()
          setIsOpen(true)
        }}
      >
        <Pencil />
        Edit
      </DropdownMenuItem>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>Edit patient</DialogTitle>
          <DialogDescription>
            Changes are recorded in the audit log.
          </DialogDescription>
        </DialogHeader>
        <Form {...form}>
          <form onSubmit={form.handleSubmit((d) => mutation.mutate(d))}>
            <PatientFormFields form={form} />
            <DialogFooter>
              <DialogClose asChild>
                <Button variant="outline" disabled={mutation.isPending}>
                  Cancel
                </Button>
              </DialogClose>
              <LoadingButton type="submit" loading={mutation.isPending}>
                Save
              </LoadingButton>
            </DialogFooter>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  )
}

export default EditPatient
