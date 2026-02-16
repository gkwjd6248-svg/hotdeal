/**
 * API client configuration and helper functions.
 *
 * In development: directly calls localhost:8000
 * In production: uses Next.js rewrites to proxy /api/* to the backend
 */

import axios from "axios";

// Use relative URL in production (leverages Next.js rewrites), direct URL in dev
const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL
  ? `${process.env.NEXT_PUBLIC_API_URL}/api/v1`
  : "/api/v1";

export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  timeout: 10000,
  headers: {
    "Content-Type": "application/json",
  },
});

/**
 * SWR fetcher that uses the axios client.
 */
export const fetcher = async (url: string) => {
  const response = await apiClient.get(url);
  return response.data;
};
