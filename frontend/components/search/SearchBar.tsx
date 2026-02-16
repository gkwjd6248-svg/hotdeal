"use client";

import { useState, useEffect, useRef } from "react";
import { useRouter } from "next/navigation";
import { Search, X } from "lucide-react";
import TrendingKeywords from "./TrendingKeywords";

export default function SearchBar() {
  const [query, setQuery] = useState("");
  const [showTrending, setShowTrending] = useState(false);
  const [debouncedQuery, setDebouncedQuery] = useState("");
  const router = useRouter();
  const searchRef = useRef<HTMLDivElement>(null);

  // Debounce search query
  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedQuery(query);
    }, 300);

    return () => clearTimeout(timer);
  }, [query]);

  // Handle search navigation
  const handleSearch = (searchQuery: string) => {
    if (searchQuery.trim()) {
      router.push(`/search?q=${encodeURIComponent(searchQuery.trim())}`);
      setShowTrending(false);
      setQuery(searchQuery);
    }
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    handleSearch(query);
  };

  const handleClear = () => {
    setQuery("");
    setShowTrending(false);
  };

  // Click outside to close trending
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (
        searchRef.current &&
        !searchRef.current.contains(event.target as Node)
      ) {
        setShowTrending(false);
      }
    };

    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  return (
    <div ref={searchRef} className="relative w-full">
      <form onSubmit={handleSubmit}>
        <div className="relative">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" />
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onFocus={() => setShowTrending(true)}
            placeholder="특가 상품 검색..."
            className="w-full rounded-lg border border-border bg-card py-2 pl-10 pr-10 text-sm text-gray-200 placeholder-gray-500 transition-colors focus:border-accent focus:outline-none focus:ring-2 focus:ring-accent/20"
            aria-label="검색어 입력"
          />
          {query && (
            <button
              type="button"
              onClick={handleClear}
              className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 transition-colors hover:text-gray-200"
              aria-label="검색어 지우기"
            >
              <X className="h-4 w-4" />
            </button>
          )}
        </div>
      </form>

      {/* Trending keywords dropdown */}
      {showTrending && !query && (
        <div className="animate-fade-in absolute top-full mt-2 w-full">
          <TrendingKeywords onSelect={handleSearch} />
        </div>
      )}
    </div>
  );
}
