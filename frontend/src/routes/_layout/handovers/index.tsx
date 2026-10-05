import { useSuspenseQuery } from "@tanstack/react-query"
import { createFileRoute, Link } from "@tanstack/react-router"
import { Mic, Plus } from "lucide-react"
import { Suspense } from "react"

import { HandoversService } from "@/client"
import { StatusBadge } from "@/components/Handovers/StatusBadge"
import PendingItems from "@/components/Pending/PendingItems"
import { Button } from "@/components/ui/button"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"

function getHandoversQueryOptions() {
  return {
    queryFn: async () =>
      (await HandoversService.readHandovers({ query: { skip: 0, limit: 100 } }))
        .data,
    queryKey: ["handovers"],
  }
}

export const Route = createFileRoute("/_layout/handovers/")({
  component: Handovers,
  head: () => ({
    meta: [{ title: "Handovers - Relay" }],
  }),
})

const formatDateTime = (iso: string) =>
  new Date(iso).toLocaleString([], {
    dateStyle: "medium",
    timeStyle: "short",
  })

function HandoversTableContent() {
  const { data } = useSuspenseQuery(getHandoversQueryOptions())

  if (data.data.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center text-center py-12">
        <div className="rounded-full bg-muted p-4 mb-4">
          <Mic className="h-8 w-8 text-muted-foreground" />
        </div>
        <h3 className="text-lg font-semibold">No handovers yet</h3>
        <p className="text-muted-foreground">
          Record one at the end of your shift
        </p>
      </div>
    )
  }

  return (
    <Table>
      <TableHeader>
        <TableRow className="hover:bg-transparent">
          <TableHead>Recorded</TableHead>
          <TableHead>Shift</TableHead>
          <TableHead>Status</TableHead>
          <TableHead>
            <span className="sr-only">Open</span>
          </TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {data.data.map((h) => (
          <TableRow key={h.id}>
            <TableCell>{formatDateTime(h.recorded_at)}</TableCell>
            <TableCell className="text-muted-foreground">
              {h.shift_label ?? "—"}
            </TableCell>
            <TableCell>
              <StatusBadge status={h.status} />
            </TableCell>
            <TableCell className="text-right">
              <Button asChild variant="outline" size="sm">
                <Link to="/handovers/$handoverId" params={{ handoverId: h.id }}>
                  {h.status === "awaiting_review" ? "Review" : "Open"}
                </Link>
              </Button>
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  )
}

function Handovers() {
  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Handovers</h1>
          <p className="text-muted-foreground">Your recordings, newest first</p>
        </div>
        <Button asChild>
          <Link to="/handovers/new">
            <Plus />
            New handover
          </Link>
        </Button>
      </div>
      <Suspense fallback={<PendingItems />}>
        <HandoversTableContent />
      </Suspense>
    </div>
  )
}
