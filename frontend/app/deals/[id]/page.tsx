import Image from "next/image";
import Link from "next/link";
import { notFound } from "next/navigation";
import { Metadata } from "next";
import { MOCK_DEALS } from "@/lib/mock-data";
import { Deal, ApiResponse } from "@/lib/types";
import PriceDisplay from "@/components/common/PriceDisplay";
import PriceHistoryChart from "@/components/deals/PriceHistoryChart";
import RelativeTime from "@/components/common/RelativeTime";
import ShopLogo from "@/components/common/ShopLogo";
import VoteButtons from "@/components/deals/VoteButtons";
import CommentSection from "@/components/deals/CommentSection";
import {
  ExternalLink,
  Eye,
  MessageCircle,
  Clock,
  Tag,
  Sparkles,
  TrendingDown,
} from "lucide-react";

const API_BASE = process.env.BACKEND_URL || "http://localhost:8000";

interface DealDetail extends Deal {
  description?: string | null;
  starts_at?: string | null;
  vote_down?: number;
  price_history?: Array<{ price: number; recorded_at: string }>;
}

interface DealDetailPageProps {
  params: { id: string };
}

async function getDeal(id: string): Promise<DealDetail | null> {
  try {
    const res = await fetch(`${API_BASE}/api/v1/deals/${id}`, {
      next: { revalidate: 60 },
    });
    if (!res.ok) return null;
    const json: ApiResponse<DealDetail> = await res.json();
    if (json.status === "success") return json.data;
    return null;
  } catch {
    // Fallback to mock data
    const deal = MOCK_DEALS.find((d) => d.id === id);
    if (!deal) return null;
    return {
      ...deal,
      vote_down: 5,
      price_history: deal.original_price
        ? [
            {
              price: deal.original_price,
              recorded_at: new Date(Date.now() - 30 * 86400000).toISOString(),
            },
            {
              price: deal.original_price * 0.95,
              recorded_at: new Date(Date.now() - 20 * 86400000).toISOString(),
            },
            {
              price: deal.original_price * 0.9,
              recorded_at: new Date(Date.now() - 10 * 86400000).toISOString(),
            },
            {
              price: deal.deal_price,
              recorded_at: new Date().toISOString(),
            },
          ]
        : [],
    };
  }
}

const DEAL_TYPE_LABELS: Record<string, string> = {
  flash_sale: "타임딜",
  price_drop: "가격하락",
  coupon: "쿠폰할인",
  clearance: "재고정리",
  bundle: "번들할인",
};

export async function generateMetadata({
  params,
}: DealDetailPageProps): Promise<Metadata> {
  const { id } = params;
  const deal = await getDeal(id);

  if (!deal) {
    return {
      title: "특가를 찾을 수 없습니다",
    };
  }

  const title = deal.discount_percentage
    ? `${deal.title} | ${deal.discount_percentage}% 할인 - DealHawk`
    : `${deal.title} - DealHawk`;

  const description = deal.original_price
    ? `${deal.shop.name}에서 ${deal.discount_percentage}% 할인! ${deal.original_price.toLocaleString()}원 → ${deal.deal_price.toLocaleString()}원. ${deal.category?.name || "특가"} 최저가 정보.`
    : `${deal.shop.name}에서 ${deal.deal_price.toLocaleString()}원. ${deal.category?.name || "특가"} 최저가 정보.`;

  return {
    title,
    description,
    openGraph: {
      title,
      description,
      type: "website",
      images: deal.image_url
        ? [
            {
              url: deal.image_url,
              width: 800,
              height: 800,
              alt: deal.title,
            },
          ]
        : [],
    },
    twitter: {
      card: "summary_large_image",
      title,
      description,
      images: deal.image_url ? [deal.image_url] : [],
    },
  };
}

function AiScoreBadge({ score }: { score: number }) {
  let color = "text-gray-400 border-gray-600";
  let label = "보통";
  if (score >= 85) {
    color = "text-red-400 border-red-500/50 bg-red-500/10";
    label = "슈퍼딜";
  } else if (score >= 70) {
    color = "text-orange-400 border-orange-500/50 bg-orange-500/10";
    label = "핫딜";
  } else if (score >= 35) {
    color = "text-yellow-400 border-yellow-500/50 bg-yellow-500/10";
    label = "특가";
  }

  return (
    <span className={`inline-flex items-center gap-1 rounded-full border px-2.5 py-0.5 text-xs font-semibold ${color}`}>
      {label} {score}점
    </span>
  );
}

export default async function DealDetailPage({ params }: DealDetailPageProps) {
  const { id } = params;
  const deal = await getDeal(id);

  if (!deal) {
    notFound();
  }

  const priceHistory = deal.price_history || [];

  return (
    <div className="min-h-screen">
      <div className="mx-auto max-w-[1200px] px-4 py-8 sm:px-6">
        {/* Breadcrumb */}
        <nav className="mb-6 flex items-center gap-2 text-sm text-gray-400">
          <Link href="/" className="hover:text-accent">
            홈
          </Link>
          <span>/</span>
          <Link href="/deals" className="hover:text-accent">
            특가
          </Link>
          {deal.category && (
            <>
              <span>/</span>
              <Link
                href={`/deals?category=${deal.category.slug}`}
                className="hover:text-accent"
              >
                {deal.category.name}
              </Link>
            </>
          )}
        </nav>

        {/* Main content grid */}
        <div className="grid gap-8 lg:grid-cols-2">
          {/* Left: Image + Price Chart */}
          <div className="flex flex-col gap-6">
            <div className="overflow-hidden rounded-xl border border-border bg-card">
              <div className="relative aspect-square w-full bg-surface">
                {deal.image_url ? (
                  <Image
                    src={deal.image_url}
                    alt={deal.title}
                    fill
                    className="object-contain"
                    sizes="(max-width: 1024px) 100vw, 50vw"
                    priority
                  />
                ) : (
                  <div className="flex h-full items-center justify-center">
                    <Tag className="h-24 w-24 text-gray-600" />
                  </div>
                )}
              </div>
            </div>

            {/* Price History Chart */}
            {priceHistory.length >= 2 && (
              <PriceHistoryChart
                data={priceHistory}
                currentPrice={deal.deal_price}
              />
            )}
          </div>

          {/* Right: Details */}
          <div className="flex flex-col gap-6">
            {/* Category & Shop & Deal Type */}
            <div className="flex flex-wrap items-center gap-2">
              {deal.category && (
                <Link
                  href={`/deals?category=${deal.category.slug}`}
                  className="rounded-full bg-surface px-3 py-1 text-xs font-medium text-gray-300 transition-colors hover:bg-card-hover hover:text-accent"
                >
                  {deal.category.name}
                </Link>
              )}
              <ShopLogo name={deal.shop.name} logoUrl={deal.shop.logo_url} />
              <span className="rounded-full bg-accent/10 px-2.5 py-1 text-xs font-medium text-accent">
                {DEAL_TYPE_LABELS[deal.deal_type] || deal.deal_type}
              </span>
            </div>

            {/* Title */}
            <h1 className="text-2xl font-bold leading-tight text-white sm:text-3xl">
              {deal.title}
            </h1>

            {/* Price */}
            <div className="rounded-xl border border-accent/20 bg-accent/5 p-6">
              <PriceDisplay
                dealPrice={deal.deal_price}
                originalPrice={deal.original_price}
                discountPercentage={deal.discount_percentage}
                size="lg"
              />
            </div>

            {/* AI Score */}
            {deal.ai_score !== null && deal.ai_score > 0 && (
              <div className="rounded-xl border border-border bg-card p-4">
                <div className="flex items-start gap-3">
                  <Sparkles className="mt-1 h-5 w-5 text-accent" />
                  <div className="flex-1">
                    <div className="mb-2 flex items-center justify-between">
                      <span className="font-semibold text-gray-300">
                        AI 추천 점수
                      </span>
                      <AiScoreBadge score={deal.ai_score} />
                    </div>
                    {/* Score bar */}
                    <div className="mb-2 h-2 overflow-hidden rounded-full bg-surface">
                      <div
                        className="h-full rounded-full bg-gradient-to-r from-yellow-500 via-orange-500 to-red-500 transition-all"
                        style={{ width: `${Math.min(deal.ai_score, 100)}%` }}
                      />
                    </div>
                    {deal.ai_reasoning && (
                      <p className="text-sm text-gray-400">{deal.ai_reasoning}</p>
                    )}
                  </div>
                </div>
              </div>
            )}

            {/* Stats grid */}
            <div className="grid grid-cols-2 gap-3">
              <div className="rounded-lg border border-border bg-card p-3 text-center">
                <Eye className="mx-auto mb-1 h-4 w-4 text-gray-400" />
                <div className="text-sm font-bold text-white">
                  {deal.view_count.toLocaleString()}
                </div>
                <div className="text-xs text-gray-500">조회</div>
              </div>
              <div className="rounded-lg border border-border bg-card p-3 text-center">
                <MessageCircle className="mx-auto mb-1 h-4 w-4 text-gray-400" />
                <div className="text-sm font-bold text-white">
                  {deal.comment_count.toLocaleString()}
                </div>
                <div className="text-xs text-gray-500">댓글</div>
              </div>
            </div>

            {/* Vote buttons */}
            <VoteButtons
              dealId={deal.id}
              initialVoteUp={deal.vote_up}
              initialVoteDown={deal.vote_down || 0}
            />

            {/* CTA Button */}
            <a
              href={deal.deal_url}
              target="_blank"
              rel="noopener noreferrer"
              className="btn-primary flex items-center justify-center gap-2 py-4 text-lg"
            >
              <span>{deal.shop.name}에서 구매하기</span>
              <ExternalLink className="h-5 w-5" />
            </a>

            {/* Expiry notice */}
            {deal.expires_at && (
              <div className="flex items-center gap-2 rounded-lg border border-yellow-500/30 bg-yellow-500/10 p-3 text-sm text-yellow-400">
                <Clock className="h-4 w-4 flex-shrink-0" />
                <span>
                  이 특가는 <RelativeTime date={deal.expires_at} suffix={false} /> 종료됩니다
                </span>
              </div>
            )}

            {/* Price drop alert */}
            {deal.discount_percentage && deal.discount_percentage >= 30 && (
              <div className="flex items-center gap-2 rounded-lg border border-green-500/30 bg-green-500/10 p-3 text-sm text-green-400">
                <TrendingDown className="h-4 w-4 flex-shrink-0" />
                <span>{deal.discount_percentage}% 할인 중 - 평소보다 크게 할인된 가격입니다</span>
              </div>
            )}
          </div>
        </div>

        {/* Comments section */}
        <div className="mt-12">
          <CommentSection dealId={deal.id} />
        </div>
      </div>
    </div>
  );
}
