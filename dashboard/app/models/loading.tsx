import { FiltersSkeleton, SkeletonCard } from "@/components/skeletons"

export default function Loading() {
  return (
    <>
      <FiltersSkeleton count={1} />
      <div className="grid gap-4 xl:grid-cols-5">
        <SkeletonCard className="xl:col-span-3" bodyClassName="h-72" />
        <SkeletonCard className="xl:col-span-2" bodyClassName="h-72" />
      </div>
    </>
  )
}
