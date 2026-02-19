"use client";

import React, { createContext, useContext, useState, useEffect, useCallback } from "react";
import { apiClient } from "./api";
import { AuthUser, ApiResponse } from "./types";

interface AuthContextType {
  user: AuthUser | null;
  token: string | null;
  isLoading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, username: string, password: string) => Promise<void>;
  logout: () => void;
  resetPassword: (email: string) => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

interface AuthResponse {
  user: AuthUser;
  token: { access_token: string; token_type: string };
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  // Load user from token on mount
  useEffect(() => {
    const loadUser = async () => {
      const storedToken = localStorage.getItem("dealhawk_token");
      if (!storedToken) {
        setIsLoading(false);
        return;
      }

      try {
        // Set token in axios default headers
        apiClient.defaults.headers.common["Authorization"] = `Bearer ${storedToken}`;

        const response = await apiClient.get<ApiResponse<AuthUser>>("/auth/me");
        if (response.data.status === "success") {
          setUser(response.data.data);
          setToken(storedToken);
        } else {
          localStorage.removeItem("dealhawk_token");
          delete apiClient.defaults.headers.common["Authorization"];
        }
      } catch (error) {
        console.error("Failed to load user:", error);
        localStorage.removeItem("dealhawk_token");
        delete apiClient.defaults.headers.common["Authorization"];
      } finally {
        setIsLoading(false);
      }
    };

    loadUser();
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    const response = await apiClient.post<ApiResponse<AuthResponse>>("/auth/login", {
      email,
      password,
    });

    if (response.data.status === "success") {
      const { user: userData, token: tokenData } = response.data.data;
      const accessToken = tokenData.access_token;
      setUser(userData);
      setToken(accessToken);
      localStorage.setItem("dealhawk_token", accessToken);
      apiClient.defaults.headers.common["Authorization"] = `Bearer ${accessToken}`;
    } else {
      throw new Error("로그인에 실패했습니다");
    }
  }, []);

  const register = useCallback(async (email: string, username: string, password: string) => {
    const response = await apiClient.post<ApiResponse<AuthResponse>>("/auth/register", {
      email,
      username,
      password,
    });

    if (response.data.status === "success") {
      const { user: userData, token: tokenData } = response.data.data;
      const accessToken = tokenData.access_token;
      setUser(userData);
      setToken(accessToken);
      localStorage.setItem("dealhawk_token", accessToken);
      apiClient.defaults.headers.common["Authorization"] = `Bearer ${accessToken}`;
    } else {
      throw new Error("회원가입에 실패했습니다");
    }
  }, []);

  const logout = useCallback(() => {
    setUser(null);
    setToken(null);
    localStorage.removeItem("dealhawk_token");
    delete apiClient.defaults.headers.common["Authorization"];
  }, []);

  const resetPassword = useCallback(async (email: string) => {
    const response = await apiClient.post<ApiResponse<{ message: string }>>("/auth/reset-password", { email });
    if (response.data.status !== "success") {
      throw new Error("비밀번호 재설정 요청에 실패했습니다");
    }
  }, []);

  return (
    <AuthContext.Provider value={{ user, token, isLoading, login, register, logout, resetPassword }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}
