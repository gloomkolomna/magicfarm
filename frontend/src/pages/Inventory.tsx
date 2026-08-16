import { useEffect, useState } from 'react';
import { api, type InventoryItem } from '../api/endpoints';
import { mediaUrl } from '../api/media';
import Toast from '../components/Toast';

export default function InventoryPage() {
  const [items, setItems] = useState<InventoryItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [msg, setMsg] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const [section, setSection] = useState<string>('all');

  const [sellItem, setSellItem] = useState<InventoryItem | null>(null);
  const [sellQty, setSellQty] = useState('');
  const [sellResult, setSellResult] = useState<number | null>(null);

  const SECTIONS = [
    { key: 'all', label: 'Всё' },
    { key: 'plant', label: '🌱 Растения' },
    { key: 'product', label: '📦 Товары' },
    { key: 'potion', label: '🧪 Зелья' },
    { key: 'production', label: '🏭 Продукция' },
  ];

  useEffect(() => {
    api.inventory()
      .then(setItems)
      .catch((e) => setMsg('✗ ' + (e?.response?.data?.detail || 'Ошибка')))
      .finally(() => setLoading(false));
  }, []);

  const filtered = section === 'all' ? items : items.filter((i) => i.item_kind === section);

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
      {msg && <Toast text={msg} onClose={() => setMsg(null)} />}

      {loading ? (
        <div className="fm-card">Загрузка…</div>
      ) : items.length === 0 ? (
        <div className="fm-card" style={{ color: 'var(--text-muted)' }}>
          Склад пуст. Производите товары в шатрах на полях.
        </div>
      ) : (
        <>
          <div style={{ display: 'flex', gap: 4, marginBottom: 12, flexWrap: 'wrap' }}>
            {SECTIONS.map((s) => (
              <button
                key={s.key}
                className={section === s.key ? 'fm-btn fm-btn-sm' : 'fm-btn fm-btn-sm fm-btn-outline'}
                onClick={() => setSection(s.key)}
              >
                {s.label}
              </button>
            ))}
          </div>
          {filtered.length === 0 ? (
            <div className="fm-card" style={{ color: 'var(--text-muted)' }}>Нет предметов в этой секции.</div>
          ) : (
            <div className="fm-grid">
              {filtered.map((i) => (
                <div key={`${i.item_kind}-${i.item_id}`} className="fm-card fm-rise">
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <strong>
                        {i.item_emoji} {i.item_name}
                        {i.ingredient_icon && <span style={{ marginLeft: 6, fontSize: 14 }} title={i.ingredient_type || ''}>{i.ingredient_icon}</span>}
                      </strong>
                      <div className="fm-chip" style={{ marginTop: 4 }}>×{i.qty}</div>
                    </div>
                    {i.item_image && (
                      <img src={mediaUrl(i.item_image)} alt="" style={{ width: 64, height: 64, objectFit: 'cover', borderRadius: 8, marginLeft: 8 }} />
                    )}
                  </div>
                  <button
                    className="fm-btn fm-btn-xs fm-btn-outline"
                    style={{ marginTop: 10, width: '100%' }}
                    disabled={busy}
                    onClick={() => { setSellItem(i); setSellQty('1'); setSellResult(null); }}
                  >
                    💰 Продать излишки
                  </button>
                </div>
              ))}
            </div>
          )}
        </>
      )}

      {sellItem && (
        <div style={{ position: 'fixed', inset: 0, zIndex: 60, background: 'rgba(0,0,0,0.6)', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 16 }}>
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
