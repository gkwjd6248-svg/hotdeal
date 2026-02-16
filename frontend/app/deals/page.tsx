import { Suspense } from "react";
import DealGrid from "@/components/deals/DealGrid";
import InfiniteDealGrid from "@/components/deals/InfiniteDealGrid";
import ShopFilter from "@/components/navigation/ShopFilter";
import SortDropdown from "@/components/navigation/SortDropdown";
import { MOCK_DEALS } from "@/lib/mock-data";
import { Deal, ApiResponse } from "@/lib/types";
import { CATEGORIES } from "@/lib/constants";

const API_BASE = process.env.BACKEND_URL || "http://localhost:8000";

interface DealsPageProps {
  searchParams: {
    category?: string;
    shop?: string;
    sort?: string;
  };
}

async function getDeals(params: DealsPageProps["searchParams"]): Promise<{ deals: Deal[]; total: number }> {
  try {
    const searchParams = new URLSearchParams();
    searchParams.set("limit", "20");
    if (params.category && params.category !== "all") searchParams.set("category", params.category);
    if (params.shop) searchParams.set("shop", params.shop);
    if (params.sort) searchParams.set("sort_by", params.sort);

    const res = await fetch(`${API_BASE}/api/v1/deals?${searchParams.toString()}`, {
      next: { revalidate: 60 },
    });
    if (!res.ok) throw new Error("API error");
    const json: ApiResponse<Deal[]> = await res.json();
    return { deals: json.data, total: json.meta?.total ?? json.data.length };
  } catch {
    let deals = MOCK_DEALS;
    if (params.category && params.category !== "all") {
      deals = deals.filter((d) => d.category?.slug === params.category);
    }
    if (params.shop) {
      const shops = params.shop.split(",");
      deals = deals.filter((d) => shops.includes(d.shop.slug));
    }
    return { deals, total: deals.length };
  }
}

export default async function DealsPage({ searchParams }: DealsPageProps) {
  const { deals, total } = await getDeals(searchParams);

  const categoryMatch = CATEGORIES.find((c) => c.slug === searchParams.category);
  const categoryName = categoryMatch ? categoryMatch.name : "전체";

  return (
    <div className="min-h-screen">
      <ShopFilter />

      <div className="mx-auto max-w-[1440px] px-4 py-6 sm:px-6">
        <div className="mb-6 flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-white">
              {categoryName} 특가
            </h1>
            <p className="mt-1 text-sm text-gray-400">
              {total.toLocaleString()}개의 특가 상품
            </p>
          </div>
          <SortDropdown />
        </div>

        {/* SSR initial deals + client-side infinite scroll */}
        {total > 20 ? (
          <Suspense fallback={<DealGrid deals={deals} />}>
            <InfiniteDealGrid
              initialCategory={searchParams.category}
              initialShop={searchParams.shop}
              initialSort={searchParams.sort}
            />
          </Suspense>
        ) : (
          <DealGrid deals={deals} />
        )}
      </div>
    </div>
  );
}
