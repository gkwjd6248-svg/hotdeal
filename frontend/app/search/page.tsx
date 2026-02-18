import { Suspense } from "react";
import SortDropdown from "@/components/navigation/SortDropdown";
import SearchResults from "@/components/search/SearchResults";
import DealCardSkeleton from "@/components/deals/DealCardSkeleton";
import { Search, Sparkles, TrendingUp } from "lucide-react";
import Link from "next/link";

interface SearchPageProps {
  searchParams: {
    q?: string;
    sort?: string;
  };
}

const POPULAR_SEARCHES = [
  "스팀 게임",
  "애플 에어팟",
  "삼성 갤럭시",
  "LG 그램",
  "다이슨 청소기",
  "아이패드",
  "게이밍 마우스",
  "무선 이어폰",
];

function SearchGridSkeleton() {
  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
      {Array.from({ length: 8 }).map((_, i) => (
        <DealCardSkeleton key={i} />
      ))}
    </div>
  );
}

export default async function SearchPage({ searchParams }: SearchPageProps) {
  const query = searchParams.q?.trim() || "";
  const sort = searchParams.sort || "";

  return (
    <div className="min-h-screen">
      <div className="mx-auto max-w-[1440px] px-4 py-6 sm:px-6">
        {/* Search header */}
        <div className="mb-6 border-b border-border/50 pb-6">
          <div className="flex items-center gap-2 mb-2">
            <Search className="h-4 w-4 text-gray-500" />
            <span className="text-xs font-semibold uppercase tracking-wide text-gray-500">
              검색 결과
            </span>
          </div>
          <h1 className="text-xl font-bold text-white sm:text-2xl">
            {query ? (
              <>
                &ldquo;<span className="text-accent">{query}</span>&rdquo;{" "}
                <span className="text-gray-400 font-normal text-lg">검색 결과</span>
              </>
            ) : (
              "검색어를 입력하세요"
            )}
          </h1>
        </div>

        {query ? (
          <>
            {/* Controls */}
            <div className="mb-5 flex items-center justify-between gap-4">
              <div className="flex items-center gap-2 text-xs text-gray-500">
                <Sparkles className="h-3.5 w-3.5 text-accent" />
                <span>AI 관련성 순으로 정렬됩니다</span>
              </div>
              <SortDropdown />
            </div>

            {/* Results */}
            <Suspense fallback={<SearchGridSkeleton />}>
              <SearchResults query={query} sort={sort} />
            </Suspense>
          </>
        ) : (
          /* No query — show empty state with popular searches */
          <div className="flex flex-col items-center py-16 text-center">
            <div className="mb-6 flex h-20 w-20 items-center justify-center rounded-full bg-gradient-to-br from-surface to-card-hover">
              <Search className="h-10 w-10 text-gray-500" />
            </div>
            <h2 className="mb-2 text-lg font-semibold text-gray-300">
              검색어를 입력해주세요
            </h2>
            <p className="mb-8 text-sm text-gray-500">
              상품명, 카테고리, 쇼핑몰로 특가 상품을 찾을 수 있습니다
            </p>

            {/* Popular searches */}
            <div className="w-full max-w-lg">
              <div className="mb-3 flex items-center justify-center gap-2">
                <TrendingUp className="h-4 w-4 text-accent" />
                <span className="text-sm font-semibold text-gray-400">인기 검색어</span>
              </div>
              <div className="flex flex-wrap justify-center gap-2">
                {POPULAR_SEARCHES.map((term, i) => (
                  <Link
                    key={term}
                    href={`/search?q=${encodeURIComponent(term)}`}
                    className="inline-flex items-center gap-1.5 rounded-full border border-border bg-card px-3 py-1.5 text-sm text-gray-300 transition-all hover:border-accent/40 hover:bg-card-hover hover:text-accent"
                  >
                    <span className="text-xs font-bold text-accent/60">{i + 1}</span>
                    {term}
                  </Link>
                ))}
              </div>
            </div>

            <div className="mt-10">
              <Link
                href="/deals"
                className="btn-primary px-8 py-3 text-sm"
              >
                전체 특가 둘러보기
              </Link>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
