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

export function installGlobalErrorReporters() {
  if (installed || typeof window === 'undefined') return;
  installed = true;
  window.addEventListener('error', (e) => {
    reportVk('error', 'window_error', e.message, {
      filename: e.filename,
      lineno: e.lineno,
      colno: e.colno,
      stack: (e.error && (e.error as Error).stack) || null,
    });
  });
  window.addEventListener('unhandledrejection', (e) => {
    const reason = e.reason;
    reportVk('error', 'unhandledrejection', (reason && (reason as Error).message) || 'promise rejection', {
      stack: (reason && (reason as Error).stack) || null,
    });
  });
}
