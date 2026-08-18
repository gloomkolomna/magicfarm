import { useCallback, useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { api, type Meadow } from '../api/endpoints';
import { mediaUrl } from '../api/media';
import Toast from '../components/Toast';

const WINDOW_LABEL: Record<string, string> = {
  morning: '🌅 Утро',
  day: '☀️ День',
  night: '🌙 Ночь',
  always: '♾️ Всегда',
};

const WINDOW_RANGE: Record<string, string> = {
  morning: '04:00–10:00',
  day: '12:00–15:00',
  night: '21:00–03:00',
  always: 'всегда',
};

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

  async function doGather(cellId: number) {
    setBusy(true);
    setMsg(null);
    try {
      const res = await api.gatherCell(cellId);
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

  return (
    <div style={{ maxWidth: 'var(--shell-max-width)', margin: '0 auto', padding: 'var(--shell-pad)' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 10 }}>
        <button className="fm-btn fm-btn-outline fm-btn-xs" onClick={() => nav(-1)}>← Назад</button>
        <h1 style={{ margin: 0, fontSize: 20, flex: 1 }}>🌿 {meadow?.name}</h1>
      </div>
      {msg && <Toast text={msg} onClose={() => setMsg(null)} />}
      {meadow && (
        <div className="fm-card" style={{ marginBottom: 10, fontSize: 13, color: 'var(--text-secondary)' }}>
          Сейчас в лесу: <strong>{new Date(meadow.now_msk).toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' })} МСК</strong>.
          {' '}Каждая клетка даёт ресурс бесплатно, но только раз в сутки (сброс в 00:00 МСК).
        </div>
      )}
      <div style={{ overflow: 'auto', marginBottom: 12, border: '1px solid var(--border)', borderRadius: 'var(--radius-sm)', background: '#0c1508' }}>
        {meadow && (
          <svg width={meadow.cols * 80} height={meadow.rows * 80} style={{ display: 'block' }}>
            {meadow.map_url && (
              <image href={mediaUrl(meadow.map_url)} x={0} y={0} width={meadow.cols * 80} height={meadow.rows * 80} preserveAspectRatio="none" />
            )}
            {meadow.cells.map((c) => {
              const color = c.available
                ? 'rgba(120,220,110,0.35)'
                : c.collected_today
                ? 'rgba(120,140,110,0.28)'
                : 'rgba(110,120,140,0.30)';
              return (
                <g key={c.id}>
                  <rect x={c.col * 80} y={c.row * 80} width={80} height={80} fill={color} stroke="#2a1a0e" strokeWidth={1} />
                  <text
                    x={c.col * 80 + 40}
                    y={c.row * 80 + 44}
                    fontSize={28}
                    fill="#fff"
                    textAnchor="middle"
                    style={{ pointerEvents: 'none', textShadow: '0 1px 2px #000' }}
                  >
                    {c.collected_today ? '🌱' : '🌿'}
                  </text>
                </g>
              );
            })}
          </svg>
        )}
      </div>
      <div className="fm-grid">
        {meadow?.cells.map((c) => (
          <div key={c.id} className="fm-card fm-rise" style={{ textAlign: 'center' }}>
            <strong style={{ display: 'block', marginBottom: 4 }}>
              {WINDOW_LABEL[c.window] || c.window}
            </strong>
            <div style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 6 }}>
              {WINDOW_RANGE[c.window] || ''}
              {c.next_open_at && (
                <div>вернитесь в {new Date(c.next_open_at).toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' })}</div>
              )}
            </div>
            <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginBottom: 8 }}>
              {c.ingredients.map((i) => i.name).join(', ') || '—'}
            </div>
            {c.available ? (
              <button className="fm-btn fm-btn-sm" style={{ width: '100%' }} disabled={busy} onClick={() => doGather(c.id)}>
                🌿 Собрать
              </button>
            ) : (
              <div className="fm-btn fm-btn-sm fm-btn-outline" style={{ width: '100%', opacity: 0.7, pointerEvents: 'none' }}>
                {c.collected_today ? '✓ Собрано сегодня' : '💤 Клетка спит'}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
