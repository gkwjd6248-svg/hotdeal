"use client";

import { useEffect } from "react";
import useSWRInfinite from "swr/infinite";
import { Deal, ApiResponse } from "@/lib/types";
import DealCard from "@/components/deals/DealCard";
import DealCardSkeleton from "@/components/deals/DealCardSkeleton";
import EmptyState from "@/components/common/EmptyState";
import { useIntersection } from "@/hooks/useIntersection";
import { Loader2 } from "lucide-react";

interface SearchResultsProps {
  query: string;
  sort?: string;
}

const PAGE_SIZE = 20;

const fetcher = async (url: string) => {
  const res = await fetch(url);
  if (!res.ok) throw new Error("Search failed");
  return res.json();
};

function buildSearchKey(
  pageIndex: number,
  previousPageData: ApiResponse<Deal[]> | null,
  query: string,
  sort: string
): string | null {
  if (!query.trim()) return null;
  if (previousPageData && previousPageData.data.length < PAGE_SIZE) return null;

  const params = new URLSearchParams();
  params.set("q", query);
  params.set("page", String(pageIndex + 1));
  params.set("limit", String(PAGE_SIZE));
  if (sort && sort !== "newest") {
    params.set(
      "sort_by",
      sort === "score" ? "score" : sort === "discount" ? "discount" : sort
    );
  }

  return `/api/v1/search?${params.toString()}`;
}

export default function SearchResults({ query, sort = "" }: SearchResultsProps) {
  const getKey = (
    pageIndex: number,
    previousPageData: ApiResponse<Deal[]> | null
  ) => buildSearchKey(pageIndex, previousPageData, query, sort);

  const { data, error, size, setSize, isValidating } =
    useSWRInfinite<ApiResponse<Deal[]>>(getKey, fetcher, {
      revalidateFirstPage: true,
      revalidateOnFocus: false,
    });

  const deals = data ? data.flatMap((page) => page.data) : [];
  const total = data?.[0]?.meta?.total ?? 0;
  const isLoadingInitial = !data && !error;
  const isLoadingMore =
    isLoadingInitial ||
    (size > 0 && data && typeof data[size - 1] === "undefined");
  const isEmpty = data?.[0]?.data?.length === 0;
  const isReachingEnd =
    isEmpty || (data && (data[data.length - 1]?.data?.length ?? 0) < PAGE_SIZE);

  const { ref: sentinelRef, isIntersecting } = useIntersection({
    rootMargin: "200px",
  });

  useEffect(() => {
    if (isIntersecting && !isLoadingMore && !isReachingEnd) {
      setSize(size + 1);
    }
  }, [isIntersecting, isLoadingMore, isReachingEnd, setSize, size]);

  if (isLoadingInitial) {
    return (
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
        {Array.from({ length: 8 }).map((_, i) => (
          <DealCardSkeleton key={i} />
        ))}
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center py-20 text-center">
        <p className="mb-2 text-lg font-medium text-red-400">
          검색 중 오류가 발생했습니다
        </p>
        <p className="mb-6 text-sm text-gray-500">
          잠시 후 다시 시도해주세요
        </p>
        <button
          onClick={() => setSize(1)}
          className="rounded-lg bg-accent px-6 py-2.5 text-sm font-semibold text-black transition-opacity hover:opacity-90"
        >
          다시 검색
        </button>
      </div>
    );
  }

  if (isEmpty) {
    return (
      <EmptyState
        title={`"${query}"에 대한 검색 결과가 없습니다`}
        description="다른 검색어를 입력하거나 카테고리를 탐색해보세요."
        actionLabel="전체 특가 보기"
        actionHref="/deals"
      />
    );
  }

  return (
    <>
      {total > 0 && (
        <p className="mb-4 text-sm text-gray-400">
          &ldquo;{query}&rdquo; 검색 결과{" "}
          <span className="font-semibold text-gray-300">
            {total.toLocaleString()}
          </span>
          개
        </p>
      )}

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
        {deals.map((deal) => (
          <DealCard key={deal.id} deal={deal} />
        ))}

        {isLoadingMore &&
          Array.from({ length: 4 }).map((_, i) => (
            <DealCardSkeleton key={`skel-${i}`} />
          ))}
      </div>

      {/* Infinite scroll sentinel */}
      {!isReachingEnd && (
        <div ref={sentinelRef} className="flex justify-center py-8">
          <Loader2 className="h-6 w-6 animate-spin text-accent" />
        </div>
      )}

      {isReachingEnd && deals.length > 0 && (
        <p className="py-8 text-center text-sm text-gray-500">
          모든 검색 결과를 불러왔습니다
        </p>
      )}
    </>
  );
}
