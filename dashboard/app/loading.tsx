import { SkeletonCard } from "@/components/skeletons"

export default function Loading() {
  return (
    <>
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {Array.from({ length: 4 }, (_, i) => (
          <SkeletonCard key={i} bodyClassName="h-8 w-24" />
        ))}
      </div>
      <SkeletonCard bodyClassName="h-72" />
      <div className="grid gap-4 lg:grid-cols-3">
        <SkeletonCard className="lg:col-span-2" bodyClassName="h-64" />
        <SkeletonCard bodyClassName="h-64" />
      </div>
    </>
  )
}
