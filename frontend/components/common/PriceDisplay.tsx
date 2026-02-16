import { formatPrice, calcDiscount } from "@/lib/utils";

interface PriceDisplayProps {
  dealPrice: number;
  originalPrice?: number | null;
  discountPercentage?: number | null;
  showBadge?: boolean;
  size?: "sm" | "md" | "lg";
}

export default function PriceDisplay({
  dealPrice,
  originalPrice,
  discountPercentage,
  showBadge = true,
  size = "md",
}: PriceDisplayProps) {
  const hasDiscount = originalPrice && originalPrice > dealPrice;
  const discount =
    discountPercentage ??
    (hasDiscount ? calcDiscount(originalPrice, dealPrice) : 0);

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

  return (
    <div className="flex flex-col gap-1">
      {/* Original price with strikethrough */}
      {hasDiscount && (
        <div className="flex items-center gap-2">
          <span className={`price-original ${originalPriceClass}`}>
            {formatPrice(originalPrice)}
          </span>
          {showBadge && discount > 0 && (
            <span className="discount-badge">-{discount}%</span>
          )}
        </div>
      )}

      {/* Deal price */}
      <div className={`price-deal ${priceClass}`}>{formatPrice(dealPrice)}</div>
    </div>
  );
}
