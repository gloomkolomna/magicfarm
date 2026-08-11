import { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useSession } from '../context/SessionContext';
import { api, type FieldInfo } from '../api/endpoints';

function groupByCategory(fields: FieldInfo[]): { category: string; items: FieldInfo[] }[] {
  const map = new Map<string, FieldInfo[]>();
  for (const f of fields) {
    const cat = f.plant_category || 'default';
    if (!map.has(cat)) map.set(cat, []);
    map.get(cat)!.push(f);
  }
  return Array.from(map.entries()).map(([category, items]) => ({ category, items }));
}

export default function FieldsPage() {
  const nav = useNavigate();
  const { user } = useSession();
  const [fields, setFields] = useState<FieldInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [msg, setMsg] = useState<string | null>(null);
  const [bgUrl, setBgUrl] = useState('');
  const [page, setPage] = useState(0);
  const [potions, setPotions] = useState<any[]>([]);
  const [routeVariant, setRouteVariant] = useState<number | null>(null);

  useEffect(() => {
    Promise.all([api.fields(), api.getBackground().catch(() => ({ url: '' }))])
      .then(([flds, bg]) => { setFields(flds); setBgUrl(bg.url); })
      .catch((e) => setMsg('✗ ' + (e?.response?.data?.detail || 'Ошибка')))
      .finally(() => setLoading(false));
  }, []);

  const categories = useMemo(() => groupByCategory(fields), [fields]);
  const totalPages = categories.length;
  const safePage = Math.max(0, Math.min(page, Math.max(0, totalPages - 1)));
  const current = categories[safePage];
  const userLevel = user?.level ?? 0;

  useEffect(() => {
    if (totalPages === 0) return;
    if (page >= totalPages) setPage(totalPages - 1);
  }, [totalPages, page]);

  const handlePrev = () => { if (safePage > 0) setPage(safePage - 1); };
  const handleNext = () => { if (safePage < totalPages - 1) setPage(safePage + 1); };

  return (
    <div style={{ maxWidth: 600, margin: '0 auto', padding: 'var(--shell-pad)' }}>
      {user && (
        <div className="fm-card fm-rise" style={{ textAlign: 'center', marginBottom: 14 }}>
          <div style={{ fontSize: 24, marginBottom: 4 }}>🏆 Уровень {userLevel}</div>
          <div style={{ display: 'flex', justifyContent: 'center', gap: 16 }}>
            <span>🪙 {user.coins ?? 0}</span>
            <span>🧵 {user.crosses_total ?? 0}</span>
          </div>
        </div>
      )}
      <h1 style={{ textAlign: 'center' }}>🗺️ Поля фермы</h1>

      {msg && <div className="fm-card" style={{ marginBottom: 10, fontSize: 14 }}>{msg}</div>}

      {bgUrl && <img src={bgUrl} alt="" style={{ width: '100%', borderRadius: 12, marginBottom: 14 }} />}

      {loading ? (
        <div className="fm-card">Загрузка полей…</div>
      ) : fields.length === 0 ? (
        <div className="fm-card" style={{ color: 'var(--text-muted)' }}>
          Локаций пока нет. Администратор может создать их в разделе «⚙️ Управление».
        </div>
      ) : (
        <>
          {totalPages > 1 && (
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
              <button
                className="fm-card"
                disabled={safePage === 0}
                onClick={handlePrev}
                style={{ cursor: safePage === 0 ? 'default' : 'pointer', opacity: safePage === 0 ? 0.4 : 1, padding: '6px 14px', fontSize: 18 }}
              >
                ◀
              </button>
              <span style={{ fontWeight: 600, textTransform: 'capitalize' }}>
                {current.category === 'default' ? 'Основное' : current.category}
              </span>
              <button
                className="fm-card"
                disabled={safePage >= totalPages - 1}
                onClick={handleNext}
                style={{ cursor: safePage >= totalPages - 1 ? 'default' : 'pointer', opacity: safePage >= totalPages - 1 ? 0.4 : 1, padding: '6px 14px', fontSize: 18 }}
              >
                ▶
              </button>
            </div>
          )}
          <div className="fm-grid">
            {current.items.map((f) => {
              const locked = f.min_level > 0 && f.min_level > userLevel;
              if (locked) {
                return (
                  <div key={f.id} className="fm-card" style={{ opacity: 0.5, textAlign: 'left' }}>
                    <strong style={{ fontSize: 16 }}>🔒 {f.name}</strong>
                    <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 4 }}>
                      Откроется на уровне {f.min_level}
                    </div>
                  </div>
                );
              }
              return (
                <button
                  key={f.id}
                  className="fm-card fm-rise"
                  onClick={() => nav(`/field/${f.id}`)}
                  style={{ cursor: 'pointer', textAlign: 'left', display: 'block' }}
                >
                  <strong style={{ fontSize: 16 }}>🗺️ {f.name}</strong>
                  <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 4 }}>
                    {f.cols}×{f.rows} клеток
                  </div>
                </button>
              );
            })}
          </div>
        </>
      )}
    </div>
  );
}
