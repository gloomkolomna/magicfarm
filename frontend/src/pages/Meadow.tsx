import { useCallback, useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { api, type Meadow, type MeadowCell } from '../api/endpoints';
import LocationMap from '../components/LocationMap';
import Toast from '../components/Toast';

export default function MeadowPage() {
  const { id } = useParams<{ id: string }>();
  const nav = useNavigate();
  const [meadow, setMeadow] = useState<Meadow | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  const fieldId = Number(id);

  const load = useCallback(() => {
    if (!Number.isFinite(fieldId)) return;
    setLoading(true);
    api.meadow(fieldId)
      .then(setMeadow)
      .catch((e) => setMsg('✗ ' + (e?.response?.data?.detail || 'Ошибка')))
      .finally(() => setLoading(false));
  }, [fieldId]);

  useEffect(() => { load(); }, [load]);
  useEffect(() => {
    if (!msg) return;
    const t = setTimeout(() => setMsg(null), 4000);
    return () => clearTimeout(t);
  }, [msg]);

  async function doGather(cell: MeadowCell) {
    if (busy) return;
    setBusy(true);
    setMsg(null);
    try {
      const res = await api.gatherCell(cell.id);
      setMsg(`✓ Собрано: ${res.ingredient.name} (на складе ×${res.apothecary_qty})`);
      await load();
    } catch (e: any) {
      setMsg('✗ ' + (e?.response?.data?.detail || 'Ошибка'));
    } finally {
      setBusy(false);
    }
  }

  if (loading && !meadow) {
    return (
      <div style={{ maxWidth: 'var(--shell-max-width)', margin: '0 auto', padding: 'var(--shell-pad)' }}>
        <div className="fm-card">Загрузка поляны…</div>
      </div>
    );
  }

  const cellByPos = new Map<string, MeadowCell>();
  (meadow?.cells ?? []).forEach((c) => cellByPos.set(`${c.col},${c.row}`, c));

  return (
    <>
      <LocationMap mapUrl={meadow?.map_url ?? null} name={meadow?.name ?? ''} emoji="🌿" onBack={() => nav('/fields')}>
        {meadow && (
          <div
            style={{
              position: 'absolute', inset: 0, display: 'grid',
              gridTemplateColumns: `repeat(${meadow.cols}, 1fr)`,
              gridTemplateRows: `repeat(${meadow.rows}, 1fr)`,
            }}
          >
            {Array.from({ length: meadow.rows }).map((_, r) =>
              Array.from({ length: meadow.cols }).map((__, c) => {
                const cell = cellByPos.get(`${c},${r}`);
                if (!cell) return <div key={`empty-${c}-${r}`} />;
                const clickable = cell.available;
                const bg = cell.available
                  ? 'rgba(120,220,110,0.35)'
                  : cell.collected_today
                    ? 'rgba(120,140,110,0.28)'
                    : 'rgba(110,120,140,0.30)';
                return (
                  <div
                    key={`cell-${c}-${r}`}
                    onClick={() => { if (clickable) doGather(cell); }}
                    style={{
                      borderRight: c < meadow.cols - 1 ? '1px solid #2a1a0e' : 'none',
                      borderBottom: r < meadow.rows - 1 ? '1px solid #2a1a0e' : 'none',
                      boxShadow: 'inset 0 0 0 0.5px rgba(255,255,255,0.05)',
                      background: bg,
                      cursor: clickable ? 'pointer' : 'default',
                      touchAction: clickable ? 'manipulation' : 'auto',
                      display: 'flex', alignItems: 'center', justifyContent: 'center',
                      fontSize: 'clamp(18px, 6vw, 46px)', lineHeight: 1,
                    }}
                  >
                    {cell.collected_today ? '🌱' : cell.available ? '🌿' : '💤'}
                  </div>
                );
              }),
            )}
          </div>
        )}
      </LocationMap>

      {meadow && (
        <div style={{ position: 'fixed', left: 12, bottom: 'calc(16px + var(--vk-inset-bottom, 0px))', zIndex: 25, background: 'rgba(20,25,20,0.78)', color: '#f3ead0', border: '1px solid rgba(255,255,255,0.25)', borderRadius: 8, padding: '6px 10px', fontSize: 12, backdropFilter: 'blur(6px)' }}>
          🕒 {new Date(meadow.now_msk).toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' })} МСК · сброс в 00:00
        </div>
      )}

      {msg && <Toast text={msg} onClose={() => setMsg(null)} />}
    </>
  );
}
