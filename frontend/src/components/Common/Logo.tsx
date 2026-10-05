import { Link } from "@tanstack/react-router"
import { Mic } from "lucide-react"

import { cn } from "@/lib/utils"

interface LogoProps {
  variant?: "full" | "icon" | "responsive"
  className?: string
  asLink?: boolean
}

/** Relay wordmark: a microphone mark and the name. No image assets. */
export function Logo({
  variant = "full",
  className,
  asLink = true,
}: LogoProps) {
  const mark = (
    <span className="flex size-7 shrink-0 items-center justify-center rounded-md bg-primary text-primary-foreground">
      <Mic className="size-4" />
    </span>
  )
  const name = (
    <span className="text-lg font-semibold tracking-tight">Relay</span>
  )

  const content =
    variant === "responsive" ? (
      <span className={cn("flex items-center gap-2", className)}>
        {mark}
        <span className="group-data-[collapsible=icon]:hidden">{name}</span>
      </span>
    ) : variant === "full" ? (
      <span className={cn("flex items-center gap-2", className)}>
        {mark}
        {name}
      </span>
    ) : (
      <span className={className}>{mark}</span>
    )

  if (!asLink) {
    return content
  }

  return <Link to="/">{content}</Link>
}
