"use client";

import React, { useState } from "react";
import useSWR from "swr";
import { MessageCircle, Reply, Trash2, Send } from "lucide-react";
import { useAuth } from "@/lib/auth";
import { apiClient, fetcher } from "@/lib/api";
import { ApiResponse, Comment } from "@/lib/types";
import RelativeTime from "@/components/common/RelativeTime";

interface CommentSectionProps {
  dealId: string;
}

function CommentItem({
  comment,
  dealId,
  onReply,
  onDelete,
  currentUserId,
}: {
  comment: Comment;
  dealId: string;
  onReply: (commentId: string) => void;
  onDelete: (commentId: string) => void;
  currentUserId?: string;
}) {
  const isOwner = currentUserId === comment.user.id;

  if (comment.is_deleted) {
    return (
      <div className="rounded-lg border border-border bg-surface/50 p-4">
        <p className="text-sm text-gray-500">삭제된 댓글입니다</p>
      </div>
    );
  }

  return (
    <div className="rounded-lg border border-border bg-card p-4">
      <div className="mb-2 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="font-semibold text-gray-200">{comment.user.username}</span>
          <span className="text-xs text-gray-500">
            <RelativeTime date={comment.created_at} />
          </span>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => onReply(comment.id)}
            className="flex items-center gap-1 rounded-lg px-2 py-1 text-xs font-medium text-gray-400 transition-colors hover:bg-surface hover:text-accent"
          >
            <Reply className="h-3 w-3" />
            답글
          </button>
          {isOwner && (
            <button
              onClick={() => onDelete(comment.id)}
              className="flex items-center gap-1 rounded-lg px-2 py-1 text-xs font-medium text-gray-400 transition-colors hover:bg-red-500/10 hover:text-red-400"
            >
              <Trash2 className="h-3 w-3" />
              삭제
            </button>
          )}
        </div>
      </div>
      <p className="text-sm leading-relaxed text-gray-300">{comment.content}</p>

      {/* Nested replies */}
      {comment.replies && comment.replies.length > 0 && (
        <div className="ml-6 mt-3 space-y-3 border-l-2 border-border pl-4">
          {comment.replies.map((reply) => (
            <CommentItem
              key={reply.id}
              comment={reply}
              dealId={dealId}
              onReply={onReply}
              onDelete={onDelete}
              currentUserId={currentUserId}
            />
          ))}
        </div>
      )}
    </div>
  );
}

export default function CommentSection({ dealId }: CommentSectionProps) {
  const { user } = useAuth();
  const [newComment, setNewComment] = useState("");
  const [replyingTo, setReplyingTo] = useState<string | null>(null);
  const [replyContent, setReplyContent] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  const { data, error, mutate } = useSWR<ApiResponse<Comment[]>>(
    `/deals/${dealId}/comments`,
    fetcher,
    {
      refreshInterval: 10000, // Auto-refresh every 10s
    }
  );

  const comments = data?.data || [];
  const isLoading = !data && !error;

  const handleSubmitComment = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!user || !newComment.trim() || isSubmitting) return;

    setIsSubmitting(true);
    try {
      await apiClient.post(`/deals/${dealId}/comments`, { content: newComment.trim() });
      setNewComment("");
      mutate(); // Refresh comments
    } catch (err) {
      console.error("Failed to post comment:", err);
      alert("댓글 작성에 실패했습니다");
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleSubmitReply = async (parentId: string) => {
    if (!user || !replyContent.trim() || isSubmitting) return;

    setIsSubmitting(true);
    try {
      await apiClient.post(`/deals/${dealId}/comments`, {
        content: replyContent.trim(),
        parent_id: parentId,
      });
      setReplyContent("");
      setReplyingTo(null);
      mutate(); // Refresh comments
    } catch (err) {
      console.error("Failed to post reply:", err);
      alert("답글 작성에 실패했습니다");
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleDeleteComment = async (commentId: string) => {
    if (!confirm("댓글을 삭제하시겠습니까?")) return;

    try {
      await apiClient.delete(`/deals/${dealId}/comments/${commentId}`);
      mutate(); // Refresh comments
    } catch (err) {
      console.error("Failed to delete comment:", err);
      alert("댓글 삭제에 실패했습니다");
    }
  };

  return (
    <div className="rounded-xl border border-border bg-card p-6">
      <div className="mb-6 flex items-center gap-2">
        <MessageCircle className="h-5 w-5 text-gray-400" />
        <h2 className="text-lg font-semibold text-white">댓글 ({comments.length})</h2>
      </div>

      {/* Comment input */}
      {user ? (
        <form onSubmit={handleSubmitComment} className="mb-6">
          <div className="flex gap-2">
            <input
              type="text"
              value={newComment}
              onChange={(e) => setNewComment(e.target.value)}
              placeholder="댓글을 작성하세요..."
              className="flex-1 rounded-lg border border-border bg-surface px-4 py-2.5 text-gray-200 transition-colors placeholder:text-gray-500 focus:border-accent focus:outline-none focus:ring-2 focus:ring-accent/20"
            />
            <button
              type="submit"
              disabled={!newComment.trim() || isSubmitting}
              className="btn-primary flex items-center gap-2 px-6 disabled:cursor-not-allowed disabled:opacity-50"
            >
              <Send className="h-4 w-4" />
              <span className="hidden sm:inline">작성</span>
            </button>
          </div>
        </form>
      ) : (
        <div className="mb-6 rounded-lg border border-yellow-500/30 bg-yellow-500/10 p-4 text-center text-sm text-yellow-400">
          로그인이 필요합니다
        </div>
      )}

      {/* Comments list */}
      {isLoading ? (
        <div className="space-y-3">
          {[1, 2, 3].map((i) => (
            <div key={i} className="animate-pulse rounded-lg bg-surface p-4">
              <div className="mb-2 h-4 w-32 rounded bg-border"></div>
              <div className="h-3 w-full rounded bg-border"></div>
              <div className="mt-1 h-3 w-2/3 rounded bg-border"></div>
            </div>
          ))}
        </div>
      ) : error ? (
        <p className="py-8 text-center text-sm text-red-400">댓글을 불러오는데 실패했습니다</p>
      ) : comments.length === 0 ? (
        <p className="py-8 text-center text-sm text-gray-500">첫 댓글을 작성해보세요</p>
      ) : (
        <div className="space-y-4">
          {comments.map((comment) => (
            <div key={comment.id}>
              <CommentItem
                comment={comment}
                dealId={dealId}
                onReply={setReplyingTo}
                onDelete={handleDeleteComment}
                currentUserId={user?.id}
              />

              {/* Reply form */}
              {replyingTo === comment.id && user && (
                <div className="ml-6 mt-3 flex gap-2 border-l-2 border-accent pl-4">
                  <input
                    type="text"
                    value={replyContent}
                    onChange={(e) => setReplyContent(e.target.value)}
                    placeholder={`${comment.user.username}님에게 답글 작성...`}
                    className="flex-1 rounded-lg border border-border bg-surface px-4 py-2 text-sm text-gray-200 transition-colors placeholder:text-gray-500 focus:border-accent focus:outline-none focus:ring-2 focus:ring-accent/20"
                    autoFocus
                  />
                  <button
                    onClick={() => handleSubmitReply(comment.id)}
                    disabled={!replyContent.trim() || isSubmitting}
                    className="btn-primary px-4 py-2 text-sm disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    <Send className="h-4 w-4" />
                  </button>
                  <button
                    onClick={() => {
                      setReplyingTo(null);
                      setReplyContent("");
                    }}
                    className="rounded-lg border border-border bg-card px-4 py-2 text-sm text-gray-400 transition-colors hover:bg-surface hover:text-gray-200"
                  >
                    취소
                  </button>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
