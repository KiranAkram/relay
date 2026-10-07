import { Appearance } from "@/components/Common/Appearance"
import { RelayMark } from "@/components/Common/Logo"
import { Footer } from "./Footer"

interface AuthLayoutProps {
  children: React.ReactNode
}

export function AuthLayout({ children }: AuthLayoutProps) {
  return (
    <div className="grid min-h-svh lg:grid-cols-2">
      <div className="relative hidden overflow-hidden bg-muted dark:bg-zinc-900 lg:flex lg:flex-col lg:items-center lg:justify-center gap-6 p-10 text-center">
        {/* Soft teal wash behind the mark; the mark itself stays flat. */}
        <div
          aria-hidden="true"
          className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_at_center,_color-mix(in_oklch,var(--primary)_22%,transparent),transparent_65%)]"
        />
        <RelayMark className="relative size-24 drop-shadow-sm" />
        <div className="relative">
          <h1 className="text-4xl font-semibold tracking-tight">Relay</h1>
          <p className="mt-1 text-sm uppercase tracking-[0.2em] text-muted-foreground">
            Voice handover
          </p>
        </div>
        <p className="relative max-w-sm text-muted-foreground">
          Speak the shift handover once. Every patient gets a structured card, a
          prioritised place on the incoming doctor's dashboard, and a permanent
          record.
        </p>
      </div>
      <div className="flex flex-col gap-4 p-6 md:p-10">
        <div className="flex justify-end">
          <Appearance />
        </div>
        <div className="flex flex-1 items-center justify-center">
          <div className="w-full max-w-xs">{children}</div>
        </div>
        <Footer />
      </div>
    </div>
  )
}
