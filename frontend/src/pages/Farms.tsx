import { useState } from 'react';
import { api, type PlayerFarm, type PlayerSearchItem } from '../api/endpoints';
import Toast from '../components/Toast';

export default function FarmsPage() {
  const [q, setQ] = useState('');
  const [results, setResults] = useState<PlayerSearchItem[] | null>(null);
  const [farm, setFarm] = useState<PlayerFarm | null>(null);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  async function search() {
    setBusy(true); setMsg(null); setFarm(null);
    try {
      setResults(await api.playerSearch(q));
    } catch (e: any) {
      setMsg('✗ ' + (e?.response?.data?.detail || 'Ошибка поиска'));
      setResults([]);
    } finally {
      setBusy(false);
    }
  }

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

  return (
    <div style={{ maxWidth: 'var(--shell-max-width)', margin: '0 auto', padding: 'var(--shell-pad)' }}>
      <h1 style={{ fontSize: 20, margin: '0 0 10px' }}>🌾 Фермы игроков</h1>
      {msg && <Toast text={msg} onClose={() => setMsg(null)} />}

      {!farm ? (
        <>
          <div className="fm-card" style={{ marginBottom: 12, display: 'flex', gap: 8, alignItems: 'center' }}>
            <input
              className="fm-input"
              placeholder="Имя или ID игрока…"
              value={q}
              onChange={(e) => setQ(e.target.value)}
              onKeyDown={(e) => { if (e.key === 'Enter') search(); }}
            />
            <button className="fm-btn" disabled={busy || !q.trim()} onClick={search}>🔍 Найти</button>
          </div>
          <p style={{ fontSize: 12, color: 'var(--text-muted)', margin: '0 0 10px' }}>
            Только просмотр: фермы других игроков можно смотреть, но нельзя трогать.
          </p>
          {results !== null && (
            results.length === 0 ? (
              <div className="fm-card" style={{ color: 'var(--text-muted)' }}>Никого не найдено.</div>
            ) : (
              <div className="fm-grid">
                {results.map((p) => (
                  <button key={p.vk_id} className="fm-card fm-rise" style={{ textAlign: 'left', cursor: 'pointer' }} onClick={() => openFarm(p.vk_id)}>
                    <strong style={{ fontSize: 15 }}>👤 {p.display_name}</strong>
                    <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginTop: 4 }}>
                      🏆 Уровень {p.level} · 🪙 {p.coins} · 🧵 {p.crosses_total}
                    </div>
                    <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 2 }}>ID: {p.vk_id} →</div>
                  </button>
                ))}
              </div>
            )
          )}
        </>
      ) : (
        <div>
          <button className="fm-btn fm-btn-outline" style={{ marginBottom: 10 }} disabled={busy} onClick={() => setFarm(null)}>← Назад к поиску</button>
          <div className="fm-card" style={{ marginBottom: 10 }}>
            <strong style={{ fontSize: 17 }}>👤 {farm.display_name}</strong>
            <div style={{ fontSize: 13, color: 'var(--text-secondary)', marginTop: 4 }}>
              🏆 Уровень {farm.level} · 🪙 {farm.coins} · 🧵 {farm.crosses_total} · Раунд {farm.round} · 🏅 Достижений: {farm.achievements_total}
            </div>
          </div>

          <h3 style={{ margin: '0 0 8px' }}>🌱 Грядки ({farm.plots.length})</h3>
          {farm.plots.length === 0 ? (
            <div className="fm-card" style={{ color: 'var(--text-muted)', fontSize: 13 }}>Пусто.</div>
          ) : (
            <div className="fm-grid" style={{ marginBottom: 12 }}>
              {farm.plots.map((pl, i) => (
                <div key={i} className="fm-card" style={{ fontSize: 13 }}>
                  <strong>{pl.plant_emoji || '🌱'} {pl.plant_name || '—'}</strong>
                  <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>
                    {pl.status} · {pl.accumulated}/{pl.required} ❆
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
                    {pr.status} · {pr.accumulated}/{pr.required} ❆
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
    </div>
  );
}
