import { notFound } from "next/navigation";
import { Metadata } from "next";
import Link from "next/link";
import DealGrid from "@/components/deals/DealGrid";
import SortDropdown from "@/components/navigation/SortDropdown";
import { MOCK_DEALS } from "@/lib/mock-data";
import { SHOPS } from "@/lib/constants";
import { Deal, ApiResponse } from "@/lib/types";
import { Store, Globe, MapPin } from "lucide-react";

const API_BASE = process.env.BACKEND_URL || "http://localhost:8000";

interface ShopPageProps {
  params: Promise<{ slug: string }>;
  searchParams: { sort?: string };
}

async function getShopDeals(
  slug: string,
  params: { sort?: string }
): Promise<{ deals: Deal[]; total: number }> {
  try {
    const searchParams = new URLSearchParams();
    searchParams.set("limit", "20");
    if (params.sort) searchParams.set("sort_by", params.sort);

    const res = await fetch(
      `${API_BASE}/api/v1/shops/${slug}/deals?${searchParams.toString()}`,
      { next: { revalidate: 60 } }
    );
    if (!res.ok) throw new Error("API error");
    const json: ApiResponse<Deal[]> = await res.json();
    return { deals: json.data, total: json.meta?.total ?? json.data.length };
  } catch {
    const deals = MOCK_DEALS.filter((d) => d.shop.slug === slug);
    return { deals, total: deals.length };
  }
}

const COUNTRY_LABELS: Record<string, string> = {
  KR: "한국",
  US: "미국",
  CN: "중국",
};

export async function generateMetadata({
  params,
}: ShopPageProps): Promise<Metadata> {
  const { slug } = await params;
  const shop = SHOPS.find((s) => s.slug === slug);

  if (!shop) {
    return {
      title: "쇼핑몰을 찾을 수 없습니다",
    };
  }

  const title = `${shop.name} 특가 모음 - DealHawk`;
  const description = `${shop.name}의 최신 특가 상품을 한눈에! AI가 자동으로 찾은 최저가 정보.`;

  return {
    title,
    description,
    openGraph: {
      title,
      description,
      type: "website",
    },
    twitter: {
      card: "summary_large_image",
      title,
      description,
    },
  };
}

export default async function ShopPage({ params, searchParams }: ShopPageProps) {
  const { slug } = await params;
  const shop = SHOPS.find((s) => s.slug === slug);

  if (!shop) {
    notFound();
  }

  const { deals, total } = await getShopDeals(slug, searchParams);

  return (
    <div className="min-h-screen">
      {/* Shop header */}
      <div className="border-b border-border bg-card/30">
        <div className="mx-auto max-w-[1440px] px-4 py-6 sm:px-6">
          <nav className="mb-4 flex items-center gap-2 text-sm text-gray-400">
            <Link href="/" className="hover:text-accent">홈</Link>
            <span>/</span>
            <span className="text-gray-300">{shop.name}</span>
          </nav>

          <div className="flex items-center gap-4">
            <div className="flex h-14 w-14 items-center justify-center rounded-xl bg-accent/10 text-accent">
              <Store className="h-7 w-7" />
            </div>
            <div>
              <h1 className="text-2xl font-bold text-white">{shop.name}</h1>
              <div className="mt-1 flex items-center gap-3 text-sm text-gray-400">
                <span className="flex items-center gap-1">
                  <MapPin className="h-3.5 w-3.5" />
                  {COUNTRY_LABELS[shop.country] || shop.country}
                </span>
                <span className="flex items-center gap-1">
                  <Globe className="h-3.5 w-3.5" />
                  {total.toLocaleString()}개 특가
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Deals */}
      <div className="mx-auto max-w-[1440px] px-4 py-6 sm:px-6">
        <div className="mb-6 flex items-center justify-between">
          <h2 className="text-lg font-semibold text-white">
            {shop.name} 특가 목록
          </h2>
          <SortDropdown />
        </div>

        <DealGrid
          deals={deals}
          emptyMessage={`${shop.name}의 특가 상품이 아직 없습니다`}
        />
      </div>
    </div>
  );
}
