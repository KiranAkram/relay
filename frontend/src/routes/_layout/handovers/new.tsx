import { zodResolver } from "@hookform/resolvers/zod"
import { useMutation, useQueryClient } from "@tanstack/react-query"
import { createFileRoute, useNavigate } from "@tanstack/react-router"
import { useForm } from "react-hook-form"
import { z } from "zod"

import { HandoversService } from "@/client"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import {
  Form,
  FormControl,
  FormDescription,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form"
import { Input } from "@/components/ui/input"
import { LoadingButton } from "@/components/ui/loading-button"
import useCustomToast from "@/hooks/useCustomToast"
import { handleError } from "@/utils"

export const Route = createFileRoute("/_layout/handovers/new")({
  component: NewHandover,
  head: () => ({
    meta: [{ title: "New handover - Relay" }],
  }),
})

const AUDIO_ACCEPT = ".mp3,.mp4,.mpeg,.mpga,.m4a,.wav,.webm"
const MAX_BYTES = 25 * 1024 * 1024

const formSchema = z.object({
  file: z
    .instanceof(File, { message: "Choose a recording" })
    .refine((f) => f.size > 0, "File is empty")
    .refine((f) => f.size <= MAX_BYTES, "Recording must be 25 MB or smaller"),
  recorded_at: z.string().min(1, "Recording time is required"),
  shift_label: z.string().max(64).optional(),
})

type FormData = z.infer<typeof formSchema>

/** Value for <input type="datetime-local">: local time, no seconds. */
function localNow(): string {
  const d = new Date()
  d.setSeconds(0, 0)
  const offsetMs = d.getTimezoneOffset() * 60_000
  return new Date(d.getTime() - offsetMs).toISOString().slice(0, 16)
}

function NewHandover() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { showErrorToast } = useCustomToast()

  const form = useForm<FormData>({
    resolver: zodResolver(formSchema),
    mode: "onBlur",
    defaultValues: { recorded_at: localNow(), shift_label: "" },
  })

  const mutation = useMutation({
    mutationFn: (data: FormData) =>
      HandoversService.uploadHandover({
        body: {
          file: data.file,
          // datetime-local is in the browser's zone; send it as an absolute time.
          recorded_at: new Date(data.recorded_at).toISOString(),
          shift_label: data.shift_label || null,
        },
      }),
    onSuccess: (response) => {
      queryClient.invalidateQueries({ queryKey: ["handovers"] })
      navigate({
        to: "/handovers/$handoverId",
        params: { handoverId: response.data.id },
      })
    },
    onError: handleError.bind(showErrorToast),
  })

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">New handover</h1>
        <p className="text-muted-foreground">
          Upload the recording; it is transcribed and split into one card per
          patient for you to review.
        </p>
      </div>
      <Card className="max-w-xl">
        <CardHeader>
          <CardTitle>Recording</CardTitle>
          <CardDescription>
            One recording can cover several patients.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Form {...form}>
            <form
              onSubmit={form.handleSubmit((data) => mutation.mutate(data))}
              className="flex flex-col gap-5"
            >
              <FormField
                control={form.control}
                name="file"
                render={({ field: { onChange, name, onBlur, ref } }) => (
                  <FormItem>
                    <FormLabel>
                      Audio file <span className="text-destructive">*</span>
                    </FormLabel>
                    <FormControl>
                      <Input
                        type="file"
                        accept={AUDIO_ACCEPT}
                        name={name}
                        onBlur={onBlur}
                        ref={ref}
                        onChange={(e) => onChange(e.target.files?.[0])}
                      />
                    </FormControl>
                    <FormDescription>
                      m4a, mp3, mp4, wav or webm, up to 25 MB
                    </FormDescription>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name="recorded_at"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>
                      Recorded at <span className="text-destructive">*</span>
                    </FormLabel>
                    <FormControl>
                      <Input type="datetime-local" {...field} />
                    </FormControl>
                    <FormDescription>
                      Times like "in an hour" are counted from this moment.
                    </FormDescription>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name="shift_label"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Shift</FormLabel>
                    <FormControl>
                      <Input placeholder="e.g. Night" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <LoadingButton
                type="submit"
                loading={mutation.isPending}
                className="self-end"
              >
                Upload and process
              </LoadingButton>
            </form>
          </Form>
        </CardContent>
      </Card>
    </div>
  )
}
