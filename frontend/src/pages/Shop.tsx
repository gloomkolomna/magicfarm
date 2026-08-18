import { useCallback, useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { api, type ApothecaryItem, type BarterResult, type Shop, type ShopCell } from '../api/endpoints';
import { mediaUrl } from '../api/media';
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
  const [giveId, setGiveId] = useState<number | ''>('');
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

  const giveQty = (ingId: number | ''): number => {
    if (ingId === '') return 0;
    return shop?.apothecary.find((a) => a.ingredient_id === ingId)?.qty ?? 0;
  };

  function openCell(c: ShopCell) {
    setCell(c);
    setWantId(c.ingredients[0]?.id ?? '');
    setGiveId('');
    setQty('1');
    setResult(null);
  }

  async function doBarter() {
    if (!cell || wantId === '' || giveId === '') return;
    const q = Number(qty);
    if (!q || q < 1) { setMsg('✗ Укажите количество'); return; }
    if (giveQty(giveId) < q) { setMsg('✗ Недостаточно на аптекарском складе'); return; }
    setBusy(true);
    setMsg(null);
    try {
      const res = await api.barterCell(cell.id, wantId, giveId, q);
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

  return (
    <div style={{ maxWidth: 'var(--shell-max-width)', margin: '0 auto', padding: 'var(--shell-pad)' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 10 }}>
        <button className="fm-btn fm-btn-outline fm-btn-xs" onClick={() => nav(-1)}>← Назад</button>
        <h1 style={{ margin: 0, fontSize: 20, flex: 1 }}>🛒 {shop?.name}</h1>
      </div>
      {msg && <Toast text={msg} onClose={() => setMsg(null)} />}
      {shop && (
        <div className="fm-card" style={{ marginBottom: 10, fontSize: 13, color: 'var(--text-secondary)' }}>
          Обмен 1:1 без ограничений — отдавайте ингредиенты с аптекарского склада и получайте нужные.
        </div>
      )}
      <div style={{ overflow: 'auto', marginBottom: 12, border: '1px solid var(--border)', borderRadius: 'var(--radius-sm)', background: '#0c1508' }}>
        {shop && (
          <svg width={shop.cols * 80} height={shop.rows * 80} style={{ display: 'block' }}>
            {shop.map_url && (
              <image href={mediaUrl(shop.map_url)} x={0} y={0} width={shop.cols * 80} height={shop.rows * 80} preserveAspectRatio="none" />
            )}
            {shop.cells.map((c) => (
              <g key={c.id}>
                <rect x={c.col * 80} y={c.row * 80} width={80} height={80} fill="rgba(110,170,220,0.30)" stroke="#2a1a0e" strokeWidth={1} />
                <text x={c.col * 80 + 40} y={c.row * 80 + 44} fontSize={28} fill="#fff" textAnchor="middle" style={{ pointerEvents: 'none', textShadow: '0 1px 2px #000' }}>
                  🛒
                </text>
              </g>
            ))}
          </svg>
        )}
      </div>
      <div className="fm-grid">
        {shop?.cells.map((c) => (
          <button key={c.id} className="fm-card fm-rise" style={{ cursor: 'pointer', textAlign: 'center', display: 'block' }} onClick={() => openCell(c)}>
            <strong style={{ display: 'block', marginBottom: 6 }}>🛒 Клетка [{c.col},{c.row}]</strong>
            <div style={{ fontSize: 13, color: 'var(--text-secondary)' }}>
              {c.ingredients.map((i) => i.name).join(', ') || '—'}
            </div>
          </button>
        ))}
        {(shop?.cells.length ?? 0) === 0 && (
          <div className="fm-card" style={{ color: 'var(--text-muted)' }}>Лавка пока не завезла товар. Загляните позже.</div>
        )}
      </div>

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
                <select className="fm-input" value={wantId} onChange={(e) => setWantId(Number(e.target.value))}>
                  {cell.ingredients.map((i) => (
                    <option key={i.id} value={i.id}>{i.name}</option>
                  ))}
                </select>
                <label style={{ display: 'block', margin: '12px 0 6px', fontSize: 14 }}>Что отдаём (из аптекарского склада)</label>
                <select className="fm-input" value={giveId} onChange={(e) => setGiveId(Number(e.target.value))}>
                  <option value="">— выберите —</option>
                  {(shop?.apothecary ?? []).map((a: ApothecaryItem) => (
                    <option key={a.ingredient_id} value={a.ingredient_id}>
                      {a.name} (×{a.qty})
                    </option>
                  ))}
                </select>
                <label style={{ display: 'block', margin: '12px 0 6px', fontSize: 14 }}>Количество</label>
                <input
                  className="fm-input"
                  type="number"
                  min={1}
                  max={giveQty(giveId) || 1}
                  value={qty}
                  onChange={(e) => setQty(e.target.value)}
                />
                <button
                  className="fm-btn"
                  style={{ width: '100%', marginTop: 12 }}
                  disabled={busy || wantId === '' || giveId === '' || Number(qty) < 1}
                  onClick={doBarter}
                >
                  Обменять
                </button>
              </>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
