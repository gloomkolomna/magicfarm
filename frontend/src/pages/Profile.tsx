import { useCallback, useEffect, useState } from 'react';
import { useSession } from '../context/SessionContext';
import { api, type LevelGate, type PlantNormItem, type StitchReport } from '../api/endpoints';
import { mediaUrl } from '../api/media';
import Onboarding from './Onboarding';
import SubscriptionBox, { SubscriptionStatusLine, TrialExpiringBanner } from '../components/SubscriptionBox';

const STATUS_STYLE: Record<string, React.CSSProperties> = {
  accepted: { background: 'rgba(111,174,74,0.2)' },
  pending: { background: 'rgba(224,168,62,0.2)' },
  rejected: { background: 'rgba(196,87,74,0.2)' },
};

export default function ProfilePage() {
  const { user, loading: sessionLoading } = useSession();
  const [reports, setReports] = useState<StitchReport[]>([]);
  const [levels, setLevels] = useState<LevelGate[]>([]);
  const [plantNorms, setPlantNorms] = useState<PlantNormItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [showNorms, setShowNorms] = useState(false);
  const [filter, setFilter] = useState('');

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [reps, lvls, norms] = await Promise.all([
        api.stitchReports(),
        api.levels().catch(() => [] as LevelGate[]),
        api.myPlantNorms().catch(() => [] as PlantNormItem[]),
      ]);
      setReports(reps);
      setLevels(lvls);
      setPlantNorms(norms);
    } catch {
      /* ignore */
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { if (!sessionLoading) load(); }, [load, sessionLoading]);

  if (!user) return null;

  return (
    <div style={{ maxWidth: 'var(--shell-max-width)', margin: '0 auto', padding: 'var(--shell-pad)' }}>
      <div className="fm-card fm-view-allow" style={{ marginBottom: 14 }}>
        <h2 style={{ margin: '0 0 8px', fontSize: 18 }}>⏳ Подписка</h2>
        <TrialExpiringBanner />
        <SubscriptionStatusLine />
        {user.role !== 'admin' && (
          <div style={{ marginTop: 12 }}>
            <SubscriptionBox />
          </div>
        )}
      </div>
      <div className="fm-stats" style={{ marginBottom: 14 }}>
        <div className="fm-card" style={{ textAlign: 'center' }}>
          <div style={{ fontSize: 24 }}>🧵</div>
          <div style={{ fontSize: 22, fontWeight: 700 }}>{user.crosses_total}</div>
          <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>всего вышито крестиков</div>
        </div>
        <div className="fm-card" style={{ textAlign: 'center' }}>
          <div style={{ fontSize: 24 }}>🪙</div>
          <div style={{ fontSize: 22, fontWeight: 700 }}>{user.coins}</div>
          <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>монет заработано</div>
        </div>
        <div className="fm-card" style={{ textAlign: 'center' }}>
          <div style={{ fontSize: 24 }}>🌱</div>
          <div style={{ fontSize: 22, fontWeight: 700 }}>Ур.{user.level ?? 0}</div>
          <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>этап маршрутного листа</div>
        </div>
        <div className="fm-card" style={{ textAlign: 'center' }}>
          <div style={{ fontSize: 24 }}>🔄</div>
          <div style={{ fontSize: 22, fontWeight: 700 }}>Раунд {user.round}</div>
          <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>цикл игры</div>
        </div>
      </div>

      {levels.length > 0 && (
        <>
          <h2>🗺️ Маршрут ({(user.level ?? 0)} из {levels[levels.length - 1].level})</h2>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginBottom: 14 }}>
            {levels.map((g) => {
              const cur = user.level ?? 0;
              const passed = g.level < cur;
              const current = g.level === cur;
              const next = g.level === cur + 1;
              const nextGate = current ? levels.find((x) => x.level === cur + 1) : undefined;
              const coinsMissing = nextGate ? Math.max(0, nextGate.coins_required - (user.coins ?? 0)) : 0;
              const plotsMissing = nextGate ? Math.max(0, nextGate.plots_required - (user.plots_placed ?? 0)) : 0;
              const ready = nextGate !== undefined && coinsMissing === 0 && plotsMissing === 0;
              const nextCoinsProgress = nextGate && nextGate.coins_required > 0
                ? Math.min(100, Math.round(((user.coins ?? 0) / nextGate.coins_required) * 100))
                : null;
              return (
                <div
                  key={g.level}
                  className="fm-card"
                  style={{
                    display: 'flex', alignItems: 'center', gap: 10,
                    opacity: passed ? 0.6 : 1,
                    border: current ? '2px solid var(--accent-warm)' : undefined,
                    background: next ? 'rgba(224,168,62,0.08)' : undefined,
                  }}
                >
                  {g.image_url ? (
                    <img src={mediaUrl(g.image_url)} alt="" style={{ width: 44, height: 44, objectFit: 'contain', borderRadius: 6, flexShrink: 0 }} />
                  ) : (
                    <div style={{ width: 44, height: 44, borderRadius: 6, flexShrink: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 17, fontWeight: 700, background: 'var(--bg-secondary)', border: '1px solid var(--border)' }}>
                      {g.level}
                    </div>
                  )}
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap' }}>
                      <strong style={{ fontSize: 14 }}>Этап {g.level}</strong>
                      {passed && <span style={{ fontSize: 11, color: 'var(--success)' }}>✓ пройден</span>}
                      {current && <span className="fm-chip" style={{ fontSize: 11, background: 'rgba(224,168,62,0.25)' }}>📍 вы здесь</span>}
                      {next && <span style={{ fontSize: 11, color: 'var(--accent-warm)' }}>⏳ следующий</span>}
                    </div>
                    {g.unlock_type && (
                      <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginTop: 2 }}>
                        🔓 {g.unlock_type}
                      </div>
                    )}
                    {!passed && (
                      <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 2 }}>
                        🪙 {g.coins_required} монет{g.plots_required > 0 ? <> · 🌱 {g.plots_required} грядок и садов</> : null}
                      </div>
                    )}
                    {current && nextGate && (
                      <div style={{ marginTop: 6, paddingTop: 6, borderTop: '1px solid var(--border)' }}>
                        {nextCoinsProgress !== null && (
                          <>
                            <div className="fm-progress" style={{ height: 6 }}>
                              <div className="fm-progress-fill" style={{ width: `${nextCoinsProgress}%` }} />
                            </div>
                            <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 2 }}>
                              {user.coins ?? 0} / {nextGate.coins_required} 🪙
                            </div>
                          </>
                        )}
                        <div style={{ fontSize: 12, marginTop: 4, color: ready ? 'var(--success)' : 'var(--accent-warm)' }}>
                          {ready
                            ? '✅ Всё готово — переход после следующего выполненного заказа'
                            : <>Не хватает:{coinsMissing > 0 && <> 🪙 {coinsMissing}</>}{coinsMissing > 0 && plotsMissing > 0 && ' ·'}{plotsMissing > 0 && <> 🌱 {plotsMissing}</>}</>}
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </>
      )}

      <button
        className="fm-btn fm-btn-outline"
        style={{ width: '100%', marginBottom: 14 }}
        onClick={() => setShowNorms(true)}
      >
        🧵 Изменить нормы вышивки
      </button>

      {showNorms && (
        <div
          style={{
            position: 'fixed', inset: 0, zIndex: 70, background: 'rgba(0,0,0,0.6)',
            backdropFilter: 'blur(3px)', overflow: 'auto',
          }}
        >
          <div onClick={(e) => e.stopPropagation()}>
            <div style={{ maxWidth: 'var(--shell-max-width)', margin: '0 auto', padding: '8px 12px 0', textAlign: 'right' }}>
              <button className="fm-btn fm-btn-xs fm-btn-outline" onClick={() => setShowNorms(false)}>✕ Закрыть</button>
            </div>
            <Onboarding onSaved={() => setShowNorms(false)} />
          </div>
        </div>
      )}

      <h2>🌱 Цены на грядки и сады</h2>
      <p style={{ fontSize: 12, color: 'var(--text-muted)', margin: '0 0 10px' }}>
        Игра сама назначает цену (❎ за 1 растение) при посадке. Здесь её можно изменить — новая цена применится ко всем грядкам и садам этого растения.
      </p>
      {plantNorms.length === 0 ? (
        <div className="fm-card" style={{ color: 'var(--text-muted)', marginBottom: 14 }}>
          Пока нет растений с присвоенной ценой.
        </div>
      ) : (
        <div className="fm-grid" style={{ marginBottom: 14 }}>
          {plantNorms.map((n) => (
            <div key={n.plant_id} className="fm-card fm-rise" style={{ fontSize: 13 }}>
              <strong>{n.plant_emoji} {n.plant_name}</strong>
              <div style={{ color: 'var(--text-muted)', marginTop: 2, fontSize: 12 }}>
                Текущая цена: {n.norm_per_unit} ❎/шт · {n.plot_count} грядок и садов
              </div>
              <div style={{ marginTop: 6 }}>
                <PlantNormEditor plant={n} onSaved={setPlantNorms} />
              </div>
            </div>
          ))}
        </div>
      )}

      <h2>📷 Дневник вышивки</h2>
      <p style={{ fontSize: 12, color: 'var(--text-muted)', margin: '0 0 10px' }}>
        Фото отчётов хранятся 30 дней, после чего автоматически удаляются.
      </p>
      <select className="fm-input" style={{ marginBottom: 10, width: '100%' }} value={filter} onChange={(e) => setFilter(e.target.value)}>
        <option value="">Все отчёты</option>
        <option value="plant_grow">🌱 Выращивание</option>
        <option value="recipe_study">📖 Изучение</option>
        <option value="production">🏭 Переработка</option>
        <option value="tent_build">⛺ Шатёр</option>
        <option value="pet_settle">🐾 Питомец</option>
      </select>
      {loading ? (
        <div className="fm-card">Загрузка…</div>
      ) : reports.filter((r) => !filter || r.context_type === filter).length === 0 ? (
        <div className="fm-card" style={{ color: 'var(--text-muted)' }}>
          Пока нет отчётов.
        </div>
      ) : (
        <div className="fm-grid">
          {reports.filter((r) => !filter || r.context_type === filter).map((r) => {
            const photo = r.photo_after_url || r.photo_after_thumb_url;
            return (
            <div key={r.id} className="fm-card fm-rise">
              <div style={{ display: 'flex', gap: 10 }}>
                {photo && (
                  <img
                    src={mediaUrl(photo)}
                    alt=""
                    style={{ width: 60, height: 60, objectFit: 'cover', borderRadius: 'var(--radius-sm)' }}
                  />
                )}
                <div style={{ flex: 1, minWidth: 0 }}>
                  <strong>❎ {r.amount}</strong>
                  {r.note && <div style={{ fontSize: 13, color: 'var(--text-secondary)' }}>{r.note}</div>}
                  <span className="fm-chip" style={{ ...STATUS_STYLE[r.status], marginTop: 4, fontSize: 11 }}>
                    {r.status === 'accepted' ? '✓ зачтено' : r.status === 'pending' ? '⏳ ждёт' : '✖ отклонено'}
                  </span>
                </div>
              </div>
            </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

function PlantNormEditor({ plant, onSaved }: { plant: PlantNormItem; onSaved: (items: PlantNormItem[]) => void }) {
  const [val, setVal] = useState(String(plant.norm_per_unit));
  const [busy, setBusy] = useState(false);
  useEffect(() => setVal(String(plant.norm_per_unit)), [plant.norm_per_unit]);
  const valid = Number(val) >= 1;
  return (
    <div style={{ display: 'flex', gap: 4, alignItems: 'center', flexWrap: 'wrap' }}>
      <input
        className="fm-input"
        type="number"
        min={1}
        value={val}
        onChange={(e) => setVal(e.target.value)}
        style={{ width: 80 }}
        aria-label={`Цена 1 растения ${plant.plant_name}`}
      />
      <button
        className="fm-btn fm-btn-sm"
        disabled={busy || !valid}
        onClick={async () => {
          setBusy(true);
          try {
            onSaved(await api.setMyPlantNorm(plant.plant_id, Math.floor(Number(val))));
          } finally {
            setBusy(false);
          }
        }}
      >
        💾
      </button>
    </div>
  );
}
