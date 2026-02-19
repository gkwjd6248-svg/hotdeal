"use client";

import React, { useState, useMemo } from "react";
import { X, Eye, EyeOff, Check, AlertCircle } from "lucide-react";
import { useAuth } from "@/lib/auth";

interface AuthModalProps {
  isOpen: boolean;
  onClose: () => void;
}

type TabType = "login" | "register";

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

export default function AuthModal({ isOpen, onClose }: AuthModalProps) {
  const { login, register } = useAuth();
  const [activeTab, setActiveTab] = useState<TabType>("login");
  const [error, setError] = useState<string>("");
  const [isLoading, setIsLoading] = useState(false);
  const [showPassword, setShowPassword] = useState(false);

  // Login form state
  const [loginEmail, setLoginEmail] = useState("");
  const [loginPassword, setLoginPassword] = useState("");

  // Register form state
  const [registerEmail, setRegisterEmail] = useState("");
  const [registerUsername, setRegisterUsername] = useState("");
  const [registerPassword, setRegisterPassword] = useState("");
  const [registerPasswordConfirm, setRegisterPasswordConfirm] = useState("");

  // Validation
  const registerValidation = useMemo(() => {
    const errors: string[] = [];
    if (registerPassword && registerPassword.length < 8)
      errors.push("비밀번호는 8자 이상이어야 합니다");
    if (registerPassword && !/[a-zA-Z]/.test(registerPassword))
      errors.push("영문자를 포함해야 합니다");
    if (registerPassword && !/\d/.test(registerPassword))
      errors.push("숫자를 포함해야 합니다");
    if (
      registerPasswordConfirm &&
      registerPassword !== registerPasswordConfirm
    )
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
      setError(
        err?.response?.data?.detail || err?.message || "로그인에 실패했습니다"
      );
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
      onClose();
      setRegisterEmail("");
      setRegisterUsername("");
      setRegisterPassword("");
      setRegisterPasswordConfirm("");
    } catch (err: any) {
      setError(
        err?.response?.data?.detail ||
          err?.message ||
          "회원가입에 실패했습니다"
      );
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
    setRegisterPasswordConfirm("");
    setShowPassword(false);
    onClose();
  };

  const inputClass =
    "w-full rounded-lg border border-border bg-surface px-4 py-2.5 text-gray-200 transition-colors placeholder:text-gray-500 focus:border-accent focus:outline-none focus:ring-2 focus:ring-accent/20";

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
          <div className="mb-4 flex items-center gap-2 rounded-lg border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-400">
            <AlertCircle className="h-4 w-4 flex-shrink-0" />
            {error}
          </div>
        )}

        {/* Login form */}
        {activeTab === "login" && (
          <form onSubmit={handleLogin} className="space-y-4">
            <div>
              <label
                htmlFor="login-email"
                className="mb-1.5 block text-sm font-medium text-gray-300"
              >
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
              />
            </div>
            <div>
              <label
                htmlFor="login-password"
                className="mb-1.5 block text-sm font-medium text-gray-300"
              >
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
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-500 hover:text-gray-300"
                  tabIndex={-1}
                >
                  {showPassword ? (
                    <EyeOff className="h-4 w-4" />
                  ) : (
                    <Eye className="h-4 w-4" />
                  )}
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
            <p className="text-center text-xs text-gray-500">
              계정이 없으신가요?{" "}
              <button
                type="button"
                onClick={() => {
                  setActiveTab("register");
                  setError("");
                }}
                className="font-medium text-accent hover:underline"
              >
                회원가입
              </button>
            </p>
          </form>
        )}

        {/* Register form */}
        {activeTab === "register" && (
          <form onSubmit={handleRegister} className="space-y-4">
            <div>
              <label
                htmlFor="register-email"
                className="mb-1.5 block text-sm font-medium text-gray-300"
              >
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
              />
            </div>
            <div>
              <label
                htmlFor="register-username"
                className="mb-1.5 block text-sm font-medium text-gray-300"
              >
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
              />
              {registerUsername && registerUsername.length >= 2 && (
                <p className="mt-1 flex items-center gap-1 text-[10px] text-green-400">
                  <Check className="h-3 w-3" /> 사용 가능
                </p>
              )}
            </div>
            <div>
              <label
                htmlFor="register-password"
                className="mb-1.5 block text-sm font-medium text-gray-300"
              >
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
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-500 hover:text-gray-300"
                  tabIndex={-1}
                >
                  {showPassword ? (
                    <EyeOff className="h-4 w-4" />
                  ) : (
                    <Eye className="h-4 w-4" />
                  )}
                </button>
              </div>
              <PasswordStrength password={registerPassword} />
            </div>
            <div>
              <label
                htmlFor="register-password-confirm"
                className="mb-1.5 block text-sm font-medium text-gray-300"
              >
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

            {/* Validation errors */}
            {registerValidation.length > 0 && registerPassword && (
              <div className="rounded-lg border border-yellow-500/20 bg-yellow-500/5 p-2.5">
                {registerValidation.map((msg, i) => (
                  <p
                    key={i}
                    className="flex items-center gap-1.5 text-[11px] text-yellow-400/80"
                  >
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
                onClick={() => {
                  setActiveTab("login");
                  setError("");
                }}
                className="font-medium text-accent hover:underline"
              >
                로그인
              </button>
            </p>
          </form>
        )}
      </div>
    </div>
  );
}
