import { Badge } from "@/components/ui/badge"
import type { Health } from "@/lib/types"
import { cn } from "@/lib/utils"

// Colour is only used for meaning: red critical, amber warning, green healthy
const TEXT = {
  critical: "text-critical",
  warning: "text-warning",
  healthy: "text-healthy",
  neutral: "text-muted-foreground",
}

const BADGE = {
  critical: "border-critical/30 bg-critical/10",
  warning: "border-warning/30 bg-warning/10",
  healthy: "border-healthy/30 bg-healthy/10",
  neutral: "",
}

export type Tone = keyof typeof TEXT

export const HEALTH_TONE: Record<Health, Tone> = { healthy: "healthy", warning: "warning", down: "critical" }

export function StatusDot({ tone }: { tone: Tone }) {
  return <span className={cn("size-1.5 shrink-0 rounded-full bg-current", TEXT[tone])} aria-hidden />
}

export function StatusBadge({ tone, label }: { tone: Tone; label: string }) {
  return (
    <Badge variant="outline" className={cn("capitalize", BADGE[tone], TEXT[tone])}>
      <StatusDot tone={tone} />
      {label}
    </Badge>
  )
}
