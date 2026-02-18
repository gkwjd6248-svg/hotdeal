export default function DealCardSkeleton() {
  return (
    <div className="deal-card">
      {/* Image skeleton */}
      <div className="skeleton mb-3 aspect-[4/3] w-full rounded-lg" />

      {/* Title skeleton */}
      <div className="mb-2 space-y-2">
        <div className="skeleton h-4 w-full rounded" />
        <div className="skeleton h-4 w-3/4 rounded" />
      </div>

      {/* Price skeleton */}
      <div className="mb-2 space-y-1.5">
        <div className="skeleton h-3 w-20 rounded" />
        <div className="skeleton h-6 w-28 rounded" />
      </div>

      {/* Meta info skeleton */}
      <div className="border-t border-border/50 pt-2">
        <div className="flex items-center justify-between">
          <div className="skeleton h-3 w-36 rounded" />
          <div className="skeleton h-4 w-10 rounded-full" />
        </div>
      </div>

      {/* Stats skeleton */}
      <div className="mt-2 flex items-center gap-3">
        <div className="skeleton h-3 w-10 rounded" />
        <div className="skeleton h-3 w-10 rounded" />
        <div className="skeleton h-3 w-10 rounded" />
      </div>
    </div>
  );
}
