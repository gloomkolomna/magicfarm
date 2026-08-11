import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useSession } from '../context/SessionContext';
import { api, type FieldCellDetail, type FieldDetail, type Product, type Tent } from '../api/endpoints';
import { mediaUrl } from '../api/media';
import plotUrl from '../assets/plot.png';

const COLOR_LABEL: Record<string, string> = { green: '🟢', blue: '🔵', violet: '🟣' };

export default function FieldPage() {
  const { id } = useParams<{ id: string }>();
  const nav = useNavigate();
  const { refresh, loading: sessionLoading } = useSession();
  const [field, setField] = useState<FieldDetail | null>(null);
  const [products, setProducts] = useState<Product[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  // Модалка посадки.
  const [plantCell, setPlantCell] = useState<{ col: number; row: number } | null>(null);
  const [plantSel, setPlantSel] = useState<number | null>(null);
  const [plantQty, setPlantQty] = useState('1');

  // Модалка ухода за грядкой (invest) + отчёт о вышивке.
  const [careCell, setCareCell] = useState<FieldCellDetail | null>(null);
  const [investAmount, setInvestAmount] = useState('');
  const [stitchAmount, setStitchAmount] = useState('');
  const [stitchPhoto, setStitchPhoto] = useState<File | null>(null);
  const [stitchNote, setStitchNote] = useState('');

  // Модалка шатра.
  const [tentModal, setTentModal] = useState<Tent | null>(null);
  const [buildInvestAmount, setBuildInvestAmount] = useState('');

  // Модалка крафта (в построенном шатре).
  const [craftProduct, setCraftProduct] = useState<number | null>(null);
  const [craftAmount, setCraftAmount] = useState('');
  const [craftQty, setCraftQty] = useState('1');

  const [imgNaturalW, setImgNaturalW] = useState<number | null>(null);

  const fieldId = Number(id);

  const load = useCallback(async () => {
    if (!Number.isFinite(fieldId)) return;
    setLoading(true);
    try {
      const [fd, prs] = await Promise.all([api.fieldDetail(fieldId), api.products()]);
      setField(fd);
      setProducts(prs);
    } catch (e: any) {
      setMsg('✗ ' + (e?.response?.data?.detail || 'Ошибка'));
    } finally {
      setLoading(false);
    }
  }, [fieldId]);

  useEffect(() => { if (!sessionLoading) load(); }, [load, sessionLoading]);

  const cellsGrid = useMemo(() => {
    if (!field) return [];
    const grid: (FieldCellDetail | null)[][] = [];
    for (let r = 0; r < field.rows; r++) {
      const row: (FieldCellDetail | null)[] = [];
      for (let c = 0; c < field.cols; c++) {
        row.push(field.cells.find((x) => x.col === c && x.row === r) ?? null);
      }
      grid.push(row);
    }
    return grid;
  }, [field]);

  async function doPlant() {
    if (!plantCell || plantSel == null) return;
    setBusy(true); setMsg(null);
    try {
      await api.plantOnCell(fieldId, plantCell.col, plantCell.row, plantSel, Number(plantQty) || 1);
      setMsg('✓ Посажено!');
      setPlantCell(null); setPlantSel(null); setPlantQty('1');
      await load(); await refresh();
    } catch (e: any) {
      setMsg('✗ ' + (e?.response?.data?.detail || 'Ошибка'));
    } finally { setBusy(false); }
  }

  async function doInvest() {
    if (!careCell || !investAmount) return;
    const plot = careCell.plot;
    if (!plot) return;
    setBusy(true); setMsg(null);
    try {
      await api.investPlot(plot.id, Number(investAmount));
      setMsg('✓ Крестики вложены');
      setCareCell(null); setInvestAmount('');
      await load(); await refresh();
    } catch (e: any) {
      setMsg('✗ ' + (e?.response?.data?.detail || 'Ошибка'));
    } finally { setBusy(false); }
  }

  async function doStitchReport() {
    if (!stitchAmount || !stitchPhoto) return;
    setBusy(true); setMsg(null);
    try {
      await api.createStitchReport(Number(stitchAmount), stitchPhoto, stitchNote || undefined);
      setMsg('✓ Зачтено! Крестики начислены.');
      setStitchAmount(''); setStitchPhoto(null); setStitchNote('');
      await refresh();
    } catch (e: any) {
      setMsg('✗ ' + (e?.response?.data?.detail || 'Ошибка'));
    } finally { setBusy(false); }
  }

  async function doHarvest(cell: FieldCellDetail) {
    setBusy(true); setMsg(null);
    try {
      await api.harvestCell(fieldId, cell.col, cell.row);
      setMsg('✓ Урожай собран, клетка свободна');
      await load(); await refresh();
    } catch (e: any) {
      setMsg('✗ ' + (e?.response?.data?.detail || 'Ошибка'));
    } finally { setBusy(false); }
  }

  // ── Шатры: строительство ──

  async function doStartBuild(t: Tent) {
    setBusy(true); setMsg(null);
    try {
      const updated = await api.startTentBuild(fieldId, t.id);
      setMsg('✓ Стройка началась! Вытянуты карты кристаллов.');
      setTentModal(updated);
      setBuildInvestAmount(String(updated.required));
      await load(); await refresh();
    } catch (e: any) {
      setMsg('✗ ' + (e?.response?.data?.detail || 'Ошибка'));
    } finally { setBusy(false); }
  }

  async function doBuildInvest() {
    if (!tentModal || !buildInvestAmount) return;
    setBusy(true); setMsg(null);
    try {
      const updated = await api.investTentBuild(fieldId, tentModal.id, Number(buildInvestAmount));
      setMsg(updated.build_status === 'built' ? '✓ Шатёр построен!' : '✓ Крестики вложены');
      setTentModal(updated);
      if (updated.build_status === 'built') setBuildInvestAmount('');
      await load(); await refresh();
    } catch (e: any) {
      setMsg('✗ ' + (e?.response?.data?.detail || 'Ошибка'));
    } finally { setBusy(false); }
  }

  // ── Крафт в построенном шатре ──

  async function doCraft() {
    if (!tentModal || !craftProduct || !craftAmount) return;
    const prod = (await api.productions()).find((p) => p.kind === tentModal.kind);
    if (!prod) { setMsg('✓ Производство не найдено'); return; }
    setBusy(true); setMsg(null);
    try {
      await api.craftProduct(prod.id, Number(craftAmount), craftProduct, Number(craftQty));
      setMsg('✓ Товар скрафчен!');
      setCraftAmount('');
      await load(); await refresh();
    } catch (e: any) {
      setMsg('✗ ' + (e?.response?.data?.detail || 'Ошибка'));
    } finally { setBusy(false); }
  }

  if (loading) return <div style={{ maxWidth: 600, margin: '0 auto', padding: 'var(--shell-pad)' }}><div className="fm-card">Загрузка поля…</div></div>;
  if (!field) return <div style={{ maxWidth: 600, margin: '0 auto', padding: 'var(--shell-pad)' }}><div className="fm-card">Поле не найдено.</div></div>;

  function openTent(t: Tent) {
    setTentModal(t);
    setBuildInvestAmount(t.build_status === 'planted' ? String(Math.max(0, t.required - t.accumulated)) : '');
    setCraftAmount('');
    setCraftQty('1');
    if (t.build_status === 'built') {
      const first = products.find((x) => x.production_kind === t.kind);
      setCraftProduct(first ? first.id : null);
    } else {
      setCraftProduct(null);
    }
  }

  return (
    <>
      <div
        style={{
          position: 'fixed', inset: 0, zIndex: 0, overflow: 'auto',
          WebkitOverflowScrolling: 'touch', backgroundColor: '#1a2414',
        }}
      >
        {field.map_url ? (
          <div style={{ position: 'relative', display: 'inline-block', lineHeight: 0, width: '100%', minWidth: imgNaturalW ? `${imgNaturalW}px` : undefined }}>
            <img
              src={mediaUrl(field.map_url)}
              alt=""
              style={{ display: 'block', width: '100%' }}
              onLoad={(e) => setImgNaturalW((e.target as HTMLImageElement).naturalWidth)}
            />
            <div
              style={{
                position: 'absolute', inset: 0, display: 'grid',
                gridTemplateColumns: `repeat(${field.cols}, 1fr)`,
                gridTemplateRows: `repeat(${field.rows}, 1fr)`,
              }}
            >
              {Array.from({ length: field.rows }).map((_, r) =>
                Array.from({ length: field.cols }).map((__, c) => {
                  const cell = field.cells.filter((x) => x.col < field.cols && x.row < field.rows).find((x) => x.col === c && x.row === r);
                  if (!cell) return <div key={`empty-${c}-${r}`} />;
                  let bg = 'transparent';
                  if (cell.kind === 'tent') bg = 'rgba(224,168,62,0.16)';
                  else if (cell.kind === 'pet') bg = 'rgba(200,130,220,0.16)';
                  else if (cell.kind === 'barnyard') bg = 'rgba(220,180,120,0.20)';
                  else if (cell.kind === 'bed' && cell.occupant_user_id == null) bg = `center/contain no-repeat url(${plotUrl})`;
                  else if (cell.occupant_user_id != null) bg = cell.plot?.status === 'grown' ? 'rgba(111,174,74,0.30)' : 'rgba(90,143,62,0.20)';
                  const isBed = cell.kind === 'bed';
                  const grownImg = cell.plot?.status === 'grown' ? cell.plant_image_grown : cell.plant_image_young;
                  return (
                    <div
                      key={`cell-${c}-${r}`}
                      onClick={() => {
                        if (!isBed) return;
                        if (cell.occupant_user_id == null) {
                          setPlantCell({ col: c, row: r });
                          setPlantSel(field.plants[0]?.id ?? null);
                        } else {
                          setCareCell(cell);
                          setInvestAmount(cell.plot ? String(cell.plot.required - cell.plot.accumulated) : '');
                        }
                      }}
                      style={{
                        borderRight: c < field.cols - 1 ? `1px solid ${field.grid_color}` : 'none',
                        borderBottom: r < field.rows - 1 ? `1px solid ${field.grid_color}` : 'none',
                        boxShadow: 'inset 0 0 0 0.5px rgba(255,255,255,0.05)',
                        background: bg,
                        cursor: isBed ? 'pointer' : 'default',
                        position: 'relative',
                        display: 'flex', flexDirection: 'column',
                        alignItems: 'center', justifyContent: 'center',
                        overflow: 'hidden', padding: 2,
                      }}
                    >
                      {isBed && cell.occupant_user_id != null && (
                        <>
                          {grownImg ? (
                            <img
                              src={mediaUrl(grownImg)}
                              alt=""
                              style={{ maxWidth: '90%', maxHeight: '85%', objectFit: 'contain', pointerEvents: 'none' }}
                            />
                          ) : (
                            <div style={{ fontSize: '5vw', lineHeight: 1, pointerEvents: 'none' }}>{cell.plant_emoji}</div>
                          )}
                          {cell.plot && cell.plot.status !== 'grown' && (
                            <div style={{ fontSize: 9, color: '#fff', textShadow: '0 1px 2px #000', pointerEvents: 'none' }}>
                              {cell.plot.accumulated}/{cell.plot.required}
                            </div>
                          )}
                          {cell.plot && (
                            <div style={{ position: 'absolute', top: 2, right: 3, fontSize: 14, color: '#7fff7f', pointerEvents: 'none' }}>
                              {cell.plot.status === 'grown' ? '✓' : ''}
                            </div>
                          )}
                          {cell.plot && (
                            <div style={{ position: 'absolute', bottom: 2, left: 3, fontSize: 12, color: '#fff', textShadow: '0 1px 2px #000', pointerEvents: 'none', fontWeight: 700 }}>
                              ×{cell.plot.qty}
                            </div>
                          )}
                        </>
                      )}
                      {cell.kind === 'pet' && (
                        <div style={{ fontSize: '5vw', lineHeight: 1, pointerEvents: 'none', opacity: 0.7 }}>🐾</div>
                      )}
                      {cell.kind === 'barnyard' && (
                        <div style={{ fontSize: '5vw', lineHeight: 1, pointerEvents: 'none', opacity: 0.7 }}>🐄</div>
                      )}
                    </div>
                  );
                }),
              )}
            </div>

            {/* Шатры — кликабельны только в пределах своего прямоугольника. */}
            {field.tents?.map((t) => {
              const spanCols = t.col2 - t.col1 + 1;
              const spanRows = t.row2 - t.row1 + 1;
              return (
                <div
                  key={`tent-${t.id}`}
                  style={{
                    position: 'absolute', inset: 0, pointerEvents: 'none', display: 'grid',
                    gridTemplateColumns: `repeat(${field.cols}, 1fr)`,
                    gridTemplateRows: `repeat(${field.rows}, 1fr)`,
                  }}
                >
                  <div
                    onClick={() => openTent(t)}
                    style={{
                      gridColumn: `${t.col1 + 1} / span ${spanCols}`,
                      gridRow: `${t.row1 + 1} / span ${spanRows}`,
                      display: 'flex', flexDirection: 'column',
                      alignItems: 'center', justifyContent: 'center', gap: 4,
                      padding: 6, overflow: 'hidden',
                      border: t.build_status === 'slot' ? '2px dashed rgba(224,168,62,0.7)' : 'none',
                      borderRadius: 6,
                      background: t.build_status === 'planted' ? 'rgba(224,168,62,0.10)' : 'transparent',
                      cursor: 'pointer',
                      pointerEvents: 'auto',
                    }}
                  >
                    {t.build_status === 'built' && t.image_url && (
                      <img
                        src={mediaUrl(t.image_url)}
                        alt=""
                        style={{ maxWidth: '80%', maxHeight: '60%', objectFit: 'contain' }}
                      />
                    )}
                    {t.build_status === 'built' && (
                      <div style={{ fontSize: 'clamp(10px,2.6vw,16px)', color: '#ffe9b0', textAlign: 'center', textShadow: '0 1px 3px #000', lineHeight: 1.15, fontWeight: 600 }}>
                        ⛺ {t.name}
                      </div>
                    )}
                    {t.build_status === 'slot' && (
                      <div style={{ fontSize: 'clamp(11px,3vw,16px)', color: '#ffe9b0', textAlign: 'center', textShadow: '0 1px 3px #000', fontWeight: 600 }}>
                        🏗️ {t.name}
                        <div style={{ fontSize: 10, opacity: 0.85 }}>свободный слот</div>
                      </div>
                    )}
                    {t.build_status === 'planted' && (
                      <div style={{ fontSize: 'clamp(10px,2.6vw,15px)', color: '#ffe9b0', textAlign: 'center', textShadow: '0 1px 3px #000', lineHeight: 1.15, fontWeight: 600 }}>
                        🔨 {t.name}
                        <div style={{ fontSize: 10 }}>{t.accumulated}/{t.required}</div>
                      </div>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        ) : (
          <div style={{ color: 'var(--text-muted)', fontSize: 16 }}>Карта не загружена</div>
        )}
      </div>

      {/* Плавающая шапка поверх поля-фона */}
      <div
        style={{
          position: 'fixed', top: 0, left: 0, right: 0, zIndex: 20,
          display: 'flex', alignItems: 'center', gap: 8, padding: '6px 12px',
          paddingTop: 'calc(6px + var(--vk-inset-top, 0px))',
          background: 'linear-gradient(180deg, rgba(10,16,8,0.92) 0%, rgba(10,16,8,0.78) 100%)',
          backdropFilter: 'blur(8px)',
          WebkitBackdropFilter: 'blur(8px)',
        }}
      >
        <button className="fm-btn fm-btn-xs fm-btn-outline" onClick={() => nav('/fields')} style={{ background: 'rgba(255,255,255,0.14)', color: '#ffffff', borderColor: 'rgba(255,255,255,0.25)' }}>
          ← Поля
        </button>
        <h1 style={{ margin: 0, flex: 1, fontSize: 18, color: '#ffffff', textShadow: '0 1px 3px rgba(0,0,0,0.7)' }}>
          🗺️ {field.name}
        </h1>
      </div>

      {msg && (
        <div className="fm-card" style={{ position: 'fixed', top: 'calc(54px + var(--vk-inset-top, 0px))', left: 12, right: 12, zIndex: 20, fontSize: 14, background: 'rgba(15,22,12,0.85)' }}>
          {msg}
        </div>
      )}

      {/* Модалка посадки */}
      {plantCell && (
        <Modal title="🌱 Посадить растение" onClose={() => setPlantCell(null)}>
          <p style={{ fontSize: 13, color: 'var(--text-muted)' }}>
            Клетка ({plantCell.col}, {plantCell.row}). Выберите растение из списка локации:
          </p>
          {field.plants.length === 0 ? (
            <div className="fm-card" style={{ color: 'var(--text-muted)' }}>В этой локации нет разрешённых растений. Обратитесь к админу.</div>
          ) : (
            <select className="fm-input" value={plantSel ?? ''} onChange={(e) => setPlantSel(Number(e.target.value))}>
              {field.plants.map((p) => <option key={p.id} value={p.id}>{p.emoji} {p.name}</option>)}
            </select>
          )}
          <div style={{ marginTop: 8 }}>
            <label style={{ fontSize: 13 }}>Количество (1–20):</label>
            <input className="fm-input" type="number" min={1} max={20} value={plantQty} onChange={(e) => setPlantQty(e.target.value)} />
          </div>
          <button className="fm-btn" style={{ width: '100%', marginTop: 14 }} disabled={busy || plantSel == null} onClick={doPlant}>Посадить</button>
        </Modal>
      )}

      {/* Модалка ухода за грядкой (invest + отчёт о вышивке) */}
      {careCell && careCell.plot && (
        <Modal title={`${careCell.plant_emoji} ${careCell.plant_name}`} onClose={() => setCareCell(null)}>
          {careCell.plot.status === 'grown' ? (
            <>
              <p style={{ fontSize: 14, color: 'var(--success)' }}>✓ Растение выросло!</p>
              <button className="fm-btn" style={{ width: '100%', marginTop: 8 }} disabled={busy} onClick={() => { doHarvest(careCell); setCareCell(null); }}>
                🧺 Собрать урожай
              </button>
            </>
          ) : (
            <>
              <div style={{ fontSize: 13, color: 'var(--text-secondary)', marginBottom: 6 }}>
                {COLOR_LABEL[careCell.plot.crystal_color || 'green']} ×{careCell.plot.crystal_count} · осталось {Math.max(0, careCell.plot.required - careCell.plot.accumulated)} крестиков
              </div>
              <div className="fm-progress" style={{ marginBottom: 10 }}>
                <div className="fm-progress-fill" style={{ width: `${careCell.plot.required > 0 ? Math.min(100, Math.round((careCell.plot.accumulated / careCell.plot.required) * 100)) : 0}%` }} />
              </div>
              <label style={{ display: 'block', marginBottom: 6, fontSize: 14 }}>Вложить крестиков</label>
              <input className="fm-input" type="number" min={1} value={investAmount} onChange={(e) => setInvestAmount(e.target.value)} />
              <button className="fm-btn" style={{ width: '100%', marginTop: 10 }} disabled={busy || !investAmount} onClick={doInvest}>Полить крестиками</button>

              <div style={{ borderTop: '1px solid var(--border)', margin: '14px 0', paddingTop: 4 }}>
                <strong style={{ fontSize: 14 }}>📷 Отчитаться о вышивке</strong>
                <p style={{ fontSize: 12, color: 'var(--text-muted)', margin: '4px 0 8px' }}>
                  Фото вышивки начислит крестики на баланс — потом полейте грядку.
                </p>
                <label style={{ display: 'block', marginBottom: 6, fontSize: 14 }}>Сколько крестиков вышито</label>
                <input className="fm-input" type="number" min={1} value={stitchAmount} onChange={(e) => setStitchAmount(e.target.value)} placeholder="например, 150" />
                <label style={{ display: 'block', margin: '10px 0 6px', fontSize: 14 }}>Фото</label>
                <input type="file" accept="image/*" capture="environment" onChange={(e) => setStitchPhoto(e.target.files?.[0] || null)} />
                <label style={{ display: 'block', margin: '10px 0 6px', fontSize: 14 }}>Заметка (необязательно)</label>
                <input className="fm-input" value={stitchNote} onChange={(e) => setStitchNote(e.target.value)} placeholder="что вышили" />
                <button className="fm-btn fm-btn-outline" style={{ width: '100%', marginTop: 12 }} disabled={busy || !stitchAmount || !stitchPhoto} onClick={doStitchReport}>
                  Отправить отчёт
                </button>
              </div>
            </>
          )}
        </Modal>
      )}

      {/* Модалка шатра (slot / planted / built) */}
      {tentModal && (
        <Modal title={`⛺ ${tentModal.name}`} onClose={() => setTentModal(null)}>
          {tentModal.build_status === 'slot' && (
            <>
              <p style={{ fontSize: 14, color: 'var(--text-secondary)' }}>
                Свободный слот под производство. Начните стройку — вытянутся карты кристаллов, и появится норма вышивки.
              </p>
              <button className="fm-btn" style={{ width: '100%', marginTop: 12 }} disabled={busy} onClick={() => doStartBuild(tentModal)}>
                🏗️ Начать строительство
              </button>
            </>
          )}

          {tentModal.build_status === 'planted' && (
            <>
              <div style={{ fontSize: 13, color: 'var(--text-secondary)', marginBottom: 6 }}>
                {COLOR_LABEL[tentModal.crystal_color || 'green']} ×{tentModal.crystal_count} · осталось {Math.max(0, tentModal.required - tentModal.accumulated)} крестиков
              </div>
              <div className="fm-progress" style={{ marginBottom: 10 }}>
                <div className="fm-progress-fill" style={{ width: `${tentModal.required > 0 ? Math.min(100, Math.round((tentModal.accumulated / tentModal.required) * 100)) : 0}%` }} />
              </div>
              <label style={{ display: 'block', marginBottom: 6, fontSize: 14 }}>Вложить крестиков</label>
              <input className="fm-input" type="number" min={1} value={buildInvestAmount} onChange={(e) => setBuildInvestAmount(e.target.value)} />
              <button className="fm-btn" style={{ width: '100%', marginTop: 12 }} disabled={busy || !buildInvestAmount} onClick={doBuildInvest}>
                Вложить в стройку
              </button>
              <p style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 8 }}>
                Чтобы пополнить баланс крестиков — отчитайтесь о вышивке в модалке грядки.
              </p>
            </>
          )}

          {tentModal.build_status === 'built' && (
            <>
              <p style={{ fontSize: 14, color: 'var(--success)', marginBottom: 10 }}>✓ Шатёр построен! Можно крафтить товары.</p>
              <label style={{ display: 'block', marginBottom: 6, fontSize: 14 }}>Товар</label>
              <select className="fm-input" value={craftProduct ?? ''} onChange={(e) => setCraftProduct(Number(e.target.value))}>
                <option value="">— выберите —</option>
                {products.filter((p) => p.production_kind === tentModal.kind).map((p) => (
                  <option key={p.id} value={p.id}>{p.emoji} {p.name}</option>
                ))}
              </select>
              <label style={{ display: 'block', margin: '10px 0 6px', fontSize: 14 }}>Сколько крестиков вложить</label>
              <input className="fm-input" type="number" min={1} value={craftAmount} onChange={(e) => setCraftAmount(e.target.value)} placeholder="кратное норме цикла" />
              <label style={{ display: 'block', margin: '10px 0 6px', fontSize: 14 }}>Товаров за цикл</label>
              <input className="fm-input" type="number" min={1} value={craftQty} onChange={(e) => setCraftQty(e.target.value)} />
              <button className="fm-btn" style={{ width: '100%', marginTop: 14 }} disabled={busy || !craftProduct || !craftAmount} onClick={doCraft}>
                Скрафтить
              </button>
            </>
          )}
        </Modal>
      )}
    </>
  );
}

function Modal({ title, onClose, children }: { title: string; onClose: () => void; children: React.ReactNode }) {
  return (
    <div onClick={onClose} style={{ position: 'fixed', inset: 0, zIndex: 60, background: 'rgba(0,0,0,0.6)', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 16 }}>
      <div className="fm-card fm-rise" onClick={(e) => e.stopPropagation()} style={{ width: '100%', maxWidth: 420, maxHeight: '85vh', overflowY: 'auto' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
          <h2 style={{ margin: 0 }}>{title}</h2>
          <button className="fm-btn fm-btn-xs fm-btn-outline" onClick={onClose}>✕</button>
        </div>
        {children}
      </div>
    </div>
  );
}
