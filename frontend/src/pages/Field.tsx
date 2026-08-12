import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useSession } from '../context/SessionContext';
import { api, type CrystalCard, type FieldCellDetail, type FieldDetail, type PlantBed, type Product, type Tent } from '../api/endpoints';
import { mediaUrl } from '../api/media';
import plotUrl from '../assets/plot.png';

const COLOR_LABEL: Record<string, string> = { green: '🟢', blue: '🔵', violet: '🟣' };
const CARD_IMAGE: Record<string, string> = { green: '🟢', blue: '🔵', violet: '🟣', treasure_green: '💎', treasure_blue: '💎', treasure_violet: '💎' };

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

  // Модалка посадки дерева в слот сада.
  const [plantBed, setPlantBed] = useState<PlantBed | null>(null);
  const [plantBedSel, setPlantBedSel] = useState<number | null>(null);
  const [plantBedQty, setPlantBedQty] = useState('1');

  // Модалка ухода за грядкой (invest) + отчёт о вышивке.
  const [careCell, setCareCell] = useState<FieldCellDetail | null>(null);
  const [careBedId, setCareBedId] = useState<number | null>(null);
  const [investAmount, setInvestAmount] = useState('');
  const [stitchAmount, setStitchAmount] = useState('');
  const [stitchPhotoBefore, setStitchPhotoBefore] = useState<File | null>(null);
  const [stitchPhoto, setStitchPhoto] = useState<File | null>(null);
  const [stitchNote, setStitchNote] = useState('');

  // Модалка шатра.
  const [tentModal, setTentModal] = useState<Tent | null>(null);
  const [buildInvestAmount, setBuildInvestAmount] = useState('');

  // Модалка крафта (в построенном шатре).
  const [craftProduct, setCraftProduct] = useState<number | null>(null);
  const [craftAmount, setCraftAmount] = useState('');
  const [craftQty, setCraftQty] = useState('1');

  const [cardResult, setCardResult] = useState<{ cards: { color: string; value: number; is_treasure: boolean }[]; title: string; norm?: number; qty?: number } | null>(null);
  const [showVideo, setShowVideo] = useState(false);
  const [cardVideoUrl, setCardVideoUrl] = useState<string | null>(null);
  const [crystalCards, setCrystalCards] = useState<CrystalCard[]>([]);
  const [zoomedImg, setZoomedImg] = useState<string | null>(null);
  const videoRef = useRef<HTMLVideoElement | null>(null);

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

  const loadVideo = useCallback(async () => {
    try {
      const [gm, cards] = await Promise.all([
        api.gameMediaByCode('card_shuffle').catch(() => null),
        api.crystalCards().catch(() => [] as CrystalCard[]),
      ]);
      if (gm?.url) setCardVideoUrl(mediaUrl(gm.url));
      setCrystalCards(cards || []);
    } catch {}
  }, []);

  useEffect(() => { loadVideo(); }, [loadVideo]);

  useEffect(() => {
    if (careCell?.plot?.norm_revealed && careCell?.plot?.drawn_cards_json && !cardResult) {
      let cards: { color: string; value: number; is_treasure: boolean }[] = [];
      try { cards = JSON.parse(careCell.plot.drawn_cards_json); } catch {}
      if (cards.length > 0) {
        setCardResult({
          cards,
          title: `📖 Норма для ${careCell.plant_name || 'растения'}`,
          norm: careCell.plot.required ?? 0,
          qty: careCell.plot.qty ?? 0,
        });
      }
    }
  }, [careCell, cardResult]);

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
      setMsg('✓ Посажено! Нажмите на грядку чтобы узнать норму.');
      setPlantCell(null); setPlantSel(null); setPlantQty('1');
      await load(); await refresh();
    } catch (e: any) {
      setMsg('✗ ' + (e?.response?.data?.detail || 'Ошибка'));
    } finally { setBusy(false); }
  }

  async function doPlantBed() {
    if (!plantBed || plantBedSel == null) return;
    setBusy(true); setMsg(null);
    try {
      await api.plantOnBed(fieldId, plantBed.id, plantBedSel, Number(plantBedQty) || 1);
      setMsg('✓ Дерево посажено! Нажмите на слот чтобы узнать норму.');
      setPlantBed(null); setPlantBedSel(null); setPlantBedQty('1');
      await load(); await refresh();
    } catch (e: any) {
      setMsg('✗ ' + (e?.response?.data?.detail || 'Ошибка'));
    } finally { setBusy(false); }
  }

  function bedToCareCell(pb: PlantBed): FieldCellDetail {
    return {
      id: -1, col: pb.col1, row: pb.row1, kind: 'bed',
      plant_id: pb.plant_id, occupant_user_id: pb.occupant_user_id, tent_id: null,
      plant_name: pb.plant_name ?? null,
      plant_emoji: pb.plant_emoji ?? null,
      plant_image_young: pb.plant_image_young ?? null,
      plant_image_grown: pb.plant_image_grown ?? null,
      plot: pb.plot ?? null,
      tent_name: null, tent_image: null, occupant_name: null,
    };
  }

  async function doInvest() {
    if (!careCell || !investAmount) return;
    const plot = careCell.plot;
    if (!plot) return;
    setBusy(true); setMsg(null);
    try {
      await api.investPlot(plot.id, Number(investAmount));
      setMsg('✓ Крестики вложены');
      setCareCell(null); setCareBedId(null); setInvestAmount('');
      await load(); await refresh();
    } catch (e: any) {
      setMsg('✗ ' + (e?.response?.data?.detail || 'Ошибка'));
    } finally { setBusy(false); }
  }

  async function doStitchReport() {
    if (!stitchAmount || !stitchPhoto || !stitchPhotoBefore) return;
    setBusy(true); setMsg(null);
    try {
      await api.createStitchReport(
        Number(stitchAmount), stitchPhotoBefore, stitchPhoto, stitchNote || undefined,
        'plant_grow', careCell?.plot?.id,
      );
      setMsg('✓ Зачтено! Крестики начислены.');
      setStitchAmount(''); setStitchPhotoBefore(null); setStitchPhoto(null); setStitchNote('');
      setCareCell(null); setCareBedId(null);
      await load(); await refresh();
    } catch (e: any) {
      setMsg('✗ ' + (e?.response?.data?.detail || 'Ошибка'));
    } finally { setBusy(false); }
  }

  async function doHarvest(cell: FieldCellDetail) {
    setBusy(true); setMsg(null);
    try {
      if (careBedId != null) {
        await api.harvestBed(fieldId, careBedId);
        setMsg('✓ Урожай собран');
      } else {
        await api.harvestCell(fieldId, cell.col, cell.row);
        setMsg('✓ Урожай собран, клетка свободна');
      }
      setCareBedId(null);
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

  if (loading) return <div style={{ maxWidth: 'var(--shell-max-width)', margin: '0 auto', padding: 'var(--shell-pad)' }}><div className="fm-card">Загрузка поля…</div></div>;
  if (!field) return <div style={{ maxWidth: 'var(--shell-max-width)', margin: '0 auto', padding: 'var(--shell-pad)' }}><div className="fm-card">Поле не найдено.</div></div>;

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
          position: 'fixed', inset: 0, top: 'calc(54px + var(--vk-inset-top, 0px))', zIndex: 0, overflow: 'auto',
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
                      onClick={async () => {
                        if (!isBed) return;
                        if (cell.occupant_user_id == null) {
                          setPlantCell({ col: c, row: r });
                          setPlantSel(field.plants[0]?.id ?? null);
                        } else {
                          setShowVideo(false);
                          setCardResult(null);
                          const [fd, prs] = await Promise.all([api.fieldDetail(fieldId), api.products()]);
                          const freshCell = fd.cells.find((x: FieldCellDetail) => x.col === c && x.row === r);
                          setField(fd);
                          setProducts(prs);
                          if (freshCell) {
                            setCareCell(freshCell);
                            setInvestAmount(freshCell.plot ? String(freshCell.plot.required - freshCell.plot.accumulated) : '');
                          }
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
                            <div style={{ position: 'absolute', bottom: 10, left: 3, fontSize: 12, color: '#fff', textShadow: '0 1px 2px #000', pointerEvents: 'none', fontWeight: 700 }}>
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

            {/* Садовые слоты-деревья — кликабельны в пределах своего прямоугольника. */}
            {field.plant_category === 'orchard' && field.plant_beds?.map((pb) => {
              const spanCols = pb.col2 - pb.col1 + 1;
              const spanRows = pb.row2 - pb.row1 + 1;
              const occupied = pb.occupant_user_id != null;
              const grownImg = pb.plot?.status === 'grown' ? pb.plant_image_grown : pb.plant_image_young;
              return (
                <div
                  key={`bed-${pb.id}`}
                  style={{
                    position: 'absolute', inset: 0, pointerEvents: 'none', display: 'grid',
                    gridTemplateColumns: `repeat(${field.cols}, 1fr)`,
                    gridTemplateRows: `repeat(${field.rows}, 1fr)`,
                  }}
                >
                  <div
                    onClick={() => {
                      if (!occupied) {
                        setPlantBed(pb);
                        setPlantBedSel(field.plants[0]?.id ?? null);
                      } else {
                        setShowVideo(false);
                        setCardResult(null);
                        setCareBedId(pb.id);
                        setCareCell(bedToCareCell(pb));
                        setInvestAmount(pb.plot ? String(pb.plot.required - (pb.plot.accumulated ?? 0)) : '');
                      }
                    }}
                    style={{
                      gridColumn: `${pb.col1 + 1} / span ${spanCols}`,
                      gridRow: `${pb.row1 + 1} / span ${spanRows}`,
                      display: 'flex', flexDirection: 'column',
                      alignItems: 'center', justifyContent: 'center', gap: 4,
                      padding: 6, overflow: 'hidden',
                      border: !occupied ? '2px dashed rgba(120,200,90,0.7)' : 'none',
                      borderRadius: 6,
                      background: occupied && pb.plot
                        ? (pb.plot.status === 'grown' ? 'rgba(111,174,74,0.25)' : 'rgba(90,143,62,0.15)')
                        : 'transparent',
                      cursor: 'pointer',
                      pointerEvents: 'auto',
                      position: 'relative',
                    }}
                  >
                    {occupied && grownImg && (
                      <img src={mediaUrl(grownImg)} alt="" style={{ maxWidth: '70%', maxHeight: '55%', objectFit: 'contain', pointerEvents: 'none' }} />
                    )}
                    {occupied && !grownImg && pb.plant_emoji && (
                      <div style={{ fontSize: '8vw', lineHeight: 1, pointerEvents: 'none' }}>{pb.plant_emoji}</div>
                    )}
                    {occupied && pb.plot && pb.plot.status !== 'grown' && (
                      <div style={{ fontSize: 11, color: '#fff', textShadow: '0 1px 2px #000', pointerEvents: 'none' }}>
                        {pb.plot.accumulated}/{pb.plot.required}
                      </div>
                    )}
                    {occupied && pb.plot && pb.plot.status === 'grown' && (
                      <div style={{ fontSize: 20, color: '#7fff7f', pointerEvents: 'none' }}>✓</div>
                    )}
                    {occupied && pb.plot && (
                      <div style={{ position: 'absolute', bottom: 6, left: 6, fontSize: 13, color: '#fff', textShadow: '0 1px 2px #000', fontWeight: 700, pointerEvents: 'none' }}>
                        ×{pb.plot.qty}
                      </div>
                    )}
                    {!occupied && (
                      <div style={{ fontSize: 'clamp(11px,3vw,16px)', color: '#d7f5c0', textAlign: 'center', textShadow: '0 1px 3px #000', fontWeight: 600, pointerEvents: 'none' }}>
                        🌳 Слот дерева
                        <div style={{ fontSize: 10, opacity: 0.85 }}>свободно</div>
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
          {(() => {
            const plantedIds = new Set(field.cells.filter((c) => c.plant_id != null && c.occupant_user_id != null).map((c) => c.plant_id!));
            const available = field.plants.filter((p) => !plantedIds.has(p.id));
            if (available.length === 0) {
              return <div className="fm-card" style={{ color: 'var(--text-muted)' }}>Все доступные растения уже посажены.</div>;
            }
            return (
              <select className="fm-input" value={plantSel ?? ''} onChange={(e) => setPlantSel(Number(e.target.value))}>
                {available.map((p) => <option key={p.id} value={p.id}>{p.emoji} {p.name}</option>)}
              </select>
            );
          })()}
          <div style={{ marginTop: 8 }}>
            <label style={{ fontSize: 13 }}>Количество (1–20):</label>
            <input className="fm-input" type="number" min={1} max={20} value={plantQty} onChange={(e) => setPlantQty(e.target.value)} />
          </div>
          <button className="fm-btn" style={{ width: '100%', marginTop: 14 }} disabled={busy || plantSel == null} onClick={doPlant}>Посадить</button>
        </Modal>
      )}

      {/* Модалка посадки дерева в слот сада */}
      {plantBed && (
        <Modal title="🌳 Посадить дерево" onClose={() => setPlantBed(null)}>
          <p style={{ fontSize: 13, color: 'var(--text-muted)' }}>
            Слот дерева ({plantBed.col2 - plantBed.col1 + 1}×{plantBed.row2 - plantBed.row1 + 1}). Выберите садовое растение:
          </p>
          {(() => {
            const plantedIds = new Set<number>([
              ...field.cells.filter((c) => c.plant_id != null && c.occupant_user_id != null).map((c) => c.plant_id!),
              ...(field.plant_beds?.filter((b) => b.plant_id != null && b.occupant_user_id != null).map((b) => b.plant_id!) ?? []),
            ]);
            const available = field.plants.filter((p) => !plantedIds.has(p.id));
            if (available.length === 0) {
              return <div className="fm-card" style={{ color: 'var(--text-muted)' }}>Все доступные растения уже посажены.</div>;
            }
            return (
              <select className="fm-input" value={plantBedSel ?? ''} onChange={(e) => setPlantBedSel(Number(e.target.value))}>
                {available.map((p) => <option key={p.id} value={p.id}>{p.emoji} {p.name}</option>)}
              </select>
            );
          })()}
          <div style={{ marginTop: 8 }}>
            <label style={{ fontSize: 13 }}>Количество плодов (1–20):</label>
            <input className="fm-input" type="number" min={1} max={20} value={plantBedQty} onChange={(e) => setPlantBedQty(e.target.value)} />
          </div>
          <button className="fm-btn" style={{ width: '100%', marginTop: 14 }} disabled={busy || plantBedSel == null} onClick={doPlantBed}>Посадить дерево</button>
        </Modal>
      )}

      {/* Модалка ухода за грядкой (норма + отчёт) */}
      {careCell && careCell.plot && (
        <Modal
          title={`${careCell.plant_emoji || ''} ${careCell.plant_name || ''}`.trim() || 'Грядка'}
          onClose={() => { setCareCell(null); setCareBedId(null); }}
          wide={showVideo || (careCell.plot.norm_revealed && !showVideo)}
        >
          {careCell.plot.status === 'grown' ? (
            <>
              <p style={{ fontSize: 14, color: 'var(--success)' }}>✓ Растение выросло!</p>
              <button className="fm-btn" style={{ width: '100%', marginTop: 8 }} disabled={busy} onClick={() => { doHarvest(careCell); setCareCell(null); setCareBedId(null); }}>
                🧺 Собрать урожай
              </button>
            </>
          ) : !careCell.plot.norm_revealed && careCell.plot.accumulated === 0 && careCell.plot.required > 0 && careCell.plot.drawn_cards_json ? (
            <>
              <p style={{ fontSize: 14, color: 'var(--text-secondary)', marginBottom: 4 }}>
                🌱 Молодое растение — норма ещё не объявлена
              </p>
              <button
                className="fm-btn"
                style={{ width: '100%', marginTop: 8 }}
                disabled={busy}
                onClick={async () => {
                  let cards: { color: string; value: number; is_treasure: boolean }[] = [];
                  if (careCell.plot?.drawn_cards_json) {
                    try { cards = JSON.parse(careCell.plot.drawn_cards_json); } catch {}
                  }
                  if (cards.length > 0 && careCell.plot) {
                    setCardResult({
                      cards,
                      title: `📖 Норма для ${careCell.plant_name || 'растения'}`,
                      norm: careCell.plot.required ?? 0,
                      qty: careCell.plot.qty ?? 0,
                    });
                    setShowVideo(!!cardVideoUrl);
                    try {
                      const updated = await api.revealNorm(careCell.plot.id);
                      setCareCell({ ...careCell, plot: { ...careCell.plot, ...updated } });
                    } catch {}
                  }
                }}
              >
                🔮 Узнать норму
              </button>
            </>
          ) : (
            <>
              {careCell.plot.norm_revealed && (
                <>
                  {showVideo && cardVideoUrl ? (
                    <div style={{ textAlign: 'center', marginBottom: 12 }}>
                      <video
                        ref={videoRef}
                        src={cardVideoUrl}
                        autoPlay
                        muted
                        playsInline
                        style={{ width: '100%', maxHeight: '50vh', borderRadius: 8 }}
                        onEnded={() => setShowVideo(false)}
                        onError={() => setShowVideo(false)}
                      />
                      <button className="fm-btn fm-btn-sm fm-btn-outline" style={{ marginTop: 6 }} onClick={() => setShowVideo(false)}>
                        Пропустить видео
                      </button>
                    </div>
                  ) : cardResult && (
                    <>
                      <div style={{ display: 'flex', justifyContent: 'center', gap: 10, flexWrap: 'wrap', marginBottom: 10 }}>
                        {cardResult.cards.map((c, i) => {
                          const cardImg = crystalCards.find(
                            cc => cc.color === c.color && cc.value === c.value && cc.is_treasure === c.is_treasure
                          )?.image_url;
                          return (
                            <div key={i} style={{ textAlign: 'center', padding: 6, borderRadius: 10, background: 'var(--bg-secondary)', border: '1px solid var(--border)', minWidth: 100 }}>
                              {cardImg ? (
                                <img
                                  src={mediaUrl(cardImg)}
                                  alt=""
                                  style={{ width: '30vw', maxWidth: 160, height: 'auto', objectFit: 'contain', marginBottom: 4, cursor: 'pointer' }}
                                  onClick={(e) => { e.stopPropagation(); setZoomedImg(mediaUrl(cardImg)); }}
                                />
                              ) : (
                                <div style={{ fontSize: 48, lineHeight: 1, marginBottom: 4 }}>
                                  {c.is_treasure ? '💎' : c.color === 'green' ? '🟢' : c.color === 'blue' ? '🔵' : '🟣'}
                                </div>
                              )}
                              <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>
                                {c.is_treasure ? 'Сокровище' : `${c.value}`}
                              </div>
                            </div>
                          );
                        })}
                      </div>
                      {(cardResult.norm != null) && (
                        <p style={{ fontSize: 16, fontWeight: 700, textAlign: 'center', margin: '8px 0', color: 'var(--text-accent)' }}>
                          Итоговая норма: {cardResult.norm} ✝️
                          {cardResult.qty && cardResult.qty > 1 ? <> (×{cardResult.qty} растений)</> : ''}
                        </p>
                      )}
                      <div style={{ borderTop: '1px solid var(--border)', margin: '10px 0' }} />
                    </>
                  )}
                </>
              )}

              {!showVideo && (
                <div style={{ borderTop: careCell.plot.norm_revealed ? 'none' : '1px solid var(--border)', paddingTop: careCell.plot.norm_revealed ? 0 : 4 }}>
                  <strong style={{ fontSize: 14 }}>📷 Отчитаться о вышивке</strong>
                  <p style={{ fontSize: 12, color: 'var(--text-muted)', margin: '4px 0 8px' }}>
                    Вышейте норму {careCell.plot.required ?? '?'} крестиков, сделайте фото и отправьте отчёт.
                  </p>
                  <label style={{ display: 'block', marginBottom: 6, fontSize: 14 }}>Сколько крестиков вышито</label>
                  <input className="fm-input" type="number" min={1} value={stitchAmount} onChange={(e) => setStitchAmount(e.target.value)} placeholder="например, 150" />
                  <label style={{ display: 'block', margin: '10px 0 6px', fontSize: 14 }}>Фото ДО вышивки</label>
                  <input type="file" accept="image/*" capture="environment" onChange={(e) => setStitchPhotoBefore(e.target.files?.[0] || null)} />
                  {stitchPhotoBefore && <div style={{ fontSize: 11, color: '#5f8', marginTop: 2 }}>✓ {stitchPhotoBefore.name}</div>}
                  <label style={{ display: 'block', margin: '10px 0 6px', fontSize: 14 }}>Фото ПОСЛЕ вышивки</label>
                  <input type="file" accept="image/*" capture="environment" onChange={(e) => setStitchPhoto(e.target.files?.[0] || null)} />
                  {stitchPhoto && <div style={{ fontSize: 11, color: '#5f8', marginTop: 2 }}>✓ {stitchPhoto.name}</div>}
                  <label style={{ display: 'block', margin: '10px 0 6px', fontSize: 14 }}>Заметка (необязательно)</label>
                  <input className="fm-input" value={stitchNote} onChange={(e) => setStitchNote(e.target.value)} placeholder="что вышили" />
                  <button className="fm-btn fm-btn-outline" style={{ width: '100%', marginTop: 12 }} disabled={busy || !stitchAmount || !stitchPhotoBefore || !stitchPhoto} onClick={doStitchReport}>
                    Отправить отчёт
                  </button>
                </div>
              )}
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

      {zoomedImg && (
        <div style={{ position: 'fixed', inset: 0, zIndex: 80, background: 'rgba(0,0,0,0.85)', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 16 }}>
          <button
            onClick={() => setZoomedImg(null)}
            style={{ position: 'absolute', top: 16, right: 16, zIndex: 1, fontSize: 24, background: 'none', border: 'none', color: '#fff', cursor: 'pointer', padding: '8px 12px' }}
          >
            ✕
          </button>
          <img src={zoomedImg} alt="" style={{ maxWidth: '90vw', maxHeight: '90vh', objectFit: 'contain' }} onClick={(e) => e.stopPropagation()} />
        </div>
      )}

    </>
  );
}

function Modal({ title, onClose, children, wide }: { title: string; onClose: () => void; children: React.ReactNode; wide?: boolean }) {
  return (
    <div style={{ position: 'fixed', inset: 0, zIndex: 60, background: 'rgba(0,0,0,0.6)', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: wide ? 8 : 16 }}>
      <div className="fm-card fm-rise" onClick={(e) => e.stopPropagation()} style={{ width: '100%', maxWidth: wide ? '95vw' : 'calc(var(--shell-max-width) * 0.7)', maxHeight: wide ? '95vh' : '85vh', overflowY: 'auto' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
          <h2 style={{ margin: 0 }}>{title}</h2>
          <button className="fm-btn fm-btn-xs fm-btn-outline" onClick={onClose}>✕</button>
        </div>
        {children}
      </div>
    </div>
  );
}
