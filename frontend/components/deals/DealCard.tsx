import Image from "next/image";
import Link from "next/link";
import { Deal } from "@/lib/types";
import PriceDisplay from "@/components/common/PriceDisplay";
import RelativeTime from "@/components/common/RelativeTime";
import ShopLogo from "@/components/common/ShopLogo";
import { Eye, ThumbsUp, MessageCircle } from "lucide-react";

interface DealCardProps {
  deal: Deal;
}

export default function DealCard({ deal }: DealCardProps) {
  const discountPercentage =
    deal.discount_percentage ??
    (deal.original_price && deal.original_price > deal.deal_price
      ? Math.round(
          ((deal.original_price - deal.deal_price) / deal.original_price) * 100
        )
      : null);

  return (
    <Link href={`/deals/${deal.id}`} className="group block">
      <article className="deal-card relative h-full overflow-hidden">
        {/* Image container */}
        <div className="relative mb-3 aspect-[4/3] w-full overflow-hidden rounded-lg bg-surface">
          {deal.image_url ? (
            <Image
              src={deal.image_url}
              alt={deal.title}
              fill
              className="object-cover transition-transform duration-300 group-hover:scale-105"
              sizes="(max-width: 640px) 100vw, (max-width: 1024px) 50vw, (max-width: 1440px) 33vw, 25vw"
            />
          ) : (
            <div className="flex h-full items-center justify-center">
              <span className="text-4xl text-gray-600">🏷️</span>
            </div>
          )}

          {/* Shop logo badge - top left */}
          <div className="absolute left-2 top-2">
            <ShopLogo name={deal.shop.name} logoUrl={deal.shop.logo_url} />
          </div>

          {/* Discount badge - top right */}
          {discountPercentage && discountPercentage > 0 && (
            <div className="absolute right-2 top-2">
              <div className="rounded-full bg-price-discount px-2.5 py-1 text-xs font-bold text-white shadow-lg">
                -{discountPercentage}%
              </div>
            </div>
          )}
        </div>

        {/* Content */}
        <div className="flex flex-col gap-2">
          {/* Title - max 2 lines */}
          <h3 className="line-clamp-2 min-h-[2.5rem] text-sm font-medium leading-tight text-gray-200">
            {deal.title}
          </h3>

          {/* Price */}
          <PriceDisplay
            dealPrice={deal.deal_price}
            originalPrice={deal.original_price}
            discountPercentage={discountPercentage}
            showBadge={false}
            size="md"
          />

          {/* Meta info */}
          <div className="flex items-center justify-between border-t border-border/50 pt-2 text-xs text-gray-400">
            <div className="flex items-center gap-2">
              <span className="font-medium text-gray-300">{deal.shop.name}</span>
              <span>•</span>
              <RelativeTime date={deal.created_at} />
            </div>

            {/* AI Score */}
            {deal.ai_score !== null && deal.ai_score > 0 && (
              <div className="flex items-center gap-1">
                <div
                  className="h-1.5 w-12 rounded-full bg-surface"
                  role="progressbar"
                  aria-valuenow={deal.ai_score}
                  aria-valuemin={0}
                  aria-valuemax={100}
                >
                  <div
                    className="h-full rounded-full bg-accent transition-all"
                    style={{ width: `${deal.ai_score}%` }}
                  />
                </div>
                <span className="text-xs font-medium text-accent">
                  AI {deal.ai_score}
                </span>
              </div>
            )}
          </div>

          {/* Stats row */}
          <div className="flex items-center gap-3 text-xs text-gray-500">
            <div className="flex items-center gap-1">
              <Eye className="h-3 w-3" />
              <span>{deal.view_count.toLocaleString()}</span>
            </div>
            <div className="flex items-center gap-1">
              <ThumbsUp className="h-3 w-3" />
              <span>{deal.vote_up.toLocaleString()}</span>
            </div>
            <div className="flex items-center gap-1">
              <MessageCircle className="h-3 w-3" />
              <span>{deal.comment_count.toLocaleString()}</span>
            </div>
          </div>
        </div>
      </article>
    </Link>
  );
}
