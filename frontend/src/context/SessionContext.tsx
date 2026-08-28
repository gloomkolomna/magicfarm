import { createContext, useContext, useEffect, useState, type ReactNode } from 'react';
import client from '../api/client';
import { useVkBridge } from './VkBridgeContext';

export interface MeUser {
  vk_id: number;
  role: string;
  status: string;
  display_name: string | null;
  crosses_balance: number;
  crosses_total: number;
  coins: number;
  round: number;
  level: number;
  unlocked_plot_level: number;
  unlocked_garden_level: number;
  onboarding_done: boolean;
  story_seen: boolean;
  plots_placed: number;
  locked_locations: string[];
  access_active: boolean;
  trial_active: boolean;
  subscription_active: boolean;
  trial_until: string | null;
  subscription_until: string | null;
  subscription_dlc_codes: string[];
  days_left: number | null;
  trial_days_left: number | null;
  subscription_days_left: number | null;
  block_after_expiry: boolean;
  is_donor: boolean;
  donor_exempt: boolean;
  game_open: boolean;
  block_reason: string | null;
}

interface SessionState {
  user: MeUser | null;
  token: string | null;
  loading: boolean;
  error: string | null;
  logout: () => void;
  refresh: () => Promise<void>;
  readOnly: boolean;
}

const SessionContext = createContext<SessionState>({
  user: null,
  token: null,
  loading: true,
  error: null,
  logout: () => {},
  refresh: async () => {},
  readOnly: false,
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

  const readOnly = !!user && user.role !== 'admin' && !user.access_active;

  return (
    <SessionContext.Provider value={{ user, token, loading, error, logout, refresh, readOnly }}>
      {children}
    </SessionContext.Provider>
  );
}

export function useSession() {
  return useContext(SessionContext);
}
