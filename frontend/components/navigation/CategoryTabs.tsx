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

// Map backend icon strings to Lucide icons
function getIconForSlug(slug: string, icon?: string) {
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
        const res = await fetch("/api/v1/categories", {
          next: { revalidate: 300 },
        } as RequestInit);
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
    <div className="border-t border-border/50 px-4 sm:px-6">
      <div className="scrollbar-hide flex gap-2 overflow-x-auto py-3">
        {categories.map((category) => {
          const Icon = getIconForSlug(category.slug, category.icon);
          const isActive = activeCategory === category.slug;

          return (
            <button
              key={category.slug}
              onClick={() => handleCategoryClick(category.slug)}
              className={cn(
                "category-chip whitespace-nowrap",
                isActive && "category-chip-active",
                isLoading && category.slug !== "all" && "opacity-0"
              )}
              aria-pressed={isActive}
            >
              <Icon className="h-4 w-4" />
              <span>{category.name}</span>
              {category.deal_count !== undefined && category.deal_count > 0 && (
                <span
                  className={cn(
                    "ml-1 rounded-full px-1.5 py-0.5 text-[10px] font-bold leading-none",
                    isActive
                      ? "bg-white/20 text-white"
                      : "bg-surface text-gray-400"
                  )}
                >
                  {category.deal_count}
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
              className="h-9 w-24 animate-pulse rounded-full bg-surface"
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
        <div className="border-t border-border/50 px-4 sm:px-6 py-3">
          <div className="flex gap-2">
            {Array.from({ length: 7 }).map((_, i) => (
              <div
                key={i}
                className="h-9 w-24 animate-pulse rounded-full bg-surface"
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
