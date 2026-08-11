import { useCallback, useEffect, useState } from 'react';
import { useSession } from '../context/SessionContext';
import { api, type StitchReport } from '../api/endpoints';
import { mediaUrl } from '../api/media';
import Onboarding from './Onboarding';

const STATUS_STYLE: Record<string, React.CSSProperties> = {
  accepted: { background: 'rgba(111,174,74,0.2)' },
  pending: { background: 'rgba(224,168,62,0.2)' },
  rejected: { background: 'rgba(196,87,74,0.2)' },
};

export default function ProfilePage() {
  const { user, loading: sessionLoading } = useSession();
  const [reports, setReports] = useState<StitchReport[]>([]);
  const [loading, setLoading] = useState(true);
  const [showNorms, setShowNorms] = useState(false);
  const [filter, setFilter] = useState('');

  const load = useCallback(async () => {
    setLoading(true);
    try {
      setReports(await api.stitchReports());
    } catch {
      /* ignore */
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { if (!sessionLoading) load(); }, [load, sessionLoading]);

  if (!user) return null;

  return (
    <div style={{ maxWidth: 600, margin: '0 auto', padding: 'var(--shell-pad)' }}>
      <h1 style={{ textAlign: 'center' }}>👤 Профиль</h1>

      <div className="fm-card fm-rise" style={{ marginBottom: 14, textAlign: 'center' }}>
        <div style={{ fontSize: 14, color: 'var(--text-muted)' }}>Вышивальщица</div>
        <div style={{ fontFamily: 'var(--font-display)', fontSize: 20 }}>
          {user.display_name || `Игрок #${user.vk_id}`}
        </div>
      </div>

      <div className="fm-grid" style={{ gridTemplateColumns: 'repeat(2, 1fr)', marginBottom: 14 }}>
        <div className="fm-card" style={{ textAlign: 'center' }}>
          <div style={{ fontSize: 24 }}>🧵</div>
          <div style={{ fontSize: 22, fontWeight: 700 }}>{user.crosses_total}</div>
          <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>всего вышито крестиков</div>
        </div>
        <div className="fm-card" style={{ textAlign: 'center' }}>
          <div style={{ fontSize: 24 }}>✝️</div>
          <div style={{ fontSize: 22, fontWeight: 700 }}>{user.crosses_balance}</div>
          <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>крестиков на балансе</div>
        </div>
        <div className="fm-card" style={{ textAlign: 'center' }}>
          <div style={{ fontSize: 24 }}>🪙</div>
          <div style={{ fontSize: 22, fontWeight: 700 }}>{user.coins}</div>
          <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>монет заработано</div>
        </div>
        <div className="fm-card" style={{ textAlign: 'center' }}>
          <div style={{ fontSize: 24 }}>🌱</div>
          <div style={{ fontSize: 22, fontWeight: 700 }}>Ур.{user.round}</div>
          <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>раунд игры</div>
        </div>
      </div>

      <button
        className="fm-btn fm-btn-outline"
        style={{ width: '100%', marginBottom: 14 }}
        onClick={() => setShowNorms(true)}
      >
        🧵 Изменить нормы вышивки
      </button>

      {showNorms && (
        <div
          onClick={() => setShowNorms(false)}
          style={{
            position: 'fixed', inset: 0, zIndex: 70, background: 'rgba(0,0,0,0.6)',
            backdropFilter: 'blur(3px)', overflow: 'auto',
          }}
        >
          <div onClick={(e) => e.stopPropagation()}>
            <div style={{ maxWidth: 600, margin: '0 auto', padding: '8px 12px 0', textAlign: 'right' }}>
              <button className="fm-btn fm-btn-xs fm-btn-outline" onClick={() => setShowNorms(false)}>✕ Закрыть</button>
            </div>
            <Onboarding onSaved={() => setShowNorms(false)} />
          </div>
        </div>
      )}

      <h2>📷 Дневник вышивки</h2>
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
          {reports.filter((r) => !filter || r.context_type === filter).map((r) => (
            <div key={r.id} className="fm-card fm-rise">
              <div style={{ display: 'flex', gap: 10 }}>
                {r.photo_after_url && (
                  <img
                    src={mediaUrl(r.photo_after_url)}
                    alt=""
                    style={{ width: 60, height: 60, objectFit: 'cover', borderRadius: 'var(--radius-sm)' }}
                  />
                )}
                <div style={{ flex: 1, minWidth: 0 }}>
                  <strong>✝️ {r.amount}</strong>
                  {r.note && <div style={{ fontSize: 13, color: 'var(--text-secondary)' }}>{r.note}</div>}
                  <span className="fm-chip" style={{ ...STATUS_STYLE[r.status], marginTop: 4, fontSize: 11 }}>
                    {r.status === 'accepted' ? '✓ зачтено' : r.status === 'pending' ? '⏳ ждёт' : '✖ отклонено'}
                  </span>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
