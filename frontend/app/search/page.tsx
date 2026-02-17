import { Suspense } from "react";
import SortDropdown from "@/components/navigation/SortDropdown";
import SearchResults from "@/components/search/SearchResults";
import DealCardSkeleton from "@/components/deals/DealCardSkeleton";
import { Search } from "lucide-react";
import Link from "next/link";

interface SearchPageProps {
  searchParams: {
    q?: string;
    sort?: string;
  };
}

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
              "검색어를 입력하세요"
            )}
          </h1>
        </div>

        {query ? (
          <>
            {/* Controls */}
            <div className="mb-6 flex items-center justify-end">
              <SortDropdown />
            </div>

            {/* Results */}
            <Suspense fallback={<SearchGridSkeleton />}>
              <SearchResults query={query} sort={sort} />
            </Suspense>
          </>
        ) : (
          /* No query state */
          <div className="flex flex-col items-center justify-center py-20 text-center">
            <Search className="mb-4 h-16 w-16 text-gray-600" />
            <p className="mb-2 text-lg font-medium text-gray-300">
              검색어를 입력해주세요
            </p>
            <p className="mb-6 text-sm text-gray-500">
              상품명, 카테고리, 쇼핑몰로 검색할 수 있습니다
            </p>
            <Link
              href="/deals"
              className="rounded-lg bg-accent px-6 py-2.5 text-sm font-semibold text-black transition-opacity hover:opacity-90"
            >
              전체 특가 보기
            </Link>
          </div>
        )}
      </div>
    </div>
  );
}
