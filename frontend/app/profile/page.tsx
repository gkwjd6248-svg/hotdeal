"use client";

import { useAuth } from "@/lib/auth";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import {
  User,
  Mail,
  Calendar,
  LogOut,
  Shield,
  Bell,
  Heart,
  MessageCircle,
  ThumbsUp,
  Settings,
} from "lucide-react";
import Link from "next/link";
import AuthModal from "@/components/auth/AuthModal";

export default function ProfilePage() {
  const { user, logout, isLoading } = useAuth();
  const router = useRouter();
  const [showAuthModal, setShowAuthModal] = useState(false);

  useEffect(() => {
    if (!isLoading && !user) {
      setShowAuthModal(true);
    }
  }, [isLoading, user]);

  if (isLoading) {
    return (
      <div className="flex min-h-[60vh] items-center justify-center">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-accent border-t-transparent" />
      </div>
    );
  }

  if (!user) {
    return (
      <>
        <div className="flex min-h-[60vh] flex-col items-center justify-center gap-4 px-4">
          <User className="h-16 w-16 text-gray-600" />
          <h1 className="text-xl font-bold text-white">로그인이 필요합니다</h1>
          <p className="text-sm text-gray-400">
            프로필을 확인하려면 먼저 로그인해주세요.
          </p>
          <button
            onClick={() => setShowAuthModal(true)}
            className="btn-primary px-6 py-2.5"
          >
            로그인 / 회원가입
          </button>
        </div>
        <AuthModal
          isOpen={showAuthModal}
          onClose={() => setShowAuthModal(false)}
        />
      </>
    );
  }

  return (
    <div className="mx-auto max-w-[800px] px-4 py-8 sm:px-6">
      {/* Profile header */}
      <div className="mb-8 rounded-2xl border border-border bg-card p-6 shadow-lg shadow-black/10">
        <div className="flex items-start gap-4">
          <div className="flex h-16 w-16 flex-shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-accent to-orange-600 text-2xl font-bold text-white shadow-lg shadow-accent/30">
            {user.username.charAt(0).toUpperCase()}
          </div>
          <div className="flex-1 min-w-0">
            <h1 className="text-xl font-bold text-white">{user.username}</h1>
            <div className="mt-1 flex items-center gap-1.5 text-sm text-gray-400">
              <Mail className="h-3.5 w-3.5" />
              <span>{user.email}</span>
            </div>
            <div className="mt-1 flex items-center gap-1.5 text-xs text-gray-500">
              <Shield className="h-3 w-3" />
              <span>일반 회원</span>
            </div>
          </div>
          <button
            onClick={() => {
              logout();
              router.push("/");
            }}
            className="flex items-center gap-1.5 rounded-lg border border-border bg-surface px-3 py-2 text-sm font-medium text-gray-400 transition-all hover:border-red-500/30 hover:bg-red-500/10 hover:text-red-400"
          >
            <LogOut className="h-4 w-4" />
            <span className="hidden sm:inline">로그아웃</span>
          </button>
        </div>
      </div>

      {/* Quick stats */}
      <div className="mb-8 grid grid-cols-3 gap-3">
        <div className="rounded-xl border border-border bg-card p-4 text-center">
          <Heart className="mx-auto mb-2 h-5 w-5 text-red-400" />
          <div className="text-lg font-bold text-white">0</div>
          <div className="text-xs text-gray-500">관심 딜</div>
        </div>
        <div className="rounded-xl border border-border bg-card p-4 text-center">
          <ThumbsUp className="mx-auto mb-2 h-5 w-5 text-blue-400" />
          <div className="text-lg font-bold text-white">0</div>
          <div className="text-xs text-gray-500">추천</div>
        </div>
        <div className="rounded-xl border border-border bg-card p-4 text-center">
          <MessageCircle className="mx-auto mb-2 h-5 w-5 text-green-400" />
          <div className="text-lg font-bold text-white">0</div>
          <div className="text-xs text-gray-500">댓글</div>
        </div>
      </div>

      {/* Menu sections */}
      <div className="space-y-3">
        <h2 className="mb-2 text-sm font-semibold text-gray-400">메뉴</h2>

        <Link
          href="/deals"
          className="flex items-center gap-3 rounded-xl border border-border bg-card p-4 transition-all hover:border-accent/30 hover:bg-card-hover"
        >
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-accent/10">
            <Bell className="h-5 w-5 text-accent" />
          </div>
          <div className="flex-1">
            <div className="text-sm font-medium text-white">가격 알림</div>
            <div className="text-xs text-gray-500">
              관심 상품의 가격이 내려가면 알림을 받으세요
            </div>
          </div>
          <span className="rounded-full bg-accent/20 px-2 py-0.5 text-[10px] font-semibold text-accent">
            준비 중
          </span>
        </Link>

        <Link
          href="/deals"
          className="flex items-center gap-3 rounded-xl border border-border bg-card p-4 transition-all hover:border-accent/30 hover:bg-card-hover"
        >
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-red-500/10">
            <Heart className="h-5 w-5 text-red-400" />
          </div>
          <div className="flex-1">
            <div className="text-sm font-medium text-white">관심 목록</div>
            <div className="text-xs text-gray-500">
              저장한 딜 목록을 확인하세요
            </div>
          </div>
          <span className="rounded-full bg-accent/20 px-2 py-0.5 text-[10px] font-semibold text-accent">
            준비 중
          </span>
        </Link>

        <Link
          href="/deals"
          className="flex items-center gap-3 rounded-xl border border-border bg-card p-4 transition-all hover:border-accent/30 hover:bg-card-hover"
        >
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-blue-500/10">
            <Settings className="h-5 w-5 text-blue-400" />
          </div>
          <div className="flex-1">
            <div className="text-sm font-medium text-white">설정</div>
            <div className="text-xs text-gray-500">
              알림 설정, 관심 카테고리 등
            </div>
          </div>
          <span className="rounded-full bg-accent/20 px-2 py-0.5 text-[10px] font-semibold text-accent">
            준비 중
          </span>
        </Link>
      </div>
    </div>
  );
}
