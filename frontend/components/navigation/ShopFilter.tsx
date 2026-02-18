"use client";

import { Suspense, useEffect, useState } from "react";
import { useSearchParams, useRouter, usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import { Store, Check } from "lucide-react";

interface ApiShop {
  id: string;
  name: string;
  slug: string;
  logo_url: string | null;
  is_active: boolean;
  country: string;
  deal_count?: number;
}

function ShopFilterInner() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();
  const selectedShops = searchParams.get("shop")?.split(",").filter(Boolean) || [];

  const [shops, setShops] = useState<ApiShop[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;

    async function fetchShops() {
      try {
        const res = await fetch("/api/v1/shops");
        if (!res.ok) throw new Error("Failed to fetch shops");
        const json = await res.json();
        if (!cancelled && json.status === "success") {
          const activeShops: ApiShop[] = json.data.filter(
            (s: ApiShop) => s.is_active
          );
          setShops(activeShops);
        }
      } catch {
        // Silently fail
      } finally {
        if (!cancelled) setIsLoading(false);
      }
    }

    fetchShops();
    return () => {
      cancelled = true;
    };
  }, []);

  const handleShopClick = (slug: string) => {
    const params = new URLSearchParams(searchParams.toString());
    let newShops: string[];

    if (slug === "all") {
      params.delete("shop");
    } else {
      if (selectedShops.includes(slug)) {
        newShops = selectedShops.filter((s) => s !== slug);
      } else {
        newShops = [...selectedShops, slug];
      }

      if (newShops.length === 0) {
        params.delete("shop");
      } else {
        params.set("shop", newShops.join(","));
      }
    }

    const target = pathname === "/" ? "/deals" : pathname;
    const queryString = params.toString();
    router.push(queryString ? `${target}?${queryString}` : target);
  };

  const isAllSelected = selectedShops.length === 0;

  // Don't render the bar if there's only one shop (no meaningful filter)
  if (!isLoading && shops.length <= 1) {
    return null;
  }

  return (
    <div className="border-y border-border/50 bg-card/20 px-4 py-2.5 sm:px-6">
      <div className="mx-auto max-w-[1440px]">
        <div className="flex items-center gap-3">
          {/* Label */}
          <div className="flex items-center gap-1.5 flex-shrink-0">
            <Store className="h-3.5 w-3.5 text-gray-500" />
            <span className="text-xs font-semibold uppercase tracking-wide text-gray-500">
              쇼핑몰
            </span>
          </div>

          {/* Divider */}
          <div className="h-4 w-px bg-border flex-shrink-0" />

          <div className="scrollbar-hide flex flex-1 gap-1.5 overflow-x-auto">
            {/* All button */}
            <button
              onClick={() => handleShopClick("all")}
              className={cn(
                "shop-chip whitespace-nowrap flex-shrink-0",
                isAllSelected && "shop-chip-active"
              )}
              aria-pressed={isAllSelected}
            >
              {isAllSelected && <Check className="h-3 w-3 flex-shrink-0" />}
              <span>전체</span>
            </button>

            {/* Divider */}
            <div className="my-1 w-px bg-border/50 flex-shrink-0" />

            {/* Shop chips from API */}
            {isLoading
              ? Array.from({ length: 4 }).map((_, i) => (
                  <div
                    key={`skel-${i}`}
                    className="skeleton h-7 w-16 flex-shrink-0 rounded-full"
                  />
                ))
              : shops.map((shop) => {
                  const isSelected = selectedShops.includes(shop.slug);

                  return (
                    <button
                      key={shop.slug}
                      onClick={() => handleShopClick(shop.slug)}
                      className={cn(
                        "shop-chip whitespace-nowrap flex-shrink-0",
                        isSelected && "shop-chip-active"
                      )}
                      aria-pressed={isSelected}
                    >
                      {isSelected && <Check className="h-3 w-3 flex-shrink-0" />}
                      <span>{shop.name}</span>
                      {shop.deal_count !== undefined && shop.deal_count > 0 && (
                        <span
                          className={cn(
                            "rounded-full px-1.5 py-0.5 text-[9px] font-bold tabular-nums",
                            isSelected
                              ? "bg-accent/20 text-accent"
                              : "bg-surface text-gray-500"
                          )}
                        >
                          {shop.deal_count > 999
                            ? `${Math.floor(shop.deal_count / 1000)}k`
                            : shop.deal_count}
                        </span>
                      )}
                    </button>
                  );
                })}
          </div>
        </div>
      </div>
    </div>
  );
}

export default function ShopFilter() {
  return (
    <Suspense
      fallback={
        <div className="border-y border-border/50 bg-card/20 px-4 py-2.5 sm:px-6">
          <div className="h-7" />
        </div>
      }
    >
      <ShopFilterInner />
    </Suspense>
  );
}
