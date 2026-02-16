import { PackageOpen } from "lucide-react";
import Link from "next/link";

interface EmptyStateProps {
  title?: string;
  description?: string;
  actionLabel?: string;
  actionHref?: string;
}

export default function EmptyState({
  title = "특가 상품을 찾을 수 없습니다",
  description = "다른 카테고리를 탐색하거나 검색어를 변경해보세요.",
  actionLabel,
  actionHref,
}: EmptyStateProps) {
  return (
    <div className="flex min-h-[400px] flex-col items-center justify-center rounded-xl border border-dashed border-border bg-card/30 p-12 text-center">
      <div className="mb-4 rounded-full bg-surface p-4">
        <PackageOpen className="h-12 w-12 text-gray-500" />
      </div>
      <h3 className="mb-2 text-xl font-semibold text-gray-300">{title}</h3>
      <p className="mb-6 max-w-md text-sm text-gray-500">{description}</p>
      {actionLabel && actionHref && (
        <Link href={actionHref} className="btn-primary">
          {actionLabel}
        </Link>
      )}
    </div>
  );
}
