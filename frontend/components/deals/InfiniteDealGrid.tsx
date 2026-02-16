"use client";

import { useEffect } from "react";
import { useSearchParams } from "next/navigation";
import DealCard from "./DealCard";
import DealCardSkeleton from "./DealCardSkeleton";
import EmptyState from "@/components/common/EmptyState";
import { useInfiniteDeals } from "@/hooks/useInfiniteDeals";
import { useIntersection } from "@/hooks/useIntersection";
import { Loader2 } from "lucide-react";

interface InfiniteDealGridProps {
  /** Initial deals from server-side render (shown while SWR hydrates) */
  initialCategory?: string;
  initialShop?: string;
  initialSort?: string;
  emptyMessage?: string;
}

export default function InfiniteDealGrid({
  initialCategory,
  initialShop,
  initialSort,
  emptyMessage = "특가 상품을 찾을 수 없습니다",
}: InfiniteDealGridProps) {
  const searchParams = useSearchParams();
  const category = initialCategory || searchParams.get("category") || undefined;
  const shop = initialShop || searchParams.get("shop") || undefined;
  const sort = initialSort || searchParams.get("sort") || undefined;

  const {
    deals,
    total,
    isLoadingInitial,
    isLoadingMore,
    isReachingEnd,
    loadMore,
  } = useInfiniteDeals({ category, shop, sort });

  // Infinite scroll sentinel
  const { ref: sentinelRef, isIntersecting } = useIntersection({
    rootMargin: "200px",
  });

  useEffect(() => {
    if (isIntersecting && !isLoadingMore && !isReachingEnd) {
      loadMore();
    }
  }, [isIntersecting, isLoadingMore, isReachingEnd, loadMore]);

  if (isLoadingInitial) {
    return (
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
        {Array.from({ length: 12 }).map((_, i) => (
          <DealCardSkeleton key={i} />
        ))}
      </div>
    );
  }

  if (deals.length === 0) {
    return (
      <EmptyState
        title={emptyMessage}
        description="다른 카테고리를 탐색하거나 검색어를 변경해보세요."
        actionLabel="전체 특가 보기"
        actionHref="/deals"
      />
    );
  }

  return (
    <>
      {total > 0 && (
        <p className="mb-4 text-sm text-gray-400">
          총 {total.toLocaleString()}개 특가
        </p>
      )}

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
        {deals.map((deal) => (
          <DealCard key={deal.id} deal={deal} />
        ))}

        {isLoadingMore &&
          Array.from({ length: 4 }).map((_, i) => (
            <DealCardSkeleton key={`skeleton-${i}`} />
          ))}
      </div>

      {/* Sentinel for intersection observer */}
      {!isReachingEnd && (
        <div ref={sentinelRef} className="flex justify-center py-8">
          <Loader2 className="h-6 w-6 animate-spin text-accent" />
        </div>
      )}

      {isReachingEnd && deals.length > 0 && (
        <p className="py-8 text-center text-sm text-gray-500">
          모든 특가를 불러왔습니다
        </p>
      )}
    </>
  );
}
