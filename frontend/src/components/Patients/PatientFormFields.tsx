import type { UseFormReturn } from "react-hook-form"
import { z } from "zod"

import type { Sex } from "@/client"
import {
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form"
import { Input } from "@/components/ui/input"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"

export const patientSchema = z.object({
  mrn: z.string().min(1, "MRN is required").max(32),
  family_name: z.string().min(1, "Family name is required").max(128),
  given_name: z.string().min(1, "Given name is required").max(128),
  birth_date: z.string().optional(),
  sex: z.enum(["male", "female", "other", "unknown"]),
  bed: z.string().max(32).optional(),
  unit: z.string().max(64).optional(),
  admitting_diagnosis: z.string().max(512).optional(),
  attending_name: z.string().max(128).optional(),
})

export type PatientFormData = z.infer<typeof patientSchema>

const SEXES: { value: Sex; label: string }[] = [
  { value: "unknown", label: "Unknown" },
  { value: "female", label: "Female" },
  { value: "male", label: "Male" },
  { value: "other", label: "Other" },
]

/** Empty strings from the form become nulls for the API. */
export const toApi = (data: PatientFormData) => ({
  ...data,
  birth_date: data.birth_date || null,
  bed: data.bed || null,
  unit: data.unit || null,
  admitting_diagnosis: data.admitting_diagnosis || null,
  attending_name: data.attending_name || null,
})

export function PatientFormFields({
  form,
}: {
  form: UseFormReturn<PatientFormData>
}) {
  const text = (
    name: keyof PatientFormData,
    label: string,
    required = false,
    type = "text",
  ) => (
    <FormField
      control={form.control}
      name={name}
      render={({ field }) => (
        <FormItem>
          <FormLabel>
            {label} {required && <span className="text-destructive">*</span>}
          </FormLabel>
          <FormControl>
            <Input type={type} {...field} required={required} />
          </FormControl>
          <FormMessage />
        </FormItem>
      )}
    />
  )

  return (
    <div className="grid gap-4 py-4 sm:grid-cols-2">
      {text("mrn", "MRN", true)}
      {text("bed", "Bed")}
      {text("family_name", "Family name", true)}
      {text("given_name", "Given name", true)}
      {text("birth_date", "Date of birth", false, "date")}
      <FormField
        control={form.control}
        name="sex"
        render={({ field }) => (
          <FormItem>
            <FormLabel>Sex</FormLabel>
            <Select value={field.value} onValueChange={field.onChange}>
              <FormControl>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
              </FormControl>
              <SelectContent>
                {SEXES.map((s) => (
                  <SelectItem key={s.value} value={s.value}>
                    {s.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <FormMessage />
          </FormItem>
        )}
      />
      {text("unit", "Unit")}
      {text("attending_name", "Attending")}
      <div className="sm:col-span-2">
        {text("admitting_diagnosis", "Admitting diagnosis")}
      </div>
    </div>
  )
}
