import { FiltersSkeleton, SkeletonCard } from "@/components/skeletons"

export default function Loading() {
  return (
    <>
      <FiltersSkeleton count={4} />
      <SkeletonCard bodyClassName="h-96" />
    </>
  )
}
