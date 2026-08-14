import axios from 'axios';

const API_BASE = window.location.origin + '/magicfarm/api';
const TOKEN_KEY = 'token';

const client = axios.create({
  baseURL: API_BASE,
  headers: { 'Content-Type': 'application/json' },
  timeout: 15000,
});

client.interceptors.request.use((config) => {
  const token = localStorage.getItem(TOKEN_KEY);
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

let vkLaunch: { vkUserId: number | null; launchParams: Record<string, string> } = {
  vkUserId: null,
  launchParams: {},
};
let refreshPromise: Promise<string | null> | null = null;

export function setVkLaunchInfo(vkUserId: number | null, launchParams: Record<string, string>) {
  vkLaunch = { vkUserId, launchParams };
}

async function relogin(): Promise<string | null> {
  if (refreshPromise) return refreshPromise;
  const { vkUserId, launchParams } = vkLaunch;
  if (vkUserId == null) return null;
  refreshPromise = (async () => {
    try {
      const res = await client.post('/auth/session', {
        params: { ...launchParams, vk_user_id: String(vkUserId) },
      });
      const token = res.data?.token as string | undefined;
      if (!token) return null;
      localStorage.setItem(TOKEN_KEY, token);
      return token;
    } catch {
      return null;
    } finally {
      refreshPromise = null;
    }
  })();
  return refreshPromise;
}

client.interceptors.response.use(
  (response) => response,
  async (error) => {
    const original = error?.config;
    const status = error?.response?.status;
    const url: string = original?.url || '';
    if (
      status === 401 &&
      original &&
      !original._retry &&
      !url.includes('/auth/session')
    ) {
      original._retry = true;
      const newToken = await relogin();
      if (newToken) {
        original.headers.Authorization = `Bearer ${newToken}`;
        return client.request(original);
      }
    }
    return Promise.reject(error);
  },
);

export default client;
