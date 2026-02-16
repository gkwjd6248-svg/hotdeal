import { Deal } from "@/lib/types";
import DealCard from "./DealCard";
import DealCardSkeleton from "./DealCardSkeleton";
import EmptyState from "@/components/common/EmptyState";

interface DealGridProps {
  deals: Deal[];
  loading?: boolean;
  emptyMessage?: string;
}

export default function DealGrid({
  deals,
  loading = false,
  emptyMessage = "특가 상품을 찾을 수 없습니다",
}: DealGridProps) {
  if (loading) {
    return (
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
        {Array.from({ length: 12 }).map((_, i) => (
          <DealCardSkeleton key={i} />
        ))}
      </div>
    );
  }

  if (deals.length === 0) {
    return (
      <EmptyState
        title={emptyMessage}
        description="다른 카테고리를 탐색하거나 검색어를 변경해보세요."
        actionLabel="전체 특가 보기"
        actionHref="/deals"
      />
    );
  }

  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
      {deals.map((deal) => (
        <DealCard key={deal.id} deal={deal} />
      ))}
    </div>
  );
}
