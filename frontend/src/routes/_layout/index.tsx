import { useQueryClient, useSuspenseQuery } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"
import { ClipboardList, RefreshCw } from "lucide-react"
import { Suspense } from "react"

import { DashboardService } from "@/client"
import { formatClock } from "@/components/Dashboard/countdown"
import { PatientCard } from "@/components/Dashboard/PatientCard"
import PendingDashboard from "@/components/Pending/PendingDashboard"
import { Button } from "@/components/ui/button"
import { useNow } from "@/hooks/useNow"

// Flags fire on read: refetching is what makes an alert appear on time.
const REFRESH_MS = 30_000

function getDashboardQueryOptions() {
  return {
    queryFn: async () => (await DashboardService.readDashboard()).data,
    queryKey: ["dashboard"],
    refetchInterval: REFRESH_MS,
  }
}

export const Route = createFileRoute("/_layout/")({
  component: Dashboard,
  head: () => ({
    meta: [
      {
        title: "Dashboard - Relay",
      },
    ],
  }),
})

function DashboardContent() {
  const { data } = useSuspenseQuery(getDashboardQueryOptions())
  const now = useNow()

  if (data.patients.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center text-center py-12">
        <div className="rounded-full bg-muted p-4 mb-4">
          <ClipboardList className="h-8 w-8 text-muted-foreground" />
        </div>
        <h3 className="text-lg font-semibold">No confirmed handovers yet</h3>
        <p className="text-muted-foreground">
          Patients appear here once a handover is confirmed
        </p>
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-4">
      <p className="text-xs text-muted-foreground">
        Updated {formatClock(data.generated_at)} · refreshes every{" "}
        {REFRESH_MS / 1000}s
      </p>
      {data.patients.map((row) => (
        <PatientCard key={row.patient.id} row={row} now={now} />
      ))}
    </div>
  )
}

function Dashboard() {
  const queryClient = useQueryClient()

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Dashboard</h1>
          <p className="text-muted-foreground">
            Patients by stated severity, then nearest due task
          </p>
        </div>
        <Button
          variant="outline"
          onClick={() =>
            queryClient.invalidateQueries({ queryKey: ["dashboard"] })
          }
        >
          <RefreshCw />
          Refresh
        </Button>
      </div>
      <Suspense fallback={<PendingDashboard />}>
        <DashboardContent />
      </Suspense>
    </div>
  )
}
