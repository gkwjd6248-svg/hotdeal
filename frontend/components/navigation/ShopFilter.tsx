"use client";

import { Suspense } from "react";
import { useSearchParams, useRouter, usePathname } from "next/navigation";
import { SHOPS } from "@/lib/constants";
import { cn } from "@/lib/utils";
import { Check } from "lucide-react";

function ShopFilterInner() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();
  const selectedShops = searchParams.get("shop")?.split(",") || [];

  const handleShopClick = (slug: string) => {
    const params = new URLSearchParams(searchParams.toString());
    let newShops: string[];

    if (slug === "all") {
      // Clear all shop filters
      params.delete("shop");
    } else {
      // Toggle shop selection
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

            {/* Shop chips */}
            {SHOPS.map((shop) => {
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
    <Suspense fallback={<div className="border-y border-border/50 bg-card/30 px-4 py-3 sm:px-6" />}>
      <ShopFilterInner />
    </Suspense>
  );
}
