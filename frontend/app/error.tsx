"use client";

import { useEffect } from "react";
import { AlertTriangle, RefreshCcw } from "lucide-react";

export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    // Log the error to an error reporting service
    console.error("Error boundary caught:", error);
  }, [error]);

  return (
    <div className="flex min-h-screen flex-col items-center justify-center p-8">
      <div className="w-full max-w-md rounded-xl border border-border bg-card p-8 text-center">
        {/* Error icon */}
        <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-price-deal/10">
          <AlertTriangle className="h-8 w-8 text-price-deal" />
        </div>

        {/* Error title */}
        <h2 className="mb-2 text-2xl font-bold text-white">
          오류가 발생했습니다
        </h2>

        {/* Error message */}
        <p className="mb-6 text-sm text-gray-400">
          페이지를 불러오는 중 문제가 발생했습니다.
          {process.env.NODE_ENV === "development" && error.message && (
            <span className="mt-2 block font-mono text-xs text-gray-500">
              {error.message}
            </span>
          )}
        </p>

        {/* Retry button */}
        <button
          onClick={reset}
          className="btn-primary inline-flex items-center gap-2"
        >
          <RefreshCcw className="h-4 w-4" />
          <span>다시 시도</span>
        </button>

        {/* Help text */}
        <p className="mt-4 text-xs text-gray-500">
          문제가 계속되면 페이지를 새로고침하거나 잠시 후 다시 시도해주세요.
        </p>
      </div>
    </div>
  );
}
