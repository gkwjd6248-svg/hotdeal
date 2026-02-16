import DealCardSkeleton from "@/components/deals/DealCardSkeleton";

export default function Loading() {
  return (
    <div className="min-h-screen">
      {/* Category tabs skeleton */}
      <div className="sticky top-0 z-40 border-b border-border bg-card/95 backdrop-blur supports-[backdrop-filter]:bg-card/80">
        <div className="mx-auto max-w-[1440px] px-4 sm:px-6">
          <div className="flex gap-2 overflow-x-auto py-3 scrollbar-hide">
            {[...Array(6)].map((_, i) => (
              <div
                key={i}
                className="h-9 w-24 animate-pulse rounded-full bg-surface"
              />
            ))}
          </div>
        </div>
      </div>

      {/* Shop filter skeleton */}
      <div className="border-b border-border bg-background">
        <div className="mx-auto max-w-[1440px] px-4 py-3 sm:px-6">
          <div className="flex gap-2 overflow-x-auto scrollbar-hide">
            {[...Array(8)].map((_, i) => (
              <div
                key={i}
                className="h-8 w-20 animate-pulse rounded-lg bg-surface"
              />
            ))}
          </div>
        </div>
      </div>

      {/* Main content skeleton */}
      <div className="mx-auto max-w-[1440px] px-4 py-6 sm:px-6">
        {/* Header skeleton */}
        <div className="mb-6 flex items-center justify-between">
          <div className="h-8 w-48 animate-pulse rounded-lg bg-surface" />
          <div className="h-10 w-32 animate-pulse rounded-lg bg-surface" />
        </div>

        {/* Deal grid skeleton */}
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          {[...Array(12)].map((_, i) => (
            <DealCardSkeleton key={i} />
          ))}
        </div>
      </div>
    </div>
  );
}
