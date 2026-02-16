/**
 * Application-wide constants.
 */

import {
  Laptop,
  CreditCard,
  Gamepad2,
  Smartphone,
  Tv,
  ShoppingBag,
  type LucideIcon,
} from "lucide-react";

/** Default page size for paginated API calls */
export const DEFAULT_PAGE_SIZE = 20;

/** Maximum page size allowed by the API */
export const MAX_PAGE_SIZE = 100;

/** Deal type display labels */
export const DEAL_TYPE_LABELS: Record<string, string> = {
  flash_sale: "Flash Sale",
  coupon: "Coupon",
  clearance: "Clearance",
  price_drop: "Price Drop",
};

/** Deal type color classes */
export const DEAL_TYPE_COLORS: Record<string, string> = {
  flash_sale: "bg-red-500/20 text-red-400",
  coupon: "bg-green-500/20 text-green-400",
  clearance: "bg-yellow-500/20 text-yellow-400",
  price_drop: "bg-blue-500/20 text-blue-400",
};

/** Category definition */
export interface CategoryDef {
  slug: string;
  name: string;
  icon: LucideIcon;
}

/** Product categories - slugs must match backend seed data exactly */
export const CATEGORIES: CategoryDef[] = [
  { slug: "all", name: "전체", icon: ShoppingBag },
  { slug: "pc-hardware", name: "PC/하드웨어", icon: Laptop },
  { slug: "gift-cards", name: "상품권/쿠폰", icon: CreditCard },
  { slug: "games-software", name: "게임/SW", icon: Gamepad2 },
  { slug: "laptop-mobile", name: "노트북/모바일", icon: Smartphone },
  { slug: "electronics-tv", name: "가전/TV", icon: Tv },
  { slug: "living-food", name: "생활/식품", icon: ShoppingBag },
];

/** Shop definition */
export interface ShopDef {
  slug: string;
  name: string;
  country: string;
  logo_url?: string;
}

/** Supported shopping platforms - must match backend seed data */
export const SHOPS: ShopDef[] = [
  { slug: "coupang", name: "쿠팡", country: "KR" },
  { slug: "naver", name: "네이버쇼핑", country: "KR" },
  { slug: "11st", name: "11번가", country: "KR" },
  { slug: "himart", name: "하이마트", country: "KR" },
  { slug: "auction", name: "옥션", country: "KR" },
  { slug: "gmarket", name: "지마켓", country: "KR" },
  { slug: "ssg", name: "SSG", country: "KR" },
  { slug: "lotteon", name: "롯데온", country: "KR" },
  { slug: "interpark", name: "인터파크", country: "KR" },
  { slug: "musinsa", name: "무신사", country: "KR" },
  { slug: "ssf", name: "SSF", country: "KR" },
  { slug: "aliexpress", name: "알리익스프레스", country: "CN" },
  { slug: "amazon", name: "아마존", country: "US" },
  { slug: "ebay", name: "이베이", country: "US" },
  { slug: "steam", name: "스팀", country: "GLOBAL" },
  { slug: "newegg", name: "뉴에그", country: "US" },
  { slug: "taobao", name: "타오바오", country: "CN" },
];

/** Sort options */
export const SORT_OPTIONS = [
  { value: "newest", label: "최신순" },
  { value: "score", label: "AI추천순" },
  { value: "discount", label: "할인율순" },
  { value: "views", label: "조회순" },
] as const;

/** Trending keywords (will be fetched from API in production) */
export const TRENDING_KEYWORDS = [
  "애플 에어팟",
  "삼성 갤럭시",
  "LG 그램",
  "다이슨 청소기",
  "아이패드",
  "플레이스테이션5",
  "닌텐도 스위치",
  "로봇청소기",
  "공기청정기",
  "커피머신",
];
