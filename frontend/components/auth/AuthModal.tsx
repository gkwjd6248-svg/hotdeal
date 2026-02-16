"use client";

import React, { useState } from "react";
import { X } from "lucide-react";
import { useAuth } from "@/lib/auth";

interface AuthModalProps {
  isOpen: boolean;
  onClose: () => void;
}

type TabType = "login" | "register";

export default function AuthModal({ isOpen, onClose }: AuthModalProps) {
  const { login, register } = useAuth();
  const [activeTab, setActiveTab] = useState<TabType>("login");
  const [error, setError] = useState<string>("");
  const [isLoading, setIsLoading] = useState(false);

  // Login form state
  const [loginEmail, setLoginEmail] = useState("");
  const [loginPassword, setLoginPassword] = useState("");

  // Register form state
  const [registerEmail, setRegisterEmail] = useState("");
  const [registerUsername, setRegisterUsername] = useState("");
  const [registerPassword, setRegisterPassword] = useState("");

  if (!isOpen) return null;

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setIsLoading(true);

    try {
      await login(loginEmail, loginPassword);
      onClose();
      setLoginEmail("");
      setLoginPassword("");
    } catch (err: any) {
      setError(err?.response?.data?.detail || err?.message || "로그인에 실패했습니다");
    } finally {
      setIsLoading(false);
    }
  };

  const handleRegister = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setIsLoading(true);

    try {
      await register(registerEmail, registerUsername, registerPassword);
      onClose();
      setRegisterEmail("");
      setRegisterUsername("");
      setRegisterPassword("");
    } catch (err: any) {
      setError(err?.response?.data?.detail || err?.message || "회원가입에 실패했습니다");
    } finally {
      setIsLoading(false);
    }
  };

  const handleClose = () => {
    setError("");
    setLoginEmail("");
    setLoginPassword("");
    setRegisterEmail("");
    setRegisterUsername("");
    setRegisterPassword("");
    onClose();
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm">
      <div className="relative w-full max-w-md rounded-xl border border-border bg-card p-6 shadow-xl">
        {/* Close button */}
        <button
          onClick={handleClose}
          className="absolute right-4 top-4 rounded-lg p-1 text-gray-400 transition-colors hover:bg-surface hover:text-gray-200"
          aria-label="닫기"
        >
          <X className="h-5 w-5" />
        </button>

        {/* Tabs */}
        <div className="mb-6 flex gap-2 border-b border-border">
          <button
            onClick={() => {
              setActiveTab("login");
              setError("");
            }}
            className={`flex-1 border-b-2 pb-3 text-sm font-semibold transition-colors ${
              activeTab === "login"
                ? "border-accent text-accent"
                : "border-transparent text-gray-400 hover:text-gray-300"
            }`}
          >
            로그인
          </button>
          <button
            onClick={() => {
              setActiveTab("register");
              setError("");
            }}
            className={`flex-1 border-b-2 pb-3 text-sm font-semibold transition-colors ${
              activeTab === "register"
                ? "border-accent text-accent"
                : "border-transparent text-gray-400 hover:text-gray-300"
            }`}
          >
            회원가입
          </button>
        </div>

        {/* Error display */}
        {error && (
          <div className="mb-4 rounded-lg border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-400">
            {error}
          </div>
        )}

        {/* Login form */}
        {activeTab === "login" && (
          <form onSubmit={handleLogin} className="space-y-4">
            <div>
              <label htmlFor="login-email" className="mb-1.5 block text-sm font-medium text-gray-300">
                이메일
              </label>
              <input
                id="login-email"
                type="email"
                value={loginEmail}
                onChange={(e) => setLoginEmail(e.target.value)}
                required
                className="w-full rounded-lg border border-border bg-surface px-4 py-2.5 text-gray-200 transition-colors placeholder:text-gray-500 focus:border-accent focus:outline-none focus:ring-2 focus:ring-accent/20"
                placeholder="email@example.com"
              />
            </div>
            <div>
              <label htmlFor="login-password" className="mb-1.5 block text-sm font-medium text-gray-300">
                비밀번호
              </label>
              <input
                id="login-password"
                type="password"
                value={loginPassword}
                onChange={(e) => setLoginPassword(e.target.value)}
                required
                className="w-full rounded-lg border border-border bg-surface px-4 py-2.5 text-gray-200 transition-colors placeholder:text-gray-500 focus:border-accent focus:outline-none focus:ring-2 focus:ring-accent/20"
                placeholder="••••••••"
              />
            </div>
            <button
              type="submit"
              disabled={isLoading}
              className="btn-primary w-full py-3 text-base font-semibold disabled:cursor-not-allowed disabled:opacity-50"
            >
              {isLoading ? "로그인 중..." : "로그인"}
            </button>
          </form>
        )}

        {/* Register form */}
        {activeTab === "register" && (
          <form onSubmit={handleRegister} className="space-y-4">
            <div>
              <label htmlFor="register-email" className="mb-1.5 block text-sm font-medium text-gray-300">
                이메일
              </label>
              <input
                id="register-email"
                type="email"
                value={registerEmail}
                onChange={(e) => setRegisterEmail(e.target.value)}
                required
                className="w-full rounded-lg border border-border bg-surface px-4 py-2.5 text-gray-200 transition-colors placeholder:text-gray-500 focus:border-accent focus:outline-none focus:ring-2 focus:ring-accent/20"
                placeholder="email@example.com"
              />
            </div>
            <div>
              <label htmlFor="register-username" className="mb-1.5 block text-sm font-medium text-gray-300">
                닉네임
              </label>
              <input
                id="register-username"
                type="text"
                value={registerUsername}
                onChange={(e) => setRegisterUsername(e.target.value)}
                required
                minLength={2}
                maxLength={20}
                className="w-full rounded-lg border border-border bg-surface px-4 py-2.5 text-gray-200 transition-colors placeholder:text-gray-500 focus:border-accent focus:outline-none focus:ring-2 focus:ring-accent/20"
                placeholder="닉네임"
              />
            </div>
            <div>
              <label htmlFor="register-password" className="mb-1.5 block text-sm font-medium text-gray-300">
                비밀번호
              </label>
              <input
                id="register-password"
                type="password"
                value={registerPassword}
                onChange={(e) => setRegisterPassword(e.target.value)}
                required
                minLength={8}
                className="w-full rounded-lg border border-border bg-surface px-4 py-2.5 text-gray-200 transition-colors placeholder:text-gray-500 focus:border-accent focus:outline-none focus:ring-2 focus:ring-accent/20"
                placeholder="••••••••"
              />
              <p className="mt-1.5 text-xs text-gray-500">8자 이상, 영문 + 숫자 포함</p>
            </div>
            <button
              type="submit"
              disabled={isLoading}
              className="btn-primary w-full py-3 text-base font-semibold disabled:cursor-not-allowed disabled:opacity-50"
            >
              {isLoading ? "가입 중..." : "회원가입"}
            </button>
          </form>
        )}
      </div>
    </div>
  );
}
