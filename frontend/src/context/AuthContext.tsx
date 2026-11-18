import { createContext, useContext, useEffect, useMemo, useState, ReactNode } from "react";
import { authApi, User } from "../services/api";

interface AuthState {
  user: User | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  verifyOtp: (email: string, otp: string) => Promise<void>;
  register: (name: string, email: string, password: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthState>(null as unknown as AuthState);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(() => {
    const raw = localStorage.getItem("user");
    return raw ? JSON.parse(raw) : null;
  });
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const token = localStorage.getItem("token");
    if (!token) {
      setLoading(false);
      return;
    }
    authApi
      .me()
      .then((r) => {
        setUser(r.data.user);
        localStorage.setItem("user", JSON.stringify(r.data.user));
      })
      .catch(() => {
        localStorage.removeItem("token");
        localStorage.removeItem("user");
        setUser(null);
      })
      .finally(() => setLoading(false));
  }, []);

  function persist(token: string, u: User) {
    localStorage.setItem("token", token);
    localStorage.setItem("user", JSON.stringify(u));
    setUser(u);
  }

  const value = useMemo<AuthState>(
    () => ({
      user,
      loading,
      login: async (email, password) => {
        await authApi.login(email, password);
      },
      verifyOtp: async (email, otp) => {
        const r = await authApi.verifyOtp(email, otp);
        persist(r.data.token, r.data.user);
      },
      register: async (name, email, password) => {
        const r = await authApi.register(name, email, password);
        persist(r.data.token, r.data.user);
      },
      logout: () => {
        authApi.logout().catch(() => {});
        localStorage.removeItem("token");
        localStorage.removeItem("user");
        setUser(null);
      },
    }),
    [user, loading],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export const useAuth = () => useContext(AuthContext);
