"use client";

import Link from "next/link";
import { Flame, Github, LogOut, User } from "lucide-react";
import SearchBar from "@/components/search/SearchBar";
import CategoryTabs from "./CategoryTabs";
import { useAuth } from "@/lib/auth";
import { useState } from "react";
import AuthModal from "@/components/auth/AuthModal";

export default function Header() {
  const { user, logout, isLoading } = useAuth();
  const [showAuthModal, setShowAuthModal] = useState(false);
  return (
    <header className="sticky top-0 z-50 border-b border-border bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
      <div className="mx-auto max-w-[1440px]">
        {/* Top bar */}
        <div className="flex items-center justify-between gap-4 px-4 py-3 sm:px-6">
          {/* Logo */}
          <Link
            href="/"
            className="flex items-center gap-2 text-xl font-bold text-accent transition-colors hover:text-accent-hover"
          >
            <Flame className="h-6 w-6" />
            <span className="hidden sm:inline">DealHawk</span>
          </Link>

          {/* Search Bar */}
          <div className="flex-1 max-w-2xl">
            <SearchBar />
          </div>

          {/* Right side links */}
          <div className="flex items-center gap-3">
            {!isLoading && (
              <>
                {user ? (
                  <>
                    <div className="flex items-center gap-2 rounded-lg bg-surface px-3 py-1.5">
                      <User className="h-4 w-4 text-gray-400" />
                      <span className="text-sm font-medium text-gray-200">{user.username}</span>
                    </div>
                    <button
                      onClick={logout}
                      className="rounded-lg bg-card px-3 py-1.5 text-sm font-medium text-gray-300 transition-colors hover:bg-surface hover:text-gray-200"
                      aria-label="로그아웃"
                    >
                      <span className="hidden sm:inline">로그아웃</span>
                      <LogOut className="h-4 w-4 sm:hidden" />
                    </button>
                  </>
                ) : (
                  <button
                    onClick={() => setShowAuthModal(true)}
                    className="rounded-lg bg-accent px-4 py-1.5 text-sm font-semibold text-white transition-colors hover:bg-accent-hover"
                  >
                    로그인
                  </button>
                )}
              </>
            )}
            <Link
              href="https://github.com/yourusername/dealhawk"
              target="_blank"
              rel="noopener noreferrer"
              className="rounded-lg p-2 text-gray-400 transition-colors hover:bg-card hover:text-gray-200"
              aria-label="GitHub"
            >
              <Github className="h-5 w-5" />
            </Link>
          </div>
        </div>

        {/* Category tabs */}
        <CategoryTabs />
      </div>

      {/* Auth Modal */}
      <AuthModal isOpen={showAuthModal} onClose={() => setShowAuthModal(false)} />
    </header>
  );
}
