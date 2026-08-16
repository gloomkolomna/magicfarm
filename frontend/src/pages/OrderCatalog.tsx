import { useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useSession } from '../context/SessionContext';
import { api, type Order } from '../api/endpoints';
import { mediaUrl } from '../api/media';
import Toast from '../components/Toast';

type SortKey = 'product_name' | 'qty' | 'reward_coins' | 'customer' | 'name' | 'created_at';

const COLUMNS: { key: SortKey; label: string; align?: 'right' }[] = [
  { key: 'product_name', label: 'Товар' },
  { key: 'qty', label: 'Кол-во', align: 'right' },
  { key: 'reward_coins', label: '🪙 Награда', align: 'right' },
  { key: 'customer', label: 'Заказчик' },
  { key: 'name', label: 'Название' },
  { key: 'created_at', label: 'Дата' },
];

function fmtDate(s: string | null): string {
  if (!s) return '—';
  const d = new Date(s);
  if (Number.isNaN(d.getTime())) return '—';
  return d.toLocaleDateString('ru-RU', { day: '2-digit', month: '2-digit', year: '2-digit' });
}

function cellValue(o: Order, key: SortKey): string | number {
  if (key === 'product_name') return o.product_name.toLowerCase();
  if (key === 'customer') return (o.customer || '').toLowerCase();
  if (key === 'name') return (o.name || '').toLowerCase();
  if (key === 'created_at') return o.created_at || '';
  return o[key];
}

export default function OrderCatalogPage() {
  const { refresh, loading: sessionLoading } = useSession();
  const nav = useNavigate();
  const [orders, setOrders] = useState<Order[]>([]);
  const [loading, setLoading] = useState(true);
  const [busyId, setBusyId] = useState<number | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const [filter, setFilter] = useState('');
  const [sortKey, setSortKey] = useState<SortKey>('created_at');
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('desc');
  const [zoomImg, setZoomImg] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      setOrders(await api.availableOrders());
    } catch (e: any) {
      setMsg('✗ ' + (e?.response?.data?.detail || 'Ошибка загрузки'));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { if (!sessionLoading) load(); }, [load, sessionLoading]);

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
  }, [orders, filter, sortKey, sortDir]);

  function toggleSort(key: SortKey) {
    if (key === sortKey) {
      setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'));
    } else {
      setSortKey(key);
      setSortDir('asc');
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

      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
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

      {loading ? (
        <div className="fm-card">Загрузка заказов…</div>
      ) : rows.length === 0 ? (
        <div className="fm-card" style={{ color: 'var(--text-muted)' }}>
          {filter ? 'Ничего не найдено по фильтру.' : 'Свободных заказов пока нет. Загляните позже!'}
        </div>
      ) : (
        <div className="fm-card" style={{ overflowX: 'auto', padding: 0 }}>
          <table className="fm-table" style={{ width: '100%' }}>
            <thead>
              <tr>
                {COLUMNS.map((c) => (
                  <th
                    key={c.key}
                    style={{ cursor: 'pointer', userSelect: 'none', whiteSpace: 'nowrap', textAlign: c.align || 'left' }}
                    onClick={() => toggleSort(c.key)}
                  >
                    {c.label}{sortKey === c.key ? (sortDir === 'asc' ? ' ↑' : ' ↓') : ''}
                  </th>
                ))}
                <th></th>
              </tr>
            </thead>
            <tbody>
              {rows.map((o) => (
                <tr key={o.id}>
                  <td style={{ whiteSpace: 'nowrap' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                      {o.image_url && (
                        <img
                          src={mediaUrl(o.image_url)}
                          alt=""
                          style={{ width: 32, height: 32, objectFit: 'cover', borderRadius: 4, cursor: 'pointer', flexShrink: 0 }}
                          onClick={() => setZoomImg(mediaUrl(o.image_url!))}
                        />
                      )}
                      <span>{o.product_emoji} {o.product_name}</span>
                    </div>
                  </td>
                  <td style={{ textAlign: 'right' }}>×{o.qty}</td>
                  <td style={{ textAlign: 'right', whiteSpace: 'nowrap' }}>🪙 {o.reward_coins}</td>
                  <td>{o.customer || '—'}</td>
                  <td style={{ maxWidth: 160, overflow: 'hidden', textOverflow: 'ellipsis' }}>{o.name || '—'}</td>
                  <td style={{ whiteSpace: 'nowrap' }}>{fmtDate(o.created_at)}</td>
                  <td>
                    <button
                      className="fm-btn fm-btn-sm"
                      disabled={busyId !== null}
                      onClick={() => take(o.id)}
                    >
                      {busyId === o.id ? '…' : 'Взять'}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
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
