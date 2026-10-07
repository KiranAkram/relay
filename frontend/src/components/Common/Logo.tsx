import { Link } from "@tanstack/react-router"

import { cn } from "@/lib/utils"

interface LogoProps {
  variant?: "full" | "icon" | "responsive"
  className?: string
  asLink?: boolean
}

/**
 * The Relay mark: microphone and two relayed sound arcs on a rounded square.
 * Same drawing as `public/relay-mark.svg` (the browser tab icon); the square
 * takes the theme's primary colour so it follows light and dark mode.
 */
export function RelayMark({ className }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 64 64"
      aria-hidden="true"
      className={cn("size-7 shrink-0", className)}
    >
      <rect width="64" height="64" rx="14" className="fill-primary" />
      <rect x="20" y="13" width="14" height="24" rx="7" fill="#fff" />
      <path
        d="M14 30v3a13 13 0 0 0 26 0v-3"
        fill="none"
        stroke="#fff"
        strokeWidth="3.5"
        strokeLinecap="round"
      />
      <path
        d="M27 46v6M20 52h14"
        fill="none"
        stroke="#fff"
        strokeWidth="3.5"
        strokeLinecap="round"
      />
      <path
        d="M44 25a7 7 0 0 1 0 14"
        fill="none"
        stroke="#fff"
        strokeWidth="3"
        strokeLinecap="round"
        opacity="0.9"
      />
      <path
        d="M49 20a12 12 0 0 1 0 24"
        fill="none"
        stroke="#fff"
        strokeWidth="3"
        strokeLinecap="round"
        opacity="0.6"
      />
    </svg>
  )
}

/** Relay wordmark: the mark and the name. No image assets. */
export function Logo({
  variant = "full",
  className,
  asLink = true,
}: LogoProps) {
  const mark = <RelayMark />
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
