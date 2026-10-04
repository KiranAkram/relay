import { Card, CardContent, CardHeader } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"

const PendingDashboard = () => (
  <div className="flex flex-col gap-4">
    {Array.from({ length: 3 }).map((_, index) => (
      <Card key={index}>
        <CardHeader>
          <Skeleton className="h-6 w-64" />
          <Skeleton className="h-3 w-32" />
        </CardHeader>
        <CardContent className="flex flex-col gap-2">
          <Skeleton className="h-4 w-full" />
          <Skeleton className="h-4 w-3/4" />
          <Skeleton className="h-12 w-full" />
        </CardContent>
      </Card>
    ))}
  </div>
)

export default PendingDashboard
