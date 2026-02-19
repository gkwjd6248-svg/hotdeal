"use client";

import React, { useState, useMemo, useEffect, Suspense } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import { Flame, Zap, Eye, EyeOff, Check, AlertCircle, ArrowLeft } from "lucide-react";
import { useAuth } from "@/lib/auth";

type TabType = "login" | "register" | "reset";

function PasswordStrength({ password }: { password: string }) {
  const strength = useMemo(() => {
    if (!password) return { level: 0, label: "", color: "" };
    let score = 0;
    if (password.length >= 8) score++;
    if (password.length >= 12) score++;
    if (/[a-z]/.test(password) && /[A-Z]/.test(password)) score++;
    if (/\d/.test(password)) score++;
    if (/[^a-zA-Z0-9]/.test(password)) score++;

    if (score <= 1) return { level: 1, label: "약함", color: "bg-red-500" };
    if (score <= 2) return { level: 2, label: "보통", color: "bg-yellow-500" };
    if (score <= 3) return { level: 3, label: "강함", color: "bg-green-500" };
    return { level: 4, label: "매우 강함", color: "bg-emerald-400" };
  }, [password]);

  if (!password) return null;

  return (
    <div className="mt-1.5">
      <div className="flex gap-1">
        {[1, 2, 3, 4].map((i) => (
          <div
            key={i}
            className={`h-1 flex-1 rounded-full transition-colors ${
              i <= strength.level ? strength.color : "bg-gray-700"
            }`}
          />
        ))}
      </div>
      <p className="mt-1 text-[10px] text-gray-500">
        비밀번호 강도: <span className="font-medium">{strength.label}</span>
      </p>
    </div>
  );
}

function LoginPageContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { user, isLoading: authLoading, login, register, resetPassword } = useAuth();

  const tabParam = searchParams.get("tab");
  const initialTab: TabType =
    tabParam === "register" ? "register" : tabParam === "reset" ? "reset" : "login";

  const [activeTab, setActiveTab] = useState<TabType>(initialTab);
  const [error, setError] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [resetSent, setResetSent] = useState(false);

  // Login form
  const [loginEmail, setLoginEmail] = useState("");
  const [loginPassword, setLoginPassword] = useState("");

  // Register form
  const [registerEmail, setRegisterEmail] = useState("");
  const [registerUsername, setRegisterUsername] = useState("");
  const [registerPassword, setRegisterPassword] = useState("");
  const [registerPasswordConfirm, setRegisterPasswordConfirm] = useState("");

  // Reset form
  const [resetEmail, setResetEmail] = useState("");

  // Redirect if already logged in
  useEffect(() => {
    if (!authLoading && user) {
      router.replace("/");
    }
  }, [authLoading, user, router]);

  // Sync tab with URL param
  useEffect(() => {
    const t = searchParams.get("tab");
    if (t === "register") setActiveTab("register");
    else if (t === "reset") setActiveTab("reset");
    else setActiveTab("login");
  }, [searchParams]);

  const registerValidation = useMemo(() => {
    const errors: string[] = [];
    if (registerPassword && registerPassword.length < 8)
      errors.push("비밀번호는 8자 이상이어야 합니다");
    if (registerPassword && !/[a-zA-Z]/.test(registerPassword))
      errors.push("영문자를 포함해야 합니다");
    if (registerPassword && !/\d/.test(registerPassword))
      errors.push("숫자를 포함해야 합니다");
    if (registerPasswordConfirm && registerPassword !== registerPasswordConfirm)
      errors.push("비밀번호가 일치하지 않습니다");
    if (registerUsername && registerUsername.length < 2)
      errors.push("닉네임은 2자 이상이어야 합니다");
    return errors;
  }, [registerPassword, registerPasswordConfirm, registerUsername]);

  const canSubmitRegister =
    registerEmail &&
    registerUsername.length >= 2 &&
    registerPassword.length >= 8 &&
    /[a-zA-Z]/.test(registerPassword) &&
    /\d/.test(registerPassword) &&
    registerPassword === registerPasswordConfirm;

  if (authLoading || user) {
    return (
      <div className="flex min-h-[80vh] items-center justify-center">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-accent border-t-transparent" />
      </div>
    );
  }

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setIsLoading(true);
    try {
      await login(loginEmail, loginPassword);
      router.push("/");
    } catch (err: any) {
      setError(err?.response?.data?.detail || err?.message || "로그인에 실패했습니다");
    } finally {
      setIsLoading(false);
    }
  };

  const handleRegister = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!canSubmitRegister) return;
    setError("");
    setIsLoading(true);
    try {
      await register(registerEmail, registerUsername, registerPassword);
      router.push("/");
    } catch (err: any) {
      setError(err?.response?.data?.detail || err?.message || "회원가입에 실패했습니다");
    } finally {
      setIsLoading(false);
    }
  };

  const handleResetPassword = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setIsLoading(true);
    try {
      await resetPassword(resetEmail);
      setResetSent(true);
    } catch (err: any) {
      setError(err?.response?.data?.detail || err?.message || "요청 처리에 실패했습니다");
    } finally {
      setIsLoading(false);
    }
  };

  const switchTab = (tab: TabType) => {
    setActiveTab(tab);
    setError("");
    setResetSent(false);
    const url = tab === "login" ? "/login" : `/login?tab=${tab}`;
    router.replace(url);
  };

  const inputClass =
    "w-full rounded-lg border border-border bg-surface px-4 py-2.5 text-gray-200 transition-colors placeholder:text-gray-500 focus:border-accent focus:outline-none focus:ring-2 focus:ring-accent/20";

  return (
    <div className="flex min-h-[80vh] items-center justify-center px-4 py-12">
      <div className="w-full max-w-md">
        {/* Logo */}
        <Link
          href="/"
          className="group mb-8 flex flex-col items-center gap-2"
        >
          <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-gradient-to-br from-accent to-orange-600 shadow-lg shadow-accent/30 transition-shadow group-hover:shadow-accent/50">
            <Flame className="h-6 w-6 text-white" />
          </div>
          <div className="flex flex-col items-center leading-none">
            <span className="text-xl font-extrabold tracking-tight text-white">
              Deal<span className="text-accent">Hawk</span>
            </span>
            <span className="flex items-center gap-0.5 text-[10px] font-medium text-gray-500">
              <Zap className="h-2.5 w-2.5 text-accent/60" />
              AI 특가 자동수집
            </span>
          </div>
        </Link>

        {/* Card */}
        <div className="rounded-2xl border border-border bg-card p-6 shadow-xl shadow-black/20">
          {/* Tabs */}
          <div className="mb-6 flex gap-2 border-b border-border">
            <button
              onClick={() => switchTab("login")}
              className={`flex-1 border-b-2 pb-3 text-sm font-semibold transition-colors ${
                activeTab === "login"
                  ? "border-accent text-accent"
                  : "border-transparent text-gray-400 hover:text-gray-300"
              }`}
            >
              로그인
            </button>
            <button
              onClick={() => switchTab("register")}
              className={`flex-1 border-b-2 pb-3 text-sm font-semibold transition-colors ${
                activeTab === "register"
                  ? "border-accent text-accent"
                  : "border-transparent text-gray-400 hover:text-gray-300"
              }`}
            >
              회원가입
            </button>
            <button
              onClick={() => switchTab("reset")}
              className={`flex-1 border-b-2 pb-3 text-sm font-semibold transition-colors ${
                activeTab === "reset"
                  ? "border-accent text-accent"
                  : "border-transparent text-gray-400 hover:text-gray-300"
              }`}
            >
              비밀번호 찾기
            </button>
          </div>

          {/* Error */}
          {error && (
            <div className="mb-4 flex items-center gap-2 rounded-lg border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-400">
              <AlertCircle className="h-4 w-4 flex-shrink-0" />
              {error}
            </div>
          )}

          {/* Login Tab */}
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
                  className={inputClass}
                  placeholder="email@example.com"
                  autoComplete="email"
                />
              </div>
              <div>
                <label htmlFor="login-password" className="mb-1.5 block text-sm font-medium text-gray-300">
                  비밀번호
                </label>
                <div className="relative">
                  <input
                    id="login-password"
                    type={showPassword ? "text" : "password"}
                    value={loginPassword}
                    onChange={(e) => setLoginPassword(e.target.value)}
                    required
                    className={`${inputClass} pr-10`}
                    placeholder="비밀번호 입력"
                    autoComplete="current-password"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-500 hover:text-gray-300"
                    tabIndex={-1}
                  >
                    {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                  </button>
                </div>
              </div>
              <button
                type="submit"
                disabled={isLoading}
                className="btn-primary w-full py-3 text-base font-semibold disabled:cursor-not-allowed disabled:opacity-50"
              >
                {isLoading ? "로그인 중..." : "로그인"}
              </button>
              <div className="flex items-center justify-between text-xs text-gray-500">
                <button
                  type="button"
                  onClick={() => switchTab("reset")}
                  className="hover:text-accent hover:underline"
                >
                  비밀번호를 잊으셨나요?
                </button>
                <button
                  type="button"
                  onClick={() => switchTab("register")}
                  className="font-medium text-accent hover:underline"
                >
                  회원가입
                </button>
              </div>
            </form>
          )}

          {/* Register Tab */}
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
                  className={inputClass}
                  placeholder="email@example.com"
                  autoComplete="email"
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
                  className={inputClass}
                  placeholder="2~20자"
                  autoComplete="username"
                />
                {registerUsername && registerUsername.length >= 2 && (
                  <p className="mt-1 flex items-center gap-1 text-[10px] text-green-400">
                    <Check className="h-3 w-3" /> 사용 가능
                  </p>
                )}
              </div>
              <div>
                <label htmlFor="register-password" className="mb-1.5 block text-sm font-medium text-gray-300">
                  비밀번호
                </label>
                <div className="relative">
                  <input
                    id="register-password"
                    type={showPassword ? "text" : "password"}
                    value={registerPassword}
                    onChange={(e) => setRegisterPassword(e.target.value)}
                    required
                    minLength={8}
                    className={`${inputClass} pr-10`}
                    placeholder="8자 이상, 영문 + 숫자"
                    autoComplete="new-password"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-500 hover:text-gray-300"
                    tabIndex={-1}
                  >
                    {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                  </button>
                </div>
                <PasswordStrength password={registerPassword} />
              </div>
              <div>
                <label htmlFor="register-password-confirm" className="mb-1.5 block text-sm font-medium text-gray-300">
                  비밀번호 확인
                </label>
                <input
                  id="register-password-confirm"
                  type={showPassword ? "text" : "password"}
                  value={registerPasswordConfirm}
                  onChange={(e) => setRegisterPasswordConfirm(e.target.value)}
                  required
                  className={inputClass}
                  placeholder="비밀번호 재입력"
                  autoComplete="new-password"
                />
                {registerPasswordConfirm && (
                  <p
                    className={`mt-1 flex items-center gap-1 text-[10px] ${
                      registerPassword === registerPasswordConfirm
                        ? "text-green-400"
                        : "text-red-400"
                    }`}
                  >
                    {registerPassword === registerPasswordConfirm ? (
                      <>
                        <Check className="h-3 w-3" /> 일치
                      </>
                    ) : (
                      <>
                        <AlertCircle className="h-3 w-3" /> 불일치
                      </>
                    )}
                  </p>
                )}
              </div>

              {registerValidation.length > 0 && registerPassword && (
                <div className="rounded-lg border border-yellow-500/20 bg-yellow-500/5 p-2.5">
                  {registerValidation.map((msg, i) => (
                    <p key={i} className="flex items-center gap-1.5 text-[11px] text-yellow-400/80">
                      <AlertCircle className="h-3 w-3 flex-shrink-0" />
                      {msg}
                    </p>
                  ))}
                </div>
              )}

              <button
                type="submit"
                disabled={isLoading || !canSubmitRegister}
                className="btn-primary w-full py-3 text-base font-semibold disabled:cursor-not-allowed disabled:opacity-50"
              >
                {isLoading ? "가입 중..." : "회원가입"}
              </button>
              <p className="text-center text-xs text-gray-500">
                이미 계정이 있으신가요?{" "}
                <button
                  type="button"
                  onClick={() => switchTab("login")}
                  className="font-medium text-accent hover:underline"
                >
                  로그인
                </button>
              </p>
            </form>
          )}

          {/* Reset Password Tab */}
          {activeTab === "reset" && (
            <>
              {resetSent ? (
                <div className="space-y-4 text-center">
                  <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-full bg-green-500/10">
                    <Check className="h-8 w-8 text-green-400" />
                  </div>
                  <h3 className="text-lg font-bold text-white">이메일을 확인해주세요</h3>
                  <p className="text-sm text-gray-400">
                    <span className="font-medium text-gray-200">{resetEmail}</span>
                    (으)로 비밀번호 재설정 링크를 보냈습니다.
                    <br />
                    메일함을 확인해주세요.
                  </p>
                  <button
                    onClick={() => switchTab("login")}
                    className="inline-flex items-center gap-1.5 text-sm font-medium text-accent hover:underline"
                  >
                    <ArrowLeft className="h-4 w-4" />
                    로그인으로 돌아가기
                  </button>
                </div>
              ) : (
                <form onSubmit={handleResetPassword} className="space-y-4">
                  <p className="text-sm text-gray-400">
                    가입 시 사용한 이메일을 입력하시면 비밀번호 재설정 링크를 보내드립니다.
                  </p>
                  <div>
                    <label htmlFor="reset-email" className="mb-1.5 block text-sm font-medium text-gray-300">
                      이메일
                    </label>
                    <input
                      id="reset-email"
                      type="email"
                      value={resetEmail}
                      onChange={(e) => setResetEmail(e.target.value)}
                      required
                      className={inputClass}
                      placeholder="email@example.com"
                      autoComplete="email"
                    />
                  </div>
                  <button
                    type="submit"
                    disabled={isLoading || !resetEmail}
                    className="btn-primary w-full py-3 text-base font-semibold disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    {isLoading ? "전송 중..." : "재설정 링크 전송"}
                  </button>
                  <p className="text-center text-xs text-gray-500">
                    <button
                      type="button"
                      onClick={() => switchTab("login")}
                      className="inline-flex items-center gap-1 font-medium text-accent hover:underline"
                    >
                      <ArrowLeft className="h-3 w-3" />
                      로그인으로 돌아가기
                    </button>
                  </p>
                </form>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}

export default function LoginPage() {
  return (
    <Suspense
      fallback={
        <div className="flex min-h-[80vh] items-center justify-center">
          <div className="h-8 w-8 animate-spin rounded-full border-2 border-accent border-t-transparent" />
        </div>
      }
    >
      <LoginPageContent />
    </Suspense>
  );
}
