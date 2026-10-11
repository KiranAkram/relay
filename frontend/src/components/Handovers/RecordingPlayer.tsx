import { useQuery } from "@tanstack/react-query"
import { AxiosError } from "axios"
import { Loader2 } from "lucide-react"
import { useEffect } from "react"

import { HandoversService } from "@/client"

/**
 * Plays a handover recording for its author or an admin.
 *
 * The audio element cannot send the bearer token, so the bytes are fetched
 * through the API client and played from a blob URL (never a token in a query
 * string). The blob URL is revoked when the component unmounts. Recordings
 * are at most RECORDING_MAX_SECONDS, so the whole file is fetched at once.
 */
export function RecordingPlayer({
  handoverId,
  purgedAt,
}: {
  handoverId: string
  purgedAt?: string | null
}) {
  const {
    data: url,
    error,
    isPending,
  } = useQuery({
    queryKey: ["handovers", handoverId, "audio"],
    queryFn: async () => {
      const response = await HandoversService.readHandoverAudio({
        path: { id: handoverId },
        responseType: "blob",
      })
      return URL.createObjectURL(response.data as Blob)
    },
    enabled: !purgedAt,
    staleTime: Number.POSITIVE_INFINITY,
    retry: false,
  })

  useEffect(() => {
    return () => {
      if (url) URL.revokeObjectURL(url)
    }
  }, [url])

  if (purgedAt) {
    return (
      <p className="text-sm text-muted-foreground">
        Recording purged on{" "}
        {new Date(purgedAt).toLocaleDateString([], { dateStyle: "medium" })}{" "}
        after the retention period.
      </p>
    )
  }
  if (isPending) {
    return (
      <p className="flex items-center gap-2 text-sm text-muted-foreground">
        <Loader2 className="size-4 animate-spin" /> Loading recording…
      </p>
    )
  }
  if (error) {
    return <p className="text-sm text-muted-foreground">{reason(error)}</p>
  }
  return (
    // biome-ignore lint/a11y/useMediaCaption: no timed caption file exists; the written transcript on the review page stands in for captions
    <audio controls preload="metadata" src={url} className="w-full max-w-xl">
      Your browser cannot play this recording.
    </audio>
  )
}

function reason(error: Error): string {
  if (error instanceof AxiosError) {
    const status = error.response?.status
    const detail = error.response?.data?.detail
    if (status === 403) {
      return "Only the doctor who recorded this handover or an admin can play it."
    }
    if ((status === 404 || status === 410) && typeof detail === "string") {
      return detail
    }
  }
  return "Recording could not be loaded."
}
