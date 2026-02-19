"use client";

import Link from "next/link";
import { Flame, Github, LogOut, User, Zap } from "lucide-react";
import SearchBar from "@/components/search/SearchBar";
import CategoryTabs from "./CategoryTabs";
import { useAuth } from "@/lib/auth";

export default function Header() {
  const { user, logout, isLoading } = useAuth();

  return (
    <header className="sticky top-0 z-50 border-b border-border bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/80 shadow-lg shadow-black/20">
      <div className="mx-auto max-w-[1440px]">
        {/* Top bar */}
        <div className="flex items-center justify-between gap-3 px-4 py-3 sm:gap-4 sm:px-6">
          {/* Logo */}
          <Link
            href="/"
            className="group flex items-center gap-2 flex-shrink-0 transition-opacity hover:opacity-90"
            aria-label="DealHawk 홈"
          >
            {/* Icon mark */}
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-br from-accent to-orange-600 shadow-md shadow-accent/30 transition-shadow group-hover:shadow-accent/50">
              <Flame className="h-4 w-4 text-white" />
            </div>
            {/* Wordmark */}
            <div className="hidden sm:flex sm:flex-col sm:leading-none">
              <span className="text-base font-extrabold tracking-tight text-white">
                Deal<span className="text-accent">Hawk</span>
              </span>
              <span className="flex items-center gap-0.5 text-[9px] font-medium text-gray-500">
                <Zap className="h-2.5 w-2.5 text-accent/60" />
                AI 특가 자동수집
              </span>
            </div>
          </Link>

          {/* Search Bar - grows to fill space */}
          <div className="min-w-0 flex-1">
            <SearchBar />
          </div>

          {/* Right side actions */}
          <div className="flex items-center gap-2 flex-shrink-0">
            {!isLoading && (
              <>
                {user ? (
                  <div className="flex items-center gap-2">
                    <Link
                      href="/profile"
                      className="hidden sm:flex items-center gap-2 rounded-lg border border-border bg-card px-3 py-1.5 transition-all hover:border-accent/30 hover:bg-card-hover"
                    >
                      <User className="h-3.5 w-3.5 text-accent" />
                      <span className="text-sm font-medium text-gray-200">{user.username}</span>
                    </Link>
                    <Link
                      href="/profile"
                      className="sm:hidden rounded-lg border border-border bg-card p-1.5 text-gray-400 transition-all hover:border-accent/30 hover:text-accent"
                    >
                      <User className="h-4 w-4" />
                    </Link>
                    <button
                      onClick={logout}
                      className="rounded-lg border border-border bg-card px-3 py-1.5 text-sm font-medium text-gray-400 transition-all hover:border-red-500/30 hover:bg-red-500/10 hover:text-red-400"
                      aria-label="로그아웃"
                    >
                      <span className="hidden sm:inline">로그아웃</span>
                      <LogOut className="h-4 w-4 sm:hidden" />
                    </button>
                  </div>
                ) : (
                  <Link
                    href="/login"
                    className="btn-primary px-4 py-1.5 text-sm"
                  >
                    로그인
                  </Link>
                )}
              </>
            )}
            <Link
              href="https://github.com/gkwjd6248-svg/hotdeal"
              target="_blank"
              rel="noopener noreferrer"
              className="rounded-lg border border-border p-2 text-gray-500 transition-all hover:border-gray-600 hover:bg-card hover:text-gray-300"
              aria-label="GitHub 저장소"
            >
              <Github className="h-4 w-4" />
            </Link>
          </div>
        </div>

        {/* Category tabs */}
        <CategoryTabs />
      </div>

    </header>
  );
}
