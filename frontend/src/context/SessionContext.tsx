import { createContext, useContext, useEffect, useState, type ReactNode } from 'react';
import client from '../api/client';
import { useVkBridge } from './VkBridgeContext';
import { isAdminAllowed } from '../auth/adminGate';

export interface MeUser {
  vk_id: number;
  role: string;
  display_name: string | null;
  crosses_balance: number;
  crosses_total: number;
  coins: number;
  round: number;
  level: number;
  unlocked_plot_level: number;
  unlocked_garden_level: number;
  onboarding_done: boolean;
  plots_placed: number;
}

interface SessionState {
  user: MeUser | null;
  token: string | null;
  loading: boolean;
  error: string | null;
  logout: () => void;
  refresh: () => Promise<void>;
}

const SessionContext = createContext<SessionState>({
  user: null,
  token: null,
  loading: true,
  error: null,
  logout: () => {},
  refresh: async () => {},
});

const TOKEN_KEY = 'token';

export function SessionProvider({ children }: { children: ReactNode }) {
  const { vkUserId, loading: vkLoading, launchParams } = useVkBridge();
  const [user, setUser] = useState<MeUser | null>(null);
  const [token, setToken] = useState<string | null>(localStorage.getItem(TOKEN_KEY));
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // 1. Логин: когда есть vkUserId и нет валидного токена — получить новый.
  useEffect(() => {
    if (vkLoading || vkUserId == null) return;
    if (!isAdminAllowed(vkUserId)) {
      setLoading(false);
      return;
    }

    let cancelled = false;

    async function login() {
      try {
        const res = await client.post('/auth/session', { params: { ...launchParams, vk_user_id: String(vkUserId) } });
        if (cancelled) return;
        const t = res.data.token as string;
        localStorage.setItem(TOKEN_KEY, t);
        setToken(t);
        setError(null);
      } catch (e: any) {
        if (cancelled) return;
        setError(e?.response?.data?.detail || 'Ошибка авторизации');
        setLoading(false);
      }
    }

    // Если токен уже есть — попробуем /me; если протух — перевыпустим.
    async function verify() {
      try {
        const res = await client.get('/me');
        if (cancelled) return;
        setUser(res.data);
        setLoading(false);
      } catch {
        await login();
      }
    }

    if (token) {
      verify();
    } else {
      login();
    }

    return () => { cancelled = true; };
  }, [vkUserId, vkLoading, token]);

  // 2. После получения токена — загрузить /me.
  useEffect(() => {
    if (!token || user) return;
    let cancelled = false;
    client.get('/me')
      .then((res) => { if (!cancelled) { setUser(res.data); setLoading(false); } })
      .catch((e) => {
        if (cancelled) return;
        setError(e?.response?.data?.detail || 'Не удалось загрузить профиль');
        setLoading(false);
      });
    return () => { cancelled = true; };
  }, [token, user]);

  function logout() {
    localStorage.removeItem(TOKEN_KEY);
    setToken(null);
    setUser(null);
  }

  async function refresh() {
    try {
      const res = await client.get('/me');
      setUser(res.data);
    } catch {
      /* ignore */
    }
  }

  return (
    <SessionContext.Provider value={{ user, token, loading, error, logout, refresh }}>
      {children}
    </SessionContext.Provider>
  );
}

export function useSession() {
  return useContext(SessionContext);
}
