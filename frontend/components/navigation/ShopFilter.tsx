"use client";

import { Suspense, useEffect, useState } from "react";
import { useSearchParams, useRouter, usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import { Check } from "lucide-react";

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
          // Only show active shops that have deals
          const activeShops: ApiShop[] = json.data.filter(
            (s: ApiShop) => s.is_active
          );
          setShops(activeShops);
        }
      } catch {
        // Silently fail - show no shop filters
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

    // If on homepage, navigate to deals page; otherwise stay on current page
    const target = pathname === "/" ? "/deals" : pathname;
    const queryString = params.toString();
    router.push(queryString ? `${target}?${queryString}` : target);
  };

  const isAllSelected = selectedShops.length === 0;

  // Don't render the bar if there's only one shop (no meaningful filter)
  // but still show when loading to avoid layout shift
  if (!isLoading && shops.length <= 1) {
    return null;
  }

  return (
    <div className="border-y border-border/50 bg-card/30 px-4 py-3 sm:px-6">
      <div className="mx-auto max-w-[1440px]">
        <div className="flex items-center gap-3">
          <span className="text-sm font-medium text-gray-400">쇼핑몰:</span>
          <div className="scrollbar-hide flex flex-1 gap-2 overflow-x-auto">
            {/* All button */}
            <button
              onClick={() => handleShopClick("all")}
              className={cn(
                "shop-chip whitespace-nowrap",
                isAllSelected && "shop-chip-active"
              )}
            >
              {isAllSelected && <Check className="h-3 w-3" />}
              <span>전체</span>
            </button>

            {/* Shop chips from API */}
            {isLoading
              ? Array.from({ length: 4 }).map((_, i) => (
                  <div
                    key={`skel-${i}`}
                    className="h-8 w-20 animate-pulse rounded-full bg-surface"
                  />
                ))
              : shops.map((shop) => {
                  const isSelected = selectedShops.includes(shop.slug);

                  return (
                    <button
                      key={shop.slug}
                      onClick={() => handleShopClick(shop.slug)}
                      className={cn(
                        "shop-chip whitespace-nowrap",
                        isSelected && "shop-chip-active"
                      )}
                    >
                      {isSelected && <Check className="h-3 w-3" />}
                      <span>{shop.name}</span>
                      {shop.deal_count !== undefined && shop.deal_count > 0 && (
                        <span className="ml-1 text-[10px] text-gray-500">
                          {shop.deal_count.toLocaleString()}
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
        <div className="border-y border-border/50 bg-card/30 px-4 py-3 sm:px-6" />
      }
    >
      <ShopFilterInner />
    </Suspense>
  );
}
