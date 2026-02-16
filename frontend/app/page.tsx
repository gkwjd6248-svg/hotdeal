import DealGrid from "@/components/deals/DealGrid";
import ShopFilter from "@/components/navigation/ShopFilter";
import SortDropdown from "@/components/navigation/SortDropdown";
import TrendingKeywords from "@/components/search/TrendingKeywords";
import { MOCK_DEALS } from "@/lib/mock-data";
import { Deal, ApiResponse } from "@/lib/types";
import { Flame, Sparkles } from "lucide-react";

const API_BASE = process.env.BACKEND_URL || "http://localhost:8000";

async function getDeals(): Promise<Deal[]> {
  try {
    const res = await fetch(`${API_BASE}/api/v1/deals?limit=20&sort_by=newest`, {
      next: { revalidate: 60 },
    });
    if (!res.ok) throw new Error("API error");
    const json: ApiResponse<Deal[]> = await res.json();
    return json.data;
  } catch {
    // Fallback to mock data if API is unavailable
    return MOCK_DEALS;
  }
}

export default async function HomePage() {
  const deals = await getDeals();

  return (
    <div className="min-h-screen">
      {/* Hero section */}
      <section className="border-b border-border bg-gradient-to-b from-surface/30 to-background">
        <div className="mx-auto max-w-[1440px] px-4 py-8 sm:px-6 sm:py-12">
          <div className="text-center">
            <div className="mb-4 inline-flex items-center gap-2 rounded-full bg-accent/10 px-4 py-2 text-accent">
              <Sparkles className="h-4 w-4" />
              <span className="text-sm font-semibold">AI 추천</span>
            </div>
            <h1 className="mb-4 text-3xl font-bold text-white sm:text-4xl lg:text-5xl">
              AI가 찾은 오늘의{" "}
              <span className="text-accent">특가</span>
            </h1>
            <p className="mb-8 text-lg text-gray-400">
              주요 쇼핑몰의 최고 할인 상품을 한눈에 비교하세요
            </p>

            {/* Trending keywords - desktop only */}
            <div className="hidden md:block">
              <div className="mx-auto max-w-2xl">
                <div className="flex items-start gap-3 rounded-lg border border-border/50 bg-card/50 p-4">
                  <Flame className="mt-1 h-5 w-5 flex-shrink-0 text-accent" />
                  <div className="flex-1">
                    <h2 className="mb-2 text-left text-sm font-semibold text-gray-300">
                      실시간 인기 검색어
                    </h2>
                    <div className="flex flex-wrap gap-2">
                      {["애플 에어팟", "삼성 갤럭시", "LG 그램", "다이슨 청소기", "아이패드"].map(
                        (keyword, i) => (
                          <a
                            key={keyword}
                            href={`/search?q=${encodeURIComponent(keyword)}`}
                            className="inline-flex items-center gap-1.5 rounded-full bg-surface px-3 py-1.5 text-xs font-medium text-gray-300 transition-colors hover:bg-card-hover hover:text-accent"
                          >
                            <span className="text-accent">{i + 1}</span>
                            {keyword}
                          </a>
                        )
                      )}
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Shop filter */}
      <ShopFilter />

      {/* Main content */}
      <div className="mx-auto max-w-[1440px] px-4 py-6 sm:px-6">
        {/* Controls bar */}
        <div className="mb-6 flex items-center justify-between">
          <div>
            <h2 className="text-lg font-semibold text-white">
              전체 특가{" "}
              <span className="text-sm font-normal text-gray-400">
                ({deals.length.toLocaleString()}개)
              </span>
            </h2>
          </div>
          <SortDropdown />
        </div>

        {/* Deal grid */}
        <DealGrid deals={deals} />
      </div>
    </div>
  );
}
