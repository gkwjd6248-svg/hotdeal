import { PackageOpen } from "lucide-react";
import Link from "next/link";

interface EmptyStateProps {
  title?: string;
  description?: string;
  actionLabel?: string;
  actionHref?: string;
  icon?: React.ReactNode;
}

export default function EmptyState({
  title = "특가 상품을 찾을 수 없습니다",
  description = "다른 카테고리를 탐색하거나 검색어를 변경해보세요.",
  actionLabel,
  actionHref,
  icon,
}: EmptyStateProps) {
  return (
    <div className="flex min-h-[400px] flex-col items-center justify-center rounded-2xl border border-dashed border-border bg-card/20 p-12 text-center">
      <div className="mb-5 flex h-20 w-20 items-center justify-center rounded-full bg-gradient-to-br from-surface to-card-hover shadow-lg">
        {icon ?? <PackageOpen className="h-10 w-10 text-gray-500" />}
      </div>
      <h3 className="mb-2 text-lg font-semibold text-gray-300">{title}</h3>
      <p className="mb-6 max-w-sm text-sm leading-relaxed text-gray-500">{description}</p>
      {actionLabel && actionHref && (
        <Link href={actionHref} className="btn-primary px-6 py-2.5 text-sm">
          {actionLabel}
        </Link>
      )}
    </div>
  );
}
