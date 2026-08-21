import { useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useSession } from '../context/SessionContext';
import { api, type Order, type UserPotion } from '../api/endpoints';
import { mediaUrl } from '../api/media';
import Toast from '../components/Toast';

type SortKey = 'availability' | 'product_name' | 'qty' | 'reward_coins' | 'customer';

const SORT_OPTIONS: { key: SortKey; label: string }[] = [
  { key: 'availability', label: '✅ Наличие' },
  { key: 'product_name', label: 'Товар' },
  { key: 'qty', label: 'Кол-во' },
  { key: 'reward_coins', label: '🪙 Награда' },
  { key: 'customer', label: 'Заказчик' },
];

export default function OrderCatalogPage() {
  const { refresh, loading: sessionLoading } = useSession();
  const nav = useNavigate();
  const [orders, setOrders] = useState<Order[]>([]);
  const [inventory, setInventory] = useState<Record<number, number>>({});
  const [potions, setPotions] = useState<UserPotion[]>([]);
  const [loading, setLoading] = useState(true);
  const [busyId, setBusyId] = useState<number | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const [filter, setFilter] = useState('');
  const [sortKey, setSortKey] = useState<SortKey>('availability');
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('desc');
  const [zoomImg, setZoomImg] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [ord, inv, pots] = await Promise.all([
        api.availableOrders(),
        api.inventory().catch(() => []),
        api.userPotions().catch(() => [] as UserPotion[]),
      ]);
      setOrders(ord);
      const invMap: Record<number, number> = {};
      for (const i of inv) {
        if (i.item_kind === 'product') invMap[i.item_id] = (invMap[i.item_id] || 0) + i.qty;
      }
      setInventory(invMap);
      setPotions(pots);
    } catch (e: any) {
      setMsg('✗ ' + (e?.response?.data?.detail || 'Ошибка загрузки'));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { if (!sessionLoading) load(); }, [load, sessionLoading]);

  function haveFor(o: Order): number {
    if (o.potion_recipe_id != null) {
      return potions.some((p) => p.potion_recipe_id === o.potion_recipe_id && !p.used) ? 1 : 0;
    }
    return inventory[o.product_id ?? -1] || 0;
  }

  function availabilityTier(o: Order): number {
    const have = haveFor(o);
    return have >= o.qty ? 2 : have > 0 ? 1 : 0;
  }

  function cellValue(o: Order, key: SortKey): string | number {
    if (key === 'availability') return availabilityTier(o);
    if (key === 'product_name') return o.product_name.toLowerCase();
    if (key === 'customer') return (o.customer || '').toLowerCase();
    return o[key];
  }

  const rows = useMemo(() => {
    const q = filter.trim().toLowerCase();
    const filtered = q
      ? orders.filter((o) =>
          o.product_name.toLowerCase().includes(q) ||
          (o.customer || '').toLowerCase().includes(q) ||
          (o.name || '').toLowerCase().includes(q))
      : orders;
    const sorted = [...filtered].sort((a, b) => {
      const va = cellValue(a, sortKey);
      const vb = cellValue(b, sortKey);
      if (va < vb) return sortDir === 'asc' ? -1 : 1;
      if (va > vb) return sortDir === 'asc' ? 1 : -1;
      return 0;
    });
    return sorted;
  }, [orders, filter, sortKey, sortDir, inventory, potions]);

  function toggleSort(key: SortKey) {
    if (key === sortKey) {
      setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'));
    } else {
      setSortKey(key);
      setSortDir(key === 'availability' ? 'desc' : 'asc');
    }
  }

  async function take(id: number) {
    setBusyId(id);
    setMsg(null);
    try {
      const o = await api.takeOrder(id);
      setMsg(`✓ Заказ взят: ${o.product_emoji || ''} ${o.product_name} ×${o.qty}`);
      await refresh();
      nav('/orders');
    } catch (e: any) {
      setMsg('✗ ' + (e?.response?.data?.detail || 'Ошибка'));
      setBusyId(null);
      await load();
    }
  }

  return (
    <div style={{ maxWidth: 'var(--shell-max-width)', margin: '0 auto', padding: 'var(--shell-pad)' }}>
      {msg && <Toast text={msg} onClose={() => setMsg(null)} />}

      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12, flexWrap: 'wrap' }}>
        <button className="fm-btn fm-btn-sm fm-btn-outline" onClick={() => nav('/orders')}>← Назад</button>
        <h2 style={{ margin: 0, fontSize: 18 }}>Каталог заказов</h2>
      </div>

      <input
        className="fm-input"
        style={{ marginBottom: 12 }}
        placeholder="🔍 Фильтр: товар, заказчик, название…"
        value={filter}
        onChange={(e) => setFilter(e.target.value)}
      />

      <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginBottom: 12 }}>
        {SORT_OPTIONS.map((c) => (
          <button
            key={c.key}
            className={sortKey === c.key ? 'fm-btn fm-btn-sm' : 'fm-btn fm-btn-sm fm-btn-outline'}
            onClick={() => toggleSort(c.key)}
          >
            {c.label}{sortKey === c.key ? (sortDir === 'asc' ? ' ↑' : ' ↓') : ''}
          </button>
        ))}
      </div>

      {loading ? (
        <div className="fm-card">Загрузка заказов…</div>
      ) : rows.length === 0 ? (
        <div className="fm-card" style={{ color: 'var(--text-muted)' }}>
          {filter ? 'Ничего не найдено по фильтру.' : 'Свободных заказов пока нет. Загляните позже!'}
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          {rows.map((o) => {
            const locked = o.available === false;
            const have = haveFor(o);
            const ok = have >= o.qty;
            const orderImg = o.image_url || o.product_image_url || o.potion_image_url;
            return (
              <div key={o.id} className="fm-card fm-rise" style={locked ? { opacity: 0.55 } : undefined}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap', marginBottom: 8 }}>
                  {orderImg ? (
                    <img
                      src={mediaUrl(orderImg)}
                      alt=""
                      style={{ height: 40, maxWidth: 64, width: 'auto', objectFit: 'contain', borderRadius: 6, flexShrink: 0, cursor: 'pointer' }}
                      onClick={() => setZoomImg(mediaUrl(orderImg!))}
                    />
                  ) : (
                    <span style={{ fontSize: 17, flexShrink: 0 }}>{o.product_emoji || '📦'}</span>
                  )}
                  <strong style={{ minWidth: 0, overflowWrap: 'anywhere' }}>{o.product_name}</strong>
                  <span className="fm-chip" style={{ fontSize: 12, flexShrink: 0 }}>×{o.qty}</span>
                  <span className="fm-chip" style={{ fontSize: 12, flexShrink: 0, color: 'var(--accent-warm)', fontWeight: 600 }}>🪙 {o.reward_coins}</span>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap', fontSize: 13 }}>
                  <span style={{ color: 'var(--text-secondary)', minWidth: 0, overflowWrap: 'anywhere' }}>
                    👤 {o.customer || '—'}
                  </span>
                  {have > 0 && (
                    <span className="fm-chip" style={{ fontSize: 12, color: ok ? 'var(--success)' : 'var(--text-secondary)', flexShrink: 0 }}>
                      {ok ? '✓' : ' част.'} {o.potion_recipe_id != null ? 'зелье готово' : `на складе: ${have}`}
                    </span>
                  )}
                  <span style={{ flex: 1 }} />
                  {locked ? (
                    <span style={{ fontSize: 12, color: 'var(--text-muted)' }} title={o.lock_reason || ''}>
                      🔒 {o.lock_reason || 'Недоступно'}
                    </span>
                  ) : (
                    <button
                      className="fm-btn fm-btn-sm"
                      disabled={busyId !== null}
                      onClick={() => take(o.id)}
                    >
                      {busyId === o.id ? '…' : 'Взять'}
                    </button>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}

      {zoomImg && (
        <div style={{ position: 'fixed', inset: 0, zIndex: 80, background: 'rgba(0,0,0,0.85)', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 16 }}>
          <button
            onClick={() => setZoomImg(null)}
            style={{ position: 'absolute', top: 16, right: 16, zIndex: 1, fontSize: 24, background: 'none', border: 'none', color: '#fff', cursor: 'pointer', padding: '8px 12px' }}
          >
            ✕
          </button>
          <img src={zoomImg} alt="" style={{ maxWidth: '90vw', maxHeight: '90vh', objectFit: 'contain' }} onClick={(e) => e.stopPropagation()} />
        </div>
      )}
    </div>
  );
}
