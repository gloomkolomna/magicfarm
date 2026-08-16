import { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useSession } from '../context/SessionContext';
import { api, type FieldInfo, type LevelGate } from '../api/endpoints';
import { mediaUrl } from '../api/media';
import Toast from '../components/Toast';

const FIELD_KIND_LABEL: Record<string, string> = {
  garden_beds: '🌱 Грядки',
  orchard: '🍎 Сады',
  barnyard: '🐄 Скотный двор',
  house: '🏠 Дом',
  brewery: '🧪 Зельеварня',
  library: '📖 Библиотека',
  lawn: '🐾 Питомцы',
  default: '🗺️ Поля',
};

function groupByCategory(fields: FieldInfo[]): { category: string; items: FieldInfo[] }[] {
  const map = new Map<string, FieldInfo[]>();
  for (const f of fields) {
    const cat = f.field_kind || f.plant_category || 'default';
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
  const [levels, setLevels] = useState<LevelGate[]>([]);

  useEffect(() => {
    Promise.all([
      api.fields(),
      api.getBackground().catch(() => ({ url: '' })),
      api.userPotions().catch(() => [] as any[]),
      api.levels().catch(() => [] as any[]),
    ])
      .then(([flds, bg, pots, lvls]) => {
        setFields(flds);
        setBgUrl(bg.url);
        setPotions(pots);
        setLevels(lvls);
      })
      .catch((e) => setMsg('✗ ' + (e?.response?.data?.detail || 'Ошибка')))
      .finally(() => setLoading(false));
  }, []);

  const unactivated = potions.filter((p: any) => p.activated === false);

  const categories = useMemo(() => groupByCategory(fields), [fields]);
  const totalPages = categories.length;
  const safePage = Math.max(0, Math.min(page, Math.max(0, totalPages - 1)));
  const current = categories[safePage];
  const userLevel = user?.level ?? 0;
  const levelImage = levels.find((l) => l.level === userLevel)?.image_url;

  useEffect(() => {
    if (totalPages === 0) return;
    if (page >= totalPages) setPage(totalPages - 1);
  }, [totalPages, page]);

  const handlePrev = () => { if (safePage > 0) setPage(safePage - 1); };
  const handleNext = () => { if (safePage < totalPages - 1) setPage(safePage + 1); };

  return (
    <div style={{ maxWidth: 'var(--shell-max-width)', margin: '0 auto', padding: 'var(--shell-pad)' }}>
      {user && (
        <div className="fm-card fm-rise" style={{ textAlign: 'center', marginBottom: 14 }}>
          {levelImage && (
            <img src={mediaUrl(levelImage)} alt={`Уровень ${userLevel}`} style={{ maxWidth: 200, maxHeight: 100, marginBottom: 8, borderRadius: 8 }} />
          )}
          <div style={{ fontSize: 24, marginBottom: 4 }}>🏆 Уровень {userLevel}</div>
          <div style={{ display: 'flex', justifyContent: 'center', gap: 16 }}>
            <span>🪙 {user.coins ?? 0}</span>
            <span>🧵 {user.crosses_total ?? 0}</span>
          </div>
          {unactivated.length > 0 && (
            <div style={{ marginTop: 6, fontSize: 13, color: 'var(--text-secondary)' }}>
              ⚗️ Зелий для активации: {unactivated.length}
              <span style={{ color: 'var(--text-muted)' }}>
                {' '}({unactivated.map((p: any) => p.bonus_code || p.potion_name).filter(Boolean).join(', ')})
              </span>
            </div>
          )}
        </div>
      )}
      {msg && <Toast text={msg} onClose={() => setMsg(null)} />}
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
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10, background: 'linear-gradient(180deg, var(--leaf) 0%, var(--grass) 100%)', border: '1px solid var(--grass-deep)', borderRadius: 'var(--radius-md)', padding: '8px 10px', color: '#1a2414' }}>
              <button
                disabled={safePage === 0}
                onClick={handlePrev}
                style={{ cursor: safePage === 0 ? 'default' : 'pointer', opacity: safePage === 0 ? 0.4 : 1, padding: '6px 14px', fontSize: 18, background: 'transparent', border: 'none', color: 'inherit' }}
              >
                ◀
              </button>
              <span style={{ fontWeight: 600, textTransform: 'capitalize' }}>
                {FIELD_KIND_LABEL[current.category] || current.category}
              </span>
              <button
                disabled={safePage >= totalPages - 1}
                onClick={handleNext}
                style={{ cursor: safePage >= totalPages - 1 ? 'default' : 'pointer', opacity: safePage >= totalPages - 1 ? 0.4 : 1, padding: '6px 14px', fontSize: 18, background: 'transparent', border: 'none', color: 'inherit' }}
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
