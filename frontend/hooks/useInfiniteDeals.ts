"use client";

import useSWRInfinite from "swr/infinite";
import { Deal, ApiResponse } from "@/lib/types";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

interface UseInfiniteDealsOptions {
  category?: string;
  shop?: string;
  sort?: string;
  limit?: number;
  /** SWR polling interval in ms (0 = disabled). Default 30000 (30s). */
  refreshInterval?: number;
}

const fetcher = async (url: string) => {
  const res = await fetch(url);
  if (!res.ok) throw new Error("API error");
  return res.json();
};

export function useInfiniteDeals(options: UseInfiniteDealsOptions = {}) {
  const { category, shop, sort, limit = 20, refreshInterval = 30000 } = options;

  const getKey = (pageIndex: number, previousPageData: ApiResponse<Deal[]> | null) => {
    // Reached the end
    if (previousPageData && previousPageData.data.length < limit) return null;

    const params = new URLSearchParams();
    params.set("page", String(pageIndex + 1));
    params.set("limit", String(limit));
    if (category && category !== "all") params.set("category", category);
    if (shop) params.set("shop", shop);
    if (sort) params.set("sort_by", sort);

    return `${API_BASE}/api/v1/deals?${params.toString()}`;
  };

  const { data, error, size, setSize, isValidating, mutate } =
    useSWRInfinite<ApiResponse<Deal[]>>(getKey, fetcher, {
      refreshInterval,
      revalidateFirstPage: true,
      revalidateOnFocus: false,
    });

  const deals = data ? data.flatMap((page) => page.data) : [];
  const total = data?.[0]?.meta?.total ?? 0;
  const isLoadingInitial = !data && !error;
  const isLoadingMore =
    isLoadingInitial || (size > 0 && data && typeof data[size - 1] === "undefined");
  const isEmpty = data?.[0]?.data?.length === 0;
  const isReachingEnd =
    isEmpty || (data && data[data.length - 1]?.data?.length < limit);

  return {
    deals,
    total,
    error,
    isLoadingInitial,
    isLoadingMore: !!isLoadingMore,
    isReachingEnd: !!isReachingEnd,
    isValidating,
    size,
    setSize,
    mutate,
    loadMore: () => setSize(size + 1),
  };
}
