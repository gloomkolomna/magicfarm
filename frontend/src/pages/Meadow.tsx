import { useCallback, useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { api, type Meadow, type MeadowCell } from '../api/endpoints';
import LocationMap from '../components/LocationMap';
import Toast from '../components/Toast';

function fmtCountdown(targetIso: string | null, now: number): string {
  if (!targetIso) return '';
  const target = new Date(targetIso).getTime();
  const diff = target - now;
  if (diff <= 0) return '';
  const sec = Math.floor(diff / 1000);
  const h = Math.floor(sec / 3600);
  const m = Math.floor((sec % 3600) / 60);
  const s = sec % 60;
  if (h > 0) return `${h}ч ${m}м`;
  if (m > 0) return `${m}м ${s}с`;
  return `${s}с`;
}

export default function MeadowPage() {
  const { id } = useParams<{ id: string }>();
  const nav = useNavigate();
  const [meadow, setMeadow] = useState<Meadow | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const [nowTs, setNowTs] = useState(() => Date.now());

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
    const t = setInterval(() => setNowTs(Date.now()), 1000);
    return () => clearInterval(t);
  }, []);
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
      <LocationMap mapUrl={meadow?.map_url ?? null} name={meadow?.name ?? ''} emoji="🌿" onBack={() => nav('/infirmary')}>
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
                const emoji = cell.collected_today ? '🌱' : cell.available ? '🌿' : '💤';
                const left = fmtCountdown(cell.countdown_to, nowTs);
                const countdown = left
                  ? (cell.available ? `⏳ ${left}` : cell.collected_today ? `🔁 ${left}` : `⏰ ${left}`)
                  : '';
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
                      display: 'flex', flexDirection: 'column', gap: 1,
                      alignItems: 'center', justifyContent: 'center',
                    }}
                  >
                    <span style={{ fontSize: 'clamp(16px, 5vw, 38px)', lineHeight: 1 }}>{emoji}</span>
                    {countdown && (
                      <span style={{ fontSize: 'clamp(9px, 2.2vw, 12px)', fontWeight: 600, color: '#fff', textShadow: '0 1px 2px #000', lineHeight: 1.1 }}>
                        {countdown}
                      </span>
                    )}
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
