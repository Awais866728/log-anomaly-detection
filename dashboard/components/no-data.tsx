import { cn } from "@/lib/utils"

// Shown wherever a value isn't available yet, instead of an invented number
export const NO_DATA = "no data yet"

export function NoData({ className }: { className?: string }) {
  return <span className={cn("text-sm font-normal text-muted-foreground", className)}>{NO_DATA}</span>
}
