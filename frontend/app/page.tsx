import { Suspense } from "react";
import Link from "next/link";
import ShopFilter from "@/components/navigation/ShopFilter";
import SortDropdown from "@/components/navigation/SortDropdown";
import InfiniteDealGrid from "@/components/deals/InfiniteDealGrid";
import DealCardSkeleton from "@/components/deals/DealCardSkeleton";
import { ApiResponse, Deal } from "@/lib/types";
import { Flame, Sparkles } from "lucide-react";

const API_BASE = process.env.BACKEND_URL || "http://localhost:8000";

const TRENDING_KEYWORDS = [
  "애플 에어팟",
  "삼성 갤럭시",
  "LG 그램",
  "다이슨 청소기",
  "아이패드",
];

async function getTotalDeals(): Promise<number> {
  try {
    const res = await fetch(`${API_BASE}/api/v1/deals?limit=1`, {
      next: { revalidate: 60 },
    });
    if (!res.ok) throw new Error("API error");
    const json: ApiResponse<Deal[]> = await res.json();
    return json.meta?.total ?? 0;
  } catch {
    return 0;
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

export default async function HomePage() {
  const total = await getTotalDeals();

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
                      {TRENDING_KEYWORDS.map((keyword, i) => (
                        <Link
                          key={keyword}
                          href={`/search?q=${encodeURIComponent(keyword)}`}
                          className="inline-flex items-center gap-1.5 rounded-full bg-surface px-3 py-1.5 text-xs font-medium text-gray-300 transition-colors hover:bg-card-hover hover:text-accent"
                        >
                          <span className="text-accent">{i + 1}</span>
                          {keyword}
                        </Link>
                      ))}
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
              {total > 0 && (
                <span className="text-sm font-normal text-gray-400">
                  ({total.toLocaleString()}개)
                </span>
              )}
            </h2>
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
