import { useCallback, useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { api, type DiagnoseResult, type HandbookDisease, type InfirmaryDetail } from '../api/endpoints';
import { mediaUrl } from '../api/media';
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
      await load();
    } catch (e: any) {
      setMsg('✗ ' + (e?.response?.data?.detail || 'Ошибка'));
    } finally {
      setBusy(false);
    }
  }

  if (loading && !detail) {
    return (
      <div style={{ maxWidth: 'var(--shell-max-width)', margin: '0 auto', padding: 'var(--shell-pad)' }}>
        <div className="fm-card">Загрузка лечебницы…</div>
      </div>
    );
  }

  return (
    <div style={{ maxWidth: 'var(--shell-max-width)', margin: '0 auto', padding: 'var(--shell-pad)' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 10 }}>
        <button className="fm-btn fm-btn-outline fm-btn-xs" onClick={() => nav(-1)}>← Назад</button>
        <h1 style={{ margin: 0, fontSize: 20, flex: 1 }}>🌲 {detail?.name}</h1>
        <button className="fm-btn fm-btn-outline fm-btn-xs" onClick={() => setShowHandbook(true)}>📖 Справочник</button>
      </div>
      {msg && <Toast text={msg} onClose={() => setMsg(null)} />}

      {detail?.patient_id && (
        <div className="fm-card fm-rise" style={{ textAlign: 'center', marginBottom: 12 }}>
          {detail.patient_image_url && (
            <img src={mediaUrl(detail.patient_image_url)} alt={detail.patient_name || ''} style={{ maxWidth: 220, maxHeight: 140, borderRadius: 8, marginBottom: 8 }} />
          )}
          <div style={{ fontSize: 20, fontWeight: 600 }}>{detail.patient_name}</div>
          <div style={{ fontSize: 13, color: 'var(--text-secondary)' }}>
            Уровень {detail.patient_level}
          </div>
          {detail.healed ? (
            <div className="fm-card" style={{ background: 'rgba(127,255,127,0.12)', marginTop: 10 }}>
              ✅ Вылечен. Карточка добавлена в коллекцию.
            </div>
          ) : (
            <div style={{ fontSize: 13, color: 'var(--text-muted)', marginTop: 6 }}>
              Осмотрите части тела, сверьтесь со справочником и поставьте диагноз.
            </div>
          )}
        </div>
      )}

      {detail && !detail.healed && (
        <>
          <div style={{ overflow: 'auto', marginBottom: 12, border: '1px solid var(--border)', borderRadius: 'var(--radius-sm)', background: '#0c1508' }}>
            <svg width={detail.cols * 80} height={detail.rows * 80} style={{ display: 'block' }}>
              {detail.map_url && (
                <image href={mediaUrl(detail.map_url)} x={0} y={0} width={detail.cols * 80} height={detail.rows * 80} preserveAspectRatio="none" />
              )}
              {detail.part_cells.map((pc) => (
                <g key={pc.id} onClick={() => doExamine(pc.part_code)} style={{ cursor: 'pointer' }}>
                  <rect x={pc.col * 80} y={pc.row * 80} width={80} height={80} fill="rgba(220,150,120,0.35)" stroke="#2a1a0e" strokeWidth={1} />
                  <text x={pc.col * 80 + 40} y={pc.row * 80 + 46} fontSize={24} fill="#fff" textAnchor="middle" style={{ pointerEvents: 'none', textShadow: '0 1px 2px #000' }}>
                    🔍
                  </text>
                </g>
              ))}
            </svg>
          </div>

          <div className="fm-grid">
            {detail.part_cells.map((pc) => (
              <button key={pc.id} className="fm-card fm-rise" style={{ cursor: 'pointer', textAlign: 'left', display: 'block' }} onClick={() => doExamine(pc.part_code)}>
                <strong>🔍 {pc.part_code}</strong>
              </button>
            ))}
          </div>

          {symptoms && (
            <div className="fm-card" style={{ marginTop: 10, background: 'rgba(220,150,120,0.12)' }}>
              <strong>Осмотр «{symptoms.part_code}»:</strong>
              {symptoms.symptoms.length === 0 ? (
                <div style={{ color: 'var(--text-muted)', marginTop: 4 }}>В этой части тела всё спокойно.</div>
              ) : (
                <ul style={{ margin: '6px 0 0 18px' }}>
                  {symptoms.symptoms.map((s, i) => <li key={i}>{s}</li>)}
                </ul>
              )}
            </div>
          )}

          <div className="fm-card" style={{ marginTop: 12 }}>
            <h3 style={{ margin: '0 0 8px' }}>Поставить диагноз</h3>
            {result ? (
              <div className="fm-card" style={{ background: result.correct ? 'rgba(127,255,127,0.12)' : 'rgba(255,150,150,0.12)', fontSize: 14 }}>
                {result.correct ? (
                  <>
                    ✓ Верно! Вы получили карточку рецепта «{result.remedy_name}».
                    <div style={{ marginTop: 6, fontSize: 13 }}>
                      Состав: {result.recipe_items.map((i) => `${i.ingredient_name} ×${i.qty}`).join(', ')}
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
          </div>
        </>
      )}

      {showHandbook && (
        <div style={{ position: 'fixed', inset: 0, zIndex: 60, background: 'rgba(0,0,0,0.6)', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 16 }}>
          <div className="fm-card fm-rise" onClick={(e) => e.stopPropagation()} style={{ width: '100%', maxWidth: 'calc(var(--shell-max-width) * 0.9)', maxHeight: '80vh', overflowY: 'auto' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
              <h2 style={{ margin: 0 }}>📖 Справочник болезней</h2>
              <button className="fm-btn fm-btn-xs fm-btn-outline" onClick={() => setShowHandbook(false)}>✕</button>
            </div>
            {handbook.map((d) => (
              <div key={d.id} className="fm-card" style={{ marginBottom: 8 }}>
                <strong>{d.name}</strong>
                {d.remedy_name && <span style={{ color: 'var(--text-secondary)' }}> — мазь: {d.remedy_name}</span>}
                <ul style={{ margin: '6px 0 0 18px', fontSize: 13 }}>
                  {d.symptoms.map((s, i) => <li key={i}>{s.part_code}: {s.text}</li>)}
                </ul>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
