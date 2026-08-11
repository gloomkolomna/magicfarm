import { useEffect, useState } from 'react';
import { api, type InventoryItem } from '../api/endpoints';

export default function InventoryPage() {
  const [items, setItems] = useState<InventoryItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [msg, setMsg] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const [sellItem, setSellItem] = useState<InventoryItem | null>(null);
  const [sellQty, setSellQty] = useState('');
  const [sellResult, setSellResult] = useState<number | null>(null);

  useEffect(() => {
    api.inventory()
      .then(setItems)
      .catch((e) => setMsg('✗ ' + (e?.response?.data?.detail || 'Ошибка')))
      .finally(() => setLoading(false));
  }, []);

  async function doSell() {
    if (!sellItem || !sellQty) return;
    setBusy(true);
    setSellResult(null);
    try {
      const res = await api.sellSurplus(sellItem.item_kind, sellItem.item_id, Number(sellQty));
      setSellResult(res.coins_earned);
      const updated = await api.inventory();
      setItems(updated);
    } catch (e: any) {
      setMsg('✗ ' + (e?.response?.data?.detail || 'Ошибка'));
    } finally {
      setBusy(false);
    }
  }

  function closeSell() {
    setSellItem(null);
    setSellQty('');
    setSellResult(null);
  }

  return (
    <div style={{ maxWidth: 'var(--shell-max-width)', margin: '0 auto', padding: 'var(--shell-pad)' }}>
      {msg && <div className="fm-card" style={{ marginBottom: 10, fontSize: 14 }}>{msg}</div>}

      {loading ? (
        <div className="fm-card">Загрузка…</div>
      ) : items.length === 0 ? (
        <div className="fm-card" style={{ color: 'var(--text-muted)' }}>
          Склад пуст. Производите товары в шатрах на полях.
        </div>
      ) : (
        <div className="fm-grid">
          {items.map((i) => (
            <div key={`${i.item_kind}-${i.item_id}`} className="fm-card fm-rise">
              <strong>{i.item_emoji} {i.item_name}</strong>
              <div className="fm-chip" style={{ marginTop: 6 }}>×{i.qty}</div>
              <button
                className="fm-btn fm-btn-xs fm-btn-outline"
                style={{ marginTop: 8, width: '100%' }}
                disabled={busy}
                onClick={() => { setSellItem(i); setSellQty('1'); setSellResult(null); }}
              >
                💰 Продать излишки
              </button>
            </div>
          ))}
        </div>
      )}

      {sellItem && (
        <div onClick={closeSell} style={{ position: 'fixed', inset: 0, zIndex: 60, background: 'rgba(0,0,0,0.6)', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 16 }}>
          <div className="fm-card fm-rise" onClick={(e) => e.stopPropagation()} style={{ width: '100%', maxWidth: 'calc(var(--shell-max-width) * 0.633)' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
              <h2 style={{ margin: 0 }}>💰 Продать излишки</h2>
              <button className="fm-btn fm-btn-xs fm-btn-outline" onClick={closeSell}>✕</button>
            </div>
            <p style={{ fontSize: 14, marginBottom: 10 }}>
              {sellItem.item_emoji} {sellItem.item_name} — на складе: <strong>×{sellItem.qty}</strong>
            </p>
            {sellResult !== null ? (
              <div className="fm-card" style={{ background: 'rgba(127,255,127,0.12)', fontSize: 14, marginBottom: 10 }}>
                ✓ Продано! Получено монет: <strong>{sellResult}</strong>
              </div>
            ) : (
              <>
                <label style={{ display: 'block', marginBottom: 6, fontSize: 14 }}>Количество</label>
                <input
                  className="fm-input"
                  type="number"
                  min={1}
                  max={sellItem.qty}
                  value={sellQty}
                  onChange={(e) => setSellQty(e.target.value)}
                />
                <button
                  className="fm-btn"
                  style={{ width: '100%', marginTop: 12 }}
                  disabled={busy || !sellQty || Number(sellQty) < 1 || Number(sellQty) > sellItem.qty}
                  onClick={doSell}
                >
                  Продать
                </button>
              </>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
