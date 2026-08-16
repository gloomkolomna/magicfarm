import { useEffect, useState } from 'react';
import { api, type LibraryRecipe, type Product } from '../api/endpoints';
import { mediaUrl } from '../api/media';
import Toast from '../components/Toast';

const TENT_KINDS: Record<string, string> = {
  alchemy: '⚗️',
  sewing: '🧵',
  workshop: '🔨',
  barnyard: '🏚️',
};

const LEVEL_LABELS: Record<number, string> = { 1: 'I', 2: 'II', 3: 'III' };

export default function LibraryPage() {
  const [recipes, setRecipes] = useState<LibraryRecipe[]>([]);
  const [products, setProducts] = useState<Product[]>([]);
  const [norms, setNorms] = useState<Record<string, number | null>>({});
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  const [studyRecipe, setStudyRecipe] = useState<LibraryRecipe | null>(null);

  const load = async () => {
    setLoading(true);
    try {
      const [recs, prs, mine] = await Promise.all([
        api.library(),
        api.products(),
        api.myCrystalNorms(),
      ]);
      setRecipes(recs);
      setProducts(prs);
      setNorms({
        lvl1: mine.study_norms?.level1 ?? null,
        lvl2: mine.study_norms?.level2 ?? null,
        lvl3: mine.study_norms?.level3 ?? null,
      });
    } catch (e: any) {
      setMsg('✗ ' + (e?.response?.data?.detail || 'Ошибка'));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  async function doStudy() {
    if (!studyRecipe) return;
    setBusy(true); setMsg(null);
    try {
      const updated = await api.studyRecipe(studyRecipe.id);
      setRecipes((prev) => prev.map((r) => (r.id === updated.id ? updated : r)));
      setMsg('✓ Изучение начато!');
      setStudyRecipe(null);
    } catch (e: any) {
      setMsg('✗ ' + (e?.response?.data?.detail || 'Ошибка'));
    } finally { setBusy(false); }
  }

  function findProduct(recipe: LibraryRecipe): Product | undefined {
    return products.find((p) => p.id === recipe.product_id);
  }

  function tentIcon(kind: string | null | undefined): string {
    if (!kind) return '';
    return TENT_KINDS[kind] || '⛺';
  }

  const grouped = recipes.reduce<Record<number, LibraryRecipe[]>>((acc, r) => {
    if (!acc[r.level]) acc[r.level] = [];
    acc[r.level].push(r);
    return acc;
  }, {});

  return (
    <div style={{ maxWidth: 'var(--shell-max-width)', margin: '0 auto', padding: 'var(--shell-pad)' }}>
      {!loading && (
        <div className="fm-card fm-rise" style={{ textAlign: 'center', marginBottom: 14 }}>
          <div style={{ fontSize: 13, color: 'var(--text-secondary)' }}>
            Нормы изучения (крестиков):
          </div>
          <div style={{ display: 'flex', justifyContent: 'center', gap: 12, marginTop: 6, fontSize: 14 }}>
            {[1, 2, 3].map((lvl) => (
              <span key={lvl}>
                {LEVEL_LABELS[lvl]} — {norms[`lvl${lvl}`] ?? '—'}
              </span>
            ))}
          </div>
          {(norms.lvl1 == null || norms.lvl2 == null || norms.lvl3 == null) && (
            <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 6 }}>
              Задайте личные нормы изучения в профиле (Настройки норм)
            </div>
          )}
        </div>
      )}

      {msg && <Toast text={msg} onClose={() => setMsg(null)} />}

      {loading ? (
        <div className="fm-card">Загрузка библиотеки…</div>
      ) : recipes.length === 0 ? (
        <div className="fm-card" style={{ color: 'var(--text-muted)' }}>
          Рецептов пока нет. Администратор добавит их позже.
        </div>
      ) : (
        [1, 2, 3].map((lvl) => {
          const items = grouped[lvl];
          if (!items || items.length === 0) return null;
          return (
            <div key={lvl} style={{ marginBottom: 16 }}>
              <h2 style={{ fontSize: 16, marginBottom: 8, color: 'var(--text-secondary)' }}>
                Уровень {LEVEL_LABELS[lvl]}
              </h2>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                {items.map((r) => {
                  const prod = findProduct(r);
                  const tent = tentIcon(prod?.production_kind);

                  return (
                    <div
                      key={r.id}
                      className={`fm-card fm-rise ${r.status === 'locked' ? '' : 'fm-card-studied'}`}
                      onClick={() => {
                        if (r.status === 'locked') setStudyRecipe(r);
                      }}
                      style={{
                        cursor: r.status === 'locked' ? 'pointer' : 'default',
                        display: 'flex',
                        alignItems: 'center',
                        gap: 10,
                        opacity: r.status === 'studied' ? 1 : r.status === 'studying' ? 0.75 : 1,
                      }}
                    >
                      <div style={{ fontSize: 28, flexShrink: 0 }}>
                        {r.source_kind === 'animal_product' ? (r.source_product_emoji || '🥚') : (r.plant_emoji || '🌱')}
                      </div>
                      <div style={{ flex: 1, minWidth: 0 }}>
                        <div style={{ fontSize: 14, fontWeight: 600 }}>
                          {r.source_kind === 'animal_product' ? r.source_product_name : r.plant_name}
                        </div>
                        <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>
                          {r.status === 'studied' ? 'изучен' : r.status === 'studying' ? 'изучается…' : 'закрыт'}
                        </div>
                      </div>

                      <div style={{ fontSize: 20, color: 'var(--text-muted)', flexShrink: 0 }}>→</div>

                      <div style={{ width: 60, textAlign: 'center', flexShrink: 0 }}>
                        {r.status === 'studied' ? (
                          <>
                            <div style={{ fontSize: 24 }}>{r.product_emoji || '📦'}</div>
                            <div style={{ fontSize: 10, color: 'var(--text-secondary)', lineHeight: 1.15 }}>
                              {r.product_name}
                            </div>
                          </>
                        ) : r.status === 'studying' ? (
                          <>
                            <div style={{ fontSize: 24, opacity: 0.5 }}>{r.product_emoji || '📦'}</div>
                            <div style={{ fontSize: 10, color: 'var(--text-secondary)', lineHeight: 1.15 }}>
                              {r.product_name}
                            </div>
                          </>
                        ) : (
                          <div style={{ fontSize: 24, color: 'var(--text-muted)' }}>?</div>
                        )}
                      </div>

                      {tent && (
                        <div style={{ fontSize: 16, color: 'var(--text-muted)', flexShrink: 0 }} title={prod?.production_kind ?? ''}>
                          {tent}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          );
        })
      )}

      {studyRecipe && (
        <Modal title="📖 Начать изучение" onClose={() => setStudyRecipe(null)}>
          <div style={{ textAlign: 'center', marginBottom: 12 }}>
            <div style={{ fontSize: 32 }}>
              {studyRecipe.source_kind === 'animal_product' ? (studyRecipe.source_product_emoji || '🥚') : (studyRecipe.plant_emoji || '🌱')}
            </div>
            <div style={{ fontSize: 18, fontWeight: 600 }}>
              {studyRecipe.source_kind === 'animal_product' ? studyRecipe.source_product_name : studyRecipe.plant_name}
            </div>
            <div style={{ fontSize: 24, color: 'var(--text-muted)', marginTop: 4 }}>→</div>
            <div style={{ fontSize: 32 }}>{studyRecipe.product_emoji || '📦'}</div>
            <div style={{ fontSize: 16 }}>{studyRecipe.product_name}</div>
          </div>
          <p style={{ fontSize: 13, color: 'var(--text-secondary)', textAlign: 'center' }}>
            Для изучения потребуется {norms[`lvl${studyRecipe.level}`] ?? '—'} крестиков.
            После начала изучения вы сможете завершить его через фото-отчёт вышивки.
          </p>
          <button
            className="fm-btn"
            style={{ width: '100%', marginTop: 14 }}
            disabled={busy}
            onClick={doStudy}
          >
            Начать изучение
          </button>
        </Modal>
      )}
    </div>
  );
}

function Modal({ title, onClose, children }: { title: string; onClose: () => void; children: React.ReactNode }) {
  return (
    <div style={{ position: 'fixed', inset: 0, zIndex: 60, background: 'rgba(0,0,0,0.6)', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 16 }}>
      <div className="fm-card fm-rise" onClick={(e) => e.stopPropagation()} style={{ width: '100%', maxWidth: 'calc(var(--shell-max-width) * 0.7)', maxHeight: '85vh', overflowY: 'auto' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
          <h2 style={{ margin: 0 }}>{title}</h2>
          <button className="fm-btn fm-btn-xs fm-btn-outline" onClick={onClose}>✕</button>
        </div>
        {children}
      </div>
    </div>
  );
}
