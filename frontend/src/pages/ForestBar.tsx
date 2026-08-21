import { useCallback, useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { Swiper, SwiperSlide } from 'swiper/react';
import type { Swiper as SwiperInstance } from 'swiper';
import 'swiper/css';
import { useSession } from '../context/SessionContext';
import { api, type BarZone, type FieldDetail, type FieldInfo, type Shaker } from '../api/endpoints';
import { mediaUrl } from '../api/media';
import LocationMap from '../components/LocationMap';
import Toast from '../components/Toast';

const COCKTAIL_KIND_ICON: Record<string, string> = {
  product: '📦',
  plant: '🌿',
  ingredient: '🌾',
  remedy: '⚗️',
};

const COCKTAIL_KIND_LABEL: Record<string, string> = {
  product: 'Товар',
  plant: 'Растение',
  ingredient: 'Ингредиент',
  remedy: 'Лекарство',
};

function Modal({ title, children, onClose }: { title: string; children: React.ReactNode; onClose: () => void }) {
  return (
    <div
      style={{ position: 'fixed', inset: 0, zIndex: 60, background: 'rgba(0,0,0,0.6)', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 14 }}
      onClick={onClose}
    >
      <div
        className="fm-card"
        style={{ maxWidth: 520, width: '100%', maxHeight: '86vh', overflowY: 'auto', margin: 0 }}
        onClick={(e) => e.stopPropagation()}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10, gap: 8 }}>
          <strong>{title}</strong>
          <button className="fm-btn fm-btn-xs" onClick={onClose} aria-label="Закрыть">✕</button>
        </div>
        {children}
      </div>
    </div>
  );
}

export default function ForestBarHubPage() {
  const nav = useNavigate();
  const { user, loading: sessionLoading } = useSession();
  const [fields, setFields] = useState<FieldInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const userLevel = user?.level ?? 0;

  useEffect(() => {
    if (sessionLoading) return;
    setLoading(true);
    api.fields()
      .then((all) => setFields(all.filter((f) => f.field_kind === 'forest_bar')))
      .catch(() => setFields([]))
      .finally(() => setLoading(false));
  }, [sessionLoading]);

  return (
    <div style={{ maxWidth: 'var(--shell-max-width)', margin: '0 auto', padding: 'var(--shell-pad)' }}>
      <h1 style={{ fontSize: 20, margin: '0 0 10px' }}>🍹 Лесной бар</h1>
      <h2 style={{ fontSize: 16, marginBottom: 10 }}>Бары</h2>
      {loading ? (
        <div className="fm-card">Загрузка…</div>
      ) : fields.length === 0 ? (
        <div className="fm-card" style={{ color: 'var(--text-muted)' }}>Баров пока нет.</div>
      ) : (
        <div className="fm-grid" style={{ marginBottom: 16 }}>
          {fields.map((f) => {
            const locked = f.min_level > 0 && f.min_level > userLevel;
            if (locked) {
              return (
                <div key={f.id} className="fm-card" style={{ opacity: 0.5, textAlign: 'left' }}>
                  <strong style={{ fontSize: 13 }}>🔒 {f.name}</strong>
                  <div style={{ color: 'var(--text-muted)', marginTop: 2 }}>Откроется на уровне {f.min_level}</div>
                </div>
              );
            }
            return (
              <button key={f.id} className="fm-card fm-rise" style={{ fontSize: 13, textAlign: 'left', cursor: 'pointer' }} onClick={() => nav(`/forest-bar/${f.id}`)}>
                <strong>🍹 {f.name}</strong>
                <div style={{ color: 'var(--text-muted)', marginTop: 2 }}>{f.cols}×{f.rows} клеток</div>
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}

export function ForestBarScenePage() {
  const { id } = useParams<{ id: string }>();
  const nav = useNavigate();
  const { refresh } = useSession();
  const [field, setField] = useState<FieldDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  const [showBook, setShowBook] = useState(false);
  const [shakerModal, setShakerModal] = useState(false);
  const [swiper, setSwiper] = useState<SwiperInstance | null>(null);
  const [bookPage, setBookPage] = useState(0);
  const [bookInitialSlide, setBookInitialSlide] = useState(0);
  const [mixVideoUrl, setMixVideoUrl] = useState<string | null>(null);
  const [mixVideoOpen, setMixVideoOpen] = useState(false);
  const [pendingMixMsg, setPendingMixMsg] = useState<string | null>(null);
  const [zoomedImg, setZoomedImg] = useState<string | null>(null);

  const fieldId = Number(id);

  const load = useCallback(async () => {
    if (!Number.isFinite(fieldId)) return;
    setLoading(true);
    try {
      const fd = await api.fieldDetail(fieldId);
      setField(fd);
    } catch (e: any) {
      setMsg('✗ ' + (e?.response?.data?.detail || 'Ошибка'));
    } finally {
      setLoading(false);
    }
  }, [fieldId]);

  useEffect(() => { load(); }, [load]);

  useEffect(() => {
    api.gameMediaByCode('cocktail_mix')
      .then((gm) => { if (gm.url) setMixVideoUrl(mediaUrl(gm.url)); })
      .catch(() => {});
  }, []);

  useEffect(() => {
    if (!msg) return;
    const t = setTimeout(() => setMsg(null), 4000);
    return () => clearTimeout(t);
  }, [msg]);

  const activeShaker = field?.active_shaker ?? null;
  const barZones = field?.bar_zones ?? [];
  const shakerZone = barZones.find((z) => z.zone_kind === 'shaker') ?? null;
  const bookZone = barZones.find((z) => z.zone_kind === 'book') ?? null;
  const cardZones = barZones.filter((z) => z.zone_kind === 'cocktail_card');
  const recipes = field?.cocktail_recipes ?? [];
  const activeRecipe = activeShaker?.cocktail_recipe_id != null
    ? recipes.find((r) => r.id === activeShaker.cocktail_recipe_id) ?? null
    : null;

  function openBook(recipeId?: number) {
    const idx = recipeId == null ? 0 : Math.max(0, recipes.findIndex((r) => r.id === recipeId));
    setBookInitialSlide(idx);
    setBookPage(idx);
    setShowBook(true);
  }

  async function installShaker(recipeId: number) {
    setBusy(true); setMsg(null);
    try {
      await api.installShaker(recipeId);
      setShowBook(false);
      setMsg('✓ Шейкер установлен!');
      await load(); await refresh();
    } catch (e: any) {
      setMsg('✗ ' + (e?.response?.data?.detail || 'Ошибка'));
    } finally { setBusy(false); }
  }

  async function mixNow() {
    if (!activeShaker) return;
    setBusy(true); setMsg(null);
    try {
      const res = await api.mixCocktail();
      setShakerModal(false);
      const okMsg = `✓ Коктейль «${res.recipe_name}» готов! +${res.coins_earned} монет`;
      if (mixVideoUrl) {
        setPendingMixMsg(okMsg);
        setMixVideoOpen(true);
      } else {
        setMsg(okMsg);
      }
      await load(); await refresh();
    } catch (e: any) {
      setMsg('✗ ' + (e?.response?.data?.detail || 'Ошибка'));
    } finally { setBusy(false); }
  }

  function endMixVideo() {
    setMixVideoOpen(false);
    if (pendingMixMsg) {
      setMsg(pendingMixMsg);
      setPendingMixMsg(null);
    }
  }

  if (loading && !field) {
    return (
      <div style={{ maxWidth: 'var(--shell-max-width)', margin: '0 auto', padding: 'var(--shell-pad)' }}>
        <div className="fm-card">Загрузка бара…</div>
      </div>
    );
  }

  return (
    <>
      <LocationMap mapUrl={field?.map_url ?? null} name={field?.name ?? ''} emoji="🍹" onBack={() => nav('/forest-bar')} backLabel="Лесной бар">
        {field && (
          <>
            {shakerZone && (
              <ZoneRect cols={field.cols} rows={field.rows} zone={shakerZone} onClick={() => (activeShaker ? setShakerModal(true) : openBook())}>
                {activeShaker && shakerZone.image_url ? (
                  <img src={mediaUrl(shakerZone.image_url)} alt="" style={{ position: 'absolute', inset: 0, width: '100%', height: '100%', objectFit: 'contain', pointerEvents: 'none' }} />
                ) : (
                  <div style={{ fontSize: 'clamp(24px,8vw,52px)', lineHeight: 1 }}>🍸</div>
                )}
                <div style={{ position: 'absolute', left: 2, right: 2, bottom: 1, fontSize: 'clamp(9px,2.2vw,13px)', color: '#ffe6c0', textAlign: 'center', textShadow: '0 1px 3px #000', fontWeight: 600, background: 'rgba(10,16,8,0.45)', borderRadius: 4, padding: '0 4px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {activeShaker ? `🍸 ${activeShaker.recipe_name ?? 'Шейкер'}` : 'Место шейкера'}
                </div>
              </ZoneRect>
            )}

            {bookZone && (
              <ZoneRect cols={field.cols} rows={field.rows} zone={bookZone} onClick={() => openBook()}>
                {bookZone.image_url ? (
                  <img src={mediaUrl(bookZone.image_url)} alt="" style={{ position: 'absolute', inset: 0, width: '100%', height: '100%', objectFit: 'contain', pointerEvents: 'none' }} />
                ) : (
                  <div style={{ fontSize: 'clamp(24px,8vw,52px)', lineHeight: 1 }}>📖</div>
                )}
                <div style={{ position: 'absolute', left: 2, right: 2, bottom: 1, fontSize: 'clamp(9px,2.2vw,13px)', color: '#ffe6c0', textAlign: 'center', textShadow: '0 1px 3px #000', fontWeight: 600, background: 'rgba(10,16,8,0.45)', borderRadius: 4, padding: '0 4px' }}>
                  Книга коктейлей
                </div>
              </ZoneRect>
            )}

            {cardZones.map((z) => {
              const cocktailImg = (activeRecipe?.image_url || activeRecipe?.card_image_url) || z.recipe_image || z.recipe_card_image || null;
              return (
                <ZoneRect key={z.id} cols={field.cols} rows={field.rows} zone={z}>
                  {cocktailImg ? (
                    <img src={mediaUrl(cocktailImg)} alt="" style={{ position: 'absolute', inset: 0, width: '100%', height: '100%', objectFit: 'contain', pointerEvents: 'none' }} />
                  ) : (
                    <div style={{ fontSize: 'clamp(24px,8vw,52px)', lineHeight: 1 }}>🍹</div>
                  )}
                </ZoneRect>
              );
            })}
          </>
        )}
      </LocationMap>

      {msg && <Toast text={msg} onClose={() => setMsg(null)} />}

      {showBook && field && (
        <Modal title="📖 Книга коктейлей" onClose={() => setShowBook(false)}>
          {activeShaker && (
            <div className="fm-card" style={{ marginBottom: 10, fontSize: 13 }}>
              Уже установлен шейкер с рецептом «{activeShaker.recipe_name}». Сначала смешайте коктейль.
            </div>
          )}
          {recipes.length === 0 ? (
            <div className="fm-card" style={{ color: 'var(--text-muted)' }}>В этом баре нет привязанных коктейлей.</div>
          ) : (
            <>
              <Swiper
                onSwiper={setSwiper}
                onSlideChange={(s) => setBookPage(s.activeIndex)}
                slidesPerView={1}
                spaceBetween={0}
                initialSlide={bookInitialSlide}
                style={{ paddingBottom: 4 }}
              >
                {recipes.map((r) => (
                  <SwiperSlide key={r.id}>
                    <div style={{ textAlign: 'center' }}>
                      {(r.card_image_url || r.image_url) ? (
                        <img
                          src={mediaUrl(r.card_image_url || r.image_url!)}
                          alt={r.name}
                          onClick={() => setZoomedImg(mediaUrl(r.card_image_url || r.image_url!))}
                          style={{ maxWidth: '100%', maxHeight: 260, borderRadius: 10, objectFit: 'contain', cursor: 'zoom-in' }}
                        />
                      ) : (
                        <div style={{ height: 160, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 64, background: 'rgba(255,255,255,0.04)', borderRadius: 10 }}>🍹</div>
                      )}
                      <div style={{ marginTop: 10 }}>
                        <strong style={{ fontSize: 17 }}>{r.unlocked ? '' : '🔒 '}{r.name}</strong>
                      </div>
                      <div style={{ fontSize: 13, color: 'var(--accent-warm)', fontWeight: 600, marginTop: 4 }}>
                        🪙 Награда: {r.reward_coins}
                      </div>
                      <div style={{ fontSize: 13, color: 'var(--text-secondary)', marginTop: 4 }}>
                        Состав: {r.items.map((i) => `${i.name || COCKTAIL_KIND_LABEL[i.kind]} ×${i.qty}`).join(', ')}
                      </div>
                      {r.description && <p style={{ fontSize: 13, color: 'var(--text-secondary)', margin: '6px 0' }}>{r.description}</p>}
                      {!r.unlocked && r.patient_name && (
                        <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 4 }}>
                          Вылечите «{r.patient_name}»
                        </div>
                      )}
                    </div>
                  </SwiperSlide>
                ))}
              </Swiper>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: 12 }}>
                <button className="fm-btn fm-btn-outline" style={{ minWidth: 60 }} disabled={!swiper || swiper.isBeginning} onClick={() => swiper?.slidePrev()}>◀</button>
                <span style={{ fontSize: 13, color: 'var(--text-muted)' }}>{bookPage + 1} / {recipes.length}</span>
                <button className="fm-btn fm-btn-outline" style={{ minWidth: 60 }} disabled={!swiper || swiper.isEnd} onClick={() => swiper?.slideNext()}>▶</button>
              </div>
              <button
                className="fm-btn"
                style={{ width: '100%', marginTop: 12 }}
                disabled={busy || !!activeShaker || !recipes[bookPage]?.unlocked}
                onClick={() => installShaker(recipes[bookPage].id)}
              >
                {recipes[bookPage]?.unlocked ? '🍸 Установить шейкер' : '🔒 Рецепт закрыт'}
              </button>
            </>
          )}
        </Modal>
      )}

      {shakerModal && activeShaker && (
        <Modal title={`🍸 ${activeShaker.recipe_name ?? 'Шейкер'}`} onClose={() => setShakerModal(false)}>
          <div style={{ fontSize: 13, color: 'var(--text-muted)', marginBottom: 8 }}>
            Соберите все ингредиенты, чтобы смешать коктейль.
          </div>
          <div className="fm-grid" style={{ marginBottom: 10 }}>
            {activeShaker.items.map((it, idx) => (
              <div key={idx} className="fm-card" style={{ textAlign: 'center', fontSize: 13, background: it.enough ? 'rgba(111,174,74,0.18)' : undefined }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: 30 }}>
                  {it.image_url ? (
                    <img src={mediaUrl(it.image_url)} alt="" style={{ maxHeight: 28, maxWidth: '90%', objectFit: 'contain' }} />
                  ) : (
                    <span style={{ fontSize: 20 }}>{it.emoji || COCKTAIL_KIND_ICON[it.kind] || '❓'}</span>
                  )}
                </div>
                <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>{it.name || COCKTAIL_KIND_LABEL[it.kind] || it.kind}</div>
                <div style={{ fontSize: 11, color: it.enough ? 'var(--success)' : 'var(--accent-warm)' }}>
                  {it.have}/{it.qty} {it.enough ? '✓' : ''}
                </div>
              </div>
            ))}
          </div>
          {activeShaker.items.every((i) => i.enough) ? (
            <button className="fm-btn" style={{ width: '100%' }} disabled={busy} onClick={mixNow}>🍸 Смешать коктейль</button>
          ) : (
            <div className="fm-card" style={{ fontSize: 13, color: 'var(--text-muted)' }}>Не хватает ингредиентов.</div>
          )}
        </Modal>
      )}

      {mixVideoOpen && mixVideoUrl && (
        <Modal title="🍸 Смешивание коктейля" onClose={endMixVideo}>
          <video
            src={mixVideoUrl}
            autoPlay
            muted
            playsInline
            style={{ width: '100%', maxHeight: '55vh', borderRadius: 8 }}
            onEnded={endMixVideo}
            onError={endMixVideo}
          />
          <button className="fm-btn fm-btn-sm fm-btn-outline" style={{ marginTop: 6 }} onClick={endMixVideo}>
            Пропустить
          </button>
        </Modal>
      )}

      {zoomedImg && (
        <div
          style={{ position: 'fixed', inset: 0, zIndex: 80, background: 'rgba(0,0,0,0.7)', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 16 }}
          onClick={() => setZoomedImg(null)}
        >
          <img src={zoomedImg} alt="" style={{ maxWidth: '90vw', maxHeight: '80vh', borderRadius: 10 }} />
        </div>
      )}
    </>
  );
}

function ZoneRect({ cols, rows, zone, children, onClick }: { cols: number; rows: number; zone: BarZone; children: React.ReactNode; onClick?: () => void }) {
  const spanCols = zone.col2 - zone.col1 + 1;
  const spanRows = zone.row2 - zone.row1 + 1;
  return (
    <div
      style={{
        position: 'absolute', inset: 0, pointerEvents: 'none', display: 'grid',
        gridTemplateColumns: `repeat(${cols}, 1fr)`,
        gridTemplateRows: `repeat(${rows}, 1fr)`,
      }}
    >
      <div
        onClick={onClick}
        style={{
          gridColumn: `${zone.col1 + 1} / span ${spanCols}`,
          gridRow: `${zone.row1 + 1} / span ${spanRows}`,
          position: 'relative', display: 'flex', flexDirection: 'column',
          alignItems: 'center', justifyContent: 'center',
          padding: 2, overflow: 'hidden', borderRadius: 6,
          border: '2px dashed rgba(220,170,90,0.6)',
          cursor: onClick ? 'pointer' : 'default', touchAction: 'manipulation', pointerEvents: 'auto',
        }}
      >
        {children}
      </div>
    </div>
  );
}
