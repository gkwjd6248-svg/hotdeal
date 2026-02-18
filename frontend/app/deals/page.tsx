import { Suspense } from "react";
import InfiniteDealGrid from "@/components/deals/InfiniteDealGrid";
import DealCardSkeleton from "@/components/deals/DealCardSkeleton";
import ShopFilter from "@/components/navigation/ShopFilter";
import SortDropdown from "@/components/navigation/SortDropdown";
import { ApiResponse, Deal } from "@/lib/types";
import { LayoutGrid } from "lucide-react";

const API_BASE = process.env.BACKEND_URL || "http://localhost:8000";

interface DealsPageProps {
  searchParams: {
    category?: string;
    shop?: string;
    sort?: string;
  };
}

/** Fetch just the total count + category name for the page header (SSR) */
async function getDealsMetadata(params: {
  category?: string;
  shop?: string;
  sort?: string;
}): Promise<{ total: number; categoryName: string }> {
  try {
    const qs = new URLSearchParams();
    qs.set("limit", "1");
    if (params.category && params.category !== "all") {
      qs.set("category", params.category);
    }
    if (params.shop) qs.set("shop", params.shop);
    if (params.sort) qs.set("sort_by", params.sort);

    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 5000);
    const res = await fetch(`${API_BASE}/api/v1/deals?${qs.toString()}`, {
      next: { revalidate: 30 },
      signal: controller.signal,
    });
    clearTimeout(timeout);
    if (!res.ok) throw new Error("API error");
    const json: ApiResponse<Deal[]> = await res.json();
    const total = json.meta?.total ?? 0;

    let categoryName = "전체";
    if (params.category && params.category !== "all") {
      try {
        const catController = new AbortController();
        const catTimeout = setTimeout(() => catController.abort(), 5000);
        const catRes = await fetch(`${API_BASE}/api/v1/categories`, {
          next: { revalidate: 300 },
          signal: catController.signal,
        });
        clearTimeout(catTimeout);
        if (catRes.ok) {
          const catJson = await catRes.json();
          const matched = catJson.data?.find(
            (c: { slug: string; name: string }) => c.slug === params.category
          );
          if (matched) categoryName = matched.name;
        }
      } catch {
        categoryName = params.category;
      }
    }

    return { total, categoryName };
  } catch {
    return { total: 0, categoryName: params.category || "전체" };
  }
}

function DealsGridSkeleton() {
  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
      {Array.from({ length: 12 }).map((_, i) => (
        <DealCardSkeleton key={i} />
      ))}
    </div>
  );
}

export default async function DealsPage({ searchParams }: DealsPageProps) {
  const { total, categoryName } = await getDealsMetadata(searchParams);
  const isFiltered = Boolean(searchParams.category || searchParams.shop);

  return (
    <div className="min-h-screen">
      <ShopFilter />

      <div className="mx-auto max-w-[1440px] px-4 py-6 sm:px-6">
        {/* Page header */}
        <div className="mb-6 flex items-start justify-between gap-4">
          <div>
            <div className="flex items-center gap-2">
              <LayoutGrid className="h-5 w-5 text-accent" />
              <h1 className="text-xl font-bold text-white sm:text-2xl">
                {categoryName}{" "}
                <span className="text-accent">특가</span>
              </h1>
            </div>
            <div className="mt-1 flex items-center gap-2 text-sm text-gray-400">
              {total > 0 ? (
                <span>
                  총{" "}
                  <span className="font-semibold text-gray-300">
                    {total.toLocaleString()}
                  </span>
                  개 상품
                </span>
              ) : (
                <span>검색 중...</span>
              )}
              {isFiltered && (
                <span className="rounded-full bg-accent/10 px-2 py-0.5 text-xs font-medium text-accent">
                  필터 적용됨
                </span>
              )}
            </div>
          </div>
          <SortDropdown />
        </div>

        {/* Client-side infinite scroll grid */}
        <Suspense fallback={<DealsGridSkeleton />}>
          <InfiniteDealGrid />
        </Suspense>
      </div>
    </div>
  );
}
