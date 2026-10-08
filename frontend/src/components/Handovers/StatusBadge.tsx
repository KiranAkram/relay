import type { HandoverStatus } from "@/client"
import { Badge } from "@/components/ui/badge"

export const PROCESSING: HandoverStatus[] = [
  "uploaded",
  "transcribing",
  "extracting",
  "matching",
]

const LABELS: Record<HandoverStatus, string> = {
  uploaded: "Uploaded",
  transcribing: "Transcribing",
  extracting: "Extracting",
  matching: "Matching patients",
  awaiting_review: "Awaiting review",
  confirmed: "Confirmed",
  failed: "Failed",
  rejected: "Not a handover",
  discarded: "Discarded",
}

const VARIANTS: Record<
  HandoverStatus,
  "default" | "secondary" | "destructive" | "outline"
> = {
  uploaded: "secondary",
  transcribing: "secondary",
  extracting: "secondary",
  matching: "secondary",
  awaiting_review: "default",
  confirmed: "outline",
  failed: "destructive",
  rejected: "destructive",
  discarded: "outline",
}

export function StatusBadge({ status }: { status: HandoverStatus }) {
  return <Badge variant={VARIANTS[status]}>{LABELS[status]}</Badge>
}

export const isProcessing = (status: HandoverStatus) =>
  PROCESSING.includes(status)
