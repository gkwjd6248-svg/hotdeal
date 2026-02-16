"use client";

import { Suspense } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import { CATEGORIES } from "@/lib/constants";
import { cn } from "@/lib/utils";

function CategoryTabsInner() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const activeCategory = searchParams.get("category") || "all";

  const handleCategoryClick = (slug: string) => {
    const params = new URLSearchParams(searchParams.toString());

    if (slug === "all") {
      params.delete("category");
    } else {
      params.set("category", slug);
    }

    // Navigate to deals page with category filter
    router.push(`/deals?${params.toString()}`);
  };

  return (
    <div className="border-t border-border/50 px-4 sm:px-6">
      <div className="scrollbar-hide flex gap-2 overflow-x-auto py-3">
        {CATEGORIES.map((category) => {
          const Icon = category.icon;
          const isActive = activeCategory === category.slug;

          return (
            <button
              key={category.slug}
              onClick={() => handleCategoryClick(category.slug)}
              className={cn(
                "category-chip whitespace-nowrap",
                isActive && "category-chip-active"
              )}
              aria-pressed={isActive}
            >
              <Icon className="h-4 w-4" />
              <span>{category.name}</span>
            </button>
          );
        })}
      </div>
    </div>
  );
}

export default function CategoryTabs() {
  return (
    <Suspense fallback={<div className="border-t border-border/50 px-4 sm:px-6 py-3" />}>
      <CategoryTabsInner />
    </Suspense>
  );
}
