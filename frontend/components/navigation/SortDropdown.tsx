"use client";

import { Suspense } from "react";
import { useSearchParams, useRouter, usePathname } from "next/navigation";
import { SORT_OPTIONS } from "@/lib/constants";
import { ArrowUpDown } from "lucide-react";

function SortDropdownInner() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();
  const currentSort = searchParams.get("sort") || "newest";

  const handleSortChange = (value: string) => {
    const params = new URLSearchParams(searchParams.toString());

    if (value === "newest") {
      params.delete("sort");
    } else {
      params.set("sort", value);
    }

    const queryString = params.toString();
    router.push(queryString ? `${pathname}?${queryString}` : pathname);
  };

  const currentLabel =
    SORT_OPTIONS.find((opt) => opt.value === currentSort)?.label || "최신순";

  return (
    <div className="relative inline-block">
      <label htmlFor="sort-select" className="sr-only">
        정렬 방식 선택
      </label>
      <div className="relative">
        <ArrowUpDown className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" />
        <select
          id="sort-select"
          value={currentSort}
          onChange={(e) => handleSortChange(e.target.value)}
          className="appearance-none rounded-lg border border-border bg-card py-2 pl-9 pr-10 text-sm font-medium text-gray-300 transition-colors hover:border-accent/50 hover:bg-card-hover focus:border-accent focus:outline-none focus:ring-2 focus:ring-accent/20"
        >
          {SORT_OPTIONS.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
        <div className="pointer-events-none absolute inset-y-0 right-0 flex items-center pr-3">
          <svg
            className="h-4 w-4 text-gray-400"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M19 9l-7 7-7-7"
            />
          </svg>
        </div>
      </div>
    </div>
  );
}

export default function SortDropdown() {
  return (
    <Suspense fallback={<div className="h-10 w-32 rounded-lg bg-card animate-pulse" />}>
      <SortDropdownInner />
    </Suspense>
  );
}
