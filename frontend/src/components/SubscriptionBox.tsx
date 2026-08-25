import { useEffect, useRef, useState } from 'react';
import { api, type PaymentPrice } from '../api/endpoints';
import { useSession } from '../context/SessionContext';

function parseDate(iso: string | null): Date | null {
  if (!iso) return null;
  return new Date(iso.endsWith('Z') ? iso : iso + 'Z');
}

function formatDate(iso: string | null): string {
  const d = parseDate(iso);
  return d ? d.toLocaleDateString('ru-RU') : '—';
}

const OFFERTA_URL = 'https://belovolovhome.ru/magicfarm/game/offerta.html';
const PRIVACY_URL = 'https://belovolovhome.ru/magicfarm/game/private.html';
const GROUP_URL = 'https://vk.ru/krestiki_s_korgi';
const EMAIL_RE = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;

const BLOCK_STYLE: React.CSSProperties = {
  display: 'flex',
  flexDirection: 'column',
  gap: 8,
  padding: 12,
  border: '1px solid rgba(255,255,255,0.14)',
  borderRadius: 12,
};

export function SubscriptionBox({ onPaid }: { onPaid?: () => void }) {
  const { user, refresh } = useSession();
  const [price, setPrice] = useState<PaymentPrice | null>(null);
  const [email, setEmail] = useState('');
  const [agree, setAgree] = useState(false);
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState<string | null>(null);
  const pollingRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const donorBlocked = !!user?.game_open && user.role !== 'admin' && !user.is_donor && !user.donor_exempt;
  const activeSub = !!user?.subscription_active;
  const currentCodes = user?.subscription_dlc_codes ?? [];
  const [selected, setSelected] = useState<string[]>(activeSub ? [] : currentCodes);

  useEffect(() => {
    api.paymentPrice().then(setPrice).catch(() => {});
    return () => { if (pollingRef.current) clearInterval(pollingRef.current); };
  }, []);

  const toggle = (code: string) => {
    if (activeSub && currentCodes.includes(code)) return;
    setSelected((prev) => (prev.includes(code) ? prev.filter((c) => c !== code) : [...prev, code]));
  };

  const selectedNew = activeSub ? selected.filter((c) => !currentCodes.includes(c)) : [];
  const topupDays = price?.topup_days_left ?? null;
  const topupTotal = price ? price.dlc.filter((d) => selectedNew.includes(d.code)).reduce((s, d) => s + (d.topup_rub ?? 0), 0) : 0;
  const fullTotal = price ? price.base_rub + price.dlc.filter((d) => selected.includes(d.code)).reduce((s, d) => s + d.price_rub, 0) : 0;
  const renewTotal = price ? price.base_rub + price.dlc.filter((d) => currentCodes.includes(d.code)).reduce((s, d) => s + d.price_rub, 0) : 0;
  const currentNames = price ? price.dlc.filter((d) => currentCodes.includes(d.code)).map((d) => d.name) : [];
  const newDlc = price ? price.dlc.filter((d) => !currentCodes.includes(d.code)) : [];

  async function pay(mode: 'topup' | 'renew' | 'full') {
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
    const codesToSend =
      mode === 'topup' ? [...currentCodes, ...selectedNew]
      : mode === 'renew' ? currentCodes
      : selected;
    try {
      const order = await api.createSubscriptionOrder({
        dlc_codes: codesToSend,
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
            setStatus(
              mode === 'topup' ? 'ДЛС добавлены в подписку! 🎉'
              : mode === 'renew' ? 'Подписка продлена! 🎉'
              : 'Подписка активирована! 🎉'
            );
            setBusy(false);
            setSelected([]);
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

  const emailField = (
    <div>
      <label style={{ display: 'block', fontSize: 13, color: 'var(--text-secondary)', margin: '0 0 4px' }}>Email для электронного чека *</label>
      <input
        type="email"
        placeholder="email@example.com"
        value={email}
        onChange={(e) => setEmail(e.target.value)}
        className="fm-input"
        style={{ padding: '10px 12px', background: 'rgba(5,9,4,0.55)', backdropFilter: 'blur(8px)', WebkitBackdropFilter: 'blur(8px)' }}
        disabled={busy}
      />
    </div>
  );

  const agreeField = (
    <label className="fm-story-text" style={{ display: 'flex', alignItems: 'flex-start', gap: 8, fontSize: 13, cursor: 'pointer' }}>
      <input type="checkbox" checked={agree} onChange={(e) => setAgree(e.target.checked)} disabled={busy} style={{ marginTop: 2 }} />
      <span>
        Принимаю условия{' '}
        <a href={OFFERTA_URL} target="_blank" rel="noreferrer">оферты</a> и{' '}
        <a href={PRIVACY_URL} target="_blank" rel="noreferrer">политики обработки персональных данных</a>
      </span>
    </label>
  );

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
        activeSub ? (
          <>
            <div style={{ fontSize: 16 }}>
              Подписка активна до <b>{formatDate(user?.subscription_until ?? null)}</b>
            </div>
            <div style={{ fontSize: 13, color: 'var(--text-muted)' }}>
              В составе: базовая подписка{currentNames.length ? ` + ${currentNames.join(', ')}` : ''}
            </div>

            {newDlc.length > 0 && (
              <div style={BLOCK_STYLE}>
                <div style={{ fontSize: 14, fontWeight: 600 }}>Докупить ДЛС</div>
                {newDlc.map((d) => (
                  <label key={d.code} style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 15, cursor: 'pointer' }}>
                    <input type="checkbox" checked={selected.includes(d.code)} onChange={() => toggle(d.code)} disabled={busy} />
                    <span>
                      + {d.name}{' '}
                      <span style={{ color: 'var(--text-muted)' }}>
                        (доплата {d.topup_rub} ₽{topupDays != null ? ` за ${topupDays} дн.` : ''})
                      </span>
                    </span>
                  </label>
                ))}
                <button
                  className="fm-btn"
                  onClick={() => pay('topup')}
                  disabled={busy || !selectedNew.length}
                  style={{ padding: '12px 16px', fontSize: 16 }}
                >
                  Добавить в подписку за {topupTotal} ₽
                </button>
                <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>
                  ДЛС добавятся до конца оплаченного периода, срок подписки не изменится. Полная цена ДЛС — со следующего продления.
                </div>
              </div>
            )}

            <div style={BLOCK_STYLE}>
              <div style={{ fontSize: 14, fontWeight: 600 }}>Продление</div>
              <div style={{ fontSize: 15 }}>
                Базовая подписка{currentNames.length ? ` + ${currentNames.join(', ')}` : ''} · {price.period_days} дн. — <b>{renewTotal} ₽</b>
              </div>
              <button
                className="fm-btn"
                onClick={() => pay('renew')}
                disabled={busy}
                style={{ padding: '12px 16px', fontSize: 16 }}
              >
                Продлить на {price.period_days} дн. — {renewTotal} ₽
              </button>
              <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>
                Отказаться от ДЛС можно при следующем продлении: сумма изменится с нового периода, возврат средств не осуществляется.
              </div>
            </div>

            {emailField}
            {agreeField}
            {status && <div style={{ fontSize: 14, color: 'var(--text-secondary)' }}>{status}</div>}
          </>
        ) : user?.trial_active ? (
          <>
            <div style={{ fontSize: 16 }}>
              ⏳ Идёт пробный период — до <b>{formatDate(user.trial_until)}</b>
            </div>
            <div style={{ fontSize: 14, color: 'var(--text-secondary)' }}>
              Оформление подписки станет доступно после окончания пробного периода.
              Мы заранее напомним — за 5, 3 и 1 день до его конца.
            </div>
          </>
        ) : (
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
            {emailField}
            {agreeField}
            <button className="fm-btn" onClick={() => pay('full')} disabled={busy} style={{ padding: '14px 16px', fontSize: 17 }}>
              Перейти к оплате {fullTotal} ₽
            </button>
            {status && <div style={{ fontSize: 14, color: 'var(--text-secondary)' }}>{status}</div>}
          </>
        )
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
  return (
    <div>
      {user.subscription_active && (
        <div>
          Подписка активна до <b>{formatDate(user.subscription_until)}</b>
          {user.subscription_dlc_codes.length > 0 && (
            <span> (+ {user.subscription_dlc_codes.join(', ')})</span>
          )}
        </div>
      )}
      {user.trial_active && (
        <div>
          Пробный период до <b>{formatDate(user.trial_until)}</b>
          {user.trial_days_left != null ? ` (осталось ${user.trial_days_left} дн.)` : ''}
        </div>
      )}
      {!user.subscription_active && !user.trial_active && (
        <div>Подписка не активна — оформление ниже</div>
      )}
      {donorLine}
    </div>
  );
}

export function TrialExpiringBanner() {
  const { user } = useSession();
  if (!user || user.role === 'admin' || !user.trial_active) return null;
  const days = user.trial_days_left;
  if (days == null || days <= 0 || days > 5) return null;
  const sub = parseDate(user.subscription_until);
  const trial = parseDate(user.trial_until);
  if (sub && trial && sub > trial) return null;
  return (
    <div
      className="fm-card"
      style={{
        borderColor: 'rgba(255, 193, 7, 0.55)',
        background: 'rgba(255, 193, 7, 0.08)',
        display: 'flex',
        alignItems: 'baseline',
        gap: 8,
        fontSize: 14,
        marginBottom: 12,
      }}
    >
      <span style={{ fontSize: 20 }}>⏳</span>
      <span>
        Пробный период заканчивается: осталось <b>{days} дн.</b> (до {formatDate(user.trial_until)}).
        После окончания триала можно оформить подписку — прогресс сохранится.
      </span>
    </div>
  );
}

export default SubscriptionBox;
