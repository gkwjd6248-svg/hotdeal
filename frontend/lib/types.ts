/**
 * Shared TypeScript type definitions for the DealHawk frontend.
 */

/** Standard API response envelope */
export interface ApiResponse<T> {
  status: "success" | "error";
  data: T;
  meta?: PaginationMeta;
}

/** Pagination metadata */
export interface PaginationMeta {
  page: number;
  limit: number;
  total: number;
  total_pages: number;
}

/** Error response shape */
export interface ApiError {
  status: "error";
  error: {
    code: string;
    message: string;
    field?: string;
  };
}

/** Product entity */
export interface Product {
  id: string;
  external_id: string;
  source_platform: string;
  title: string;
  description: string;
  original_price: number;
  image_url: string;
  product_url: string;
  brand: string;
  metadata: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

/** Deal entity - matches backend API response */
export interface Deal {
  id: string;
  title: string;
  deal_price: number;
  original_price: number | null;
  discount_percentage: number | null;
  ai_score: number | null;
  ai_reasoning: string | null;
  deal_type: string;
  deal_url: string;
  image_url: string | null;
  is_active: boolean;
  expires_at: string | null;
  created_at: string;
  view_count: number;
  vote_up: number;
  comment_count: number;
  shop: {
    name: string;
    slug: string;
    logo_url: string | null;
    country: string;
  };
  category: {
    name: string;
    slug: string;
  } | null;
}

/** Category entity */
export interface Category {
  id: string;
  name: string;
  slug: string;
  parent_id: string | null;
  description: string;
  icon_url: string;
  children?: Category[];
  created_at: string;
}

/** Price history data point */
export interface PriceHistoryPoint {
  id: string;
  product_id: string;
  price: number;
  recorded_at: string;
}

/** Shop / platform entity */
export interface Shop {
  id: string;
  name: string;
  slug: string;
  logo_url: string;
  base_url: string;
  is_active: boolean;
}

/** Auth user entity */
export interface AuthUser {
  id: string;
  email: string;
  username: string;
}

/** Comment entity */
export interface Comment {
  id: string;
  deal_id: string;
  user: { id: string; username: string };
  parent_id: string | null;
  content: string;
  is_deleted: boolean;
  created_at: string;
  updated_at: string;
  replies: Comment[];
}
