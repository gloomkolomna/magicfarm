import { useEffect, useRef, useState } from 'react';
import { api, type PaymentPrice } from '../api/endpoints';
import { useSession } from '../context/SessionContext';

function formatDate(iso: string | null): string {
  if (!iso) return '—';
  const d = new Date(iso.endsWith('Z') ? iso : iso + 'Z');
  return d.toLocaleDateString('ru-RU');
}

const OFFERTA_URL = 'https://belovolovhome.ru/magicfarm/game/offerta.docx';
const PRIVACY_URL = 'https://belovolovhome.ru/magicfarm/game/private.html';
const GROUP_URL = 'https://vk.ru/krestiki_s_korgi';
const EMAIL_RE = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;

export function SubscriptionBox({ onPaid }: { onPaid?: () => void }) {
  const { user, refresh } = useSession();
  const [price, setPrice] = useState<PaymentPrice | null>(null);
  const [selected, setSelected] = useState<string[]>(user?.subscription_dlc_codes ?? []);
  const [email, setEmail] = useState('');
  const [agree, setAgree] = useState(false);
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState<string | null>(null);
  const pollingRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const donorBlocked = !!user?.game_open && user.role !== 'admin' && !user.is_donor && !user.donor_exempt;

  useEffect(() => {
    api.paymentPrice().then(setPrice).catch(() => {});
    return () => { if (pollingRef.current) clearInterval(pollingRef.current); };
  }, []);

  const toggle = (code: string) => {
    setSelected((prev) => (prev.includes(code) ? prev.filter((c) => c !== code) : [...prev, code]));
  };

  const total = price ? price.base_rub + price.dlc.filter((d) => selected.includes(d.code)).reduce((s, d) => s + d.price_rub, 0) : 0;

  async function pay() {
    if (busy || !price) return;
    if (!EMAIL_RE.test(email.trim())) {
      setStatus('Укажите корректный email — на него придёт электронный чек');
      return;
    }
    if (!agree) {
      setStatus('Подтвердите согласие с офертой и политикой обработки персональных данных');
      return;
    }
    setBusy(true);
    setStatus(null);
    try {
      const order = await api.createSubscriptionOrder({
        dlc_codes: selected,
        receipt_email: email.trim(),
      });
      setStatus('Ожидание оплаты…');
      const win = window.open(order.payment_url, '_blank');
      if (!win) window.location.href = order.payment_url;
      const started = Date.now();
      pollingRef.current = setInterval(async () => {
        if (Date.now() - started > 120000) {
          if (pollingRef.current) clearInterval(pollingRef.current);
          setStatus('Не дождались подтверждения. Статус можно проверить позже в профиле.');
          setBusy(false);
          return;
        }
        try {
          const st = await api.paymentOrderStatus(order.order_id);
          if (st.status === 'success') {
            if (pollingRef.current) clearInterval(pollingRef.current);
            setStatus('Подписка активирована! 🎉');
            setBusy(false);
            await refresh();
            onPaid?.();
          }
        } catch { /* ignore */ }
      }, 3000);
    } catch (e: any) {
      setStatus(e?.response?.data?.detail || 'Не удалось создать заказ');
      setBusy(false);
    }
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      {donorBlocked ? (
        <>
          <div style={{ fontSize: 46, textAlign: 'center' }}>🐶</div>
          {user?.subscription_active ? (
            <>
              <div style={{ fontSize: 16, textAlign: 'center' }}>
                Вы доигрываете оплаченный период — до <b>{formatDate(user.subscription_until)}</b>.
              </div>
              <div style={{ fontSize: 14, color: 'var(--text-secondary)', textAlign: 'center' }}>
                Продление станет доступно после возобновления донат-подписки группы.
              </div>
            </>
          ) : (
            <>
              <div style={{ fontSize: 16, textAlign: 'center' }}>
                Играть и продлевать подписку могут только доны группы «Крестики от Корги».
              </div>
              <div style={{ fontSize: 14, color: 'var(--text-secondary)', textAlign: 'center' }}>
                Станьте доном — и волшебная ферма снова откроется!
              </div>
            </>
          )}
          <p style={{ margin: '8px 0 0', textAlign: 'center' }}>
            <a
              className="fm-btn"
              href={GROUP_URL}
              target="_blank"
              rel="noreferrer"
              style={{ display: 'inline-block', padding: '12px 18px', textDecoration: 'none' }}
            >
              Стать доном 🎁
            </a>
          </p>
        </>
      ) : price ? (
        <>
          <div style={{ fontSize: 16 }}>
            <b>{price.base_rub} ₽</b> — базовая подписка на {price.period_days} дней
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            {price.dlc.map((d) => (
              <label key={d.code} style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 15, cursor: 'pointer' }}>
                <input type="checkbox" checked={selected.includes(d.code)} onChange={() => toggle(d.code)} disabled={busy} />
                <span>+ {d.name} <span style={{ color: 'var(--text-muted)' }}>(+{d.price_rub} ₽)</span></span>
              </label>
            ))}
          </div>
          <input
            type="email"
            placeholder="Email для электронного чека *"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="fm-input"
            style={{ padding: '10px 12px' }}
            disabled={busy}
          />
          <label style={{ display: 'flex', alignItems: 'flex-start', gap: 8, fontSize: 13, cursor: 'pointer', color: 'var(--text-secondary)' }}>
            <input type="checkbox" checked={agree} onChange={(e) => setAgree(e.target.checked)} disabled={busy} style={{ marginTop: 2 }} />
            <span>
              Принимаю условия{' '}
              <a href={OFFERTA_URL} target="_blank" rel="noreferrer">оферты</a> и{' '}
              <a href={PRIVACY_URL} target="_blank" rel="noreferrer">политики обработки персональных данных</a>
            </span>
          </label>
          <button className="fm-btn" onClick={pay} disabled={busy} style={{ padding: '14px 16px', fontSize: 17 }}>
            {busy ? 'Ожидание оплаты…' : `Перейти к оплате ${total} ₽`}
          </button>
          {status && <div style={{ fontSize: 14, color: 'var(--text-secondary)' }}>{status}</div>}
          <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>
            📄 <a href={OFFERTA_URL} target="_blank" rel="noreferrer">Оферта</a>
            {' · '}
            🔒 <a href={PRIVACY_URL} target="_blank" rel="noreferrer">Политика обработки персональных данных</a>
          </div>
        </>
      ) : (
        <div style={{ color: 'var(--text-muted)' }}>Загрузка цен…</div>
      )}
    </div>
  );
}

export function SubscriptionStatusLine() {
  const { user } = useSession();
  if (!user) return null;
  if (user.role === 'admin') return <div>Роль админа — подписка не требуется</div>;
  const donorLine = user.game_open && !user.is_donor && !user.donor_exempt
    ? <div style={{ marginTop: 4 }}>🐶 Дон-статус группы не активен</div>
    : null;
  if (user.subscription_active) {
    return (
      <div>
        <div>
          Подписка активна до <b>{formatDate(user.subscription_until)}</b>
          {user.subscription_dlc_codes.length > 0 && (
            <span> (+ {user.subscription_dlc_codes.join(', ')})</span>
          )}
        </div>
        {donorLine}
      </div>
    );
  }
  if (user.trial_active) {
    return (
      <div>
        <div>
          Пробный период до <b>{formatDate(user.trial_until)}</b>
          {user.days_left != null ? ` (осталось ${user.days_left} дн.)` : ''}
        </div>
        {donorLine}
      </div>
    );
  }
  return (
    <div>
      <div>Подписка не активна — оформление ниже</div>
      {donorLine}
    </div>
  );
}

export default SubscriptionBox;
