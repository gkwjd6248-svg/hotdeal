
"use client";

import Image from "next/image";
import Link from "next/link";
import { useState } from "react";
import { Deal } from "@/lib/types";
import PriceDisplay from "@/components/common/PriceDisplay";
import RelativeTime from "@/components/common/RelativeTime";
import ShopLogo from "@/components/common/ShopLogo";
import { Eye, ThumbsUp, MessageCircle, Sparkles, Tag } from "lucide-react";

interface DealCardProps {
  deal: Deal;
  featured?: boolean;
}

function AiScoreBadge({ score }: { score: number }) {
  if (score >= 80) {
    return (
      <span className="ai-score-badge-high">
        <Sparkles className="h-2.5 w-2.5" />
        {score}
      </span>
    );
  }
  if (score >= 50) {
    return (
      <span className="ai-score-badge-medium">
        <Sparkles className="h-2.5 w-2.5" />
        {score}
      </span>
    );
  }
  return (
    <span className="ai-score-badge-low">
      <Sparkles className="h-2.5 w-2.5" />
      {score}
    </span>
  );
}

export default function DealCard({ deal, featured = false }: DealCardProps) {
  const [imgError, setImgError] = useState(false);

  const discountPercentage =
    deal.discount_percentage ??
    (deal.original_price && deal.original_price > deal.deal_price
      ? Math.round(
          ((deal.original_price - deal.deal_price) / deal.original_price) * 100
        )
      : null);

  const cardClass = featured ? "deal-card-featured" : "deal-card";

  return (
    <Link href={`/deals/${deal.id}`} className="group block">
      <article className={`${cardClass} relative h-full overflow-hidden`}>
        {/* Image container */}
        <div className="relative mb-3 aspect-[4/3] w-full overflow-hidden rounded-lg bg-surface">
          {deal.image_url && !imgError ? (
            <Image
              src={deal.image_url}
              alt={deal.title}
              fill
              className="object-cover transition-transform duration-500 group-hover:scale-[1.08]"
              sizes="(max-width: 640px) 100vw, (max-width: 1024px) 50vw, (max-width: 1440px) 33vw, 25vw"
              onError={() => setImgError(true)}
            />
          ) : (
            <div className="flex h-full items-center justify-center bg-gradient-to-br from-surface to-card-hover">
              <Tag className="h-10 w-10 text-gray-600" />
            </div>
          )}

          {/* Gradient overlay on hover */}
          <div className="absolute inset-0 bg-gradient-to-t from-black/20 to-transparent opacity-0 transition-opacity duration-300 group-hover:opacity-100" />

          {/* Shop logo badge - top left */}
          <div className="absolute left-2 top-2">
            <ShopLogo name={deal.shop.name} logoUrl={deal.shop.logo_url} />
          </div>

          {/* Discount badge - top right */}
          {discountPercentage && discountPercentage > 0 && (
            <div className="absolute right-2 top-2">
              <div className="discount-badge-prominent">
                -{discountPercentage}%
              </div>
            </div>
          )}
        </div>

        {/* Content */}
        <div className="flex flex-col gap-2">
          {/* Title - max 2 lines */}
          <h3 className="line-clamp-2 min-h-[2.5rem] text-sm font-medium leading-tight text-gray-200 transition-colors group-hover:text-white">
            {deal.title}
          </h3>

          {/* Price */}
          <PriceDisplay
            dealPrice={deal.deal_price}
            originalPrice={deal.original_price}
            discountPercentage={discountPercentage}
            showBadge={false}
            showSavings={true}
            size="md"
            dealType={deal.deal_type}
          />

          {/* Meta info row */}
          <div className="flex items-center justify-between border-t border-border/50 pt-2 text-xs text-gray-400">
            <div className="flex items-center gap-1.5 min-w-0">
              <span className="font-medium text-gray-300 truncate">{deal.shop.name}</span>
              <span className="flex-shrink-0">·</span>
              <RelativeTime date={deal.created_at} />
            </div>

            {/* AI Score Badge */}
            {deal.ai_score !== null && deal.ai_score > 0 && (
              <AiScoreBadge score={deal.ai_score} />
            )}
          </div>

          {/* Stats row */}
          <div className="flex items-center gap-3 text-xs text-gray-500">
            <div className="flex items-center gap-1 hover:text-gray-400 transition-colors">
              <Eye className="h-3 w-3" />
              <span>{deal.view_count.toLocaleString()}</span>
            </div>
            <div className="flex items-center gap-1 hover:text-gray-400 transition-colors">
              <ThumbsUp className="h-3 w-3" />
              <span>{deal.vote_up.toLocaleString()}</span>
            </div>
            <div className="flex items-center gap-1 hover:text-gray-400 transition-colors">
              <MessageCircle className="h-3 w-3" />
              <span>{deal.comment_count.toLocaleString()}</span>
            </div>
          </div>
        </div>
      </article>
    </Link>
  );
}
