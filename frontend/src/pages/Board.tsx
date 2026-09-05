import { useEffect, useMemo, useState } from 'react';
import { api, type BoardItemIn, type BoardPost } from '../api/endpoints';
import { mediaUrl } from '../api/media';
import { confirmDialog } from '../components/Confirm';
import ItemPicker from '../components/ItemPicker';
import Toast from '../components/Toast';

interface PickItem {
  kind: 'plant' | 'product' | 'ingredient';
  item_id: number;
  name: string;
  emoji: string | null;
  image: string | null;
  qty?: number;
}

interface RowForm {
  kind: 'plant' | 'product' | 'ingredient';
  item_id: string;
}

const EMPTY_ROWS: RowForm[] = [{ kind: 'plant', item_id: '' }];

const KIND_LABEL: Record<string, string> = { plant: 'Растение', product: 'Товар', ingredient: 'Ингредиент' };
const KIND_EMOJI: Record<string, string> = { plant: '🌿', product: '📦', ingredient: '⚗️' };

const STATUS_LABEL: Record<string, string> = {
  open: 'открыто',
  fulfilled: '✅ выполнено',
  cancelled: '🗑 отменено',
  expired: '⏳ истекло',
};

function errDetail(e: any): string {
  return e?.response?.data?.detail || 'Ошибка';
}

function Chip({ it }: { it: BoardPost['items'][number] }) {
  return (
    <span className="fm-chip" style={{ maxWidth: '100%' }}>
      {it.item_image ? (
        <img src={mediaUrl(it.item_image)} alt="" style={{ height: 18, width: 'auto', flexShrink: 0, borderRadius: 3 }} />
      ) : (
        <span style={{ flexShrink: 0 }}>{it.item_emoji || '📦'}</span>
      )}
      <span style={{ wordBreak: 'break-word', overflowWrap: 'anywhere', minWidth: 0 }}>
        {it.item_name}{it.qty > 1 ? ` ×${it.qty}` : ''}
      </span>
    </span>
  );
}

function BoardItems({ items }: { items: BoardPost['items'] }) {
  const give = items.filter((i) => i.direction === 'give');
  const want = items.filter((i) => i.direction === 'want');
  return (
    <div style={{ fontSize: 13 }}>
      {give.length > 0 && (
        <div style={{ marginBottom: 4 }}>
          <div style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 3 }}>Отдаёт:</div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>{give.map((i) => <Chip key={i.id} it={i} />)}</div>
        </div>
      )}
      {want.length > 0 && (
        <div>
          <div style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 3 }}>Хочет получить:</div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>{want.map((i) => <Chip key={i.id} it={i} />)}</div>
        </div>
      )}
    </div>
  );
}

function fmt(iso: string | null): string {
  if (!iso) return '';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '';
  return d.toLocaleDateString('ru-RU', { day: '2-digit', month: '2-digit' });
}

function byKind(list: PickItem[]): Record<string, PickItem[]> {
  const by: Record<string, PickItem[]> = { plant: [], product: [], ingredient: [] };
  for (const it of list) by[it.kind].push(it);
  return by;
}

export default function BoardPage() {
  const [tab, setTab] = useState<'board' | 'mine' | 'create' | 'history'>('board');
  const [posts, setPosts] = useState<BoardPost[]>([]);
  const [mine, setMine] = useState<BoardPost[]>([]);
  const [history, setHistory] = useState<BoardPost[]>([]);
  const [giveItems, setGiveItems] = useState<PickItem[]>([]);
  const [wantItems, setWantItems] = useState<PickItem[]>([]);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const [delivering, setDelivering] = useState(false);

  const [message, setMessage] = useState('');
  const [giveRows, setGiveRows] = useState<RowForm[]>(EMPTY_ROWS);
  const [wantRows, setWantRows] = useState<RowForm[]>(EMPTY_ROWS);

  const load = async () => {
    const [b, m, h] = await Promise.all([api.board(), api.boardMine(), api.boardHistory()]);
    setPosts(b);
    setMine(m);
    setHistory(h);
  };

  useEffect(() => {
    (async () => {
      try {
        const [inv, aph] = await Promise.all([api.inventory(), api.apothecary()]);
        setGiveItems([
          ...inv.filter((i) => i.item_kind === 'plant').map((i) => ({ kind: 'plant' as const, item_id: i.item_id, name: i.item_name, emoji: i.item_emoji, image: i.item_image, qty: i.qty })),
          ...inv.filter((i) => i.item_kind === 'product').map((i) => ({ kind: 'product' as const, item_id: i.item_id, name: i.item_name, emoji: i.item_emoji, image: i.item_image, qty: i.qty })),
          ...aph.map((i) => ({ kind: 'ingredient' as const, item_id: i.ingredient_id, name: i.name, emoji: null, image: i.image_url, qty: i.qty })),
        ].filter((i) => i.qty > 0));
      } catch { /* ignore */ }
      try {
        const [plants, products, ings] = await Promise.all([api.plants(), api.products(), api.ingredients()]);
        setWantItems([
          ...plants.map((p) => ({ kind: 'plant' as const, item_id: p.id, name: p.name, emoji: p.emoji, image: p.image_harvested_url || p.image_grown_url || p.image_url })),
          ...products.map((p) => ({ kind: 'product' as const, item_id: p.id, name: p.name, emoji: p.emoji, image: p.image_url })),
          ...ings.map((i) => ({ kind: 'ingredient' as const, item_id: i.id, name: i.name, emoji: null, image: i.image_url })),
        ]);
      } catch { /* ignore */ }
      try { await load(); } catch { /* ignore */ }
    })();
  }, []);

  useEffect(() => {
    const id = setInterval(() => {
      load().catch(() => {});
    }, 15000);
    return () => clearInterval(id);
  }, []);

  useEffect(() => {
    if (!delivering) return;
    const t = setTimeout(() => setDelivering(false), 3000);
    return () => clearTimeout(t);
  }, [delivering]);

  const giveOf = useMemo(() => byKind(giveItems), [giveItems]);
  const wantOf = useMemo(() => byKind(wantItems), [wantItems]);

  async function submitPost() {
    const items: BoardItemIn[] = [];
    for (const [section, rows] of [['give', giveRows], ['want', wantRows]] as const) {
      for (const r of rows) {
        const itemId = Number(r.item_id);
        if (!itemId) continue;
        items.push({ kind: r.kind, item_id: itemId, qty: 1, direction: section });
      }
    }
    if (items.length === 0) { setMsg('✗ Добавьте предметы'); return; }
    if (!items.some((i) => i.direction === 'give')) { setMsg('✗ Укажите, что вы отдаёте'); return; }
    if (!items.some((i) => i.direction === 'want')) { setMsg('✗ Укажите, что вы хотите получить'); return; }
    setBusy(true); setMsg(null);
    try {
      await api.createBoardPost({ message: message.trim() || null, items });
      setMsg('✓ Объявление размещено');
      setMessage('');
      setGiveRows(EMPTY_ROWS.map((r) => ({ ...r })));
      setWantRows(EMPTY_ROWS.map((r) => ({ ...r })));
      setTab('mine');
      await load();
    } catch (e) {
      setMsg('✗ ' + errDetail(e));
    } finally { setBusy(false); }
  }

  async function respond(id: number) {
    setBusy(true); setMsg(null);
    try {
      await api.respondBoardPost(id);
      setDelivering(true);
      await load();
    } catch (e) {
      setMsg('✗ ' + errDetail(e));
    } finally { setBusy(false); }
  }

  async function cancel(id: number) {
    if (!(await confirmDialog('Снять объявление? Предметы вернутся на склад.'))) return;
    setBusy(true); setMsg(null);
    try {
      await api.cancelBoardPost(id);
      setMsg('✓ Объявление снято');
      await load();
    } catch (e) {
      setMsg('✗ ' + errDetail(e));
    } finally { setBusy(false); }
  }

  function renderRows(section: 'give' | 'want') {
    const rows = section === 'give' ? giveRows : wantRows;
    const setSectionRows = section === 'give' ? setGiveRows : setWantRows;
    const source = section === 'give' ? giveOf : wantOf;
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
            {opts.length === 0 ? (
              <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>{section === 'give' ? 'Нет таких предметов на складе.' : 'Таких предметов в игре нет.'}</div>
            ) : (
              <ItemPicker
                items={opts.map((it) => ({ key: String(it.item_id), title: it.name, image: it.image, emoji: it.emoji ?? KIND_EMOJI[r.kind], badge: section === 'give' ? `есть ${it.qty}` : undefined }))}
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
      <h1 style={{ fontSize: 20, margin: '0 0 10px' }}>📋 Доска объявлений</h1>
      {msg && <Toast text={msg} onClose={() => setMsg(null)} />}

      {delivering && (
        <div style={{ position: 'fixed', inset: 0, zIndex: 90, background: 'rgba(0,0,0,0.6)', backdropFilter: 'blur(3px)', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 16 }}>
          <div className="fm-card fm-rise" style={{ textAlign: 'center', width: '100%', maxWidth: 320 }}>
            <div style={{ fontSize: 46, marginBottom: 8 }}>🚚</div>
            <div style={{ fontSize: 17, fontWeight: 600, overflowWrap: 'anywhere' }}>Товар доставляется</div>
          </div>
        </div>
      )}

      <div style={{ display: 'flex', gap: 6, marginBottom: 12, flexWrap: 'wrap' }}>
        {([['board', '📋 Доска'], ['mine', `📌 Мои (${mine.length})`], ['create', '➕ Разместить'], ['history', '📜 История']] as const).map(([key, label]) => (
          <button key={key} className={tab === key ? 'fm-btn fm-btn-sm' : 'fm-btn fm-btn-sm fm-btn-outline'} onClick={() => setTab(key)}>{label}</button>
        ))}
      </div>

      {tab === 'board' && (
        posts.length === 0 ? (
          <div className="fm-card" style={{ color: 'var(--text-muted)' }}>Объявлений, которые вы можете выполнить, пока нет.</div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            {posts.map((p) => (
              <div key={p.id} className="fm-card fm-rise" style={{ fontSize: 13, minWidth: 0 }}>
                <div style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 6, overflowWrap: 'anywhere' }}>
                  👤 {p.author_name} · {fmt(p.created_at)}
                </div>
                {p.message && <div style={{ fontStyle: 'italic', marginBottom: 6, overflowWrap: 'anywhere' }}>«{p.message}»</div>}
                <BoardItems items={p.items} />
                <div style={{ display: 'flex', gap: 6, marginTop: 8, flexWrap: 'wrap' }}>
                  <button className="fm-btn fm-btn-sm" disabled={busy} onClick={() => respond(p.id)}>🤝 Откликнуться</button>
                </div>
              </div>
            ))}
          </div>
        )
      )}

      {tab === 'mine' && (
        <>
          {mine.length > 0 && (
            <div className="fm-card" style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 10, overflowWrap: 'anywhere' }}>
              💡 Ваше объявление видно только тем, у кого есть запрошенный предмет.
            </div>
          )}
          {mine.length === 0 ? (
            <div className="fm-card" style={{ color: 'var(--text-muted)' }}>Активных объявлений нет.</div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
              {mine.map((p) => (
                <div key={p.id} className="fm-card fm-rise" style={{ fontSize: 13, minWidth: 0 }}>
                  <div style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 6, overflowWrap: 'anywhere' }}>
                    {STATUS_LABEL[p.status] ?? p.status} · до {fmt(p.expires_at)}
                  </div>
                  {p.message && <div style={{ fontStyle: 'italic', marginBottom: 6, overflowWrap: 'anywhere' }}>«{p.message}»</div>}
                  <BoardItems items={p.items} />
                  <div style={{ display: 'flex', gap: 6, marginTop: 8, flexWrap: 'wrap' }}>
                    <button className="fm-btn fm-btn-sm fm-btn-outline" disabled={busy} onClick={() => cancel(p.id)}>🗑 Снять</button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </>
      )}

      {tab === 'create' && (
        <div className="fm-card">
          <label style={{ display: 'block', fontSize: 13, marginBottom: 2 }}>Сообщение</label>
          <input className="fm-input" value={message} onChange={(e) => setMessage(e.target.value)} placeholder="Короткое сообщение…" />

          <div style={{ fontSize: 14, fontWeight: 600, margin: '12px 0 6px' }}>📤 Я отдаю</div>
          {renderRows('give')}

          <div style={{ fontSize: 14, fontWeight: 600, margin: '14px 0 6px' }}>📥 Хочу получить</div>
          {renderRows('want')}

          <div style={{ display: 'flex', gap: 8, marginTop: 12, flexWrap: 'wrap' }}>
            <button className="fm-btn fm-btn-sm" disabled={busy} onClick={submitPost}>📋 Разместить объявление</button>
          </div>
        </div>
      )}

      {tab === 'history' && (
        history.length === 0 ? (
          <div className="fm-card" style={{ color: 'var(--text-muted)' }}>История пуста.</div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            {history.map((p) => (
              <div key={p.id} className="fm-card fm-rise" style={{ fontSize: 13, minWidth: 0 }}>
                <div style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 6, overflowWrap: 'anywhere' }}>
                  {STATUS_LABEL[p.status] ?? p.status} · {fmt(p.created_at)}
                </div>
                {p.message && <div style={{ fontStyle: 'italic', marginBottom: 6, overflowWrap: 'anywhere' }}>«{p.message}»</div>}
                <BoardItems items={p.items} />
              </div>
            ))}
          </div>
        )
      )}
    </div>
  );
}
