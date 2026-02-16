import Link from "next/link";
import { Flame } from "lucide-react";

export default function Footer() {
  return (
    <footer className="mt-auto border-t border-border bg-card">
      <div className="mx-auto max-w-[1440px] px-4 py-8 sm:px-6">
        <div className="flex flex-col items-center justify-between gap-4 sm:flex-row">
          {/* Logo and description */}
          <div className="flex items-center gap-2">
            <Flame className="h-5 w-5 text-accent" />
            <span className="text-sm font-semibold text-gray-300">DealHawk</span>
            <span className="text-sm text-gray-500">|</span>
            <span className="text-sm text-gray-500">AI 특가 모아보기</span>
          </div>

          {/* Links */}
          <div className="flex items-center gap-6 text-sm">
            <Link
              href="/about"
              className="text-gray-400 transition-colors hover:text-gray-200"
            >
              소개
            </Link>
            <Link
              href="/privacy"
              className="text-gray-400 transition-colors hover:text-gray-200"
            >
              개인정보처리방침
            </Link>
            <Link
              href="/terms"
              className="text-gray-400 transition-colors hover:text-gray-200"
            >
              이용약관
            </Link>
          </div>
        </div>

        {/* Copyright */}
        <div className="mt-4 text-center text-xs text-gray-500">
          © 2026 DealHawk. All rights reserved.
        </div>
      </div>
    </footer>
  );
}
