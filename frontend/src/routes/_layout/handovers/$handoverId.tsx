import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { createFileRoute, useNavigate } from "@tanstack/react-router"
import { AxiosError } from "axios"
import { AlertTriangle, Loader2 } from "lucide-react"
import { useState } from "react"

import { type HandoverDetailPublic, HandoversService } from "@/client"
import { ConfirmDialog } from "@/components/Common/ConfirmDialog"
import { ReviewCard } from "@/components/Handovers/ReviewCard"
import { isProcessing, StatusBadge } from "@/components/Handovers/StatusBadge"
import PendingDashboard from "@/components/Pending/PendingDashboard"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { LoadingButton } from "@/components/ui/loading-button"
import useCustomToast from "@/hooks/useCustomToast"
import { handleError } from "@/utils"

export const Route = createFileRoute("/_layout/handovers/$handoverId")({
  component: HandoverPage,
  head: () => ({
    meta: [{ title: "Review handover - Relay" }],
  }),
})

const POLL_MS = 2000

type UnresolvedCard = {
  id: string
  mention_verbatim: string
  match_status: string
}

/** The 409 body from confirm lists the cards that still need a patient. */
function unresolvedFrom(error: Error): UnresolvedCard[] | null {
  if (!(error instanceof AxiosError) || error.response?.status !== 409)
    return null
  const detail = (error.response.data as any)?.detail
  return Array.isArray(detail?.cards) ? detail.cards : null
}

function HandoverPage() {
  const { handoverId } = Route.useParams()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { showSuccessToast, showErrorToast } = useCustomToast()
  const [unresolved, setUnresolved] = useState<UnresolvedCard[]>([])

  const { data, isPending, error } = useQuery({
    queryKey: ["handovers", handoverId],
    queryFn: async () =>
      (await HandoversService.readHandover({ path: { id: handoverId } })).data,
    refetchInterval: (query) =>
      query.state.data && isProcessing(query.state.data.status)
        ? POLL_MS
        : false,
  })
  const refresh = () =>
    queryClient.invalidateQueries({ queryKey: ["handovers"] })

  const retry = useMutation({
    mutationFn: () =>
      HandoversService.retryHandover({ path: { id: handoverId } }),
    onError: handleError.bind(showErrorToast),
    onSettled: refresh,
  })
  const discard = useMutation({
    mutationFn: () =>
      HandoversService.discardHandover({ path: { id: handoverId } }),
    onSuccess: () => {
      showSuccessToast("Handover discarded")
      navigate({ to: "/handovers" })
    },
    onError: handleError.bind(showErrorToast),
    onSettled: refresh,
  })
  const confirm = useMutation({
    mutationFn: () =>
      HandoversService.confirmHandover({ path: { id: handoverId } }),
    onSuccess: () => {
      showSuccessToast("Handover confirmed")
      queryClient.invalidateQueries({ queryKey: ["dashboard"] })
      navigate({ to: "/" })
    },
    onError: (err: Error) => {
      const cards = unresolvedFrom(err)
      if (cards) {
        setUnresolved(cards)
      } else {
        handleError.call(showErrorToast, err)
      }
    },
    onSettled: refresh,
  })

  if (isPending) return <PendingDashboard />
  if (error || !data) {
    return (
      <Alert variant="destructive">
        <AlertTriangle />
        <AlertTitle>Could not load this handover</AlertTitle>
        <AlertDescription>{error?.message}</AlertDescription>
      </Alert>
    )
  }

  const reviewing = data.status === "awaiting_review"

  return (
    <div className="flex flex-col gap-6">
      <Header handover={data} />

      {isProcessing(data.status) && (
        <Alert>
          <Loader2 className="animate-spin" />
          <AlertTitle>Processing the recording</AlertTitle>
          <AlertDescription>
            Transcribing, extracting cards and matching patients. This page
            updates by itself.
          </AlertDescription>
        </Alert>
      )}

      {data.status === "failed" && (
        <Alert variant="destructive">
          <AlertTriangle />
          <AlertTitle>Processing failed (attempt {data.attempts})</AlertTitle>
          <AlertDescription className="flex flex-col gap-3">
            <code className="text-xs">{data.last_error}</code>
            <LoadingButton
              variant="outline"
              size="sm"
              className="self-start"
              loading={retry.isPending}
              onClick={() => retry.mutate()}
            >
              Retry
            </LoadingButton>
          </AlertDescription>
        </Alert>
      )}

      {unresolved.length > 0 && reviewing && (
        <Alert variant="destructive">
          <AlertTriangle />
          <AlertTitle>Some cards still need a patient</AlertTitle>
          <AlertDescription>
            <ul className="list-disc pl-5">
              {unresolved.map((c) => (
                <li key={c.id}>
                  “{c.mention_verbatim}” — {c.match_status}
                </li>
              ))}
            </ul>
          </AlertDescription>
        </Alert>
      )}

      {data.patients.map((card) => (
        <ReviewCard
          key={card.id}
          handoverId={data.id}
          card={card}
          readOnly={!reviewing}
        />
      ))}

      {reviewing && (
        <div className="flex items-center justify-between rounded-md border p-4">
          <ConfirmDialog
            trigger={
              <Button variant="ghost" className="text-destructive">
                Discard handover
              </Button>
            }
            title="Discard this handover?"
            description="The recording and draft cards are kept for audit, but nothing reaches a patient record and it cannot be confirmed later."
            confirmLabel="Discard"
            loading={discard.isPending}
            onConfirm={() => discard.mutate()}
          />
          <LoadingButton
            size="lg"
            loading={confirm.isPending}
            onClick={() => confirm.mutate()}
          >
            Confirm handover
          </LoadingButton>
        </div>
      )}

      {data.transcript_text && (
        <details className="rounded-md border p-4 text-sm">
          <summary className="cursor-pointer font-medium">Transcript</summary>
          <p className="mt-3 whitespace-pre-wrap text-muted-foreground">
            {data.transcript_text}
          </p>
        </details>
      )}
    </div>
  )
}

function Header({ handover }: { handover: HandoverDetailPublic }) {
  const recorded = new Date(handover.recorded_at).toLocaleString([], {
    dateStyle: "medium",
    timeStyle: "short",
  })
  return (
    <div className="flex flex-wrap items-start justify-between gap-3">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Review handover</h1>
        <p className="text-muted-foreground">
          Recorded {recorded}
          {handover.shift_label ? ` · ${handover.shift_label}` : ""}
          {handover.patients.length > 0
            ? ` · ${handover.patients.length} patient${handover.patients.length === 1 ? "" : "s"}`
            : ""}
        </p>
      </div>
      <StatusBadge status={handover.status} />
    </div>
  )
}
