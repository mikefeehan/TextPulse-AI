"use client";

import {
  createContext,
  startTransition,
  useContext,
  useEffect,
  useState,
} from "react";

import {
  hasLiveApi,
  login,
  me,
  readStoredAuth,
  signup,
  writeStoredAuth,
} from "@/lib/api";
import type { AuthResponse, User } from "@/lib/types";

type AuthContextValue = {
  auth: AuthResponse | null;
  user: User | null;
  token: string | null;
  booting: boolean;
  demoMode: boolean;
  signIn: (email: string, password: string) => Promise<AuthResponse>;
  signUp: (email: string, password: string) => Promise<AuthResponse>;
  signOut: () => void;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [auth, setAuth] = useState<AuthResponse | null>(null);
  const [booting, setBooting] = useState(true);

  useEffect(() => {
    const stored = readStoredAuth();
    if (!stored) {
      startTransition(() => {
        setBooting(false);
      });
      return;
    }

    void me(stored.access_token)
      .then((user) => {
        startTransition(() => {
          const nextAuth = { ...stored, user };
          setAuth(nextAuth);
          writeStoredAuth(nextAuth);
          setBooting(false);
        });
      })
      .catch(() => {
        startTransition(() => {
          setAuth(stored);
          setBooting(false);
        });
      });
  }, []);

  async function handleLogin(email: string, password: string) {
    const response = await login(email, password);
    startTransition(() => {
      setAuth(response);
      writeStoredAuth(response);
    });
    return response;
  }

  async function handleSignup(email: string, password: string) {
    const response = await signup(email, password);
    startTransition(() => {
      setAuth(response);
      writeStoredAuth(response);
    });
    return response;
  }

  function handleSignOut() {
    startTransition(() => {
      setAuth(null);
      writeStoredAuth(null);
    });
  }

  return (
    <AuthContext.Provider
      value={{
        auth,
        user: auth?.user ?? null,
        token: auth?.access_token ?? null,
        booting,
        demoMode: !hasLiveApi() || auth?.access_token === "demo-token",
        signIn: handleLogin,
        signUp: handleSignup,
        signOut: handleSignOut,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within AuthProvider.");
  }
  return context;
}
