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

/**
 * Microphone recording through the browser's MediaRecorder.
 * Stops on its own at `maxSeconds` (the server refuses anything longer).
 */
export function useRecorder({ maxSeconds }: { maxSeconds: number }) {
  const [state, setState] = useState<RecorderState>("idle")
  const [error, setError] = useState<string | null>(null)
  const [elapsedS, setElapsedS] = useState(0)
  const [recording, setRecording] = useState<Recording | null>(null)
  const recorderRef = useRef<MediaRecorder | null>(null)
  const chunksRef = useRef<Blob[]>([])
  const startedAtRef = useRef<Date | null>(null)
  const timerRef = useRef<number | null>(null)
  const maxSecondsRef = useRef(maxSeconds)
  maxSecondsRef.current = maxSeconds

  // Browsers remove navigator.mediaDevices on a plain http page that is not
  // localhost, so "not supported" is usually "not https", not an old browser.
  const unsupportedReason =
    typeof window !== "undefined" && !window.isSecureContext
      ? "Recording needs a secure (https) connection. Open Relay over https."
      : typeof navigator === "undefined" ||
          !navigator.mediaDevices?.getUserMedia ||
          typeof MediaRecorder === "undefined" ||
          !pickMimeType()
        ? "This browser cannot record audio. Use a current version of Chrome, Edge, Firefox or Safari."
        : null
  const supported = unsupportedReason === null

  const stop = useCallback(() => {
    if (recorderRef.current?.state === "recording") recorderRef.current.stop()
  }, [])

  const start = useCallback(async () => {
    setError(null)
    setRecording(null)
    const picked = pickMimeType()
    if (!supported || !picked) {
      setError(unsupportedReason ?? "This browser cannot record audio.")
      return
    }
    setState("requesting")
    let stream: MediaStream
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true })
    } catch {
      setState("idle")
      setError(
        "Microphone access was refused. Allow the microphone for this site in the browser, then press Record again.",
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
      const elapsed = (Date.now() - startedAt.getTime()) / 1000
      setRecording({
        blob,
        filename: `handover.${picked.ext}`,
        startedAt,
        // Never above the cap, never zero: the server validates both.
        durationS: Math.min(
          Math.max(Math.round(elapsed), 1),
          maxSecondsRef.current,
        ),
      })
      setState("done")
    }
    recorderRef.current = recorder
    startedAtRef.current = new Date()
    setElapsedS(0)
    recorder.start(1000)
    setState("recording")
    timerRef.current = window.setInterval(() => {
      const elapsed = Math.round(
        (Date.now() - (startedAtRef.current?.getTime() ?? 0)) / 1000,
      )
      setElapsedS(elapsed)
      if (elapsed >= maxSecondsRef.current) stop()
    }, 500)
  }, [supported, unsupportedReason, stop])

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

  return {
    supported,
    unsupportedReason,
    state,
    error,
    elapsedS,
    secondsLeft: Math.max(maxSeconds - elapsedS, 0),
    maxSeconds,
    recording,
    start,
    stop,
    reset,
  }
}
