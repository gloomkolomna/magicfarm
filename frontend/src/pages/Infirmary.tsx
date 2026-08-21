import { useCallback, useEffect, useRef, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { Swiper, SwiperSlide } from 'swiper/react';
import type { Swiper as SwiperInstance } from 'swiper';
import 'swiper/css';
import { api, BODY_PART_LABELS, type DiagnoseResult, type HandbookDisease, type Infirmary, type InfirmaryDetail, type InfirmaryZone } from '../api/endpoints';
import { mediaUrl } from '../api/media';
import HeartsBurst from '../components/HeartsBurst';
import InfirmaryBackground from '../components/InfirmaryBackground';
import LocationMap from '../components/LocationMap';
import StitchReportForm from '../components/StitchReportForm';
import Toast from '../components/Toast';

const LOCATION_META: Record<string, { emoji: string; route: string }> = {
  infirmary: { emoji: '🌲', route: '/infirmary/' },
  meadow: { emoji: '🌿', route: '/meadow/' },
  shop: { emoji: '🛒', route: '/shop/' },
  remedy_lab: { emoji: '⚗️', route: '/remedy-lab/' },
  forest_bar: { emoji: '🍹', route: '/forest-bar/' },
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
    <>
      <InfirmaryBackground />
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
          {current.status === 'diagnosed' && current.remedy_lab_field_id != null && (
            <button className="fm-btn" style={{ width: '100%', marginTop: 10 }} onClick={() => nav(`/remedy-lab/${current.remedy_lab_field_id}`)}>
              ⚗️ Сварить лекарство
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

      <h2 style={{ fontSize: 16, margin: '16px 0 8px' }}>💭 Воспоминания</h2>
      {(hub?.memories ?? []).length === 0 ? (
        <div className="fm-card" style={{ color: 'var(--text-muted)', fontSize: 13 }}>Пока никого не вылечили.</div>
      ) : (
        <div className="fm-grid">
          {(hub?.memories ?? []).map((m) => (
            <div key={m.patient_id} className="fm-card fm-rise" style={{ textAlign: 'center' }}>
              {m.healthy_image_url ? (
                <img src={mediaUrl(m.healthy_image_url)} alt="" style={{ width: '100%', maxHeight: 120, objectFit: 'contain', marginBottom: 6, borderRadius: 8 }} />
              ) : (
                <div style={{ fontSize: 40, lineHeight: '120px' }}>🐾</div>
              )}
              <strong style={{ display: 'block', fontSize: 13 }}>{m.name}</strong>
              <div style={{ fontSize: 12, color: 'var(--success)' }}>Здорово ✅</div>
            </div>
          ))}
        </div>
      )}
      </div>
    </>
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

  const [symptoms, setSymptoms] = useState<{ part_code: string; symptoms: string[]; first_time?: boolean; penalty_due?: number } | null>(null);
  const [showHandbook, setShowHandbook] = useState(false);
  const [penaltyPayOpen, setPenaltyPayOpen] = useState(false);
  const [result, setResult] = useState<DiagnoseResult | null>(null);
  const [showWellbeing, setShowWellbeing] = useState(false);
  const [previewImage, setPreviewImage] = useState<string | null>(null);
  const [hearts, setHearts] = useState<{ x: number; y: number; k: number } | null>(null);
  const [healVideoUrl, setHealVideoUrl] = useState<string | null>(null);
  const [healVideoOpen, setHealVideoOpen] = useState(false);
  const [healDoneMsg, setHealDoneMsg] = useState<string | null>(null);
  const [bookImgUrl, setBookImgUrl] = useState<string | null>(null);
  const [previewScale, setPreviewScale] = useState(1);
  const [previewPan, setPreviewPan] = useState({ x: 0, y: 0 });
  const previewBoxRef = useRef<HTMLDivElement | null>(null);
  const previewImgRef = useRef<HTMLImageElement | null>(null);
  const [swiper, setSwiper] = useState<SwiperInstance | null>(null);
  const [bookPage, setBookPage] = useState(0);

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
    api.gameMediaByCode('remedy_heal')
      .then((gm) => { if (gm.url) setHealVideoUrl(mediaUrl(gm.url)); })
      .catch(() => {});
    api.gameMediaByCode('infirmary_book')
      .then((gm) => { if (gm.url) setBookImgUrl(mediaUrl(gm.url)); })
      .catch(() => {});
  }, []);
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
      await load();
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

  function doPet(e: React.MouseEvent<HTMLButtonElement>) {
    if (!detail?.patient_name) return;
    setMsg(`🤚 Вы погладили ${detail.patient_name}.`);
    setHearts({ x: e.clientX, y: e.clientY, k: Date.now() });
  }

  async function doGiveRemedy() {
    if (!detail?.patient_id) return;
    setBusy(true);
    setMsg(null);
    try {
      const res = await api.giveRemedy(detail.patient_id);
      const doneMsg = `💊 ${res.patient_name}: лекарство дано, животное здорово!`
        + (res.otter_granted ? ' 🦦 Выдра стала вашим шестым волшебным питомцем — смотрите Лужайку питомцев!' : '');
      await load();
      if (healVideoUrl) {
        setHealDoneMsg(doneMsg);
        setHealVideoOpen(true);
      } else {
        setMsg(doneMsg);
      }
    } catch (e: any) {
      setMsg('✗ ' + (e?.response?.data?.detail || 'Ошибка'));
    } finally {
      setBusy(false);
    }
  }

  function endHealVideo() {
    setHealVideoOpen(false);
    if (healDoneMsg) {
      setMsg(healDoneMsg);
      setHealDoneMsg(null);
    }
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
      <InfirmaryBackground />
      <LocationMap mapUrl={detail?.map_url ?? null} name={detail?.name ?? ''} emoji="🌲" onBack={() => nav('/infirmary')}>
        {detail && detail.status === 'sick' && (
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
                const examined = (detail.examined_parts ?? []).includes(pc.part_code);
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
                      position: 'relative',
                    }}
                  >
                    🔍
                    {examined && (
                      <span style={{ position: 'absolute', top: 2, right: 3, fontSize: 'clamp(8px,2vw,11px)', fontWeight: 700, color: '#ffd9a0', background: 'rgba(10,16,8,0.6)', borderRadius: 5, padding: '0 3px', pointerEvents: 'none' }}>
                        ❆100
                      </span>
                    )}
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
              {bookImgUrl ? (
                <img src={bookImgUrl} alt="" draggable={false} style={{ maxWidth: '92%', maxHeight: '92%', objectFit: 'contain', pointerEvents: 'none' }} />
              ) : (
                '📖'
              )}
            </div>
          </ZoneRect>
        )}
      </LocationMap>

      {detail && active && (
        <>
          {(detail.penalty_due ?? 0) > 0 && detail.patient_id != null && (
            <div style={{ position: 'fixed', top: 'calc(44px + var(--vk-inset-top, 0px))', left: 12, right: 12, zIndex: 30, maxWidth: 560, margin: '0 auto', display: 'flex', alignItems: 'center', gap: 8, background: 'rgba(200,90,90,0.22)', border: '1px solid #c66', borderRadius: 'var(--radius-md)', padding: '6px 10px', boxShadow: '0 2px 10px rgba(0,0,0,0.35)' }}>
              <span style={{ flex: 1, fontSize: 13, color: '#ffb3b3', fontWeight: 700, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                ⚠️ Штраф: {detail.penalty_due} ❆ — диагноз после оплаты
              </span>
              <button className="fm-btn fm-btn-sm" onClick={() => setPenaltyPayOpen(true)}>💳 Оплатить</button>
            </div>
          )}

          <div style={{ position: 'fixed', left: 12, right: 76, bottom: 'calc(12px + var(--vk-inset-bottom, 0px))', zIndex: 30, display: 'flex', gap: 8, flexWrap: 'wrap', justifyContent: 'center' }}>
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
              <button
                className="fm-btn"
                disabled={(detail.penalty_due ?? 0) > 0}
                title={(detail.penalty_due ?? 0) > 0 ? `Сначала отшейте штраф ${detail.penalty_due} ❆` : ''}
                onClick={() => { setResult(null); setShowHandbook(true); }}
              >
                🩺 Поставить диагноз
              </button>
            )
          )}
          {detail.status === 'diagnosed' && (
            <>
              <button className="fm-btn fm-btn-outline" title="Погладить" aria-label="Погладить" onClick={doPet}>🤚</button>
              <button className="fm-btn" disabled={busy} onClick={doGiveRemedy}>💊 Дать лекарство</button>
              {detail.remedy_lab_field_id != null && (
                <button className="fm-btn" onClick={() => nav(`/remedy-lab/${detail.remedy_lab_field_id}`)}>⚗️ Сварить лекарство</button>
              )}
              <button className="fm-btn" onClick={() => setShowWellbeing(true)}>💊 Самочувствие</button>
            </>
          )}
          {detail.status === 'treated' && (
            <>
              <button className="fm-btn fm-btn-outline" title="Погладить" aria-label="Погладить" onClick={doPet}>🤚</button>
              <button className="fm-btn" disabled={busy} onClick={doRelease}>🕊 Выпустить на волю</button>
            </>
          )}
          <button className="fm-btn fm-btn-outline" onClick={() => { setResult(null); setShowHandbook(true); }}>📖 Книга болезней</button>
        </div>
        </>
      )}

      {healVideoOpen && healVideoUrl && (
        <Modal title="💊 Лечение животного" onClose={endHealVideo}>
          <video
            src={healVideoUrl}
            autoPlay
            muted
            playsInline
            style={{ width: '100%', maxHeight: '55vh', borderRadius: 8 }}
            onEnded={endHealVideo}
            onError={endHealVideo}
          />
          <button className="fm-btn fm-btn-sm fm-btn-outline" style={{ marginTop: 6 }} onClick={endHealVideo}>
            Пропустить
          </button>
        </Modal>
      )}

      {detail && !active && (
        <div style={{ position: 'fixed', left: 12, right: 76, bottom: 'calc(12px + var(--vk-inset-bottom, 0px))', zIndex: 30 }}>
          <div className="fm-card" style={{ textAlign: 'center', margin: 0 }}>
            {detail.patient_id == null ? 'В этой локации пока нет пациента.' : 'Животное выпущено на волю. Карточка в коллекции.'}
          </div>
        </div>
      )}

      {msg && <Toast text={msg} onClose={() => setMsg(null)} />}
      {hearts && <HeartsBurst key={hearts.k} x={hearts.x} y={hearts.y} />}

      {symptoms && (
        <Modal title={`🔍 Осмотр «${BODY_PART_LABELS[symptoms.part_code] || symptoms.part_code}»`} onClose={() => setSymptoms(null)}>
          {symptoms.first_time === false && (
            <div className="fm-card" style={{ background: 'rgba(200,90,90,0.14)', border: '1px solid #c66', fontSize: 13, marginBottom: 8 }}>
              ⚠️ Повторный осмотр: +100 ❆ в долг (всего {symptoms.penalty_due ?? 0}). Перед диагнозом долг нужно отшить.
            </div>
          )}
          {symptoms.symptoms.length === 0 ? (
            <div style={{ color: 'var(--text-muted)' }}>В этой части тела всё спокойно.</div>
          ) : (
            <ul style={{ margin: '6px 0 0 18px' }}>
              {symptoms.symptoms.map((s, i) => <li key={i}>{s}</li>)}
            </ul>
          )}
        </Modal>
      )}

      {penaltyPayOpen && detail && (
        <Modal title={`⚠️ Штраф: ${detail.penalty_due} ❆`} onClose={() => setPenaltyPayOpen(false)}>
          <p style={{ fontSize: 13, color: 'var(--text-secondary)', margin: '0 0 8px' }}>
            Чтобы поставить диагноз, отшейте штраф — {detail.penalty_due} крестиков.
          </p>
          <StitchReportForm
            contextType="infirmary_penalty"
            contextId={detail.patient_id}
            required={detail.penalty_due ?? 0}
            busy={busy}
            onDone={async () => { setMsg('✓ Штраф отшит!'); setPenaltyPayOpen(false); await load(); }}
          />
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
            <>
              <Swiper
                onSwiper={setSwiper}
                onSlideChange={(s) => setBookPage(s.activeIndex)}
                slidesPerView={1}
                spaceBetween={0}
                initialSlide={0}
                style={{ paddingBottom: 4 }}
              >
                {handbook.map((d) => (
                  <SwiperSlide key={d.id}>
                    <div style={{ textAlign: 'center' }}>
                      {d.image_url ? (
                        <img
                          src={mediaUrl(d.image_url)}
                          alt={d.name}
                          onClick={() => { setPreviewScale(1); setPreviewImage(mediaUrl(d.image_url)); }}
                          style={{ maxWidth: '100%', maxHeight: 240, borderRadius: 10, objectFit: 'contain', cursor: 'zoom-in' }}
                        />
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
                  </SwiperSlide>
                ))}
              </Swiper>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: 12 }}>
                <button className="fm-btn fm-btn-outline" style={{ minWidth: 60 }} disabled={!swiper || swiper.isBeginning} onClick={() => swiper?.slidePrev()}>◀</button>
                <span style={{ fontSize: 13, color: 'var(--text-muted)' }}>{bookPage + 1} / {handbook.length}</span>
                <button className="fm-btn fm-btn-outline" style={{ minWidth: 60 }} disabled={!swiper || swiper.isEnd} onClick={() => swiper?.slideNext()}>▶</button>
              </div>
              {detail?.status === 'sick' && detail?.patient_id && handbook[bookPage] && (
                <button className="fm-btn" style={{ width: '100%', marginTop: 12, whiteSpace: 'normal', overflowWrap: 'anywhere', lineHeight: 1.3 }} disabled={busy} onClick={() => doDiagnose(handbook[bookPage].id)}>
                  🩺 Выбрать «{handbook[bookPage].name}»
                </button>
              )}
            </>
          )}
        </Modal>
      )}

      {previewImage && (
        <Modal title="🔍" onClose={() => setPreviewImage(null)}>
          <div style={{ display: 'flex', justifyContent: 'center', gap: 8, marginBottom: 10, alignItems: 'center' }}>
            <button className="fm-btn fm-btn-outline" onClick={() => { setPreviewScale((s) => Math.min(4, s + 0.5)); setPreviewPan({ x: 0, y: 0 }); }}>＋</button>
            <span style={{ fontSize: 13, color: 'var(--text-muted)', minWidth: 44, textAlign: 'center' }}>{Math.round(previewScale * 100)}%</span>
            <button className="fm-btn fm-btn-outline" onClick={() => { setPreviewScale(1); setPreviewPan({ x: 0, y: 0 }); }}>⤢</button>
            <button className="fm-btn fm-btn-outline" onClick={() => { setPreviewScale((s) => Math.max(0.5, s - 0.5)); setPreviewPan({ x: 0, y: 0 }); }}>−</button>
          </div>
          <div
            ref={previewBoxRef}
            style={{ overflow: 'hidden', height: '70vh', display: 'flex', alignItems: 'center', justifyContent: 'center', borderRadius: 10, touchAction: 'none', cursor: previewScale > 1 ? 'grab' : 'default' }}
            onPointerDown={(e) => {
              if (previewScale <= 1) return;
              e.preventDefault();
              const startX = e.clientX;
              const startY = e.clientY;
              const baseX = previewPan.x;
              const baseY = previewPan.y;
              const onMove = (ev: PointerEvent) => {
                const dx = ev.clientX - startX;
                const dy = ev.clientY - startY;
                const box = previewBoxRef.current;
                const img = previewImgRef.current;
                let maxX = 0;
                let maxY = 0;
                if (box && img) {
                  maxX = Math.max(0, (img.clientWidth * previewScale - box.clientWidth) / 2);
                  maxY = Math.max(0, (img.clientHeight * previewScale - box.clientHeight) / 2);
                }
                setPreviewPan({
                  x: Math.max(-maxX, Math.min(maxX, baseX + dx)),
                  y: Math.max(-maxY, Math.min(maxY, baseY + dy)),
                });
              };
              const onUp = () => {
                window.removeEventListener('pointermove', onMove);
                window.removeEventListener('pointerup', onUp);
                window.removeEventListener('pointercancel', onUp);
              };
              window.addEventListener('pointermove', onMove);
              window.addEventListener('pointerup', onUp);
              window.addEventListener('pointercancel', onUp);
            }}
          >
            <img
              ref={previewImgRef}
              src={previewImage}
              alt=""
              draggable={false}
              style={{
                maxWidth: '100%',
                maxHeight: '100%',
                objectFit: 'contain',
                transform: `translate(${previewPan.x}px, ${previewPan.y}px) scale(${previewScale})`,
                transition: 'transform 0.15s ease',
                borderRadius: 10,
                userSelect: 'none',
                WebkitUserSelect: 'none',
                pointerEvents: 'none',
              }}
            />
          </div>
          {previewScale > 1 && (
            <div style={{ fontSize: 12, color: 'var(--text-muted)', textAlign: 'center', marginTop: 8 }}>
              Тяните изображение, чтобы рассмотреть детали
            </div>
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
