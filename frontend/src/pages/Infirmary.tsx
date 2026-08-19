import { useCallback, useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { api, type DiagnoseResult, type HandbookDisease, type InfirmaryDetail, type InfirmaryZone } from '../api/endpoints';
import { mediaUrl } from '../api/media';
import LocationMap from '../components/LocationMap';
import Toast from '../components/Toast';

export default function InfirmaryPage() {
  const { id } = useParams<{ id: string }>();
  const nav = useNavigate();
  const [detail, setDetail] = useState<InfirmaryDetail | null>(null);
  const [handbook, setHandbook] = useState<HandbookDisease[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  const [symptoms, setSymptoms] = useState<{ part_code: string; symptoms: string[] } | null>(null);
  const [showHandbook, setShowHandbook] = useState(false);
  const [diagId, setDiagId] = useState<number | ''>('');
  const [result, setResult] = useState<DiagnoseResult | null>(null);
  const [showDiagnose, setShowDiagnose] = useState(false);
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

  async function doDiagnose() {
    if (!detail?.patient_id || diagId === '') return;
    setBusy(true);
    setMsg(null);
    try {
      const res = await api.diagnosePatient(detail.patient_id, Number(diagId));
      setResult(res);
      setShowDiagnose(false);
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

  const stageImage = detail?.status === 'treated'
    ? (detail.healthy_image_url || detail.patient_image_url)
    : detail?.status === 'diagnosed'
      ? (detail.hospital_image_url || detail.patient_image_url)
      : detail?.patient_image_url;

  const animalZone = (detail?.infirmary_zones ?? []).find((z) => z.zone_kind === 'animal') ?? null;
  const bookZone = (detail?.infirmary_zones ?? []).find((z) => z.zone_kind === 'book') ?? null;
  const canExamine = detail?.status === 'sick' && !!detail.patient_id;
  const active = !!detail?.patient_id && detail.status !== 'released';

  return (
    <>
      <LocationMap mapUrl={detail?.map_url ?? null} name={detail?.name ?? ''} emoji="🌲" onBack={() => nav('/fields')}>
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
                      background: canExamine ? 'rgba(220,150,120,0.30)' : 'rgba(220,150,120,0.12)',
                      cursor: canExamine ? 'pointer' : 'default',
                      touchAction: canExamine ? 'manipulation' : 'auto',
                      display: 'flex', alignItems: 'center', justifyContent: 'center',
                      fontSize: 'clamp(16px, 5vw, 38px)', lineHeight: 1,
                    }}
                  >
                    🔍
                  </div>
                );
              }),
            )}
          </div>
        )}

        {detail && animalZone && active && (
          <ZoneRect cols={detail.cols} rows={detail.rows} zone={animalZone} border="rgba(220,150,120,0.6)">
            <div onClick={doPet} style={{ position: 'absolute', inset: 0, cursor: 'grabbing', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              {stageImage ? (
                <img src={mediaUrl(stageImage)} alt="" style={{ width: '100%', height: '100%', objectFit: 'contain', pointerEvents: 'none' }} />
              ) : (
                <div style={{ fontSize: '9vw', lineHeight: 1, pointerEvents: 'none' }}>🐾</div>
              )}
            </div>
          </ZoneRect>
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
            <button className="fm-btn" onClick={() => { setDiagId(''); setResult(null); setShowDiagnose(true); }}>🩺 Поставить диагноз</button>
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
          <button className="fm-btn fm-btn-outline" onClick={() => setShowHandbook(true)}>📖 Справочник</button>
        </div>
      )}

      {detail && !active && (
        <div style={{ position: 'fixed', left: 12, right: 12, bottom: 'calc(12px + var(--vk-inset-bottom, 0px))', zIndex: 30 }}>
          <div className="fm-card" style={{ textAlign: 'center', margin: 0 }}>
            {detail.patient_id == null ? 'В этой лечебнице пока нет пациента.' : 'Животное выпущено на волю. Карточка в коллекции.'}
          </div>
        </div>
      )}

      {msg && <Toast text={msg} onClose={() => setMsg(null)} />}

      {symptoms && (
        <Modal title={`🔍 Осмотр «${symptoms.part_code}»`} onClose={() => setSymptoms(null)}>
          {symptoms.symptoms.length === 0 ? (
            <div style={{ color: 'var(--text-muted)' }}>В этой части тела всё спокойно.</div>
          ) : (
            <ul style={{ margin: '6px 0 0 18px' }}>
              {symptoms.symptoms.map((s, i) => <li key={i}>{s}</li>)}
            </ul>
          )}
        </Modal>
      )}

      {showDiagnose && detail?.patient_id && (
        <Modal title="🩺 Поставить диагноз" onClose={() => setShowDiagnose(false)}>
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
            </div>
          ) : (
            <>
              <select className="fm-input" value={diagId} onChange={(e) => setDiagId(Number(e.target.value))}>
                <option value="">— выберите болезнь —</option>
                {handbook.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
              </select>
              <button className="fm-btn" style={{ width: '100%', marginTop: 10 }} disabled={busy || diagId === ''} onClick={doDiagnose}>
                Диагностировать
              </button>
              <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 6 }}>
                Неверный диагноз — минус 200 крестиков.
              </div>
            </>
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

      {showHandbook && (
        <Modal title="📖 Справочник болезней" onClose={() => setShowHandbook(false)}>
          {handbook.map((d) => (
            <div key={d.id} className="fm-card" style={{ marginBottom: 8 }}>
              <strong>{d.name}</strong>
              {d.remedy_name && <span style={{ color: 'var(--text-secondary)' }}> — мазь: {d.remedy_name}</span>}
              <ul style={{ margin: '6px 0 0 18px', fontSize: 13 }}>
                {d.symptoms.map((s, i) => <li key={i}>{s.part_code}: {s.text}</li>)}
              </ul>
            </div>
          ))}
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
