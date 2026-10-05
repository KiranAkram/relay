import { useCallback, useEffect, useRef, useState } from "react"

export type RecorderState = "idle" | "requesting" | "recording" | "done"

export interface Recording {
  blob: Blob
  filename: string
  startedAt: Date
  durationS: number
}

/** Pick a container the browser can produce and the backend accepts. */
function pickMimeType(): { mime: string; ext: string } | null {
  const options: [string, string][] = [
    ["audio/webm;codecs=opus", "webm"],
    ["audio/webm", "webm"],
    ["audio/mp4", "mp4"],
  ]
  for (const [mime, ext] of options) {
    if (MediaRecorder.isTypeSupported(mime)) return { mime, ext }
  }
  return null
}

function clearTimer(ref: { current: number | null }) {
  if (ref.current !== null) {
    window.clearInterval(ref.current)
    ref.current = null
  }
}

/** Microphone recording through the browser's MediaRecorder. */
export function useRecorder() {
  const [state, setState] = useState<RecorderState>("idle")
  const [error, setError] = useState<string | null>(null)
  const [elapsedS, setElapsedS] = useState(0)
  const [recording, setRecording] = useState<Recording | null>(null)
  const recorderRef = useRef<MediaRecorder | null>(null)
  const chunksRef = useRef<Blob[]>([])
  const startedAtRef = useRef<Date | null>(null)
  const timerRef = useRef<number | null>(null)

  const supported =
    typeof navigator !== "undefined" &&
    !!navigator.mediaDevices?.getUserMedia &&
    typeof MediaRecorder !== "undefined"

  const start = useCallback(async () => {
    setError(null)
    setRecording(null)
    const picked = pickMimeType()
    if (!supported || !picked) {
      setError("This browser cannot record audio. Upload a file instead.")
      return
    }
    setState("requesting")
    let stream: MediaStream
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true })
    } catch {
      setState("idle")
      setError(
        "Microphone access was refused. Allow it in the browser, or upload a file.",
      )
      return
    }
    const recorder = new MediaRecorder(stream, { mimeType: picked.mime })
    chunksRef.current = []
    recorder.ondataavailable = (e) => {
      if (e.data.size > 0) chunksRef.current.push(e.data)
    }
    recorder.onstop = () => {
      for (const track of stream.getTracks()) track.stop()
      clearTimer(timerRef)
      const startedAt = startedAtRef.current ?? new Date()
      const blob = new Blob(chunksRef.current, { type: picked.mime })
      setRecording({
        blob,
        filename: `handover.${picked.ext}`,
        startedAt,
        durationS: Math.round((Date.now() - startedAt.getTime()) / 1000),
      })
      setState("done")
    }
    recorderRef.current = recorder
    startedAtRef.current = new Date()
    setElapsedS(0)
    recorder.start(1000)
    setState("recording")
    timerRef.current = window.setInterval(() => {
      setElapsedS(
        Math.round(
          (Date.now() - (startedAtRef.current?.getTime() ?? 0)) / 1000,
        ),
      )
    }, 500)
  }, [supported])

  const stop = useCallback(() => {
    recorderRef.current?.stop()
  }, [])

  const reset = useCallback(() => {
    setRecording(null)
    setElapsedS(0)
    setState("idle")
  }, [])

  useEffect(
    () => () => {
      clearTimer(timerRef)
      if (recorderRef.current?.state === "recording") recorderRef.current.stop()
    },
    [],
  )

  return { supported, state, error, elapsedS, recording, start, stop, reset }
}
