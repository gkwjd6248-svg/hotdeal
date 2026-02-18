"use client";

import { Suspense, useEffect, useState } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import { cn } from "@/lib/utils";
import {
  ShoppingBag,
  Laptop,
  Smartphone,
  Tv,
  Gamepad2,
  CreditCard,
  UtensilsCrossed,
  Tag,
} from "lucide-react";

interface ApiCategory {
  id: string;
  name: string;
  slug: string;
  icon?: string;
  deal_count?: number;
}

// Map backend slugs to Lucide icons
function getIconForSlug(slug: string, _icon?: string) {
  const iconMap: Record<string, React.ElementType> = {
    "pc-hardware": Laptop,
    "laptop-mobile": Smartphone,
    "electronics-tv": Tv,
    "games-software": Gamepad2,
    "gift-cards": CreditCard,
    "living-food": UtensilsCrossed,
    all: ShoppingBag,
  };
  return iconMap[slug] ?? Tag;
}

const ALL_CATEGORY: ApiCategory = {
  id: "all",
  name: "전체",
  slug: "all",
};

function CategoryTabsInner() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const activeCategory = searchParams.get("category") || "all";

  const [categories, setCategories] = useState<ApiCategory[]>([ALL_CATEGORY]);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;

    async function fetchCategories() {
      try {
        const res = await fetch("/api/v1/categories");
        if (!res.ok) throw new Error("Failed to fetch categories");
        const json = await res.json();
        if (!cancelled && json.status === "success") {
          setCategories([ALL_CATEGORY, ...json.data]);
        }
      } catch {
        // Keep showing the "전체" tab if fetch fails
      } finally {
        if (!cancelled) setIsLoading(false);
      }
    }

    fetchCategories();
    return () => {
      cancelled = true;
    };
  }, []);

  const handleCategoryClick = (slug: string) => {
    const params = new URLSearchParams(searchParams.toString());

    if (slug === "all") {
      params.delete("category");
    } else {
      params.set("category", slug);
    }

    // Always navigate to /deals with the filter applied
    router.push(`/deals?${params.toString()}`);
  };

  return (
    <div className="border-t border-border/40 px-4 sm:px-6">
      <div className="scrollbar-hide flex gap-1.5 overflow-x-auto py-2.5">
        {categories.map((category) => {
          const Icon = getIconForSlug(category.slug, category.icon);
          const isActive = activeCategory === category.slug;

          return (
            <button
              key={category.slug}
              onClick={() => handleCategoryClick(category.slug)}
              className={cn(
                "category-chip whitespace-nowrap flex-shrink-0",
                isActive && "category-chip-active",
                isLoading && category.slug !== "all" && "opacity-0 pointer-events-none"
              )}
              aria-pressed={isActive}
              aria-label={`${category.name} 카테고리${isActive ? " (선택됨)" : ""}`}
            >
              <Icon className="h-3.5 w-3.5 flex-shrink-0" />
              <span>{category.name}</span>
              {category.deal_count !== undefined && category.deal_count > 0 && (
                <span
                  className={cn(
                    "ml-0.5 rounded-full px-1.5 py-0.5 text-[10px] font-bold leading-none tabular-nums",
                    isActive
                      ? "bg-black/20 text-background"
                      : "bg-surface text-gray-400"
                  )}
                >
                  {category.deal_count > 999
                    ? `${Math.floor(category.deal_count / 1000)}k`
                    : category.deal_count}
                </span>
              )}
            </button>
          );
        })}

        {/* Skeleton pills while loading */}
        {isLoading &&
          Array.from({ length: 5 }).map((_, i) => (
            <div
              key={`skel-${i}`}
              className="skeleton h-9 w-24 flex-shrink-0 rounded-lg"
              style={{ animationDelay: `${i * 100}ms` }}
            />
          ))}
      </div>
    </div>
  );
}

export default function CategoryTabs() {
  return (
    <Suspense
      fallback={
        <div className="border-t border-border/40 px-4 sm:px-6 py-2.5">
          <div className="flex gap-1.5">
            {Array.from({ length: 7 }).map((_, i) => (
              <div
                key={i}
                className="skeleton h-9 w-24 flex-shrink-0 rounded-lg"
              />
            ))}
          </div>
        </div>
      }
    >
      <CategoryTabsInner />
    </Suspense>
  );
}
