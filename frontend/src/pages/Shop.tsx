import { useCallback, useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { api, type ApothecaryItem, type BarterResult, type Shop, type ShopCell } from '../api/endpoints';
import InfirmaryBackground from '../components/InfirmaryBackground';
import LocationMap from '../components/LocationMap';
import ItemPicker from '../components/ItemPicker';
import Toast from '../components/Toast';

export default function ShopPage() {
  const { id } = useParams<{ id: string }>();
  const nav = useNavigate();
  const [shop, setShop] = useState<Shop | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  const [cell, setCell] = useState<ShopCell | null>(null);
  const [wantId, setWantId] = useState<number | ''>('');
  const [giveSel, setGiveSel] = useState<string>('');
  const [qty, setQty] = useState('1');
  const [result, setResult] = useState<BarterResult | null>(null);

  const fieldId = Number(id);

  const load = useCallback(() => {
    if (!Number.isFinite(fieldId)) return;
    setLoading(true);
    api.shop(fieldId)
      .then(setShop)
      .catch((e) => setMsg('✗ ' + (e?.response?.data?.detail || 'Ошибка')))
      .finally(() => setLoading(false));
  }, [fieldId]);

  useEffect(() => { load(); }, [load]);
  useEffect(() => {
    if (!msg) return;
    const t = setTimeout(() => setMsg(null), 4000);
    return () => clearTimeout(t);
  }, [msg]);

  const giveOptions: { kind: string; id: number; name: string; emoji: string | null; image: string | null; qty: number }[] = [
    ...(shop?.apothecary ?? []).map((a) => ({ kind: 'ingredient', id: a.ingredient_id, name: a.name, emoji: null, image: a.image_url, qty: a.qty })),
    ...(shop?.inventory ?? []).map((i) => ({ kind: i.item_kind, id: i.item_id, name: i.item_name, emoji: i.item_emoji, image: i.item_image, qty: i.qty })),
  ];

  const selectedGive = giveOptions.find((o) => `${o.kind}:${o.id}` === giveSel);
  const giveQty = selectedGive?.qty ?? 0;

  function openCell(c: ShopCell) {
    setCell(c);
    setWantId(c.ingredients[0]?.id ?? '');
    setGiveSel('');
    setQty('1');
    setResult(null);
  }

  async function doBarter() {
    if (!cell || wantId === '' || !selectedGive) return;
    const q = Number(qty);
    if (!q || q < 1) { setMsg('✗ Укажите количество'); return; }
    if (selectedGive.qty < q) { setMsg('✗ Недостаточно предмета на складе'); return; }
    setBusy(true);
    setMsg(null);
    try {
      const res = await api.barterCell(cell.id, wantId, selectedGive.kind, selectedGive.id, q);
      setResult(res);
      const sh = await api.shop(fieldId);
      setShop(sh);
    } catch (e: any) {
      setMsg('✗ ' + (e?.response?.data?.detail || 'Ошибка'));
    } finally {
      setBusy(false);
    }
  }

  if (loading && !shop) {
    return (
      <div style={{ maxWidth: 'var(--shell-max-width)', margin: '0 auto', padding: 'var(--shell-pad)' }}>
        <div className="fm-card">Загрузка лавки…</div>
      </div>
    );
  }

  const cellByPos = new Map<string, ShopCell>();
  (shop?.cells ?? []).forEach((c) => cellByPos.set(`${c.col},${c.row}`, c));

  return (
    <>
      <InfirmaryBackground />
      <LocationMap mapUrl={shop?.map_url ?? null} name={shop?.name ?? ''} emoji="🛒" onBack={() => nav('/infirmary')}>
        {shop && (
          <div
            style={{
              position: 'absolute', inset: 0, display: 'grid',
              gridTemplateColumns: `repeat(${shop.cols}, 1fr)`,
              gridTemplateRows: `repeat(${shop.rows}, 1fr)`,
            }}
          >
            {Array.from({ length: shop.rows }).map((_, r) =>
              Array.from({ length: shop.cols }).map((__, c) => {
                const cell = cellByPos.get(`${c},${r}`);
                if (!cell) return <div key={`empty-${c}-${r}`} />;
                return (
                  <div
                    key={`cell-${c}-${r}`}
                    onClick={() => openCell(cell)}
                    style={{
                      borderRight: c < shop.cols - 1 ? '1px solid #2a1a0e' : 'none',
                      borderBottom: r < shop.rows - 1 ? '1px solid #2a1a0e' : 'none',
                      boxShadow: 'inset 0 0 0 0.5px rgba(255,255,255,0.05)',
                      background: 'rgba(110,170,220,0.30)',
                      cursor: 'pointer', touchAction: 'manipulation',
                      display: 'flex', alignItems: 'center', justifyContent: 'center',
                      fontSize: 'clamp(18px, 6vw, 46px)', lineHeight: 1,
                    }}
                  >
                    🛒
                  </div>
                );
              }),
            )}
          </div>
        )}
      </LocationMap>

      {msg && <Toast text={msg} onClose={() => setMsg(null)} />}

      {cell && (
        <div style={{ position: 'fixed', inset: 0, zIndex: 60, background: 'rgba(0,0,0,0.6)', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 16 }}>
          <div className="fm-card fm-rise" onClick={(e) => e.stopPropagation()} style={{ width: '100%', maxWidth: 'calc(var(--shell-max-width) * 0.633)' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
              <h2 style={{ margin: 0 }}>🛒 Бартер</h2>
              <button className="fm-btn fm-btn-xs fm-btn-outline" onClick={() => setCell(null)}>✕</button>
            </div>
            {result ? (
              <div className="fm-card" style={{ background: 'rgba(127,255,127,0.12)', fontSize: 14, marginBottom: 10 }}>
                ✓ Обмен прошёл: <strong>+{result.qty} {result.want.name}</strong> (отдали {result.qty} {result.give.name}).
              </div>
            ) : (
              <>
                <label style={{ display: 'block', marginBottom: 6, fontSize: 14 }}>Что берём (из лавки)</label>
                <ItemPicker
                  items={cell.ingredients.map((i) => ({ key: String(i.id), title: i.name, image: i.image_url, emoji: '⚗️' }))}
                  value={wantId === '' ? null : String(wantId)}
                  onChange={(k) => setWantId(Number(k))}
                />
                <label style={{ display: 'block', margin: '12px 0 6px', fontSize: 14 }}>Что отдаём (со склада)</label>
                {giveOptions.length === 0 ? (
                  <div className="fm-card" style={{ color: 'var(--text-muted)', fontSize: 13 }}>На складе нет предметов для обмена.</div>
                ) : (
                  <ItemPicker
                    items={giveOptions.map((o) => ({ key: `${o.kind}:${o.id}`, title: o.name, image: o.image, emoji: o.emoji ?? (o.kind === 'ingredient' ? '⚗️' : '📦'), badge: `×${o.qty}` }))}
                    value={giveSel || null}
                    onChange={setGiveSel}
                  />
                )}
                <label style={{ display: 'block', margin: '12px 0 6px', fontSize: 14 }}>Количество</label>
                <input
                  className="fm-input"
                  type="number"
                  min={1}
                  max={giveQty || 1}
                  value={qty}
                  onChange={(e) => setQty(e.target.value)}
                />
                <button
                  className="fm-btn"
                  style={{ width: '100%', marginTop: 12 }}
                  disabled={busy || wantId === '' || giveSel === '' || Number(qty) < 1}
                  onClick={doBarter}
                >
                  Обменять
                </button>
              </>
            )}
          </div>
        </div>
      )}
    </>
  );
}
