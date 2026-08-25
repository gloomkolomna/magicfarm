import client from './client';

export type VkLogLevel = 'warn' | 'error';

let installed = false;

export function reportVk(level: VkLogLevel, event: string, message?: string, details?: unknown) {
  try {
    client.post('/logs/vk', { level, event, message, details }).catch(() => {});
  } catch {
    /* noop */
  }
}

const CHUNK_RELOAD_KEY = 'chunk_reload_at';
const CHUNK_RELOAD_WINDOW_MS = 30000;

function isChunkLoadError(err: unknown): boolean {
  const msg = typeof err === 'string' ? err : err instanceof Error ? err.message : '';
  return (
    msg.includes('Failed to fetch dynamically imported module') ||
    msg.includes('Importing a module script failed') ||
    msg.includes('error loading dynamically imported module')
  );
}

function handleChunkError(): boolean {
  try {
    const last = Number(sessionStorage.getItem(CHUNK_RELOAD_KEY) || 0);
    if (Date.now() - last < CHUNK_RELOAD_WINDOW_MS) return false;
    sessionStorage.setItem(CHUNK_RELOAD_KEY, String(Date.now()));
  } catch {
    return false;
  }
  window.location.reload();
  return true;
}

export function installGlobalErrorReporters() {
  if (installed || typeof window === 'undefined') return;
  installed = true;
  window.addEventListener('error', (e) => {
    if ((isChunkLoadError(e.error) || isChunkLoadError(e.message)) && handleChunkError()) return;
    reportVk('error', 'window_error', e.message, {
      filename: e.filename,
      lineno: e.lineno,
      colno: e.colno,
      stack: (e.error && (e.error as Error).stack) || null,
    });
  });
  window.addEventListener('unhandledrejection', (e) => {
    const reason = e.reason;
    if ((isChunkLoadError(reason) || isChunkLoadError((reason && (reason as Error).message) || '')) && handleChunkError()) return;
    reportVk('error', 'unhandledrejection', (reason && (reason as Error).message) || 'promise rejection', {
      stack: (reason && (reason as Error).stack) || null,
    });
  });
}
