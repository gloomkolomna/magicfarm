import { useEffect, useRef, useState } from 'react';

type GwStatus = {
  transaction_id: string;
  status: 'pending' | 'success' | 'cancelled' | 'failed';
  paid_at: string | null;
};

const GW_BASE = window.location.origin + '/pay';
const POLL_MS = 3000;
const MAX_MS = 5 * 60 * 1000;
const OFFERTA_URL = 'https://belovolovhome.ru/magicfarm/game/offerta.html';
const PRIVACY_URL = 'https://belovolovhome.ru/magicfarm/game/private.html';

export default function PaymentStatusPage() {
  const [status, setStatus] = useState<'loading' | GwStatus['status'] | 'error' | 'notxn'>('loading');
  const params = new URLSearchParams(window.location.search);
  const txn = params.get('txn')?.trim() || '';
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    if (!txn) {
      setStatus('notxn');
      return;
    }
    const started = Date.now();
    let cancelled = false;

    const poll = async () => {
      if (Date.now() - started > MAX_MS) {
        if (timerRef.current) clearInterval(timerRef.current);
        return;
      }
      try {
        const res = await fetch(`${GW_BASE}/status/${encodeURIComponent(txn)}`);
        if (!res.ok) throw new Error(String(res.status));
        const data: GwStatus = await res.json();
        if (cancelled) return;
        setStatus(data.status);
        if (data.status !== 'pending' && timerRef.current) {
          clearInterval(timerRef.current);
          timerRef.current = null;
        }
      } catch {
        if (!cancelled) setStatus((prev) => (prev === 'success' || prev === 'failed' || prev === 'cancelled' ? prev : 'loading'));
      }
    };

    poll();
    timerRef.current = setInterval(poll, POLL_MS);
    return () => {
      cancelled = true;
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, [txn]);

  const view = (() => {
    switch (status) {
      case 'success':
        return { emoji: '✅', title: 'Оплата прошла!', text: 'Подписка активирована. Вернитесь в приложение — она подхватится автоматически.' };
      case 'failed':
      case 'cancelled':
        return { emoji: '❌', title: 'Оплата не прошла', text: 'Средства не списаны или возвращены. Попробуйте оформить подписку ещё раз в приложении.' };
      case 'notxn':
        return { emoji: '🤔', title: 'Нет номера платежа', text: 'Откройте страницу из окна оплаты или из приложения.' };
      case 'error':
        return { emoji: '⚠️', title: 'Не удалось проверить статус', text: 'Обновите страницу позже.' };
      default:
        return { emoji: '⏳', title: 'Проверяем оплату…', text: 'Обычно это занимает несколько секунд. Страница обновится сама.' };
    }
  })();

  return (
    <div style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 20 }}>
      <div className="fm-card fm-rise" style={{ maxWidth: 380, width: '100%', textAlign: 'center', padding: '28px 20px' }}>
        <div style={{ fontSize: 52 }}>{view.emoji}</div>
        <h1 style={{ fontSize: 22, margin: '10px 0 8px' }}>{view.title}</h1>
        <p style={{ color: 'var(--text-secondary)', fontSize: 15, margin: '0 0 16px' }}>{view.text}</p>
        {status === 'success' && (
          <button className="fm-btn" style={{ padding: '12px 16px', fontSize: 16 }} onClick={() => window.close()}>
            🌿 Вернуться в игру
          </button>
        )}
        {txn && status !== 'success' && (
          <div style={{ fontSize: 12, color: 'var(--text-muted)', wordBreak: 'break-all' }}>Платёж: {txn}</div>
        )}
        <div style={{ marginTop: 16, fontSize: 12, color: 'var(--text-muted)' }}>
          📄 <a href={OFFERTA_URL} target="_blank" rel="noreferrer">Оферта</a>
          {' · '}
          🔒 <a href={PRIVACY_URL} target="_blank" rel="noreferrer">Политика обработки персональных данных</a>
        </div>
      </div>
    </div>
  );
}
