import { useEffect, useState } from 'react';
import { api, type Achievement } from '../api/endpoints';
import { mediaUrl } from '../api/media';

export default function AchievementsPage() {
  const [items, setItems] = useState<Achievement[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.achievements()
      .then(setItems)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  const earned = items.filter((a) => a.earned);
  const locked = items.filter((a) => !a.earned);

  return (
    <div style={{ maxWidth: 'var(--shell-max-width)', margin: '0 auto', padding: 'var(--shell-pad)' }}>
      {loading ? (
        <div className="fm-card">Загрузка достижений…</div>
      ) : items.length === 0 ? (
        <div className="fm-card" style={{ color: 'var(--text-muted)' }}>
          Достижений пока нет.
        </div>
      ) : (
        <>
          {earned.length > 0 && (
            <div style={{ marginBottom: 16 }}>
              <h2 style={{ fontSize: 16, marginBottom: 8 }}>🏆 Получено ({earned.length})</h2>
              <div className="fm-grid">
                {earned.map((a) => (
                  <div key={a.id} className="fm-card fm-rise" style={{ textAlign: 'center' }}>
                    {a.image_url && (
                      <img src={mediaUrl(a.image_url)} alt="" style={{ width: 64, height: 64, objectFit: 'cover', borderRadius: 'var(--radius-sm)', marginBottom: 6 }} />
                    )}
                    <div style={{ fontSize: 14, fontWeight: 600 }}>{a.name}</div>
                    <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>{a.condition_kind}: {a.condition_value}</div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {locked.length > 0 && (
            <div>
              <h2 style={{ fontSize: 16, marginBottom: 8, color: 'var(--text-secondary)' }}>🔒 Закрыто ({locked.length})</h2>
              <div className="fm-grid">
                {locked.map((a) => (
                  <div key={a.id} className="fm-card" style={{ textAlign: 'center', opacity: 0.55 }}>
                    {a.image_url ? (
                      <img src={mediaUrl(a.image_url)} alt="" style={{ width: 64, height: 64, objectFit: 'cover', borderRadius: 'var(--radius-sm)', marginBottom: 6, filter: 'grayscale(0.8)' }} />
                    ) : (
                      <div style={{ width: 64, height: 64, background: 'var(--bg-card)', borderRadius: 'var(--radius-sm)', margin: '0 auto 6px', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 24 }}>
                        🔒
                      </div>
                    )}
                    <div style={{ fontSize: 14, fontWeight: 600 }}>{a.name}</div>
                    <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>{a.condition_kind}: {a.condition_value}</div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
