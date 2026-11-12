import { FiltersSkeleton, SkeletonCard } from "@/components/skeletons"

export default function Loading() {
  return (
    <>
      <FiltersSkeleton count={2} />
      <SkeletonCard bodyClassName="h-72" />
    </>
  )
}
