import { useCallback, useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { Swiper, SwiperSlide } from 'swiper/react';
import { Navigation } from 'swiper/modules';
import 'swiper/css';
import 'swiper/css/navigation';
import { api, BODY_PART_LABELS, type DiagnoseResult, type HandbookDisease, type Infirmary, type InfirmaryDetail, type InfirmaryZone } from '../api/endpoints';
import { mediaUrl } from '../api/media';
import LocationMap from '../components/LocationMap';
import Toast from '../components/Toast';

const LOCATION_META: Record<string, { emoji: string; route: string }> = {
  infirmary: { emoji: '🌲', route: '/infirmary/' },
  meadow: { emoji: '🌿', route: '/meadow/' },
  shop: { emoji: '🛒', route: '/shop/' },
  remedy_lab: { emoji: '⚗️', route: '/remedy-lab/' },
};

export default function InfirmaryHubPage() {
  const nav = useNavigate();
  const [hub, setHub] = useState<Infirmary | null>(null);
  const [loading, setLoading] = useState(true);
  const [msg, setMsg] = useState<string | null>(null);

  const load = useCallback(() => {
    setLoading(true);
    api.infirmary()
      .then(setHub)
      .catch((e) => setMsg('✗ ' + (e?.response?.data?.detail || 'Ошибка')))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => { load(); }, [load]);
  useEffect(() => {
    if (!msg) return;
    const t = setTimeout(() => setMsg(null), 4000);
    return () => clearTimeout(t);
  }, [msg]);

  if (loading && !hub) {
    return (
      <div style={{ maxWidth: 'var(--shell-max-width)', margin: '0 auto', padding: 'var(--shell-pad)' }}>
        <div className="fm-card">Загрузка лечебницы…</div>
      </div>
    );
  }

  const current = hub?.current ?? null;
  const currentScene = current?.current_field_id
    ? (current.scenes.find((s) => s.field_id === current.current_field_id) ?? current.scenes[0])
    : (current?.scenes[0] ?? null);

  return (
    <div style={{ maxWidth: 'var(--shell-max-width)', margin: '0 auto', padding: 'var(--shell-pad)' }}>
      <h1 style={{ fontSize: 20, margin: '0 0 10px' }}>🌲 Лесная лечебница</h1>
      {msg && <Toast text={msg} onClose={() => setMsg(null)} />}

      {current ? (
        <div className="fm-card fm-rise" style={{ marginBottom: 14 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            {current.animal_image_url ? (
              <img src={mediaUrl(current.animal_image_url)} alt={current.name} style={{ width: 52, height: 52, borderRadius: 12, objectFit: 'cover' }} />
            ) : (
              <div style={{ fontSize: 34, lineHeight: 1 }}>{current.animal_type_emoji || '🐾'}</div>
            )}
            <div style={{ flex: 1, minWidth: 0 }}>
              <strong style={{ fontSize: 17 }}>{current.name}</strong>
              <div style={{ fontSize: 12, color: 'var(--text-secondary)' }}>
                {current.animal_type_name || 'Животное'} · уровень {current.level}
              </div>
              {current.disease_name && current.status !== 'sick' && (
                <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>
                  Болезнь: {current.disease_name}
                </div>
              )}
              <div style={{ fontSize: 12, marginTop: 2 }}>
                {current.status === 'sick' && <span>🤒 Осмотрите животное и поставьте диагноз</span>}
                {current.status === 'diagnosed' && <span>🏥 Сварите лекарство в лаборатории снадобий</span>}
                {current.status === 'treated' && <span>✅ Животное вылечено — выпустите на волю</span>}
                {current.status === 'released' && <span>🕊 Животное выпущено</span>}
              </div>
            </div>
          </div>
          {currentScene && (
            <button className="fm-btn" style={{ width: '100%', marginTop: 10 }} onClick={() => nav(`/infirmary/${currentScene.field_id}`)}>
              Перейти в лечебницу
            </button>
          )}
        </div>
      ) : (
        <div className="fm-card" style={{ marginBottom: 14, color: 'var(--text-muted)' }}>
          Пока нет животных на лечении.
        </div>
      )}

      <h3 style={{ margin: '0 0 8px' }}>Локации лечебницы</h3>
      <div className="fm-grid" style={{ marginBottom: 14 }}>
        {(hub?.locations ?? []).map((loc) => {
          const meta = LOCATION_META[loc.field_kind] ?? { emoji: '🗺️', route: '/field/' };
          return (
            <button
              key={loc.field_id}
              className="fm-card fm-rise"
              onClick={() => nav(meta.route + loc.field_id)}
              style={{ cursor: 'pointer', textAlign: 'left', display: 'block' }}
            >
              <strong style={{ fontSize: 16 }}>{meta.emoji} {loc.name}</strong>
              {loc.map_url && (
                <img src={mediaUrl(loc.map_url)} alt="" style={{ width: '100%', marginTop: 8, borderRadius: 'var(--radius-sm)' }} />
              )}
            </button>
          );
        })}
        {(hub?.locations.length ?? 0) === 0 && (
          <div className="fm-card" style={{ color: 'var(--text-muted)' }}>Локации лечебницы ещё не созданы.</div>
        )}
      </div>

      <h3 style={{ margin: '0 0 8px' }}>Пациенты по уровням</h3>
      {(hub?.levels ?? []).map((lv) => (
        <div key={lv.level} className="fm-card" style={{ marginBottom: 8, padding: 10 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 }}>
            <strong>Уровень {lv.level}</strong>
            {!lv.unlocked && <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>🔒 Вылечите всех животных прошлого уровня</span>}
          </div>
          <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
            {lv.patients.length === 0 && <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>Животных нет</span>}
            {lv.patients.map((p) => (
              <span key={p.id} className="fm-card" style={{ padding: '4px 10px', fontSize: 13, opacity: lv.unlocked ? 1 : 0.55, display: 'inline-flex', alignItems: 'center', gap: 6 }}>
                {p.animal_image_url
                  ? <img src={mediaUrl(p.animal_image_url)} alt="" style={{ width: 22, height: 22, borderRadius: 6, objectFit: 'cover' }} />
                  : <span>{p.animal_type_emoji || '🐾'}</span>}
                {p.name}
                {p.healed ? ' ✅' : ' ⏳'}
              </span>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}

export function InfirmaryScenePage() {
  const { id } = useParams<{ id: string }>();
  const nav = useNavigate();
  const [detail, setDetail] = useState<InfirmaryDetail | null>(null);
  const [handbook, setHandbook] = useState<HandbookDisease[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  const [symptoms, setSymptoms] = useState<{ part_code: string; symptoms: string[] } | null>(null);
  const [showHandbook, setShowHandbook] = useState(false);
  const [result, setResult] = useState<DiagnoseResult | null>(null);
  const [showWellbeing, setShowWellbeing] = useState(false);

  const fieldId = Number(id);

  const load = useCallback(() => {
    if (!Number.isFinite(fieldId)) return;
    setLoading(true);
    Promise.all([
      api.infirmaryDetail(fieldId).catch(() => null),
      api.handbook().then((x) => x.diseases).catch(() => [] as HandbookDisease[]),
    ])
      .then(([d, h]) => {
        setDetail(d);
        setHandbook(h);
      })
      .catch((e) => setMsg('✗ ' + (e?.response?.data?.detail || 'Ошибка')))
      .finally(() => setLoading(false));
  }, [fieldId]);

  useEffect(() => { load(); }, [load]);
  useEffect(() => {
    if (!msg) return;
    const t = setTimeout(() => setMsg(null), 4000);
    return () => clearTimeout(t);
  }, [msg]);

  async function doExamine(partCode: string) {
    if (!detail?.patient_id) return;
    setBusy(true);
    setMsg(null);
    setResult(null);
    try {
      const res = await api.examinePatient(detail.patient_id, partCode);
      setSymptoms(res);
    } catch (e: any) {
      setMsg('✗ ' + (e?.response?.data?.detail || 'Ошибка'));
    } finally {
      setBusy(false);
    }
  }

  async function doDiagnose(diseaseId: number) {
    if (!detail?.patient_id) return;
    setBusy(true);
    setMsg(null);
    try {
      const res = await api.diagnosePatient(detail.patient_id, diseaseId);
      setResult(res);
      await load();
    } catch (e: any) {
      setMsg('✗ ' + (e?.response?.data?.detail || 'Ошибка'));
    } finally {
      setBusy(false);
    }
  }

  async function doRelease() {
    if (!detail?.patient_id) return;
    setBusy(true);
    setMsg(null);
    try {
      const res = await api.releasePatient(detail.patient_id);
      setMsg(`✓ ${res.patient_name} выпущен на волю! Карточка в коллекции.`);
      await load();
    } catch (e: any) {
      setMsg('✗ ' + (e?.response?.data?.detail || 'Ошибка'));
    } finally {
      setBusy(false);
    }
  }

  function doPet() {
    if (!detail?.patient_name) return;
    setMsg(`🤚 Вы погладили ${detail.patient_name}.`);
  }

  if (loading && !detail) {
    return (
      <div style={{ maxWidth: 'var(--shell-max-width)', margin: '0 auto', padding: 'var(--shell-pad)' }}>
        <div className="fm-card">Загрузка лечебницы…</div>
      </div>
    );
  }

  const bookZone = (detail?.infirmary_zones ?? []).find((z) => z.zone_kind === 'book') ?? null;
  const treatingScene = (detail?.patient_scenes ?? []).find((s) => s.stage === 'treating') ?? null;
  const isSickScene = detail?.stage === 'sick';
  const canExamine = detail?.status === 'sick' && !!detail.patient_id && detail?.stage === 'treating';
  const active = !!detail?.patient_id && detail.status !== 'released';

  return (
    <>
      <LocationMap mapUrl={detail?.map_url ?? null} name={detail?.name ?? ''} emoji="🌲" onBack={() => nav('/infirmary')}>
        {detail && (
          <div
            style={{
              position: 'absolute', inset: 0, display: 'grid',
              gridTemplateColumns: `repeat(${detail.cols}, 1fr)`,
              gridTemplateRows: `repeat(${detail.rows}, 1fr)`,
            }}
          >
            {Array.from({ length: detail.rows }).map((_, r) =>
              Array.from({ length: detail.cols }).map((__, c) => {
                const pc = (detail.part_cells ?? []).find((x) => x.col === c && x.row === r);
                if (!pc) return <div key={`empty-${c}-${r}`} />;
                return (
                  <div
                    key={`part-${pc.id}`}
                    onClick={() => { if (canExamine) doExamine(pc.part_code); }}
                    style={{
                      borderRight: c < detail.cols - 1 ? '1px solid #2a1a0e' : 'none',
                      borderBottom: r < detail.rows - 1 ? '1px solid #2a1a0e' : 'none',
                      boxShadow: 'inset 0 0 0 0.5px rgba(255,255,255,0.05)',
                      background: canExamine ? 'rgba(220,150,120,0.18)' : 'transparent',
                      cursor: canExamine ? 'pointer' : 'default',
                      touchAction: canExamine ? 'manipulation' : 'auto',
                      display: 'flex', alignItems: 'center', justifyContent: 'center',
                      fontSize: 'clamp(16px, 5vw, 38px)', lineHeight: 1,
                      opacity: canExamine ? 0.55 : 0.9,
                    }}
                  >
                    🔍
                  </div>
                );
              }),
            )}
          </div>
        )}

        {detail && bookZone && active && (
          <ZoneRect cols={detail.cols} rows={detail.rows} zone={bookZone} border="rgba(160,120,220,0.55)">
            <div
              onClick={() => setShowHandbook(true)}
              style={{ position: 'absolute', inset: 0, cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 'clamp(20px, 7vw, 52px)', lineHeight: 1 }}
            >
              📖
            </div>
          </ZoneRect>
        )}
      </LocationMap>

      {detail && active && (
        <div style={{ position: 'fixed', left: 12, right: 12, bottom: 'calc(12px + var(--vk-inset-bottom, 0px))', zIndex: 30, display: 'flex', gap: 8, flexWrap: 'wrap', justifyContent: 'center' }}>
          {detail.status === 'sick' && (
            isSickScene ? (
              <button
                className="fm-btn"
                disabled={!treatingScene}
                onClick={() => treatingScene && nav(`/infirmary/${treatingScene.field_id}`)}
              >
                🔍 Приступить к осмотру
              </button>
            ) : (
              <button className="fm-btn" onClick={() => { setResult(null); setShowHandbook(true); }}>🩺 Поставить диагноз</button>
            )
          )}
          {detail.status === 'diagnosed' && (
            <>
              <button className="fm-btn fm-btn-outline" onClick={doPet}>🤚 Погладить</button>
              <button className="fm-btn" onClick={() => setShowWellbeing(true)}>💊 Самочувствие</button>
            </>
          )}
          {detail.status === 'treated' && (
            <>
              <button className="fm-btn fm-btn-outline" onClick={doPet}>🤚 Погладить</button>
              <button className="fm-btn" disabled={busy} onClick={doRelease}>🕊 Выпустить на волю</button>
            </>
          )}
          <button className="fm-btn fm-btn-outline" onClick={() => { setResult(null); setShowHandbook(true); }}>📖 Книга болезней</button>
        </div>
      )}

      {detail && !active && (
        <div style={{ position: 'fixed', left: 12, right: 12, bottom: 'calc(12px + var(--vk-inset-bottom, 0px))', zIndex: 30 }}>
          <div className="fm-card" style={{ textAlign: 'center', margin: 0 }}>
            {detail.patient_id == null ? 'В этой локации пока нет пациента.' : 'Животное выпущено на волю. Карточка в коллекции.'}
          </div>
        </div>
      )}

      {msg && <Toast text={msg} onClose={() => setMsg(null)} />}

      {symptoms && (
        <Modal title={`🔍 Осмотр «${BODY_PART_LABELS[symptoms.part_code] || symptoms.part_code}»`} onClose={() => setSymptoms(null)}>
          {symptoms.symptoms.length === 0 ? (
            <div style={{ color: 'var(--text-muted)' }}>В этой части тела всё спокойно.</div>
          ) : (
            <ul style={{ margin: '6px 0 0 18px' }}>
              {symptoms.symptoms.map((s, i) => <li key={i}>{s}</li>)}
            </ul>
          )}
        </Modal>
      )}

      {showHandbook && (
        <Modal title="📖 Книга болезней" onClose={() => setShowHandbook(false)}>
          {result ? (
            <div className="fm-card" style={{ background: result.correct ? 'rgba(127,255,127,0.12)' : 'rgba(255,150,150,0.12)', fontSize: 14 }}>
              {result.correct ? (
                <>
                  ✓ Верно! Вы получили карточку рецепта «{result.remedy_name}».
                  <div style={{ marginTop: 6, fontSize: 13 }}>
                    Состав: {result.recipe_items.map((i) => `${i.ingredient_name || i.plant_name} ×${i.qty}`).join(', ')}
                  </div>
                  <div style={{ marginTop: 6, fontSize: 12, color: 'var(--text-muted)' }}>
                    Приготовьте лекарство в лаборатории снадобий.
                  </div>
                </>
              ) : (
                <>✗ Неверно. Штраф 200 крестиков. Баланс: {result.crosses_balance}.</>
              )}
              <button className="fm-btn fm-btn-outline" style={{ width: '100%', marginTop: 12 }} onClick={() => setResult(null)}>
                📖 Продолжить листать
              </button>
            </div>
          ) : handbook.length === 0 ? (
            <div style={{ color: 'var(--text-muted)' }}>Болезней пока нет.</div>
          ) : (
            <Swiper
              modules={[Navigation]}
              slidesPerView={1}
              spaceBetween={0}
              navigation
              initialSlide={0}
              style={{ paddingBottom: 4 }}
            >
              {handbook.map((d) => (
                <SwiperSlide key={d.id}>
                  <div style={{ textAlign: 'center' }}>
                    {d.image_url ? (
                      <img src={mediaUrl(d.image_url)} alt={d.name} style={{ maxWidth: '100%', maxHeight: 240, borderRadius: 10, objectFit: 'contain' }} />
                    ) : (
                      <div style={{ height: 160, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 64, background: 'rgba(255,255,255,0.04)', borderRadius: 10 }}>🦠</div>
                    )}
                    <div style={{ marginTop: 10 }}>
                      <strong style={{ fontSize: 17 }}>{d.name}</strong>
                    </div>
                    {d.remedy_name && (
                      <div style={{ fontSize: 13, color: 'var(--text-secondary)', marginTop: 2 }}>
                        Мазь: {d.remedy_name}
                      </div>
                    )}
                    {d.symptoms.length > 0 && (
                      <ul style={{ margin: '8px 0 0', paddingLeft: 18, textAlign: 'left', fontSize: 13 }}>
                        {d.symptoms.map((s, i) => <li key={i}>{BODY_PART_LABELS[s.part_code] || s.part_code}: {s.text}</li>)}
                      </ul>
                    )}
                  </div>
                  {detail?.status === 'sick' && detail?.patient_id && (
                    <button className="fm-btn" style={{ width: '100%', marginTop: 12 }} disabled={busy} onClick={() => doDiagnose(d.id)}>
                      🩺 Выбрать это заболевание
                    </button>
                  )}
                </SwiperSlide>
              ))}
            </Swiper>
          )}
        </Modal>
      )}

      {showWellbeing && detail && (
        <Modal title="💊 Самочувствие" onClose={() => setShowWellbeing(false)}>
          {detail.status === 'diagnosed' ? (
            <div style={{ fontSize: 14 }}>
              Это животное нуждается в лечении. Вы поставили диагноз «{detail.disease_name}» и должны приготовить лекарство «{detail.remedy_name}».
            </div>
          ) : (
            <div style={{ fontSize: 14 }}>Животное здорово! Можно выпустить его на волю.</div>
          )}
        </Modal>
      )}
    </>
  );
}

function ZoneRect({ cols, rows, zone, border, children }: { cols: number; rows: number; zone: InfirmaryZone; border: string; children: React.ReactNode }) {
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
        style={{
          gridColumn: `${zone.col1 + 1} / span ${spanCols}`,
          gridRow: `${zone.row1 + 1} / span ${spanRows}`,
          position: 'relative', overflow: 'hidden',
          border: `2px dashed ${border}`, borderRadius: 6,
          pointerEvents: 'auto',
        }}
      >
        {children}
      </div>
    </div>
  );
}

function Modal({ title, children, onClose }: { title: string; children: React.ReactNode; onClose: () => void }) {
  return (
    <div
      style={{
        position: 'fixed', inset: 0, zIndex: 60, background: 'rgba(0,0,0,0.6)', backdropFilter: 'blur(3px)',
        display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 16,
      }}
    >
      <div
        className="fm-card fm-rise"
        onClick={(e) => e.stopPropagation()}
        style={{ width: '100%', maxWidth: 'calc(var(--shell-max-width) * 0.8)', maxHeight: '85vh', overflowY: 'auto' }}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
          <h2 style={{ margin: 0 }}>{title}</h2>
          <button className="fm-btn fm-btn-xs fm-btn-outline" onClick={onClose}>✕</button>
        </div>
        {children}
      </div>
    </div>
  );
}
