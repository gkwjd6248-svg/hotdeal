import { Suspense } from "react";
import Link from "next/link";
import ShopFilter from "@/components/navigation/ShopFilter";
import SortDropdown from "@/components/navigation/SortDropdown";
import InfiniteDealGrid from "@/components/deals/InfiniteDealGrid";
import DealCardSkeleton from "@/components/deals/DealCardSkeleton";
import TopDealsSection from "@/components/deals/TopDealsSection";
import { ApiResponse, Deal } from "@/lib/types";
import { Flame, Sparkles, Search, TrendingUp } from "lucide-react";

const API_BASE = process.env.BACKEND_URL || "http://localhost:8000";

const TRENDING_KEYWORDS = [
  "스팀 게임",
  "애플 에어팟",
  "삼성 갤럭시",
  "LG 그램",
  "다이슨 청소기",
  "아이패드",
];

async function getTotalDeals(): Promise<number> {
  try {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 5000);
    const res = await fetch(`${API_BASE}/api/v1/deals?limit=1`, {
      next: { revalidate: 60 },
      signal: controller.signal,
    });
    clearTimeout(timeout);
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

function TopDealsSkeleton() {
  return (
    <section className="border-b border-border/50 bg-gradient-to-b from-accent/5 to-transparent py-8">
      <div className="mx-auto max-w-[1440px] px-4 sm:px-6">
        <div className="mb-5 flex items-center gap-3">
          <div className="h-8 w-8 animate-pulse rounded-lg bg-surface" />
          <div className="h-6 w-40 animate-pulse rounded bg-surface" />
        </div>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <DealCardSkeleton key={i} />
          ))}
        </div>
      </div>
    </section>
  );
}

export default async function HomePage() {
  const total = await getTotalDeals();

  return (
    <div className="min-h-screen">
      {/* Hero section - enhanced gradient */}
      <section className="relative overflow-hidden border-b border-border">
        {/* Background decorative elements */}
        <div className="pointer-events-none absolute inset-0 overflow-hidden">
          <div className="absolute -left-20 -top-20 h-80 w-80 rounded-full bg-accent/5 blur-[100px]" />
          <div className="absolute -right-20 top-10 h-60 w-60 rounded-full bg-orange-600/5 blur-[80px]" />
          <div className="absolute bottom-0 left-1/2 h-40 w-[600px] -translate-x-1/2 rounded-full bg-accent/5 blur-[60px]" />
        </div>

        <div className="relative mx-auto max-w-[1440px] px-4 py-10 sm:px-6 sm:py-14">
          <div className="text-center">
            {/* AI badge */}
            <div className="mb-5 inline-flex items-center gap-2 rounded-full border border-accent/30 bg-accent/10 px-4 py-2 text-accent shadow-lg shadow-accent/10">
              <Sparkles className="h-4 w-4" />
              <span className="text-sm font-semibold">AI 자동 수집</span>
              <span className="h-1 w-1 rounded-full bg-accent/50" />
              <span className="text-sm text-accent/80">실시간 업데이트</span>
            </div>

            {/* Main heading */}
            <h1 className="mb-4 text-3xl font-extrabold tracking-tight text-white sm:text-4xl lg:text-5xl">
              AI가 찾은 오늘의{" "}
              <span className="relative">
                <span className="gradient-text">특가</span>
                <span className="absolute -bottom-1 left-0 h-0.5 w-full bg-gradient-to-r from-accent to-yellow-400 opacity-60" />
              </span>
            </h1>

            <p className="mb-8 text-base text-gray-400 sm:text-lg">
              주요 쇼핑몰의 최고 할인 상품을 한눈에 비교하세요
              {total > 0 && (
                <span className="ml-2 font-semibold text-accent">
                  현재 {total.toLocaleString()}개 특가
                </span>
              )}
            </p>

            {/* Search CTA */}
            <div className="mb-8 flex justify-center">
              <Link
                href="/search"
                className="flex items-center gap-3 rounded-xl border border-border bg-card/80 px-6 py-3.5 text-left text-sm text-gray-400 shadow-lg backdrop-blur-sm transition-all hover:border-accent/50 hover:bg-card hover:shadow-accent/10 sm:w-80"
              >
                <Search className="h-4 w-4 flex-shrink-0 text-gray-500" />
                <span>특가 검색...</span>
                <kbd className="ml-auto hidden rounded bg-surface px-2 py-0.5 text-[10px] text-gray-500 sm:block">
                  /
                </kbd>
              </Link>
            </div>

            {/* Trending keywords */}
            <div className="hidden md:block">
              <div className="mx-auto max-w-2xl">
                <div className="flex items-start gap-3 rounded-xl border border-border/60 bg-card/50 p-4 backdrop-blur-sm">
                  <div className="flex items-center gap-1.5 flex-shrink-0 pt-0.5">
                    <TrendingUp className="h-4 w-4 text-accent" />
                    <span className="text-xs font-semibold text-gray-400 whitespace-nowrap">
                      인기 검색
                    </span>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {TRENDING_KEYWORDS.map((keyword, i) => (
                      <Link
                        key={keyword}
                        href={`/search?q=${encodeURIComponent(keyword)}`}
                        className="inline-flex items-center gap-1.5 rounded-full bg-surface px-3 py-1 text-xs font-medium text-gray-300 transition-all hover:bg-card-hover hover:text-accent hover:shadow-sm"
                      >
                        <span className="font-bold text-accent/70">{i + 1}</span>
                        {keyword}
                      </Link>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* TOP 특가 Section - AI top scored deals */}
      <Suspense fallback={<TopDealsSkeleton />}>
        <TopDealsSection />
      </Suspense>

      {/* Shop filter */}
      <ShopFilter />

      {/* Main content */}
      <div className="mx-auto max-w-[1440px] px-4 py-6 sm:px-6">
        {/* Controls bar */}
        <div className="mb-6 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Flame className="h-5 w-5 text-accent" />
            <h2 className="text-lg font-semibold text-white">
              전체 특가
              {total > 0 && (
                <span className="ml-2 text-sm font-normal text-gray-400">
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
