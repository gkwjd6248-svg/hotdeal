import { formatPrice, calcDiscount } from "@/lib/utils";

interface PriceDisplayProps {
  dealPrice: number;
  originalPrice?: number | null;
  discountPercentage?: number | null;
  showBadge?: boolean;
  showSavings?: boolean;
  size?: "sm" | "md" | "lg";
  dealType?: string;
}

const DEAL_TYPE_LABELS: Record<string, { label: string; color: string }> = {
  flash_sale: { label: "타임딜", color: "bg-red-500/20 text-red-400 border-red-500/30" },
  coupon: { label: "쿠폰가", color: "bg-blue-500/20 text-blue-400 border-blue-500/30" },
  clearance: { label: "특가", color: "bg-orange-500/20 text-orange-400 border-orange-500/30" },
  price_drop: { label: "가격하락", color: "bg-green-500/20 text-green-400 border-green-500/30" },
  bundle: { label: "묶음할인", color: "bg-purple-500/20 text-purple-400 border-purple-500/30" },
};

export default function PriceDisplay({
  dealPrice,
  originalPrice,
  discountPercentage,
  showBadge = true,
  showSavings = false,
  size = "md",
  dealType,
}: PriceDisplayProps) {
  const hasDiscount = originalPrice && originalPrice > dealPrice;
  const discount =
    discountPercentage ??
    (hasDiscount ? calcDiscount(originalPrice, dealPrice) : 0);
  const savings = hasDiscount ? originalPrice - dealPrice : 0;

  const priceClass = {
    sm: "text-base",
    md: "text-xl",
    lg: "text-2xl",
  }[size];

  const originalPriceClass = {
    sm: "text-xs",
    md: "text-sm",
    lg: "text-base",
  }[size];

  const savingsClass = {
    sm: "text-[10px]",
    md: "text-xs",
    lg: "text-sm",
  }[size];

  const typeInfo = dealType ? DEAL_TYPE_LABELS[dealType] : null;

  return (
    <div className="flex flex-col gap-1">
      {/* Original price with strikethrough + deal type badge */}
      {hasDiscount && (
        <div className="flex items-center gap-2 flex-wrap">
          <span className={`price-original ${originalPriceClass}`}>
            {formatPrice(originalPrice)}
          </span>
          {showBadge && discount > 0 && (
            <span className="discount-badge">-{discount}%</span>
          )}
          {typeInfo && (
            <span className={`inline-flex items-center rounded-md border px-1.5 py-0.5 text-[10px] font-semibold ${typeInfo.color}`}>
              {typeInfo.label}
            </span>
          )}
        </div>
      )}

      {/* Deal price */}
      <div className={`price-deal ${priceClass}`}>{formatPrice(dealPrice)}</div>

      {/* Savings amount */}
      {showSavings && savings > 0 && (
        <p className={`${savingsClass} font-medium text-green-400`}>
          {formatPrice(savings)} 절약
        </p>
      )}
    </div>
  );
}
