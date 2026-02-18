"use client";

import { useState } from "react";
import { Share2, Check, Copy, MessageCircle } from "lucide-react";

interface ShareButtonProps {
  title: string;
  url?: string;
}

export default function ShareButton({ title, url }: ShareButtonProps) {
  const [copied, setCopied] = useState(false);
  const [showMenu, setShowMenu] = useState(false);

  const shareUrl = url || (typeof window !== "undefined" ? window.location.href : "");

  const handleCopyLink = async () => {
    try {
      await navigator.clipboard.writeText(shareUrl);
      setCopied(true);
      setTimeout(() => {
        setCopied(false);
        setShowMenu(false);
      }, 2000);
    } catch {
      // Fallback for browsers without clipboard API
      const input = document.createElement("input");
      input.value = shareUrl;
      document.body.appendChild(input);
      input.select();
      document.execCommand("copy");
      document.body.removeChild(input);
      setCopied(true);
      setTimeout(() => {
        setCopied(false);
        setShowMenu(false);
      }, 2000);
    }
  };

  const handleNativeShare = async () => {
    if (navigator.share) {
      try {
        await navigator.share({
          title: title,
          url: shareUrl,
        });
      } catch {
        // User cancelled or share failed
      }
    } else {
      setShowMenu((prev) => !prev);
    }
  };

  const handleKakaoShare = () => {
    const kakaoUrl = `https://story.kakao.com/share?url=${encodeURIComponent(shareUrl)}`;
    window.open(kakaoUrl, "_blank", "width=600,height=400");
    setShowMenu(false);
  };

  return (
    <div className="relative">
      <button
        onClick={handleNativeShare}
        className="flex items-center gap-2 rounded-lg border border-border bg-card px-4 py-2.5 text-sm font-medium text-gray-300 transition-all hover:border-accent/40 hover:bg-card-hover hover:text-accent"
        aria-label="공유하기"
      >
        <Share2 className="h-4 w-4" />
        <span>공유</span>
      </button>

      {/* Share menu dropdown */}
      {showMenu && (
        <>
          {/* Backdrop */}
          <div
            className="fixed inset-0 z-40"
            onClick={() => setShowMenu(false)}
          />
          <div className="absolute right-0 top-full z-50 mt-2 min-w-[160px] overflow-hidden rounded-xl border border-border bg-card shadow-xl shadow-black/40">
            <div className="p-1">
              <button
                onClick={handleCopyLink}
                className="flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-sm text-gray-300 transition-colors hover:bg-card-hover hover:text-white"
              >
                {copied ? (
                  <Check className="h-4 w-4 text-green-400" />
                ) : (
                  <Copy className="h-4 w-4" />
                )}
                {copied ? "복사됨!" : "링크 복사"}
              </button>
              <button
                onClick={handleKakaoShare}
                className="flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-sm text-gray-300 transition-colors hover:bg-card-hover hover:text-white"
              >
                <MessageCircle className="h-4 w-4 text-yellow-400" />
                카카오스토리
              </button>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
