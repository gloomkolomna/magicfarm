import { useEffect, useMemo, useState } from 'react';
import { useSession } from '../context/SessionContext';
import { api, type PlayerSearchItem, type TradeOffer, type TradeItemIn } from '../api/endpoints';
import { mediaUrl } from '../api/media';
import { confirmDialog } from '../components/Confirm';
import ItemPicker from '../components/ItemPicker';
import Toast from '../components/Toast';

interface AvailItem {
  kind: 'plant' | 'product' | 'ingredient';
  item_id: number;
  name: string;
  emoji: string | null;
  image: string | null;
  qty: number;
}

interface RowForm {
  kind: 'plant' | 'product' | 'ingredient';
  item_id: string;
}

const EMPTY_ROWS: RowForm[] = [{ kind: 'plant', item_id: '' }];

const KIND_LABEL: Record<string, string> = { plant: 'Растение', product: 'Товар', ingredient: 'Ингредиент' };
const KIND_EMOJI: Record<string, string> = { plant: '🌿', product: '📦', ingredient: '⚗️' };

function TradeItems({ items, isMine }: { items: TradeOffer['items']; isMine: boolean }) {
  const give = items.filter((i) => i.direction === 'give');
  const want = items.filter((i) => i.direction === 'want');
  const chip = (i: TradeOffer['items'][number], reserved?: boolean) => (
    <span key={i.id} className="fm-chip">
      {i.item_image ? (
        <img src={mediaUrl(i.item_image)} alt="" style={{ height: 18, width: 'auto', verticalAlign: 'middle', marginRight: 4, borderRadius: 3 }} />
      ) : (
        <span style={{ marginRight: 4 }}>{i.item_emoji || '📦'}</span>
      )}
      {i.item_name}{reserved ? ' 🔒' : ''}
    </span>
  );
  return (
    <div style={{ fontSize: 13 }}>
      {give.length > 0 && (
        <div style={{ marginBottom: 4 }}>
          <strong style={{ fontSize: 12, color: 'var(--text-muted)' }}>{isMine ? 'Я отдаю' : 'Отдаёт'}:</strong>
          <div style={{ marginTop: 2 }}>{give.map((i) => chip(i, i.reserved))}</div>
        </div>
      )}
      {want.length > 0 && (
        <div>
          <strong style={{ fontSize: 12, color: 'var(--text-muted)' }}>{isMine ? 'Хочу получить' : 'Просит взамен'}:</strong>
          <div style={{ marginTop: 2 }}>{want.map((i) => chip(i))}</div>
        </div>
      )}
    </div>
  );
}

function buildItems(inv: { item_kind: string; item_id: number; item_name: string; item_emoji: string | null; item_image: string | null; qty: number }[], aph: { ingredient_id: number; name: string; image_url: string | null; qty: number }[]): AvailItem[] {
  return [
    ...inv.filter((i) => i.item_kind === 'plant').map((i) => ({ kind: 'plant' as const, item_id: i.item_id, name: i.item_name, emoji: i.item_emoji, image: i.item_image, qty: i.qty })),
    ...inv.filter((i) => i.item_kind === 'product').map((i) => ({ kind: 'product' as const, item_id: i.item_id, name: i.item_name, emoji: i.item_emoji, image: i.item_image, qty: i.qty })),
    ...aph.map((i) => ({ kind: 'ingredient' as const, item_id: i.ingredient_id, name: i.name, emoji: null, image: i.image_url, qty: i.qty })),
  ].filter((i) => i.qty > 0);
}

function buildItemsFromFarm(farm: { plants: { item_id: number; name: string; emoji: string | null; image?: string | null; qty: number }[]; products: { item_id: number; name: string; emoji: string | null; image?: string | null; qty: number }[]; ingredients: { item_id: number; name: string; image?: string | null; qty: number }[] }): AvailItem[] {
  return [
    ...farm.plants.map((i) => ({ kind: 'plant' as const, item_id: i.item_id, name: i.name, emoji: i.emoji, image: i.image ?? null, qty: i.qty })),
    ...farm.products.map((i) => ({ kind: 'product' as const, item_id: i.item_id, name: i.name, emoji: i.emoji, image: i.image ?? null, qty: i.qty })),
    ...farm.ingredients.map((i) => ({ kind: 'ingredient' as const, item_id: i.item_id, name: i.name, emoji: null, image: i.image ?? null, qty: i.qty })),
  ].filter((i) => i.qty > 0);
}

function byKind(list: AvailItem[]): Record<string, AvailItem[]> {
  const by: Record<string, AvailItem[]> = { plant: [], product: [], ingredient: [] };
  for (const it of list) by[it.kind].push(it);
  return by;
}

export default function TradesPage() {
  const { user } = useSession();
  const [tab, setTab] = useState<'create' | 'incoming' | 'outgoing' | 'history'>('create');
  const [incoming, setIncoming] = useState<TradeOffer[]>([]);
  const [outgoing, setOutgoing] = useState<TradeOffer[]>([]);
  const [history, setHistory] = useState<TradeOffer[]>([]);
  const [items, setItems] = useState<AvailItem[]>([]);
  const [recipientItems, setRecipientItems] = useState<AvailItem[]>([]);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  const [recipient, setRecipient] = useState<PlayerSearchItem | null>(null);
  const [recipientQuery, setRecipientQuery] = useState('');
  const [recipientResults, setRecipientResults] = useState<PlayerSearchItem[]>([]);
  const [message, setMessage] = useState('');
  const [giveRows, setGiveRows] = useState<RowForm[]>(EMPTY_ROWS);
  const [wantRows, setWantRows] = useState<RowForm[]>(EMPTY_ROWS);

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
        setItems(buildItems(inv, aph));
      } catch { /* ignore */ }
      try { await load(); } catch { /* ignore */ }
    })();
  }, []);

  const itemsOf = useMemo(() => byKind(items), [items]);
  const recipientItemsOf = useMemo(() => byKind(recipientItems), [recipientItems]);

  async function selectRecipient(p: PlayerSearchItem) {
    setRecipient(p);
    setRecipientQuery('');
    setRecipientResults([]);
    setGiveRows(EMPTY_ROWS.map((r) => ({ ...r })));
    setWantRows(EMPTY_ROWS.map((r) => ({ ...r })));
    try {
      const farm = await api.playerFarm(p.vk_id);
      setRecipientItems(buildItemsFromFarm(farm));
    } catch { /* ignore */ }
  }

  async function submitOffer() {
    if (!recipient) { setMsg('✗ Выберите игрока из списка'); return; }
    const tradeItems: TradeItemIn[] = [];
    for (const [section, sectionRows] of [['give', giveRows], ['want', wantRows]] as const) {
      for (const r of sectionRows) {
        const itemId = Number(r.item_id);
        if (!itemId) continue;
        tradeItems.push({ kind: r.kind, item_id: itemId, qty: 1, direction: section });
      }
    }
    if (tradeItems.length === 0) { setMsg('✗ Добавьте предметы в обмен'); return; }
    if (!tradeItems.some((i) => i.direction === 'give')) { setMsg('✗ Укажите, что вы отдаёте'); return; }
    if (!tradeItems.some((i) => i.direction === 'want')) { setMsg('✗ Укажите, что вы хотите получить'); return; }
    setBusy(true); setMsg(null);
    try {
      await api.createTrade({ to_user_id: recipient.vk_id, message: message.trim() || null, items: tradeItems });
      setMsg('✓ Предложение отправлено');
      setRecipient(null); setRecipientQuery(''); setRecipientItems([]); setMessage('');
      setGiveRows(EMPTY_ROWS.map((r) => ({ ...r })));
      setWantRows(EMPTY_ROWS.map((r) => ({ ...r })));
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
          {isMine ? `${o.to_name}` : `${o.from_name}`} ·{' '}
          <span style={{ fontWeight: 600, color: o.status === 'accepted' ? 'var(--success, #4caf50)' : o.status === 'rejected' ? 'var(--danger, #e5484d)' : o.status === 'cancelled' ? 'var(--text-muted)' : 'var(--text-primary)' }}>
            {o.status === 'open' ? 'открыто' : o.status === 'accepted' ? '✅ принято' : o.status === 'rejected' ? '✕ отклонено' : '🗑 отменено'}
          </span>
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

  function clearRecipient() {
    setRecipient(null);
    setRecipientQuery('');
    setRecipientResults([]);
    setRecipientItems([]);
    setGiveRows(EMPTY_ROWS.map((r) => ({ ...r })));
    setWantRows(EMPTY_ROWS.map((r) => ({ ...r })));
  }

  function renderRows(section: 'give' | 'want') {
    const rows = section === 'give' ? giveRows : wantRows;
    const setSectionRows = section === 'give' ? setGiveRows : setWantRows;
    const source = section === 'give' ? itemsOf : recipientItemsOf;
    return rows.map((r, idx) => {
      const opts = source[r.kind];
      return (
        <div key={idx} style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border)', borderRadius: 10, padding: '8px 10px', marginBottom: 8 }}>
          <div style={{ display: 'flex', gap: 8, alignItems: 'flex-start', flexWrap: 'wrap' }}>
            <div style={{ flex: '1 1 180px', minWidth: 0 }}>
              <ItemPicker
                compact
                columns={3}
                items={(['plant', 'product', 'ingredient'] as const).map((k) => ({ key: k, title: KIND_LABEL[k], emoji: KIND_EMOJI[k] }))}
                value={r.kind}
                onChange={(k) => setSectionRows(rows.map((x, i) => (i === idx ? { ...x, kind: k as RowForm['kind'], item_id: '' } : x)))}
              />
            </div>
            {rows.length > 1 && (
              <button className="fm-btn fm-btn-xs fm-btn-danger" onClick={() => setSectionRows(rows.filter((_, i) => i !== idx))} aria-label="Удалить строку">🗑</button>
            )}
          </div>
          <div style={{ marginTop: 6 }}>
            {section === 'want' && !recipient ? (
              <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>Сначала выберите игрока выше.</div>
            ) : opts.length === 0 ? (
              <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>{section === 'give' ? 'Нет таких предметов на складе.' : 'у игрока нет таких предметов'}</div>
            ) : (
              <ItemPicker
                items={opts.map((it) => ({ key: String(it.item_id), title: it.name, image: it.image, emoji: it.emoji ?? KIND_EMOJI[r.kind], badge: section === 'give' ? `есть ${it.qty}` : `у него ${it.qty}` }))}
                value={r.item_id || null}
                onChange={(k) => setSectionRows(rows.map((x, i) => (i === idx ? { ...x, item_id: k } : x)))}
              />
            )}
          </div>
        </div>
      );
    });
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
              <button className="fm-btn fm-btn-xs fm-btn-outline" onClick={clearRecipient}>✕</button>
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
                    <button key={p.vk_id} className="fm-btn fm-btn-outline" style={{ display: 'block', width: '100%', textAlign: 'left', marginBottom: 4, fontSize: 13 }} onClick={() => selectRecipient(p)}>
                      👤 {p.display_name} <span style={{ color: 'var(--text-muted)', fontSize: 12 }}>ID {p.vk_id} · 🏆 {p.level}</span>
                    </button>
                  ))}
                </div>
              )}
            </div>
          )}
          <label style={{ display: 'block', fontSize: 13, margin: '8px 0 2px' }}>Сообщение</label>
          <input className="fm-input" value={message} onChange={(e) => setMessage(e.target.value)} placeholder="Короткое сообщение…" />

          <div style={{ fontSize: 14, fontWeight: 600, margin: '12px 0 6px' }}>📤 Я отдаю</div>
          {renderRows('give')}
          <button className="fm-btn fm-btn-outline fm-btn-sm" onClick={() => setGiveRows([...giveRows, { kind: 'plant', item_id: '' }])}>➕ Добавить предмет</button>

          <div style={{ fontSize: 14, fontWeight: 600, margin: '14px 0 6px' }}>📥 Хочу получить</div>
          {renderRows('want')}
          <button className="fm-btn fm-btn-outline fm-btn-sm" onClick={() => setWantRows([...wantRows, { kind: 'plant', item_id: '' }])}>➕ Добавить предмет</button>

          <div style={{ display: 'flex', gap: 8, marginTop: 12, flexWrap: 'wrap' }}>
            <button className="fm-btn fm-btn-sm" disabled={busy} onClick={submitOffer}>📨 Отправить предложение</button>
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
