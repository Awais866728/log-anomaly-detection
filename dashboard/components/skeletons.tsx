import { Card, CardContent, CardHeader } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { cn } from "@/lib/utils"

// Loading placeholder for a card: a title line plus a body block of the given height
export function SkeletonCard({ className, bodyClassName = "h-40" }: { className?: string; bodyClassName?: string }) {
  return (
    <Card className={className}>
      <CardHeader className="gap-2">
        <Skeleton className="h-4 w-32" />
        <Skeleton className="h-3 w-48" />
      </CardHeader>
      <CardContent>
        <Skeleton className={cn("w-full", bodyClassName)} />
      </CardContent>
    </Card>
  )
}

// Placeholder for a row of filter controls
export function FiltersSkeleton({ count }: { count: number }) {
  return (
    <div className="flex flex-wrap gap-2">
      {Array.from({ length: count }, (_, i) => (
        <Skeleton key={i} className="h-8 w-40" />
      ))}
    </div>
  )
}
