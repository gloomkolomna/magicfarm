import { createContext, useContext, useEffect, useState, type ReactNode } from 'react';
import bridge, { parseURLSearchParamsForGetLaunchParams } from '@vkontakte/vk-bridge';
import { reportVk } from '../api/vkLogger';

interface VkContextType {
  vkUserId: number | null;
  isVkWebView: boolean;
  isDemo: boolean;
  launchParams: Record<string, string>;
  loading: boolean;
}

const VkBridgeContext = createContext<VkContextType>({
  vkUserId: null,
  isVkWebView: false,
  isDemo: false,
  launchParams: {},
  loading: true,
});

const DEMO_VK_ID = import.meta.env.VITE_DEMO_VK_ID
  ? Number(import.meta.env.VITE_DEMO_VK_ID)
  : null;

function withTimeout<T>(promise: Promise<T>, ms: number): Promise<T> {
  return Promise.race([
    promise,
    new Promise<T>((_, reject) =>
      setTimeout(() => reject(new Error('vk-bridge timeout')), ms),
    ),
  ]);
}

// Разбор launch params из URL — работает и для query (?vk_user_id=...),
// и для hash (#vk_user_id=...). VK на разных платформах передаёт по-разному.
function parseVkParamsFromUrl(): { vkUserId: number | null; params: Record<string, string> } {
  const sources = [window.location.search, window.location.hash];
  const params: Record<string, string> = {};
  let vkUserId: number | null = null;

  for (const src of sources) {
    const qs = src.startsWith('?') || src.startsWith('#') ? src.substring(1) : src;
    qs.split('&').forEach((p) => {
      const [k, v] = p.split('=');
      if (!k) return;
      const val = decodeURIComponent(v || '');
      params[k] = val;
      if (k === 'vk_user_id') vkUserId = Number(val);
    });
  }

  return { vkUserId, params };
}

export function VkBridgeProvider({ children }: { children: ReactNode }) {
  const [vkUserId, setVkUserId] = useState<number | null>(null);
  const [isVkWebView, setIsVkWebView] = useState(false);
  const [isDemo, setIsDemo] = useState(false);
  const [launchParams, setLaunchParams] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const applyInsetTop = (top: unknown) => {
      const px = Math.max(0, Number(top) || 0);
      document.documentElement.style.setProperty('--vk-inset-top', `${px}px`);
    };

    const listener = (e: any) => {
      const type = e?.detail?.type;
      const data = e?.detail?.data;
      if (!type || !data) return;
      if (type === 'VKWebAppUpdateConfig' || type === 'VKWebAppUpdateInsets') {
        const top = data?.insets?.top;
        if (top !== undefined) applyInsetTop(top);
      }
    };

    bridge.subscribe(listener);
    return () => {
      try { bridge.unsubscribe(listener); } catch { /* noop */ }
    };
  }, []);

  useEffect(() => {
    let cancelled = false;

    async function init() {
      let id: number | null = null;
      let params: Record<string, string> = {};
      let inVk = false;

      // 1. МГНОВЕННЫЙ способ — разбор URL (query + hash). На мобайле ВК всегда
      //    передаёт vk_user_id в URL, это не требует сети и не таймаутит.
      try {
        const lp = parseURLSearchParamsForGetLaunchParams(
          window.location.search + window.location.hash,
        );
        if (lp && (lp as any).vk_user_id) {
          inVk = true;
          id = Number((lp as any).vk_user_id);
          params = Object.fromEntries(
            Object.entries(lp).map(([k, v]) => [k, String(v)])
          );
        }
      } catch {
        // игнорируем
      }

      // 2. Запасной raw-разбор URL.
      if (!id) {
        const fallback = parseVkParamsFromUrl();
        if (fallback.vkUserId) {
          inVk = true;
          id = fallback.vkUserId;
          params = fallback.params;
        }
      }

    // 3. Обязательный запуск приложения в VK (fire-and-forget).
    bridge.send('VKWebAppInit').catch((e) => {
      reportVk('warn', 'vk_init_failed', 'VKWebAppInit rejected', { error: String(e) });
    });

    // 4. Дополнительный запрос launch params через VK Bridge — не блокирующий.
    if (!id) {
      try {
        const lp = await withTimeout(bridge.send('VKWebAppGetLaunchParams'), 3000);
        if (lp && lp.vk_user_id) {
          inVk = true;
          id = Number(lp.vk_user_id);
          params = Object.fromEntries(
            Object.entries(lp).map(([k, v]) => [k, String(v)])
          );
        }
      } catch (e) {
        reportVk('warn', 'launch_params_failed', 'VKWebAppGetLaunchParams unavailable', { error: String(e) });
        // вне VK — метод недоступен
      }
    }

      if (id) {
        setIsVkWebView(true);
        setVkUserId(id);
        setLaunchParams(params);
        reportVk('info', 'vk_app_launch', inVk ? 'launched in VK' : 'launched (URL params)', {
          vk_user_id: id,
          in_vk: inVk,
        });
        const cur = getComputedStyle(document.documentElement)
          .getPropertyValue('--vk-inset-top').trim();
        if (!cur || cur === '0px') {
          document.documentElement.style.setProperty('--vk-inset-top', '48px');
        }
      } else if (DEMO_VK_ID) {
        setIsDemo(true);
        setVkUserId(DEMO_VK_ID);
      }

      if (!cancelled) setLoading(false);
    }

    init();
    return () => { cancelled = true; };
  }, []);

  return (
    <VkBridgeContext.Provider value={{ vkUserId, isVkWebView, isDemo, launchParams, loading }}>
      {children}
    </VkBridgeContext.Provider>
  );
}

export function useVkBridge() {
  return useContext(VkBridgeContext);
}
