import { useMutation, useQueryClient } from "@tanstack/react-query"
import { createFileRoute, useNavigate } from "@tanstack/react-router"
import { Mic, RotateCcw, Square, Upload } from "lucide-react"
import { useState } from "react"

import { HandoversService } from "@/client"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { LoadingButton } from "@/components/ui/loading-button"
import useCustomToast from "@/hooks/useCustomToast"
import { useRecorder } from "@/hooks/useRecorder"
import { handleError } from "@/utils"

export const Route = createFileRoute("/_layout/handovers/new")({
  component: NewHandover,
  head: () => ({
    meta: [{ title: "New handover - Relay" }],
  }),
})

const AUDIO_ACCEPT = ".mp3,.mp4,.mpeg,.mpga,.m4a,.wav,.webm"
const MAX_BYTES = 25 * 1024 * 1024

const mmss = (s: number) =>
  `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`

/** Value for <input type="datetime-local">: local time, no seconds. */
function toLocalInput(d: Date): string {
  const copy = new Date(d)
  copy.setSeconds(0, 0)
  return new Date(copy.getTime() - copy.getTimezoneOffset() * 60_000)
    .toISOString()
    .slice(0, 16)
}

function NewHandover() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { showErrorToast } = useCustomToast()
  const recorder = useRecorder()
  const [shiftLabel, setShiftLabel] = useState("")

  const upload = useMutation({
    mutationFn: (args: { file: Blob; filename: string; recordedAt: Date }) =>
      HandoversService.uploadHandover({
        body: {
          file: new File([args.file], args.filename, { type: args.file.type }),
          recorded_at: args.recordedAt.toISOString(),
          shift_label: shiftLabel.trim() || null,
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
          Speak the handover for every patient in one go. Say the bed or the
          name, how they are, what needs doing and by when.
        </p>
      </div>

      <div className="grid gap-6 lg:grid-cols-[1fr_360px]">
        <Card>
          <CardHeader>
            <CardTitle>Record</CardTitle>
            <CardDescription>
              {recorder.state === "recording"
                ? "Recording. Press Stop when you have covered every patient."
                : recorder.state === "done"
                  ? "Listen back, then send it for processing."
                  : "Press Record and start with the first patient."}
            </CardDescription>
          </CardHeader>
          <CardContent className="flex flex-col items-center gap-6 py-8">
            <div className="font-mono text-5xl tabular-nums">
              {mmss(
                recorder.state === "done" && recorder.recording
                  ? recorder.recording.durationS
                  : recorder.elapsedS,
              )}
            </div>

            {recorder.state === "idle" || recorder.state === "requesting" ? (
              <Button
                size="lg"
                className="h-14 px-8 text-base"
                onClick={() => recorder.start()}
                disabled={
                  !recorder.supported || recorder.state === "requesting"
                }
              >
                <Mic className="size-5" />
                Record
              </Button>
            ) : recorder.state === "recording" ? (
              <Button
                size="lg"
                variant="destructive"
                className="h-14 px-8 text-base"
                onClick={recorder.stop}
              >
                <Square className="size-5" />
                Stop
              </Button>
            ) : (
              recorder.recording && (
                <div className="flex w-full flex-col items-center gap-4">
                  {/* biome-ignore lint/a11y/useMediaCaption: a dictated recording has no captions */}
                  <audio
                    controls
                    src={URL.createObjectURL(recorder.recording.blob)}
                    className="w-full max-w-md"
                  />
                  <div className="flex gap-3">
                    <Button variant="outline" onClick={recorder.reset}>
                      <RotateCcw />
                      Record again
                    </Button>
                    <LoadingButton
                      size="lg"
                      loading={upload.isPending}
                      onClick={() =>
                        recorder.recording &&
                        upload.mutate({
                          file: recorder.recording.blob,
                          filename: recorder.recording.filename,
                          recordedAt: recorder.recording.startedAt,
                        })
                      }
                    >
                      Send for processing
                    </LoadingButton>
                  </div>
                </div>
              )
            )}

            {recorder.error && (
              <p className="text-sm text-destructive">{recorder.error}</p>
            )}
            {recorder.state === "done" && recorder.recording && (
              <p className="text-xs text-muted-foreground">
                Recorded at {recorder.recording.startedAt.toLocaleTimeString()}.
                Due times like “in an hour” count from this moment.
              </p>
            )}
          </CardContent>
        </Card>

        <div className="flex flex-col gap-6">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Shift</CardTitle>
            </CardHeader>
            <CardContent>
              <Label htmlFor="shift-label" className="sr-only">
                Shift label
              </Label>
              <Input
                id="shift-label"
                placeholder="e.g. Night"
                value={shiftLabel}
                onChange={(e) => setShiftLabel(e.target.value)}
                maxLength={64}
              />
            </CardContent>
          </Card>
          <FileUpload
            disabled={upload.isPending || recorder.state === "recording"}
            onSubmit={(file, recordedAt) =>
              upload.mutate({ file, filename: file.name, recordedAt })
            }
          />
        </div>
      </div>
    </div>
  )
}

/** Fallback for testing with an existing recording. */
function FileUpload({
  disabled,
  onSubmit,
}: {
  disabled: boolean
  onSubmit: (file: File, recordedAt: Date) => void
}) {
  const [file, setFile] = useState<File | null>(null)
  const [recordedAt, setRecordedAt] = useState(() => toLocalInput(new Date()))
  const [problem, setProblem] = useState<string | null>(null)

  const choose = (f: File | undefined) => {
    setProblem(null)
    if (!f) return setFile(null)
    if (f.size === 0) return setProblem("That file is empty.")
    if (f.size > MAX_BYTES)
      return setProblem("Recording must be 25 MB or smaller.")
    setFile(f)
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Or upload a file</CardTitle>
        <CardDescription>
          m4a, mp3, mp4, wav or webm, up to 25 MB
        </CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-3">
        <Input
          type="file"
          accept={AUDIO_ACCEPT}
          onChange={(e) => choose(e.target.files?.[0])}
        />
        <div className="flex flex-col gap-1">
          <Label
            htmlFor="recorded-at"
            className="text-xs text-muted-foreground"
          >
            When was it recorded?
          </Label>
          <Input
            id="recorded-at"
            type="datetime-local"
            value={recordedAt}
            onChange={(e) => setRecordedAt(e.target.value)}
          />
        </div>
        {problem && <p className="text-sm text-destructive">{problem}</p>}
        <Button
          variant="outline"
          disabled={disabled || !file || !recordedAt}
          onClick={() => file && onSubmit(file, new Date(recordedAt))}
        >
          <Upload />
          Upload and process
        </Button>
      </CardContent>
    </Card>
  )
}
