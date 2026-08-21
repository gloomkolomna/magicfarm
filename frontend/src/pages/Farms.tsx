import { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api, type FieldDetail, type PlayerFarm, type PlayerSearchItem } from '../api/endpoints';
import FieldGridView from '../components/FieldGridView';
import Toast from '../components/Toast';

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

  useEffect(() => {
    api.playerSearch('', 100).then(setAllPlayers).catch(() => {});
  }, []);

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
                    <button className="fm-btn fm-btn-sm fm-btn-outline" style={{ flex: '1 1 45%', minWidth: 0 }} onClick={(e) => { e.stopPropagation(); writeTo(p.vk_id); }}>💬 Написать</button>
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
    </div>
  );
}
