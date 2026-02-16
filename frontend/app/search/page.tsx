import DealGrid from "@/components/deals/DealGrid";
import ShopFilter from "@/components/navigation/ShopFilter";
import SortDropdown from "@/components/navigation/SortDropdown";
import { MOCK_DEALS } from "@/lib/mock-data";
import { Deal, ApiResponse } from "@/lib/types";
import { Search } from "lucide-react";

const API_BASE = process.env.BACKEND_URL || "http://localhost:8000";

interface SearchPageProps {
  searchParams: {
    q?: string;
    shop?: string;
    sort?: string;
  };
}

async function searchDeals(params: SearchPageProps["searchParams"]): Promise<{ deals: Deal[]; total: number }> {
  const query = params.q || "";
  if (!query.trim()) return { deals: [], total: 0 };

  try {
    const searchParams = new URLSearchParams();
    searchParams.set("q", query);
    searchParams.set("limit", "20");
    if (params.shop) searchParams.set("shop", params.shop);
    if (params.sort) searchParams.set("sort_by", params.sort === "newest" ? "newest" : params.sort === "score" ? "score" : "relevance");

    const res = await fetch(`${API_BASE}/api/v1/search?${searchParams.toString()}`, {
      next: { revalidate: 60 },
    });
    if (!res.ok) throw new Error("API error");
    const json: ApiResponse<Deal[]> = await res.json();
    return { deals: json.data, total: json.meta?.total ?? json.data.length };
  } catch {
    // Fallback to mock data
    const lowerQuery = query.toLowerCase();
    const deals = MOCK_DEALS.filter(
      (d) =>
        d.title.toLowerCase().includes(lowerQuery) ||
        d.shop.name.toLowerCase().includes(lowerQuery) ||
        d.category?.name.toLowerCase().includes(lowerQuery)
    );
    return { deals, total: deals.length };
  }
}

export default async function SearchPage({ searchParams }: SearchPageProps) {
  const query = searchParams.q || "";
  const { deals, total } = await searchDeals(searchParams);

  return (
    <div className="min-h-screen">
      {/* Shop filter */}
      <ShopFilter />

      {/* Main content */}
      <div className="mx-auto max-w-[1440px] px-4 py-6 sm:px-6">
        {/* Search header */}
        <div className="mb-6">
          <div className="flex items-center gap-3 text-gray-400">
            <Search className="h-5 w-5" />
            <span className="text-sm">검색 결과</span>
          </div>
          <h1 className="mt-2 text-2xl font-bold text-white">
            {query ? (
              <>
                &ldquo;<span className="text-accent">{query}</span>&rdquo; 검색
                결과
              </>
            ) : (
              "검색 결과"
            )}
          </h1>
          <p className="mt-1 text-sm text-gray-400">
            {total.toLocaleString()}개의 특가 상품
          </p>
        </div>

        {/* Controls */}
        <div className="mb-6 flex items-center justify-end">
          <SortDropdown />
        </div>

        {/* Results */}
        <DealGrid
          deals={deals}
          emptyMessage={
            query
              ? `"${query}"에 대한 검색 결과가 없습니다`
              : "검색 결과가 없습니다"
          }
        />
      </div>
    </div>
  );
}
