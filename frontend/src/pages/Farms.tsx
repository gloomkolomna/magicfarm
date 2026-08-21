import { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api, type FieldDetail, type PlayerFarm, type PlayerSearchItem } from '../api/endpoints';
import FieldGridView from '../components/FieldGridView';
import Toast from '../components/Toast';

interface GiftItem {
  kind: 'plant' | 'product' | 'ingredient';
  item_id: number;
  name: string;
  emoji: string | null;
  qty: number;
}

const GIFT_KIND_LABEL: Record<string, string> = { plant: 'Растение', product: 'Товар', ingredient: 'Ингредиент' };

const PLOT_STATUS_LABEL: Record<string, string> = {
  planted: 'посажено',
  grown: 'выросло',
  await_replant: 'готово к пересадке',
};

const PROD_STATUS_LABEL: Record<string, string> = {
  installed: 'установлено',
};

export default function FarmsPage() {
  const nav = useNavigate();
  const [q, setQ] = useState('');
  const [allPlayers, setAllPlayers] = useState<PlayerSearchItem[]>([]);
  const [farm, setFarm] = useState<PlayerFarm | null>(null);
  const [viewField, setViewField] = useState<FieldDetail | null>(null);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  const [giftTarget, setGiftTarget] = useState<PlayerSearchItem | null>(null);
  const [giftItems, setGiftItems] = useState<GiftItem[]>([]);
  const [giftKind, setGiftKind] = useState<'plant' | 'product' | 'ingredient'>('plant');
  const [giftItemId, setGiftItemId] = useState('');
  const [giftQty, setGiftQty] = useState('1');

  useEffect(() => {
    api.playerSearch('', 100).then(setAllPlayers).catch(() => {});
  }, []);

  async function openGift(target: PlayerSearchItem) {
    setGiftTarget(target);
    setGiftKind('plant');
    setGiftItemId('');
    setGiftQty('1');
    try {
      const [inv, aph] = await Promise.all([api.inventory(), api.apothecary()]);
      const all: GiftItem[] = [
        ...inv.filter((i) => i.item_kind === 'plant').map((i) => ({ kind: 'plant' as const, item_id: i.item_id, name: i.item_name, emoji: i.item_emoji, qty: i.qty })),
        ...inv.filter((i) => i.item_kind === 'product').map((i) => ({ kind: 'product' as const, item_id: i.item_id, name: i.item_name, emoji: i.item_emoji, qty: i.qty })),
        ...aph.map((i) => ({ kind: 'ingredient' as const, item_id: i.ingredient_id, name: i.name, emoji: null, qty: i.qty })),
      ].filter((i) => i.qty > 0);
      setGiftItems(all);
    } catch { /* ignore */ }
  }

  async function sendGift() {
    if (!giftTarget) return;
    const itemId = Number(giftItemId);
    const qty = Number(giftQty) || 1;
    if (!itemId || qty < 1) { setMsg('✗ Выберите предмет и количество'); return; }
    const avail = giftItems.find((i) => i.kind === giftKind && i.item_id === itemId);
    if (avail && qty > avail.qty) { setMsg(`✗ У вас только ${avail.qty} «${avail.name}»`); return; }
    setBusy(true); setMsg(null);
    try {
      await api.sendGift({ to_user_id: giftTarget.vk_id, kind: giftKind, item_id: itemId, qty });
      setMsg(`✓ Подарок отправлен игроку ${giftTarget.display_name} — он появится у него в чате`);
      setGiftTarget(null);
    } catch (e: any) {
      setMsg('✗ ' + (e?.response?.data?.detail || 'Ошибка'));
    } finally { setBusy(false); }
  }

  const results = useMemo(() => {
    const needle = q.trim().toLowerCase();
    if (!needle) return allPlayers;
    return allPlayers.filter(
      (p) => p.display_name.toLowerCase().includes(needle) || String(p.vk_id).includes(needle),
    );
  }, [q, allPlayers]);

  async function openFarm(vkId: number) {
    setBusy(true); setMsg(null);
    try {
      setFarm(await api.playerFarm(vkId));
    } catch (e: any) {
      setMsg('✗ ' + (e?.response?.data?.detail || 'Ошибка загрузки фермы'));
    } finally {
      setBusy(false);
    }
  }

  async function openField(fieldId: number) {
    if (!farm) return;
    setBusy(true); setMsg(null);
    try {
      setViewField(await api.playerField(farm.vk_id, fieldId));
    } catch (e: any) {
      setMsg('✗ ' + (e?.response?.data?.detail || 'Ошибка загрузки локации'));
    } finally {
      setBusy(false);
    }
  }

  function writeTo(vkId: number) {
    nav(`/chat/${vkId}`);
  }

  return (
    <div style={{ maxWidth: 'var(--shell-max-width)', margin: '0 auto', padding: 'var(--shell-pad)' }}>
      <h1 style={{ fontSize: 20, margin: '0 0 10px' }}>🌾 Фермы игроков</h1>
      {msg && <Toast text={msg} onClose={() => setMsg(null)} />}

      {!farm ? (
        <>
          <div className="fm-card" style={{ marginBottom: 12 }}>
            <input
              className="fm-input"
              placeholder="Фильтр: имя или ID игрока…"
              value={q}
              onChange={(e) => setQ(e.target.value)}
            />
          </div>
          <p style={{ fontSize: 12, color: 'var(--text-muted)', margin: '0 0 10px' }}>
            Только просмотр: фермы других игроков можно смотреть и писать, но нельзя трогать.
          </p>
          {results.length === 0 ? (
            <div className="fm-card" style={{ color: 'var(--text-muted)' }}>Игроков пока нет.</div>
          ) : (
            <div className="fm-grid">
              {results.map((p) => (
                <div key={p.vk_id} className="fm-card fm-rise" style={{ textAlign: 'left', cursor: 'pointer' }} onClick={() => openFarm(p.vk_id)}>
                  <strong style={{ fontSize: 15 }}>👤 {p.display_name}</strong>
                  <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginTop: 4 }}>
                    🏆 Уровень {p.level} · 🪙 {p.coins} · 🧵 {p.crosses_total}
                  </div>
                  <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 2 }}>ID: {p.vk_id}</div>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginTop: 8 }}>
                    <button className="fm-btn fm-btn-sm" style={{ flex: '1 1 45%', minWidth: 0 }} onClick={(e) => { e.stopPropagation(); openFarm(p.vk_id); }}>👁 Смотреть</button>
                    <button className="fm-btn fm-btn-sm fm-btn-outline" style={{ flex: '1 1 45%', minWidth: 0 }} onClick={(e) => { e.stopPropagation(); openGift(p); }}>🎁 Подарок</button>
                    <button className="fm-btn fm-btn-sm fm-btn-outline" style={{ flex: '1 1 100%', minWidth: 0 }} onClick={(e) => { e.stopPropagation(); writeTo(p.vk_id); }}>💬 Написать</button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </>
      ) : (
        <div>
          <div style={{ display: 'flex', gap: 8, marginBottom: 10, flexWrap: 'wrap' }}>
            <button className="fm-btn fm-btn-sm fm-btn-outline" disabled={busy} onClick={() => setFarm(null)}>← Назад</button>
            <button className="fm-btn fm-btn-sm" disabled={busy} onClick={() => writeTo(farm.vk_id)}>💬 Написать</button>
            <button className="fm-btn fm-btn-sm" disabled={busy} onClick={() => openGift({ vk_id: farm.vk_id, display_name: farm.display_name, level: farm.level, coins: farm.coins, crosses_total: farm.crosses_total })}>🎁 Отправить подарок</button>
          </div>
          <div className="fm-card" style={{ marginBottom: 10 }}>
            <strong style={{ fontSize: 17 }}>👤 {farm.display_name}</strong>
            <div style={{ fontSize: 13, color: 'var(--text-secondary)', marginTop: 4 }}>
              🏆 Уровень {farm.level} · 🪙 {farm.coins} · 🧵 {farm.crosses_total} · Раунд {farm.round} · 🏅 Достижений: {farm.achievements_total}
            </div>
          </div>

          <h3 style={{ margin: '0 0 8px' }}>🗺️ Локации</h3>
          {farm.fields.length === 0 ? (
            <div className="fm-card" style={{ color: 'var(--text-muted)', fontSize: 13 }}>Нет открытых локаций.</div>
          ) : (
            <div className="fm-grid" style={{ marginBottom: 12 }}>
              {farm.fields.map((f) => (
                <button key={f.id} className="fm-card fm-rise" style={{ fontSize: 13, textAlign: 'left', cursor: 'pointer' }} onClick={() => openField(f.id)}>
                  <strong>🗺️ {f.name}</strong>
                  <div style={{ color: 'var(--text-muted)', marginTop: 2 }}>{f.cols}×{f.rows} клеток</div>
                </button>
              ))}
            </div>
          )}

          <h3 style={{ margin: '0 0 8px' }}>🌱 Грядки ({farm.plots.length})</h3>
          {farm.plots.length === 0 ? (
            <div className="fm-card" style={{ color: 'var(--text-muted)', fontSize: 13 }}>Пусто.</div>
          ) : (
            <div className="fm-grid" style={{ marginBottom: 12 }}>
              {farm.plots.map((pl, i) => (
                <div key={i} className="fm-card" style={{ fontSize: 13 }}>
                  <strong>{pl.plant_emoji || '🌱'} {pl.plant_name || '—'}</strong>
                  <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>
                    {PLOT_STATUS_LABEL[pl.status] || '—'} · {pl.accumulated}/{pl.required} ❆
                  </div>
                </div>
              ))}
            </div>
          )}

          <h3 style={{ margin: '0 0 8px' }}>🏭 Производства ({farm.productions.length})</h3>
          {farm.productions.length === 0 ? (
            <div className="fm-card" style={{ color: 'var(--text-muted)', fontSize: 13 }}>Пусто.</div>
          ) : (
            <div className="fm-grid" style={{ marginBottom: 12 }}>
              {farm.productions.map((pr, i) => (
                <div key={i} className="fm-card" style={{ fontSize: 13 }}>
                  <strong>{pr.name}</strong>
                  <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>
                    {PROD_STATUS_LABEL[pr.status] || '—'} · {pr.accumulated}/{pr.required} ❆
                  </div>
                </div>
              ))}
            </div>
          )}

          <h3 style={{ margin: '0 0 8px' }}>📦 Склад</h3>
          <div className="fm-card" style={{ marginBottom: 12, fontSize: 13 }}>
            {farm.plants.length === 0 && farm.products.length === 0 && farm.ingredients.length === 0 ? (
              <div style={{ color: 'var(--text-muted)' }}>Пусто.</div>
            ) : (
              <>
                {farm.plants.length > 0 && (
                  <div style={{ marginBottom: 6 }}>
                    <strong style={{ display: 'block', marginBottom: 4 }}>Растения</strong>
                    <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                      {farm.plants.map((p, i) => <span key={i} className="fm-chip">{p.emoji || '🌿'} {p.name} ×{p.qty}</span>)}
                    </div>
                  </div>
                )}
                {farm.products.length > 0 && (
                  <div style={{ marginBottom: 6 }}>
                    <strong style={{ display: 'block', marginBottom: 4 }}>Товары</strong>
                    <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                      {farm.products.map((p, i) => <span key={i} className="fm-chip">{p.emoji || '📦'} {p.name} ×{p.qty}</span>)}
                    </div>
                  </div>
                )}
                {farm.ingredients.length > 0 && (
                  <div>
                    <strong style={{ display: 'block', marginBottom: 4 }}>Ингредиенты</strong>
                    <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                      {farm.ingredients.map((p, i) => <span key={i} className="fm-chip">🍃 {p.name} ×{p.qty}</span>)}
                    </div>
                  </div>
                )}
              </>
            )}
          </div>

          <h3 style={{ margin: '0 0 8px' }}>🐾 Питомцы ({farm.pets.length})</h3>
          {farm.pets.length === 0 ? (
            <div className="fm-card" style={{ color: 'var(--text-muted)', fontSize: 13 }}>Пусто.</div>
          ) : (
            <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
              {farm.pets.map((pt, i) => <span key={i} className="fm-chip">{pt.emoji || '🐾'} {pt.name}</span>)}
            </div>
          )}
        </div>
      )}

      {viewField && (
        <div style={{ position: 'fixed', inset: 0, zIndex: 100, background: '#1a1a2e', display: 'flex', flexDirection: 'column' }}>
          <div style={{ padding: '10px var(--shell-pad)', display: 'flex', alignItems: 'center', gap: 10, background: 'rgba(0,0,0,0.4)', flexShrink: 0 }}>
            <button type="button" className="fm-btn fm-btn-sm fm-btn-outline" onClick={() => setViewField(null)} style={{ color: '#fff', borderColor: '#fff' }}>← Назад</button>
            <span style={{ color: '#ccc', fontSize: 14 }}>👁 {viewField.name} · {viewField.cols}×{viewField.rows} — только просмотр</span>
          </div>
          <div style={{ flex: 1, position: 'relative', overflow: 'auto' }}>
            <FieldGridView field={viewField} />
          </div>
        </div>
      )}

      {giftTarget && (
        <div style={{ position: 'fixed', inset: 0, zIndex: 80, background: 'rgba(0,0,0,0.65)', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 16 }} onClick={() => setGiftTarget(null)}>
          <div className="fm-card fm-rise" style={{ maxWidth: 420, width: '100%' }} onClick={(e) => e.stopPropagation()}>
            <h3 style={{ margin: '0 0 4px' }}>🎁 Подарок для {giftTarget.display_name}</h3>
            <p style={{ fontSize: 12, color: 'var(--text-muted)', margin: '0 0 10px' }}>Предмет спишется с вашего склада сразу и появится у игрока в чате.</p>
            <label style={{ display: 'block', fontSize: 13, marginBottom: 2 }}>Тип</label>
            <select className="fm-input" value={giftKind} onChange={(e) => { setGiftKind(e.target.value as 'plant' | 'product' | 'ingredient'); setGiftItemId(''); }}>
              {(['plant', 'product', 'ingredient'] as const).map((k) => <option key={k} value={k}>{GIFT_KIND_LABEL[k]}</option>)}
            </select>
            <label style={{ display: 'block', fontSize: 13, margin: '8px 0 2px' }}>Предмет</label>
            <select className="fm-input" value={giftItemId} onChange={(e) => setGiftItemId(e.target.value)}>
              <option value="">— выберите —</option>
              {giftItems.filter((i) => i.kind === giftKind).map((i) => (
                <option key={`${i.kind}-${i.item_id}`} value={String(i.item_id)}>{i.emoji || ''} {i.name} ({i.qty})</option>
              ))}
            </select>
            {giftItems.filter((i) => i.kind === giftKind).length === 0 && (
              <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 4 }}>У вас нет таких предметов на складе.</div>
            )}
            <label style={{ display: 'block', fontSize: 13, margin: '8px 0 2px' }}>Количество</label>
            <input className="fm-input" type="number" min={1} value={giftQty} onChange={(e) => setGiftQty(e.target.value)} />
            <div style={{ display: 'flex', gap: 8, marginTop: 12, flexWrap: 'wrap' }}>
              <button className="fm-btn fm-btn-sm fm-btn-outline" style={{ flex: 1 }} disabled={busy} onClick={() => setGiftTarget(null)}>Отмена</button>
              <button className="fm-btn fm-btn-sm" style={{ flex: 1 }} disabled={busy || !giftItemId} onClick={sendGift}>🎁 Отправить</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
