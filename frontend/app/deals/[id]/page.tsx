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
import ShareButton from "@/components/deals/ShareButton";
import {
  ExternalLink,
  Eye,
  MessageCircle,
  Clock,
  Tag,
  Sparkles,
  TrendingDown,
  ArrowLeft,
  BarChart3,
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
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 5000);
    const res = await fetch(`${API_BASE}/api/v1/deals/${id}`, {
      next: { revalidate: 60 },
      signal: controller.signal,
    });
    clearTimeout(timeout);
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
        ? [{ url: deal.image_url, width: 800, height: 800, alt: deal.title }]
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
  let colorClass = "text-gray-400 border-gray-600 bg-gray-500/10";
  let label = "보통";
  let barColor = "from-gray-400 to-gray-500";

  if (score >= 85) {
    colorClass = "text-red-400 border-red-500/50 bg-red-500/10";
    label = "슈퍼딜";
    barColor = "from-red-500 to-orange-400";
  } else if (score >= 70) {
    colorClass = "text-orange-400 border-orange-500/50 bg-orange-500/10";
    label = "핫딜";
    barColor = "from-orange-500 to-yellow-400";
  } else if (score >= 35) {
    colorClass = "text-yellow-400 border-yellow-500/50 bg-yellow-500/10";
    label = "특가";
    barColor = "from-yellow-500 to-yellow-300";
  }

  return { colorClass, label, barColor };
}

export default async function DealDetailPage({ params }: DealDetailPageProps) {
  const { id } = params;
  const deal = await getDeal(id);

  if (!deal) {
    notFound();
  }

  const priceHistory = deal.price_history || [];
  const discountPercentage =
    deal.discount_percentage ??
    (deal.original_price && deal.original_price > deal.deal_price
      ? Math.round(
          ((deal.original_price - deal.deal_price) / deal.original_price) * 100
        )
      : null);

  const aiScoreInfo = deal.ai_score ? AiScoreBadge({ score: deal.ai_score }) : null;

  return (
    <div className="min-h-screen">
      <div className="mx-auto max-w-[1200px] px-4 py-6 sm:px-6 sm:py-8">
        {/* Back link + Breadcrumb */}
        <nav className="mb-6 flex items-center gap-2 text-sm text-gray-400" aria-label="Breadcrumb">
          <Link
            href="/deals"
            className="flex items-center gap-1.5 font-medium text-gray-400 transition-colors hover:text-accent"
          >
            <ArrowLeft className="h-4 w-4" />
            <span>특가 목록</span>
          </Link>
          {deal.category && (
            <>
              <span className="text-gray-600">/</span>
              <Link
                href={`/deals?category=${deal.category.slug}`}
                className="transition-colors hover:text-accent"
              >
                {deal.category.name}
              </Link>
            </>
          )}
        </nav>

        {/* Main content grid */}
        <div className="grid gap-6 lg:grid-cols-2 lg:gap-10">
          {/* Left: Image + Price Chart */}
          <div className="flex flex-col gap-5">
            {/* Product image */}
            <div className="overflow-hidden rounded-2xl border border-border bg-card shadow-xl shadow-black/20">
              <div className="relative aspect-square w-full bg-surface">
                {deal.image_url ? (
                  <Image
                    src={deal.image_url}
                    alt={deal.title}
                    fill
                    className="object-contain p-4"
                    sizes="(max-width: 1024px) 100vw, 50vw"
                    priority
                  />
                ) : (
                  <div className="flex h-full items-center justify-center bg-gradient-to-br from-surface to-card-hover">
                    <Tag className="h-24 w-24 text-gray-600" />
                  </div>
                )}

                {/* Discount ribbon */}
                {discountPercentage && discountPercentage > 0 && (
                  <div className="absolute right-4 top-4">
                    <div className="rounded-full bg-gradient-to-br from-red-500 to-orange-500 px-3 py-1.5 text-sm font-black text-white shadow-lg shadow-orange-500/30">
                      -{discountPercentage}%
                    </div>
                  </div>
                )}
              </div>
            </div>

            {/* Price History Chart */}
            {priceHistory.length >= 2 && (
              <div className="rounded-2xl border border-border bg-card p-4 shadow-lg shadow-black/10">
                <div className="mb-3 flex items-center gap-2">
                  <BarChart3 className="h-4 w-4 text-accent" />
                  <span className="text-sm font-semibold text-gray-300">가격 변동 이력</span>
                </div>
                <PriceHistoryChart
                  data={priceHistory}
                  currentPrice={deal.deal_price}
                />
              </div>
            )}
          </div>

          {/* Right: Details */}
          <div className="flex flex-col gap-5">
            {/* Tags row */}
            <div className="flex flex-wrap items-center gap-2">
              {deal.category && (
                <Link
                  href={`/deals?category=${deal.category.slug}`}
                  className="rounded-full border border-border bg-surface px-3 py-1 text-xs font-medium text-gray-300 transition-all hover:border-accent/40 hover:bg-card-hover hover:text-accent"
                >
                  {deal.category.name}
                </Link>
              )}
              <span className="rounded-full border border-accent/20 bg-accent/10 px-2.5 py-1 text-xs font-semibold text-accent">
                {DEAL_TYPE_LABELS[deal.deal_type] || deal.deal_type}
              </span>
              <ShopLogo name={deal.shop.name} logoUrl={deal.shop.logo_url} />
            </div>

            {/* Title */}
            <h1 className="text-xl font-bold leading-snug text-white sm:text-2xl lg:text-3xl">
              {deal.title}
            </h1>

            {/* Price box */}
            <div className="rounded-2xl border border-accent/20 bg-gradient-to-br from-accent/5 to-transparent p-5 shadow-inner">
              <PriceDisplay
                dealPrice={deal.deal_price}
                originalPrice={deal.original_price}
                discountPercentage={deal.discount_percentage}
                size="lg"
                showBadge={true}
              />
              {deal.original_price && deal.original_price > deal.deal_price && (
                <p className="mt-2 text-xs text-gray-500">
                  정상가 대비{" "}
                  <span className="font-semibold text-price-deal">
                    {(deal.original_price - deal.deal_price).toLocaleString()}원
                  </span>{" "}
                  절약
                </p>
              )}
            </div>

            {/* AI Score */}
            {deal.ai_score !== null && deal.ai_score !== undefined && deal.ai_score > 0 && aiScoreInfo && (
              <div className="rounded-2xl border border-border bg-card p-4">
                <div className="flex items-start gap-3">
                  <div className="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-lg bg-accent/10">
                    <Sparkles className="h-4 w-4 text-accent" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="mb-2 flex items-center justify-between gap-2">
                      <span className="text-sm font-semibold text-gray-300">
                        AI 추천 점수
                      </span>
                      <span
                        className={`inline-flex items-center gap-1 rounded-full border px-2.5 py-0.5 text-xs font-bold ${aiScoreInfo.colorClass}`}
                      >
                        {aiScoreInfo.label} {deal.ai_score}점
                      </span>
                    </div>
                    {/* Score bar */}
                    <div className="mb-2 h-2 overflow-hidden rounded-full bg-surface">
                      <div
                        className={`h-full rounded-full bg-gradient-to-r ${aiScoreInfo.barColor} transition-all`}
                        style={{ width: `${Math.min(deal.ai_score, 100)}%` }}
                      />
                    </div>
                    {deal.ai_reasoning && (
                      <p className="text-xs leading-relaxed text-gray-500">{deal.ai_reasoning}</p>
                    )}
                  </div>
                </div>
              </div>
            )}

            {/* Alerts */}
            <div className="flex flex-col gap-2">
              {deal.expires_at && (
                <div className="flex items-center gap-2 rounded-xl border border-yellow-500/30 bg-yellow-500/10 p-3 text-sm text-yellow-400">
                  <Clock className="h-4 w-4 flex-shrink-0" />
                  <span>
                    이 특가는{" "}
                    <RelativeTime date={deal.expires_at} suffix={false} />{" "}
                    종료됩니다
                  </span>
                </div>
              )}
              {discountPercentage && discountPercentage >= 30 && (
                <div className="flex items-center gap-2 rounded-xl border border-green-500/30 bg-green-500/10 p-3 text-sm text-green-400">
                  <TrendingDown className="h-4 w-4 flex-shrink-0" />
                  <span>
                    {discountPercentage}% 할인 중 - 평소보다 크게 할인된 가격입니다
                  </span>
                </div>
              )}
            </div>

            {/* Stats grid */}
            <div className="grid grid-cols-3 gap-2">
              <div className="rounded-xl border border-border bg-card p-3 text-center">
                <Eye className="mx-auto mb-1.5 h-4 w-4 text-gray-500" />
                <div className="text-sm font-bold text-white tabular-nums">
                  {deal.view_count.toLocaleString()}
                </div>
                <div className="text-[10px] text-gray-600">조회수</div>
              </div>
              <div className="rounded-xl border border-border bg-card p-3 text-center">
                <MessageCircle className="mx-auto mb-1.5 h-4 w-4 text-gray-500" />
                <div className="text-sm font-bold text-white tabular-nums">
                  {deal.comment_count.toLocaleString()}
                </div>
                <div className="text-[10px] text-gray-600">댓글</div>
              </div>
              <div className="rounded-xl border border-border bg-card p-3 text-center">
                <RelativeTime date={deal.created_at} />
                <div className="text-[10px] text-gray-600 mt-0.5">등록</div>
              </div>
            </div>

            {/* Vote buttons */}
            <VoteButtons
              dealId={deal.id}
              initialVoteUp={deal.vote_up}
              initialVoteDown={deal.vote_down || 0}
            />

            {/* Action buttons */}
            <div className="flex gap-3">
              <a
                href={deal.deal_url}
                target="_blank"
                rel="noopener noreferrer"
                className="btn-primary flex flex-1 items-center justify-center gap-2 py-3.5 text-base"
              >
                <span>{deal.shop.name}에서 구매하기</span>
                <ExternalLink className="h-4 w-4" />
              </a>
              <ShareButton title={deal.title} />
            </div>
          </div>
        </div>

        {/* Description */}
        {deal.description && (
          <div className="mt-8 rounded-2xl border border-border bg-card p-6">
            <h2 className="mb-3 text-base font-semibold text-gray-300">상품 설명</h2>
            <p className="whitespace-pre-line text-sm leading-relaxed text-gray-400">
              {deal.description}
            </p>
          </div>
        )}

        {/* Comments section */}
        <div className="mt-8">
          <CommentSection dealId={deal.id} />
        </div>
      </div>
    </div>
  );
}
