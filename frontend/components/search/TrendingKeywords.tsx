"use client";

import { TRENDING_KEYWORDS } from "@/lib/constants";
import { TrendingUp } from "lucide-react";

interface TrendingKeywordsProps {
  onSelect: (keyword: string) => void;
}

export default function TrendingKeywords({ onSelect }: TrendingKeywordsProps) {
  return (
    <div className="rounded-lg border border-border bg-card shadow-xl">
      <div className="flex items-center gap-2 border-b border-border/50 px-4 py-3">
        <TrendingUp className="h-4 w-4 text-accent" />
        <span className="text-sm font-semibold text-gray-300">
          실시간 인기 검색어
        </span>
      </div>
      <div className="p-2">
        {TRENDING_KEYWORDS.map((keyword, index) => (
          <button
            key={keyword}
            onClick={() => onSelect(keyword)}
            className="flex w-full items-center gap-3 rounded-md px-3 py-2 text-left transition-colors hover:bg-card-hover"
          >
            <span className="flex h-5 w-5 items-center justify-center rounded bg-accent/20 text-xs font-bold text-accent">
              {index + 1}
            </span>
            <span className="text-sm text-gray-300">{keyword}</span>
          </button>
        ))}
      </div>
    </div>
  );
}
