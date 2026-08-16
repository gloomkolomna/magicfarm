import { useEffect, useState } from 'react';

type Pending = {
  message: string;
  title: string;
  resolve: (v: boolean) => void;
};

let pushListener: ((p: Pending) => void) | null = null;

export function confirmDialog(message: string, title = 'Подтверждение'): Promise<boolean> {
  return new Promise((resolve) => {
    if (!pushListener) {
      resolve(window.confirm(message));
      return;
    }
    pushListener({ message, title, resolve });
  });
}

export function ConfirmHost() {
  const [pending, setPending] = useState<Pending | null>(null);

  useEffect(() => {
    pushListener = (p) => setPending(p);
    return () => { pushListener = null; };
  }, []);

  if (!pending) return null;

  const current = pending;

  function close(result: boolean) {
    current.resolve(result);
    setPending(null);
  }

  return (
    <div
      style={{
        position: 'fixed', inset: 0, zIndex: 90,
        background: 'rgba(0,0,0,0.6)', backdropFilter: 'blur(3px)',
        display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 16,
      }}
      onClick={() => close(false)}
    >
      <div
        className="fm-card fm-rise"
        onClick={(e) => e.stopPropagation()}
        style={{ width: '100%', maxWidth: 360 }}
      >
        <h3 style={{ margin: '0 0 10px' }}>{pending.title}</h3>
        <p style={{ margin: '0 0 16px', fontSize: 14, color: 'var(--text-secondary)', whiteSpace: 'pre-line' }}>
          {pending.message}
        </p>
        <div style={{ display: 'flex', gap: 8 }}>
          <button
            className="fm-btn fm-btn-outline"
            style={{ flex: 1 }}
            onClick={() => close(false)}
          >
            Отмена
          </button>
          <button
            className="fm-btn"
            style={{ flex: 1 }}
            onClick={() => close(true)}
          >
            Подтвердить
          </button>
        </div>
      </div>
    </div>
  );
}
