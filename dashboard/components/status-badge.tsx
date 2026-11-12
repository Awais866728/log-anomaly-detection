import { Badge } from "@/components/ui/badge"
import { cn } from "@/lib/utils"

// Colour is only used for meaning: red critical, amber warning, green healthy
const TONES = {
  critical: "border-critical/30 bg-critical/10 text-critical",
  warning: "border-warning/30 bg-warning/10 text-warning",
  healthy: "border-healthy/30 bg-healthy/10 text-healthy",
}

export function StatusBadge({ tone, label }: { tone: keyof typeof TONES; label: string }) {
  return (
    <Badge variant="outline" className={cn("capitalize", TONES[tone])}>
      <span className="size-1.5 rounded-full bg-current" aria-hidden />
      {label}
    </Badge>
  )
}
