import type { IllnessSeverity } from "@/client"
import { Badge } from "@/components/ui/badge"

const STYLES: Record<IllnessSeverity, string> = {
  unstable: "border-transparent bg-red-600 text-white",
  watcher: "border-transparent bg-amber-500 text-black",
  stable: "border-transparent bg-emerald-600 text-white",
  unspecified: "text-muted-foreground",
}

export const SEVERITY_LABELS: Record<IllnessSeverity, string> = {
  unstable: "Unstable",
  watcher: "Watcher",
  stable: "Stable",
  unspecified: "Severity not stated",
}

export function SeverityBadge({ severity }: { severity: IllnessSeverity }) {
  return <Badge className={STYLES[severity]}>{SEVERITY_LABELS[severity]}</Badge>
}
