import Link from "next/link";
import { Flame, ChevronRight } from "lucide-react";
import { Deal, ApiResponse } from "@/lib/types";
import DealCard from "./DealCard";

const API_BASE = process.env.BACKEND_URL || "http://localhost:8000";

async function getTopDeals(): Promise<Deal[]> {
  try {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 5000);
    const res = await fetch(
      `${API_BASE}/api/v1/deals?limit=4&sort_by=score`,
      {
        next: { revalidate: 120 },
        signal: controller.signal,
      }
    );
    clearTimeout(timeout);
    if (!res.ok) throw new Error("API error");
    const json: ApiResponse<Deal[]> = await res.json();
    if (json.status === "success" && Array.isArray(json.data)) {
      return json.data;
    }
    return [];
  } catch {
    return [];
  }
}

export default async function TopDealsSection() {
  const topDeals = await getTopDeals();

  if (topDeals.length === 0) return null;

  return (
    <section className="border-b border-border/50 bg-gradient-to-b from-accent/5 to-transparent py-8">
      <div className="mx-auto max-w-[1440px] px-4 sm:px-6">
        {/* Section header */}
        <div className="mb-5 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-br from-orange-500 to-red-500 shadow-lg shadow-orange-500/30">
              <Flame className="h-4 w-4 text-white" />
            </div>
            <div>
              <h2 className="text-lg font-bold text-white">
                TOP 특가{" "}
                <span className="text-sm font-normal text-gray-400">
                  AI 추천 최고점수
                </span>
              </h2>
            </div>
          </div>
          <Link
            href="/deals?sort=score"
            className="flex items-center gap-1 text-sm font-medium text-accent transition-colors hover:text-accent-hover"
          >
            전체 보기
            <ChevronRight className="h-4 w-4" />
          </Link>
        </div>

        {/* Top deals grid */}
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {topDeals.map((deal, index) => (
            <div
              key={deal.id}
              className="animate-fade-in"
              style={{ animationDelay: `${index * 80}ms` }}
            >
              {/* Rank badge overlay wrapper */}
              <div className="relative">
                <div className="absolute -left-1 -top-1 z-10 flex h-6 w-6 items-center justify-center rounded-full bg-gradient-to-br from-orange-500 to-red-600 text-[11px] font-bold text-white shadow-md">
                  {index + 1}
                </div>
                <DealCard deal={deal} featured />
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
