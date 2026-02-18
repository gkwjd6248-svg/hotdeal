import Link from "next/link";
import { Flame, Zap, Github } from "lucide-react";

export default function Footer() {
  return (
    <footer className="mt-auto border-t border-border bg-card">
      {/* Gradient top border accent */}
      <div className="h-px bg-gradient-to-r from-transparent via-accent/40 to-transparent" />

      <div className="mx-auto max-w-[1440px] px-4 py-8 sm:px-6">
        <div className="flex flex-col items-center justify-between gap-6 sm:flex-row sm:items-start">
          {/* Brand */}
          <div className="flex flex-col items-center gap-2 sm:items-start">
            <div className="flex items-center gap-2">
              <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-gradient-to-br from-accent to-orange-600">
                <Flame className="h-3.5 w-3.5 text-white" />
              </div>
              <span className="text-base font-extrabold tracking-tight text-white">
                Deal<span className="text-accent">Hawk</span>
              </span>
            </div>
            <p className="flex items-center gap-1 text-xs text-gray-500">
              <Zap className="h-3 w-3 text-accent/50" />
              AI가 18개 쇼핑몰에서 자동으로 찾은 최저가 특가 정보
            </p>
          </div>

          {/* Links */}
          <div className="flex flex-col items-center gap-3 sm:items-end">
            <nav className="flex items-center gap-5 text-sm" aria-label="Footer navigation">
              <Link
                href="/about"
                className="text-gray-500 transition-colors hover:text-gray-300"
              >
                소개
              </Link>
              <Link
                href="/privacy"
                className="text-gray-500 transition-colors hover:text-gray-300"
              >
                개인정보처리방침
              </Link>
              <Link
                href="/terms"
                className="text-gray-500 transition-colors hover:text-gray-300"
              >
                이용약관
              </Link>
              <Link
                href="https://github.com/yourusername/dealhawk"
                target="_blank"
                rel="noopener noreferrer"
                className="text-gray-500 transition-colors hover:text-gray-300"
                aria-label="GitHub"
              >
                <Github className="h-4 w-4" />
              </Link>
            </nav>

            {/* Copyright */}
            <p className="text-xs text-gray-600">
              © 2026 DealHawk. All rights reserved.
            </p>
          </div>
        </div>

        {/* Bottom disclaimer */}
        <div className="mt-6 border-t border-border/50 pt-4">
          <p className="text-center text-[11px] leading-relaxed text-gray-600">
            이 사이트는 각 쇼핑몰의 제휴 파트너로서 구매 링크를 통한 수수료를 받을 수 있습니다.
            가격 정보는 실시간으로 변경될 수 있으며, 최신 가격은 해당 쇼핑몰에서 확인하세요.
          </p>
        </div>
      </div>
    </footer>
  );
}
