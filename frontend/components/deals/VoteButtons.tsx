"use client";

import React, { useState, useEffect } from "react";
import { ThumbsUp, ThumbsDown } from "lucide-react";
import { useAuth } from "@/lib/auth";
import { apiClient } from "@/lib/api";
import AuthModal from "@/components/auth/AuthModal";

interface VoteButtonsProps {
  dealId: string;
  initialVoteUp: number;
  initialVoteDown?: number;
}

export default function VoteButtons({
  dealId,
  initialVoteUp,
  initialVoteDown = 0,
}: VoteButtonsProps) {
  const { user } = useAuth();
  const [voteUp, setVoteUp] = useState(initialVoteUp);
  const [voteDown, setVoteDown] = useState(initialVoteDown);
  const [userVote, setUserVote] = useState<"up" | "down" | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [showAuthModal, setShowAuthModal] = useState(false);

  // Fetch user's existing vote on mount
  useEffect(() => {
    if (!user) return;
    const fetchVote = async () => {
      try {
        const res = await apiClient.get(`/deals/${dealId}/vote`);
        if (res.data.status === "success") {
          setUserVote(res.data.data.user_vote);
        }
      } catch {
        // Silently ignore - user just hasn't voted
      }
    };
    fetchVote();
  }, [user, dealId]);

  const handleVote = async (voteType: "up" | "down") => {
    if (!user) {
      setShowAuthModal(true);
      return;
    }

    if (isLoading) return;

    setIsLoading(true);

    try {
      const response = await apiClient.post(`/deals/${dealId}/vote`, { vote_type: voteType });

      if (response.data.status === "success") {
        const { vote_up, vote_down, user_vote } = response.data.data;
        setVoteUp(vote_up);
        setVoteDown(vote_down);
        setUserVote(user_vote);
      }
    } catch (error) {
      console.error("Vote failed:", error);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <>
      <div className="flex items-center gap-2">
        <button
        onClick={() => handleVote("up")}
        disabled={isLoading}
        className={`group flex items-center gap-2 rounded-lg border px-4 py-2 transition-all disabled:cursor-not-allowed disabled:opacity-50 ${
          userVote === "up"
            ? "border-accent bg-accent/10 text-accent"
            : "border-border bg-card text-gray-400 hover:border-accent/50 hover:bg-accent/5 hover:text-accent"
        }`}
        aria-label="추천"
      >
        <ThumbsUp
          className={`h-4 w-4 transition-transform ${userVote === "up" ? "fill-current" : ""} group-hover:scale-110`}
        />
        <span className="text-sm font-semibold">{voteUp.toLocaleString()}</span>
      </button>

      <button
        onClick={() => handleVote("down")}
        disabled={isLoading}
        className={`group flex items-center gap-2 rounded-lg border px-4 py-2 transition-all disabled:cursor-not-allowed disabled:opacity-50 ${
          userVote === "down"
            ? "border-red-500 bg-red-500/10 text-red-400"
            : "border-border bg-card text-gray-400 hover:border-red-500/50 hover:bg-red-500/5 hover:text-red-400"
        }`}
        aria-label="비추천"
      >
        <ThumbsDown
          className={`h-4 w-4 transition-transform ${userVote === "down" ? "fill-current" : ""} group-hover:scale-110`}
        />
        <span className="text-sm font-semibold">{voteDown.toLocaleString()}</span>
      </button>
      </div>

      {/* Auth Modal */}
      <AuthModal isOpen={showAuthModal} onClose={() => setShowAuthModal(false)} />
    </>
  );
}
