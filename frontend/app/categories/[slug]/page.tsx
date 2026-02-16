import { notFound } from "next/navigation";
import { Metadata } from "next";
import Link from "next/link";
import DealGrid from "@/components/deals/DealGrid";
import ShopFilter from "@/components/navigation/ShopFilter";
import SortDropdown from "@/components/navigation/SortDropdown";
import { MOCK_DEALS } from "@/lib/mock-data";
import { CATEGORIES } from "@/lib/constants";
import { Deal, ApiResponse } from "@/lib/types";

const API_BASE = process.env.BACKEND_URL || "http://localhost:8000";

interface CategoryPageProps {
  params: Promise<{ slug: string }>;
  searchParams: { shop?: string; sort?: string };
}

async function getCategoryDeals(
  slug: string,
  params: { shop?: string; sort?: string }
): Promise<{ deals: Deal[]; total: number }> {
  try {
    const searchParams = new URLSearchParams();
    searchParams.set("limit", "20");
    if (params.sort) searchParams.set("sort_by", params.sort);

    const res = await fetch(
      `${API_BASE}/api/v1/categories/${slug}/deals?${searchParams.toString()}`,
      { next: { revalidate: 60 } }
    );
    if (!res.ok) throw new Error("API error");
    const json: ApiResponse<Deal[]> = await res.json();
    return { deals: json.data, total: json.meta?.total ?? json.data.length };
  } catch {
    const deals = MOCK_DEALS.filter((d) => d.category?.slug === slug);
    return { deals, total: deals.length };
  }
}

export async function generateMetadata({
  params,
}: CategoryPageProps): Promise<Metadata> {
  const { slug } = await params;
  const category = CATEGORIES.find((c) => c.slug === slug);

  if (!category) {
    return {
      title: "카테고리를 찾을 수 없습니다",
    };
  }

  const title = `${category.name} 특가 모음 - DealHawk`;
  const description = `${category.name} 카테고리의 최신 특가 상품을 한눈에! AI가 18개 쇼핑몰에서 찾은 최저가 정보.`;

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

export default async function CategoryPage({
  params,
  searchParams,
}: CategoryPageProps) {
  const { slug } = await params;
  const category = CATEGORIES.find((c) => c.slug === slug);

  if (!category) {
    notFound();
  }

  const { deals, total } = await getCategoryDeals(slug, searchParams);
  const Icon = category.icon;

  return (
    <div className="min-h-screen">
      <ShopFilter />

      <div className="mx-auto max-w-[1440px] px-4 py-6 sm:px-6">
        {/* Header */}
        <div className="mb-6">
          <nav className="mb-4 flex items-center gap-2 text-sm text-gray-400">
            <Link href="/" className="hover:text-accent">홈</Link>
            <span>/</span>
            <span className="text-gray-300">{category.name}</span>
          </nav>

          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-accent/10">
                <Icon className="h-5 w-5 text-accent" />
              </div>
              <div>
                <h1 className="text-2xl font-bold text-white">
                  {category.name}
                </h1>
                <p className="text-sm text-gray-400">
                  {total.toLocaleString()}개의 특가 상품
                </p>
              </div>
            </div>
            <SortDropdown />
          </div>
        </div>

        <DealGrid deals={deals} />
      </div>
    </div>
  );
}
