import { useEffect, useMemo, useState } from 'react';
import { useSession } from '../context/SessionContext';
import { api, type PlayerSearchItem, type TradeOffer, type TradeItemIn } from '../api/endpoints';
import { confirmDialog } from '../components/Confirm';
import Toast from '../components/Toast';

interface AvailItem {
  kind: 'plant' | 'product' | 'ingredient';
  item_id: number;
  name: string;
  emoji: string | null;
  qty: number;
}

interface RowForm {
  direction: 'give' | 'want';
  kind: 'plant' | 'product' | 'ingredient';
  item_id: string;
  qty: string;
}

const KIND_LABEL: Record<string, string> = { plant: 'Растение', product: 'Товар', ingredient: 'Ингредиент' };
const DIR_LABEL: Record<string, string> = { give: 'Отдаю', want: 'Хочу получить' };
const STATUS_LABEL: Record<string, string> = { open: 'открыто', accepted: 'принято', rejected: 'отклонено', cancelled: 'отменено' };

function TradeItems({ items, isMine }: { items: TradeOffer['items']; isMine: boolean }) {
  const give = items.filter((i) => i.direction === 'give');
  const want = items.filter((i) => i.direction === 'want');
  return (
    <div style={{ fontSize: 13 }}>
      {give.length > 0 && (
        <div style={{ marginBottom: 4 }}>
          <strong style={{ fontSize: 12, color: 'var(--text-muted)' }}>{isMine ? 'Я отдаю' : 'Отдаёт'}:</strong>
          <div style={{ marginTop: 2 }}>{give.map((i) => <span key={i.id} className="fm-chip">{i.item_emoji || '📦'} {i.item_name} ×{i.qty}</span>)}</div>
        </div>
      )}
      {want.length > 0 && (
        <div>
          <strong style={{ fontSize: 12, color: 'var(--text-muted)' }}>{isMine ? 'Хочу получить' : 'Просит взамен'}:</strong>
          <div style={{ marginTop: 2 }}>{want.map((i) => <span key={i.id} className="fm-chip">{i.item_emoji || '📦'} {i.item_name} ×{i.qty}</span>)}</div>
        </div>
      )}
    </div>
  );
}

export default function TradesPage() {
  const { user } = useSession();
  const [tab, setTab] = useState<'create' | 'incoming' | 'outgoing' | 'history'>('create');
  const [incoming, setIncoming] = useState<TradeOffer[]>([]);
  const [outgoing, setOutgoing] = useState<TradeOffer[]>([]);
  const [history, setHistory] = useState<TradeOffer[]>([]);
  const [items, setItems] = useState<AvailItem[]>([]);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  const [recipient, setRecipient] = useState<PlayerSearchItem | null>(null);
  const [recipientQuery, setRecipientQuery] = useState('');
  const [recipientResults, setRecipientResults] = useState<PlayerSearchItem[]>([]);
  const [message, setMessage] = useState('');
  const [rows, setRows] = useState<RowForm[]>([{ direction: 'give', kind: 'plant', item_id: '', qty: '' }]);

  useEffect(() => {
    const q = recipientQuery.trim();
    if (!q) { setRecipientResults([]); return; }
    const t = setTimeout(() => {
      api.playerSearch(q)
        .then((r) => setRecipientResults(r.slice(0, 8)))
        .catch(() => setRecipientResults([]));
    }, 300);
    return () => clearTimeout(t);
  }, [recipientQuery]);

  const load = async () => {
    const [inc, out, hist] = await Promise.all([
      api.tradeIncoming(), api.tradeOutgoing(), api.tradeHistory(),
    ]);
    setIncoming(inc);
    setOutgoing(out);
    setHistory(hist);
  };

  useEffect(() => {
    (async () => {
      try {
        const [inv, aph] = await Promise.all([api.inventory(), api.apothecary()]);
        const all: AvailItem[] = [
          ...inv.filter((i) => i.item_kind === 'plant').map((i) => ({ kind: 'plant' as const, item_id: i.item_id, name: i.item_name, emoji: i.item_emoji, qty: i.qty })),
          ...inv.filter((i) => i.item_kind === 'product').map((i) => ({ kind: 'product' as const, item_id: i.item_id, name: i.item_name, emoji: i.item_emoji, qty: i.qty })),
          ...aph.map((i) => ({ kind: 'ingredient' as const, item_id: i.ingredient_id, name: i.name, emoji: null, qty: i.qty })),
        ].filter((i) => i.qty > 0);
        setItems(all);
      } catch { /* ignore */ }
      try { await load(); } catch { /* ignore */ }
    })();
  }, []);

  const itemsOf = useMemo(() => {
    const by: Record<string, AvailItem[]> = { plant: [], product: [], ingredient: [] };
    for (const it of items) by[it.kind].push(it);
    return by;
  }, [items]);

  async function submitOffer() {
    if (!recipient) { setMsg('✗ Выберите игрока из списка'); return; }
    const tradeItems: TradeItemIn[] = [];
    for (const r of rows) {
      const itemId = Number(r.item_id);
      const qty = Number(r.qty);
      if (!itemId || !qty || qty < 1) continue;
      const avail = itemsOf[r.kind].find((i) => i.item_id === itemId);
      if (r.direction === 'give' && avail && qty > avail.qty) { setMsg(`✗ У вас только ${avail.qty} «${avail.name}»`); return; }
      tradeItems.push({ kind: r.kind, item_id: itemId, qty, direction: r.direction });
    }
    if (tradeItems.length === 0) { setMsg('✗ Добавьте предметы в обмен'); return; }
    if (!tradeItems.some((i) => i.direction === 'give')) { setMsg('✗ Укажите, что вы отдаёте'); return; }
    setBusy(true); setMsg(null);
    try {
      await api.createTrade({ to_user_id: recipient.vk_id, message: message.trim() || null, items: tradeItems });
      setMsg('✓ Предложение отправлено');
      setRecipient(null); setRecipientQuery(''); setMessage('');
      setRows([{ direction: 'give', kind: 'plant', item_id: '', qty: '' }]);
      await load();
    } catch (e: any) {
      setMsg('✗ ' + (e?.response?.data?.detail || 'Ошибка'));
    } finally { setBusy(false); }
  }

  async function act(id: number, action: 'accept' | 'reject' | 'cancel') {
    if (action === 'reject' && !(await confirmDialog('Отклонить предложение?'))) return;
    if (action === 'cancel' && !(await confirmDialog('Отменить предложение?'))) return;
    setBusy(true); setMsg(null);
    try {
      if (action === 'accept') await api.acceptTrade(id);
      else if (action === 'reject') await api.rejectTrade(id);
      else await api.cancelTrade(id);
      setMsg(action === 'accept' ? '✓ Обмен выполнен!' : '✓ Готово');
      await load();
    } catch (e: any) {
      setMsg('✗ ' + (e?.response?.data?.detail || 'Ошибка'));
    } finally { setBusy(false); }
  }

  function renderOffer(o: TradeOffer, context: 'incoming' | 'outgoing' | 'history') {
    const isMine = user?.vk_id === o.from_user_id;
    return (
      <div key={o.id} className="fm-card fm-rise" style={{ fontSize: 13 }}>
        <div style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 6 }}>
          {isMine ? `${o.to_name}` : `${o.from_name}`} · {o.status === 'open' ? 'открыто' : STATUS_LABEL[o.status]}
        </div>
        {o.message && <div style={{ fontStyle: 'italic', marginBottom: 6 }}>«{o.message}»</div>}
        <TradeItems items={o.items} isMine={isMine} />
        <div style={{ display: 'flex', gap: 6, marginTop: 8, flexWrap: 'wrap' }}>
          {context === 'incoming' && (
            <>
              <button className="fm-btn fm-btn-sm" disabled={busy} onClick={() => act(o.id, 'accept')}>✅ Принять</button>
              <button className="fm-btn fm-btn-sm fm-btn-outline" disabled={busy} onClick={() => act(o.id, 'reject')}>✕ Отклонить</button>
            </>
          )}
          {context === 'outgoing' && (
            <button className="fm-btn fm-btn-sm fm-btn-outline" disabled={busy} onClick={() => act(o.id, 'cancel')}>🗑 Отменить</button>
          )}
        </div>
      </div>
    );
  }

  return (
    <div style={{ maxWidth: 'var(--shell-max-width)', margin: '0 auto', padding: 'var(--shell-pad)' }}>
      <h1 style={{ fontSize: 20, margin: '0 0 10px' }}>🤝 Бартер</h1>
      {msg && <Toast text={msg} onClose={() => setMsg(null)} />}

      <div style={{ display: 'flex', gap: 6, marginBottom: 12, flexWrap: 'wrap' }}>
        {([['create', '➕ Создать'], ['incoming', `📥 Входящие (${incoming.length})`], ['outgoing', `📤 Исходящие (${outgoing.length})`], ['history', '📜 История']] as const).map(([key, label]) => (
          <button key={key} className={tab === key ? 'fm-btn fm-btn-sm' : 'fm-btn fm-btn-sm fm-btn-outline'} onClick={() => setTab(key)}>{label}</button>
        ))}
      </div>

      {tab === 'create' && (
        <div className="fm-card">
          <label style={{ display: 'block', fontSize: 13, marginBottom: 2 }}>Игрок (начните вводить имя или ID)</label>
          {recipient ? (
            <div className="fm-card" style={{ display: 'flex', alignItems: 'center', gap: 8, padding: 8, marginBottom: 8 }}>
              <span style={{ flex: 1 }}>👤 {recipient.display_name} <span style={{ color: 'var(--text-muted)', fontSize: 12 }}>ID {recipient.vk_id}</span></span>
              <button className="fm-btn fm-btn-xs fm-btn-outline" onClick={() => { setRecipient(null); setRecipientQuery(''); setRecipientResults([]); }}>✕</button>
            </div>
          ) : (
            <div style={{ position: 'relative' }}>
              <input
                className="fm-input"
                value={recipientQuery}
                onChange={(e) => setRecipientQuery(e.target.value)}
                placeholder="Например: Марина или 795384…"
              />
              {recipientResults.length > 0 && (
                <div className="fm-card" style={{ position: 'absolute', left: 0, right: 0, top: '100%', zIndex: 5, padding: 6, marginTop: 4, maxHeight: 240, overflowY: 'auto' }}>
                  {recipientResults.map((p) => (
                    <button key={p.vk_id} className="fm-btn fm-btn-outline" style={{ display: 'block', width: '100%', textAlign: 'left', marginBottom: 4, fontSize: 13 }} onClick={() => setRecipient(p)}>
                      👤 {p.display_name} <span style={{ color: 'var(--text-muted)', fontSize: 12 }}>ID {p.vk_id} · 🏆 {p.level}</span>
                    </button>
                  ))}
                </div>
              )}
            </div>
          )}
          <label style={{ display: 'block', fontSize: 13, margin: '8px 0 2px' }}>Сообщение</label>
          <input className="fm-input" value={message} onChange={(e) => setMessage(e.target.value)} placeholder="Короткое сообщение…" />

          <label style={{ display: 'block', fontSize: 13, margin: '10px 0 4px' }}>Предметы обмена</label>
          {rows.map((r, idx) => {
            const opts = itemsOf[r.kind];
            const chosen = opts.find((i) => i.item_id === Number(r.item_id));
            return (
              <div key={idx} style={{ display: 'flex', gap: 6, marginBottom: 6, flexWrap: 'wrap', alignItems: 'center' }}>
                <select className="fm-input" value={r.direction} onChange={(e) => setRows(rows.map((x, i) => (i === idx ? { ...x, direction: e.target.value as 'give' | 'want' } : x)))} style={{ width: 110 }}>
                  <option value="give">Отдаю</option>
                  <option value="want">Хочу</option>
                </select>
                <select className="fm-input" value={r.kind} onChange={(e) => setRows(rows.map((x, i) => (i === idx ? { ...x, kind: e.target.value as RowForm['kind'], item_id: '' } : x)))} style={{ width: 130 }}>
                  {(['plant', 'product', 'ingredient'] as const).map((k) => <option key={k} value={k}>{KIND_LABEL[k]}</option>)}
                </select>
                <select className="fm-input" value={r.item_id} onChange={(e) => setRows(rows.map((x, i) => (i === idx ? { ...x, item_id: e.target.value } : x)))} style={{ width: 170 }}>
                  <option value="">— выберите —</option>
                  {opts.map((it) => <option key={`${it.kind}-${it.item_id}`} value={String(it.item_id)}>{it.emoji || ''} {it.name} ({it.qty})</option>)}
                </select>
                <input className="fm-input" type="number" min={1} value={r.qty} onChange={(e) => setRows(rows.map((x, i) => (i === idx ? { ...x, qty: e.target.value } : x)))} placeholder="Кол-во" style={{ width: 80 }} />
                {chosen && r.direction === 'give' && <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>есть {chosen.qty}</span>}
                {rows.length > 1 && <button className="fm-btn fm-btn-xs fm-btn-danger" onClick={() => setRows(rows.filter((_, i) => i !== idx))}>🗑</button>}
              </div>
            );
          })}
          <div style={{ display: 'flex', gap: 8, marginTop: 8, flexWrap: 'wrap' }}>
            <button className="fm-btn fm-btn-outline fm-btn-sm" onClick={() => setRows([...rows, { direction: 'give', kind: 'plant', item_id: '', qty: '' }])}>➕ Ещё строка</button>
            <button className="fm-btn" disabled={busy} onClick={submitOffer}>📨 Отправить предложение</button>
          </div>
        </div>
      )}

      {tab === 'incoming' && (
        incoming.length === 0
          ? <div className="fm-card" style={{ color: 'var(--text-muted)' }}>Входящих предложений нет.</div>
          : <div className="fm-grid">{incoming.map((o) => renderOffer(o, 'incoming'))}</div>
      )}

      {tab === 'outgoing' && (
        outgoing.length === 0
          ? <div className="fm-card" style={{ color: 'var(--text-muted)' }}>Исходящих предложений нет.</div>
          : <div className="fm-grid">{outgoing.map((o) => renderOffer(o, 'outgoing'))}</div>
      )}

      {tab === 'history' && (
        history.length === 0
          ? <div className="fm-card" style={{ color: 'var(--text-muted)' }}>История пуста.</div>
          : <div className="fm-grid">{history.map((o) => renderOffer(o, 'history'))}</div>
      )}
    </div>
  );
}
