import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import { api, fetchAuthConfig, setToken, getToken } from "../api";

export type AuthUser = {
  id: string;
  email: string;
  role: string;
  display_name: string;
  organization_id?: string;
  organization_name?: string;
  auth_provider?: string;
};

type AuthConfig = {
  auth_mode: string;
  environment: string;
  firebase?: { apiKey: string; authDomain: string; projectId: string } | null;
};

type AuthContextValue = {
  user: AuthUser | null;
  config: AuthConfig | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  loginWithGoogle: () => Promise<void>;
  logout: () => void;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [config, setConfig] = useState<AuthConfig | null>(null);
  const [loading, setLoading] = useState(true);

  const bootstrap = useCallback(async () => {
    try {
      const cfg = await fetchAuthConfig();
      setConfig(cfg);

      if (cfg.auth_mode === "disabled") {
        setUser({
          id: "anonymous",
          email: "anonymous@local",
          role: "ORG_OWNER",
          display_name: "Local Dev (auth disabled)",
          organization_id: "org-default",
        });
      } else {
        const token = getToken();
        if (token) {
          const me = await api<AuthUser>("/auth/me");
          setUser(me);
        }
      }
    } catch {
      setToken(null);
      setUser(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void bootstrap();
  }, [bootstrap]);

  const login = async (email: string, password: string) => {
    const result = await api<{ access_token: string; user: AuthUser }>("/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    });
    setToken(result.access_token);
    setUser(result.user);
  };

  const loginWithGoogle = async () => {
    if (!config?.firebase) {
      throw new Error("Firebase is not configured");
    }
    const { signInWithGoogle } = await import("./firebase");
    const idToken = await signInWithGoogle(config.firebase);
    const result = await api<{ access_token: string; user: AuthUser }>("/auth/firebase", {
      method: "POST",
      body: JSON.stringify({ id_token: idToken }),
    });
    setToken(result.access_token);
    setUser(result.user);
  };

  const logout = () => {
    setToken(null);
    setUser(null);
  };

  return (
    <AuthContext.Provider value={{ user, config, loading, login, loginWithGoogle, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuth must be used within AuthProvider");
  }
  return ctx;
}
