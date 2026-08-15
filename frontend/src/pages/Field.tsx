import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useSession } from '../context/SessionContext';
import { api, type Animal, type CraftInfo, type CraftSessionInfo, type CrystalCard, type FieldCellDetail, type FieldDetail, type HouseState, type Pet, type PlantBed, type Product, type Tent } from '../api/endpoints';
import { mediaUrl } from '../api/media';
import StitchReportForm from '../components/StitchReportForm';
import plotUrl from '../assets/plot.png';

const COLOR_LABEL: Record<string, string> = { green: '🟢', blue: '🔵', violet: '🟣' };
const CARD_IMAGE: Record<string, string> = { green: '🟢', blue: '🔵', violet: '🟣', treasure_green: '💎', treasure_blue: '💎', treasure_violet: '💎' };

const HOUSE_MATERIALS: { code: string; name: string; emoji: string }[] = [
  { code: 'glass', name: 'Стекло', emoji: '🪟' },
  { code: 'wood', name: 'Древесина', emoji: '🪵' },
  { code: 'nails', name: 'Гвозди', emoji: '🔩' },
  { code: 'pipes', name: 'Трубы', emoji: '🚰' },
  { code: 'bricks', name: 'Кирпичи', emoji: '🧱' },
  { code: 'paint', name: 'Краска', emoji: '🎨' },
];
const DICE_FACE_EMOJI = ['', '⚀', '⚁', '⚂', '⚃', '⚄', '⚅'];

const MIN_SCALE = 0.1;
const MAX_SCALE = 4;
const ZOOM_STEP = 1.25;

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
  const [stitchSending, setStitchSending] = useState(false);

  // Модалка обязательной пересадки после сбора урожая.
  const [replant, setReplant] = useState<{ cell: FieldCellDetail; bedId: number | null } | null>(null);
  const [replantQty, setReplantQty] = useState('');

  // Модалка шатра.
  const [tentModal, setTentModal] = useState<Tent | null>(null);
  const [buildInvestAmount, setBuildInvestAmount] = useState('');

  // Модалка дома ведьмы.
  const [houseModal, setHouseModal] = useState<Tent | null>(null);
  const [houseState, setHouseState] = useState<HouseState | null>(null);
  const [houseShowDice, setHouseShowDice] = useState(false);
  const [houseShowCards, setHouseShowCards] = useState(false);
  const [houseDone, setHouseDone] = useState<'video' | 'success' | null>(null);
  const [diceVideoUrl, setDiceVideoUrl] = useState<string | null>(null);
  const [diceFaceUrls, setDiceFaceUrls] = useState<(string | null)[]>([null, null, null, null, null, null, null]);
  const [houseMaterialUrls, setHouseMaterialUrls] = useState<Record<string, string | null>>({});
  const [houseBuildVideoUrl, setHouseBuildVideoUrl] = useState<string | null>(null);

  // Модалка крафта (в построенном шатре).
  const [craftProduct, setCraftProduct] = useState<number | null>(null);
  const [craftInfo, setCraftInfo] = useState<CraftInfo | null>(null);
  const [craftQty, setCraftQty] = useState('1');
  const [craftSessions, setCraftSessions] = useState<CraftSessionInfo[]>([]);
  const [activeCraft, setActiveCraft] = useState<CraftSessionInfo | null>(null);

  // Модалка загона скотного двора.
  const [barnyardCell, setBarnyardCell] = useState<FieldCellDetail | null>(null);
  const [barnyardAnimals, setBarnyardAnimals] = useState<Animal[]>([]);
  const [barnyardSel, setBarnyardSel] = useState<number | null>(null);
  const [barnyardInvest, setBarnyardInvest] = useState('');

  // Модалка клетки питомца.
  const [petCell, setPetCell] = useState<FieldCellDetail | null>(null);
  const [petCatalog, setPetCatalog] = useState<Pet[]>([]);
  const [petSel, setPetSel] = useState<number | null>(null);
  const [petSettleResult, setPetSettleResult] = useState<{ pet_id: number; pet_name: string; required: number } | null>(null);

  const [cardResult, setCardResult] = useState<{ cards: { color: string; value: number; is_treasure: boolean }[]; title: string; norm?: number; qty?: number } | null>(null);
  const [showVideo, setShowVideo] = useState(false);
  const [tentCardResult, setTentCardResult] = useState<{ cards: { color: string; value: number; is_treasure: boolean }[]; title: string; norm?: number } | null>(null);
  const [tentShowVideo, setTentShowVideo] = useState(false);
  const [cardVideoUrl, setCardVideoUrl] = useState<string | null>(null);
  const [crystalCards, setCrystalCards] = useState<CrystalCard[]>([]);
  const [zoomedImg, setZoomedImg] = useState<string | null>(null);
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const scrollRef = useRef<HTMLDivElement | null>(null);

  const [imgNaturalW, setImgNaturalW] = useState<number | null>(null);
  const [imgNaturalH, setImgNaturalH] = useState<number | null>(null);
  const [scale, setScale] = useState(1);

  const fieldId = Number(id);

  function zoomIn() { setScale((s) => Math.max(MIN_SCALE, Math.min(MAX_SCALE, s * ZOOM_STEP))); }
  function zoomOut() { setScale((s) => Math.max(MIN_SCALE, Math.min(MAX_SCALE, s / ZOOM_STEP))); }
  function resetScale() { setScale(1); }
  function fitToScreen() {
    const vp = scrollRef.current;
    if (!vp || !imgNaturalW || !imgNaturalH) return;
    const s = Math.min(vp.clientWidth / imgNaturalW, vp.clientHeight / imgNaturalH);
    setScale(Math.max(MIN_SCALE, Math.min(1, s)));
  }

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
      const [gm, cards, animals, pets, diceV, houseV, faces, mats] = await Promise.all([
        api.gameMediaByCode('card_shuffle').catch(() => null),
        api.crystalCards().catch(() => [] as CrystalCard[]),
        api.animalsAvailable().catch(() => [] as Animal[]),
        api.petsCatalog().catch(() => [] as Pet[]),
        api.gameMediaByCode('dice_roll').catch(() => null),
        api.gameMediaByCode('house_build_video').catch(() => null),
        Promise.all(Array.from({ length: 6 }, (_, i) =>
          api.gameMediaByCode(`dice_face_${i + 1}`).catch(() => null))),
        Promise.all(HOUSE_MATERIALS.map((m) =>
          api.gameMediaByCode(`house_material_${m.code}`).catch(() => null))),
      ]);
      if (gm?.url) setCardVideoUrl(mediaUrl(gm.url));
      setCrystalCards(cards || []);
      setBarnyardAnimals(animals || []);
      setPetCatalog(pets || []);
      if (diceV?.url) setDiceVideoUrl(mediaUrl(diceV.url));
      if (houseV?.url) setHouseBuildVideoUrl(mediaUrl(houseV.url));
      setDiceFaceUrls([null, ...faces.map((f) => (f?.url ? mediaUrl(f.url) : null))]);
      setHouseMaterialUrls(Object.fromEntries(HOUSE_MATERIALS.map((m, i) => [m.code, mats[i]?.url ? mediaUrl(mats[i]!.url!) : null])));
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

  useEffect(() => {
    if (!msg) return;
    const t = setTimeout(() => setMsg(null), 4000);
    return () => clearTimeout(t);
  }, [msg]);

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
      plant_image_harvested: pb.plant_image_harvested ?? null,
      plot: pb.plot ?? null,
      tent_name: null, tent_image: null, occupant_name: null,
      barnyard: null, pet: null,
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
    setBusy(true); setStitchSending(true); setMsg(null);
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
    } finally { setBusy(false); setStitchSending(false); }
  }

  function openReplant(cell: FieldCellDetail, bedId: number | null) {
    setReplant({ cell, bedId });
    setReplantQty(String(cell.plot?.qty ?? 1));
  }

  async function doHarvest(cell: FieldCellDetail) {
    setBusy(true); setMsg(null);
    try {
      if (careBedId != null) {
        const pb = await api.harvestBed(fieldId, careBedId);
        setMsg('✓ Урожай собран');
        const asCell = bedToCareCell(pb);
        setCareCell(null); setCareBedId(null);
        openReplant(asCell, pb.id);
      } else {
        const updated = await api.harvestCell(fieldId, cell.col, cell.row);
        setMsg('✓ Урожай собран');
        setCareCell(null);
        openReplant(updated, null);
      }
      await load(); await refresh();
    } catch (e: any) {
      setMsg('✗ ' + (e?.response?.data?.detail || 'Ошибка'));
    } finally { setBusy(false); }
  }

  async function doReplant() {
    if (!replant) return;
    const qty = Number(replantQty) || 0;
    if (qty < 1 || qty > 20) return;
    setBusy(true); setMsg(null);
    try {
      if (replant.bedId != null) {
        await api.replantBed(fieldId, replant.bedId, qty);
      } else {
        await api.replantCell(fieldId, replant.cell.col, replant.cell.row, qty);
      }
      setMsg('✓ Посажено заново! Узнайте норму.');
      setReplant(null);
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
      setMsg('✓ Стройка началась! Нажмите «Узнать норму».');
      setTentModal(updated);
      setBuildInvestAmount('');
      setTentCardResult(null);
      setTentShowVideo(false);
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

  async function doRevealTentNorm() {
    if (!tentModal) return;
    let cards: { color: string; value: number; is_treasure: boolean }[] = [];
    if (tentModal.drawn_cards_json) {
      try { cards = JSON.parse(tentModal.drawn_cards_json); } catch {}
    }
    setTentCardResult({ cards, title: `📖 Норма для ${tentModal.name}`, norm: tentModal.required ?? 0 });
    setTentShowVideo(!!cardVideoUrl);
    try {
      const updated = await api.revealTentNorm(fieldId, tentModal.id);
      setTentModal(updated);
      setBuildInvestAmount(String(Math.max(0, updated.required - updated.accumulated)));
    } catch {}
  }

  // ── Крафт в построенном шатре ──

  async function reloadCraftSessions() {
    try {
      setCraftSessions(await api.craftSessions());
    } catch {}
  }

  async function selectCraftProduct(id: number | null) {
    setCraftProduct(id);
    setCraftInfo(null);
    if (id == null) return;
    try {
      setCraftInfo(await api.productCraftInfo(id));
    } catch {}
  }

  async function doIssueNorm() {
    if (!tentModal || !craftProduct) return;
    const prod = (await api.productions()).find((p) => p.kind === tentModal.kind);
    if (!prod) { setMsg('✗ Производство не найдено'); return; }
    setBusy(true); setMsg(null);
    try {
      const res = await api.craftProduct(prod.id, craftProduct, Number(craftQty) || 1);
      setMsg('✓ Норма выдана!');
      setCraftQty('1');
      setCraftInfo(await api.productCraftInfo(craftProduct));
      await load(); await refresh();
      await reloadCraftSessions();
      const p = products.find((x) => x.id === craftProduct);
      setActiveCraft({
        id: res.craft_session_id,
        product_id: craftProduct,
        product_name: res.product_name,
        product_emoji: p?.emoji ?? null,
        plant_name: res.plant_name ?? res.source_product_name ?? null,
        source_product_name: null,
        qty: res.qty,
        required: res.required,
        production_kind: tentModal.kind,
        status: 'pending',
        created_at: null,
      });
    } catch (e: any) {
      setMsg('✗ ' + (e?.response?.data?.detail || 'Ошибка'));
    } finally { setBusy(false); }
  }

  async function doCancelCraft(id: number) {
    setBusy(true); setMsg(null);
    try {
      await api.cancelCraftSession(id);
      setMsg('✓ Крафт отменён');
      if (activeCraft?.id === id) setActiveCraft(null);
      await reloadCraftSessions();
    } catch (e: any) {
      setMsg('✗ ' + (e?.response?.data?.detail || 'Ошибка'));
    } finally { setBusy(false); }
  }

  // ── Скотный двор: загон на клетке ──

  function openBarnyardCell(cell: FieldCellDetail) {
    setBarnyardCell(cell);
    setBarnyardSel(cell.barnyard?.animal_id ?? barnyardAnimals[0]?.id ?? null);
    setBarnyardInvest(cell.barnyard ? String(Math.max(0, cell.barnyard.required - cell.barnyard.accumulated)) : '');
  }

  async function doBarnyardInstall() {
    if (!barnyardCell || barnyardSel == null) return;
    setBusy(true); setMsg(null);
    try {
      await api.barnyardInstallOnCell(barnyardCell.id, barnyardSel);
      setMsg('✓ Животное установлено!');
      setBarnyardCell(null);
      await load(); await refresh();
    } catch (e: any) {
      setMsg('✗ ' + (e?.response?.data?.detail || 'Ошибка'));
    } finally { setBusy(false); }
  }

  async function doBarnyardInvest() {
    if (!barnyardCell?.barnyard || !barnyardInvest) return;
    setBusy(true); setMsg(null);
    try {
      await api.barnyardInvest(barnyardCell.barnyard.slot_id, Number(barnyardInvest));
      setMsg('✓ Крестики вложены');
      setBarnyardCell(null);
      await load(); await refresh();
    } catch (e: any) {
      setMsg('✗ ' + (e?.response?.data?.detail || 'Ошибка'));
    } finally { setBusy(false); }
  }

  async function doBarnyardProduce() {
    if (!barnyardCell?.barnyard) return;
    setBusy(true); setMsg(null);
    try {
      await api.barnyardProduce(barnyardCell.barnyard.slot_id);
      setMsg('✓ Продукция получена!');
      setBarnyardCell(null);
      await load(); await refresh();
    } catch (e: any) {
      setMsg('✗ ' + (e?.response?.data?.detail || 'Ошибка'));
    } finally { setBusy(false); }
  }

  // ── Питомцы: клетка на лужайке ──

  function openPetCell(cell: FieldCellDetail) {
    setPetCell(cell);
    setPetSel(cell.pet?.pet_id ?? petCatalog[0]?.id ?? null);
    setPetSettleResult(null);
  }

  async function doPetSettle() {
    if (!petCell || petSel == null) return;
    setBusy(true); setMsg(null);
    try {
      const result = await api.settlePetOnCell(petCell.id, petSel);
      setPetSettleResult(result);
    } catch (e: any) {
      setMsg('✗ ' + (e?.response?.data?.detail || 'Ошибка'));
    } finally { setBusy(false); }
  }

  if (loading) return <div style={{ maxWidth: 'var(--shell-max-width)', margin: '0 auto', padding: 'var(--shell-pad)' }}><div className="fm-card">Загрузка поля…</div></div>;
  if (!field) return <div style={{ maxWidth: 'var(--shell-max-width)', margin: '0 auto', padding: 'var(--shell-pad)' }}><div className="fm-card">Поле не найдено.</div></div>;

  async function reloadHouseState(tentId: number) {
    try {
      const st = await api.houseState(fieldId, tentId);
      setHouseState(st);
    } catch (e: any) {
      setMsg('✗ ' + (e?.response?.data?.detail || 'Ошибка'));
    }
  }

  async function doHouseRequestMaterial() {
    if (!houseModal) return;
    setBusy(true); setMsg(null);
    try {
      const st = await api.houseRequestMaterial(fieldId, houseModal.id);
      setHouseState(st);
      setHouseShowDice(!!diceVideoUrl);
    } catch (e: any) {
      setMsg('✗ ' + (e?.response?.data?.detail || 'Ошибка'));
    } finally { setBusy(false); }
  }

  async function doHouseBuild() {
    if (!houseModal) return;
    setBusy(true); setMsg(null);
    try {
      const st = await api.houseBuild(fieldId, houseModal.id);
      setHouseState(st);
      setHouseShowCards(true);
    } catch (e: any) {
      setMsg('✗ ' + (e?.response?.data?.detail || 'Ошибка'));
    } finally { setBusy(false); }
  }

  function openTent(t: Tent) {
    if (t.kind === 'witch_house') {
      if (t.build_status === 'built') return;
      setHouseModal(t);
      setHouseState(null);
      setHouseShowDice(false);
      setHouseShowCards(false);
      setHouseDone(null);
      void reloadHouseState(t.id);
      return;
    }
    setTentModal(t);
    setBuildInvestAmount(t.build_status === 'planted' ? String(Math.max(0, t.required - t.accumulated)) : '');
    setCraftQty('1');
    setTentCardResult(null);
    setTentShowVideo(false);
    if (t.build_status === 'built') {
      const first = products.find((x) => x.production_kind === t.kind);
      void selectCraftProduct(first ? first.id : null);
      void reloadCraftSessions();
    } else {
      setCraftProduct(null);
      setCraftInfo(null);
    }
  }

  return (
    <>
      <div
        ref={scrollRef}
        style={{
            position: 'fixed', inset: 0, top: '38px', zIndex: 0, overflow: 'auto',
            overscrollBehavior: 'contain', backgroundColor: '#1a2414',
        }}
      >
        {field.map_url ? (
          <div style={{ position: 'relative', display: 'inline-block', lineHeight: 0, width: imgNaturalW ? `${Math.round(imgNaturalW * scale)}px` : '100%' }}>
            <img
              src={mediaUrl(field.map_url)}
              alt=""
              style={{ display: 'block', width: '100%' }}
              onLoad={(e) => { setImgNaturalW((e.target as HTMLImageElement).naturalWidth); setImgNaturalH((e.target as HTMLImageElement).naturalHeight); }}
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
                  else if (cell.kind === 'bed' && cell.occupant_user_id == null && field.plant_category !== 'orchard') bg = `center/contain no-repeat url(${plotUrl})`;
                  else if (cell.occupant_user_id != null) bg = cell.plot?.status === 'grown' ? 'rgba(111,174,74,0.30)' : 'rgba(90,143,62,0.20)';
                  const isBed = cell.kind === 'bed';
                  const grownImg = (cell.plot?.status === 'grown' || cell.plot?.status === 'await_replant') ? (cell.plant_image_harvested || cell.plant_image_grown) : cell.plant_image_young;
                  return (
                    <div
                      key={`cell-${c}-${r}`}
                      onClick={async () => {
                        if (cell.kind === 'barnyard') {
                          openBarnyardCell(cell);
                          return;
                        }
                        if (cell.kind === 'pet') {
                          openPetCell(cell);
                          return;
                        }
                        if (!isBed) return;
                        if (cell.occupant_user_id == null) {
                          setPlantCell({ col: c, row: r });
                          const plantedIds = new Set(field.cells.filter((x) => x.plant_id != null && x.occupant_user_id != null).map((x) => x.plant_id!));
                          setPlantSel(field.plants.find((p) => !plantedIds.has(p.id))?.id ?? null);
                        } else {
                          setShowVideo(false);
                          setCardResult(null);
                          try {
                            const [fd, prs] = await Promise.all([api.fieldDetail(fieldId), api.products()]);
                            const freshCell = fd.cells.find((x: FieldCellDetail) => x.col === c && x.row === r);
                            setField(fd);
                            setProducts(prs);
                            if (freshCell) {
                              if (freshCell.plot?.status === 'await_replant') {
                                openReplant(freshCell, null);
                              } else {
                                setCareCell(freshCell);
                                setInvestAmount(freshCell.plot ? String(freshCell.plot.required - freshCell.plot.accumulated) : '');
                              }
                            }
                          } catch (e: any) {
                            setMsg('✗ ' + (e?.response?.data?.detail || 'Не удалось загрузить грядку. Попробуйте ещё раз.'));
                          }
                        }
                      }}
                      style={{
                        borderRight: c < field.cols - 1 ? `1px solid ${field.grid_color}` : 'none',
                        borderBottom: r < field.rows - 1 ? `1px solid ${field.grid_color}` : 'none',
                        boxShadow: 'inset 0 0 0 0.5px rgba(255,255,255,0.05)',
                        background: bg,
                        cursor: isBed || cell.kind === 'barnyard' || cell.kind === 'pet' ? 'pointer' : 'default',
                        touchAction: isBed || cell.kind === 'barnyard' || cell.kind === 'pet' ? 'manipulation' : 'auto',
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
                          {cell.plot && cell.plot.status === 'planted' && (
                            <div style={{ fontSize: 9, color: '#fff', textShadow: '0 1px 2px #000', pointerEvents: 'none' }}>
                              {cell.plot.accumulated}/{cell.plot.required}
                            </div>
                          )}
                          {cell.plot && (
                            <div style={{ position: 'absolute', top: 2, right: 3, fontSize: 14, color: '#7fff7f', pointerEvents: 'none' }}>
                              {cell.plot.status === 'grown' ? '✓' : cell.plot.status === 'await_replant' ? '🔁' : ''}
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
                        <>
                          {cell.pet?.pet_id ? (
                            <div style={{ fontSize: '5vw', lineHeight: 1, pointerEvents: 'none' }}>{cell.pet.pet_emoji || '🐾'}</div>
                          ) : (
                            <div style={{ fontSize: '5vw', lineHeight: 1, pointerEvents: 'none', opacity: 0.7 }}>🐾</div>
                          )}
                          {cell.pet?.pet_id && (
                            <div style={{ fontSize: 9, color: '#fff', textShadow: '0 1px 2px #000', pointerEvents: 'none', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: '100%' }}>
                              {cell.pet.pet_name}
                            </div>
                          )}
                        </>
                      )}
                      {cell.kind === 'barnyard' && (
                        <>
                          {cell.barnyard?.status === 'ready' && (cell.barnyard.image_harvested_url || cell.barnyard.image_pen_url) ? (
                            <img
                              src={mediaUrl((cell.barnyard.image_harvested_url || cell.barnyard.image_pen_url)!)}
                              alt=""
                              style={{ maxWidth: '90%', maxHeight: '85%', objectFit: 'contain', pointerEvents: 'none' }}
                            />
                          ) : cell.barnyard?.animal_id != null && cell.barnyard.animal_emoji ? (
                            <div style={{ fontSize: '5vw', lineHeight: 1, pointerEvents: 'none' }}>{cell.barnyard.animal_emoji}</div>
                          ) : (
                            <div style={{ fontSize: '5vw', lineHeight: 1, pointerEvents: 'none', opacity: 0.7 }}>🐄</div>
                          )}
                          {cell.barnyard?.animal_id != null && cell.barnyard.status === 'building' && (
                            <div style={{ fontSize: 9, color: '#fff', textShadow: '0 1px 2px #000', pointerEvents: 'none' }}>
                              {cell.barnyard.accumulated}/{cell.barnyard.required}
                            </div>
                          )}
                          {cell.barnyard?.status === 'ready' && (
                            <div style={{ position: 'absolute', top: 2, right: 3, fontSize: 14, color: '#7fff7f', pointerEvents: 'none' }}>✓</div>
                          )}
                        </>
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
                    cursor: t.kind === 'witch_house' && t.build_status === 'built' ? 'default' : 'pointer',
                    touchAction: 'manipulation',
                    pointerEvents: 'auto',
                  }}
                >
                  {t.build_status === 'built' && t.image_url && (
                    <img
                      src={mediaUrl(t.image_url)}
                      alt=""
                      style={{ maxWidth: '85%', maxHeight: '52%', objectFit: 'contain', pointerEvents: 'none' }}
                    />
                  )}
                  {t.build_status === 'built' && (
                    <div style={{ fontSize: 'clamp(9px,2.2vw,13px)', color: '#ffe9b0', textAlign: 'center', textShadow: '0 1px 3px #000', lineHeight: 1.1, fontWeight: 600, maxWidth: '100%', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {t.kind === 'witch_house' ? '🏠' : '⛺'} {t.name}
                    </div>
                  )}
                    {t.build_status === 'slot' && (
                      <div style={{ fontSize: 'clamp(9px,2.2vw,13px)', color: '#ffe9b0', textAlign: 'center', textShadow: '0 1px 3px #000', fontWeight: 600, lineHeight: 1.15, maxWidth: '100%' }}>
                        <div style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{t.kind === 'witch_house' ? '🏚️' : '🏗️'} {t.name}</div>
                        <div style={{ fontSize: 9, opacity: 0.85 }}>{t.kind === 'witch_house' ? 'дом ведьмы' : 'свободный слот'}</div>
                      </div>
                    )}
                    {t.build_status === 'planted' && (
                      <div style={{ fontSize: 'clamp(9px,2.2vw,13px)', color: '#ffe9b0', textAlign: 'center', textShadow: '0 1px 3px #000', fontWeight: 600, lineHeight: 1.15, maxWidth: '100%' }}>
                        <div style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>🔨 {t.name}</div>
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
              const grownImg = (pb.plot?.status === 'grown' || pb.plot?.status === 'await_replant') ? (pb.plant_image_harvested || pb.plant_image_grown) : pb.plant_image_young;
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
                          const plantedIds = new Set<number>([
                            ...field.cells.filter((x) => x.plant_id != null && x.occupant_user_id != null).map((x) => x.plant_id!),
                            ...(field.plant_beds?.filter((b) => b.plant_id != null && b.occupant_user_id != null).map((b) => b.plant_id!) ?? []),
                          ]);
                          setPlantBedSel(field.plants.find((p) => !plantedIds.has(p.id))?.id ?? null);
                        } else if (pb.plot?.status === 'await_replant') {
                          openReplant(bedToCareCell(pb), pb.id);
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
                      touchAction: 'manipulation',
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
                    {occupied && pb.plot && pb.plot.status === 'planted' && (
                      <div style={{ fontSize: 11, color: '#fff', textShadow: '0 1px 2px #000', pointerEvents: 'none' }}>
                        {pb.plot.accumulated}/{pb.plot.required}
                      </div>
                    )}
                    {occupied && pb.plot && pb.plot.status === 'grown' && (
                      <div style={{ fontSize: 20, color: '#7fff7f', pointerEvents: 'none' }}>✓</div>
                    )}
                    {occupied && pb.plot && pb.plot.status === 'await_replant' && (
                      <div style={{ fontSize: 18, pointerEvents: 'none' }}>🔁</div>
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

      {/* Кнопки масштаба поля */}
      {field.map_url && (
        <div style={{ position: 'fixed', right: 12, bottom: 'calc(16px + var(--vk-inset-bottom, 0px))', zIndex: 25, display: 'flex', flexDirection: 'column', gap: 8, alignItems: 'center' }}>
          <button onClick={zoomIn} aria-label="Увеличить" style={zoomBtn}>＋</button>
          <button onClick={resetScale} aria-label="Реальный масштаб" title="Реальный масштаб (100%)" style={{ ...zoomBtn, fontSize: 13, fontWeight: 700 }}>{Math.round(scale * 100)}%</button>
          <button onClick={zoomOut} aria-label="Уменьшить" style={zoomBtn}>−</button>
          <button onClick={fitToScreen} aria-label="Вместить в экран" title="Вместить поле в экран" style={zoomBtn}>⤢</button>
        </div>
      )}

      {/* Плавающая шапка поверх поля-фона */}
      <div
        style={{
          position: 'fixed', top: 0, left: 0, right: 0, zIndex: 20,
          display: 'flex', alignItems: 'center', gap: 8, padding: '6px 12px',
          paddingTop: '6px',
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
        <div className="fm-card" style={{ position: 'fixed', top: '38px', left: 12, right: 12, zIndex: 20, fontSize: 14, background: 'rgba(15,22,12,0.85)' }}>
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
          {careCell.plot.status === 'await_replant' ? (
            <>
              <p style={{ fontSize: 14, color: 'var(--success)' }}>✓ Урожай собран!</p>
              <p style={{ fontSize: 13, color: 'var(--text-secondary)' }}>
                Укажите новое количество и посадите {careCell.plant_emoji} {careCell.plant_name} ещё раз.
              </p>
              <button className="fm-btn" style={{ width: '100%', marginTop: 8 }} disabled={busy} onClick={() => openReplant(careCell, careBedId)}>
                🌱 Посадить заново
              </button>
            </>
          ) : careCell.plot.status === 'grown' ? (
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
                  <input type="file" accept="image/*" onChange={(e) => setStitchPhotoBefore(e.target.files?.[0] || null)} />
                  {stitchPhotoBefore && <div style={{ fontSize: 11, color: '#5f8', marginTop: 2 }}>✓ {stitchPhotoBefore.name}</div>}
                  <label style={{ display: 'block', margin: '10px 0 6px', fontSize: 14 }}>Фото ПОСЛЕ вышивки</label>
                  <input type="file" accept="image/*" onChange={(e) => setStitchPhoto(e.target.files?.[0] || null)} />
                  {stitchPhoto && <div style={{ fontSize: 11, color: '#5f8', marginTop: 2 }}>✓ {stitchPhoto.name}</div>}
                  <label style={{ display: 'block', margin: '10px 0 6px', fontSize: 14 }}>Заметка (необязательно)</label>
                  <input className="fm-input" value={stitchNote} onChange={(e) => setStitchNote(e.target.value)} placeholder="что вышили" />
                  <button className="fm-btn fm-btn-outline" style={{ width: '100%', marginTop: 12, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8 }} disabled={busy || !stitchAmount || !stitchPhotoBefore || !stitchPhoto} onClick={doStitchReport}>
                    {stitchSending ? (<><span className="fm-spinner" /> Отправка отчёта…</>) : 'Отправить отчёт'}
                  </button>
                </div>
              )}
            </>
          )}
        </Modal>
      )}

      {/* Модалка обязательной пересадки: новое количество после сбора */}
      {replant && (
        <Modal title="🌱 Посадить заново" onClose={() => setReplant(null)}>
          <p style={{ fontSize: 14, color: 'var(--success)', marginBottom: 6 }}>✓ Урожай собран!</p>
          <p style={{ fontSize: 13, color: 'var(--text-secondary)', marginBottom: 10 }}>
            Укажите новое количество для посадки {replant.cell.plant_emoji} {replant.cell.plant_name}:
          </p>
          <label style={{ display: 'block', marginBottom: 6, fontSize: 14 }}>Новое количество (1–20)</label>
          <input
            className="fm-input"
            type="number"
            min={1}
            max={20}
            value={replantQty}
            onChange={(e) => setReplantQty(e.target.value)}
            autoFocus
          />
          <button
            className="fm-btn"
            style={{ width: '100%', marginTop: 14 }}
            disabled={busy || (Number(replantQty) || 0) < 1 || (Number(replantQty) || 0) > 20}
            onClick={doReplant}
          >
            Посадить
          </button>
        </Modal>
      )}

      {/* Модалка шатра (slot / planted / built) */}
      {tentModal && (
        <Modal title={`⛺ ${tentModal.name}`} onClose={() => setTentModal(null)} wide={tentModal.build_status === 'planted' && (tentShowVideo || (tentModal.norm_revealed && !tentShowVideo))}>
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
              {!tentModal.norm_revealed ? (
                <>
                  <p style={{ fontSize: 14, color: 'var(--text-secondary)' }}>
                    Стройка началась! Нажмите «Узнать норму» — вытянутся карты кристаллов, и появится норма вышивки.
                  </p>
                  <button className="fm-btn" style={{ width: '100%', marginTop: 12 }} disabled={busy} onClick={doRevealTentNorm}>
                    🔮 Узнать норму
                  </button>
                </>
              ) : tentShowVideo && cardVideoUrl ? (
                <div style={{ textAlign: 'center', marginBottom: 12 }}>
                  <video
                    ref={videoRef}
                    src={cardVideoUrl}
                    autoPlay
                    muted
                    playsInline
                    style={{ width: '100%', maxHeight: '50vh', borderRadius: 8 }}
                    onEnded={() => setTentShowVideo(false)}
                    onError={() => setTentShowVideo(false)}
                  />
                  <button className="fm-btn fm-btn-sm fm-btn-outline" style={{ marginTop: 6 }} onClick={() => setTentShowVideo(false)}>
                    Пропустить видео
                  </button>
                </div>
              ) : (
                <>
                  {tentCardResult && (
                    <>
                      <div style={{ display: 'flex', justifyContent: 'center', gap: 10, flexWrap: 'wrap', marginBottom: 10 }}>
                        {tentCardResult.cards.map((c, i) => {
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
                      <p style={{ fontSize: 16, fontWeight: 700, textAlign: 'center', margin: '8px 0', color: 'var(--text-accent)' }}>
                        Итоговая норма: {tentCardResult.norm ?? tentModal.required} ✝️
                      </p>
                      <div style={{ borderTop: '1px solid var(--border)', margin: '10px 0' }} />
                    </>
                  )}
                  <div style={{ fontSize: 13, color: 'var(--text-secondary)', marginBottom: 6 }}>
                    {COLOR_LABEL[tentModal.crystal_color || 'green']} ×{tentModal.crystal_count} · осталось {Math.max(0, tentModal.required - tentModal.accumulated)} крестиков
                  </div>
                  <div className="fm-progress" style={{ marginBottom: 10 }}>
                    <div className="fm-progress-fill" style={{ width: `${tentModal.required > 0 ? Math.min(100, Math.round((tentModal.accumulated / tentModal.required) * 100)) : 0}%` }} />
                  </div>
                  <StitchReportForm
                    contextType="tent_build"
                    contextId={tentModal.id}
                    required={Math.max(0, tentModal.required - tentModal.accumulated)}
                    busy={busy}
                    onDone={async () => { setMsg('✓ Зачтено!'); setTentModal(null); await load(); await refresh(); }}
                  />
                </>
              )}
            </>
          )}

          {tentModal.build_status === 'built' && (
            <>
              <p style={{ fontSize: 14, color: 'var(--success)', marginBottom: 10 }}>✓ Шатёр построен! Можно крафтить товары.</p>
              {craftSessions.filter((cs) => cs.production_kind === tentModal.kind).length > 0 && (
                <>
                  <label style={{ display: 'block', margin: '0 0 6px', fontSize: 14 }}>Текущие крафты</label>
                  {craftSessions.filter((cs) => cs.production_kind === tentModal.kind).map((cs) => (
                    <div key={cs.id} style={{ display: 'flex', alignItems: 'center', gap: 8, background: 'var(--bg-secondary)', border: '1px solid var(--border)', borderRadius: 10, padding: '8px 10px', marginBottom: 8 }}>
                      <div style={{ flex: 1, fontSize: 13 }}>
                        <div>{cs.product_emoji} {cs.product_name} × {cs.qty}</div>
                        <div style={{ color: 'var(--text-muted)', fontSize: 12 }}>норма: {cs.required} ✝️</div>
                      </div>
                      <button className="fm-btn" style={{ padding: '6px 10px', fontSize: 12 }} disabled={busy} onClick={() => setActiveCraft(cs)}>Продолжить</button>
                      <button className="fm-btn" style={{ padding: '6px 10px', fontSize: 12 }} disabled={busy} onClick={() => void doCancelCraft(cs.id)}>Отменить</button>
                    </div>
                  ))}
                  <div style={{ borderTop: '1px solid var(--border)', margin: '10px 0' }} />
                </>
              )}
              <label style={{ display: 'block', marginBottom: 6, fontSize: 14 }}>Новый крафт</label>
              <select className="fm-input" value={craftProduct ?? ''} onChange={(e) => void selectCraftProduct(Number(e.target.value))}>
                <option value="">— выберите —</option>
                {products.filter((p) => p.production_kind === tentModal.kind).map((p) => (
                  <option key={p.id} value={p.id}>{p.emoji} {p.name}</option>
                ))}
              </select>
              {craftInfo && (
                <div style={{ fontSize: 13, color: 'var(--text-secondary)', background: 'var(--bg-secondary)', border: '1px solid var(--border)', borderRadius: 10, padding: '8px 10px', margin: '10px 0' }}>
                  <div style={{ marginBottom: 4 }}>
                    {craftInfo.source_kind === 'animal_product'
                      ? <>{craftInfo.source_product_emoji || '🥚'} {craftInfo.source_product_name}</>
                      : <>{craftInfo.plant_emoji} {craftInfo.plant_name}</>} · на складе: {craftInfo.stock_qty} шт
                  </div>
                  <div style={{ marginBottom: 4 }}>Норма за 1 товар: {craftInfo.norm_per_unit} ✝️</div>
                  <div style={{ color: 'var(--text-accent)', fontWeight: 700 }}>
                    Итого за {Math.max(0, Number(craftQty) || 0)} шт: {craftInfo.norm_per_unit * Math.max(0, Number(craftQty) || 0)} ✝️
                  </div>
                </div>
              )}
              <label style={{ display: 'block', margin: '10px 0 6px', fontSize: 14 }}>Количество товара</label>
              <input
                className="fm-input"
                type="number"
                min={1}
                max={craftInfo ? craftInfo.stock_qty : undefined}
                value={craftQty}
                onChange={(e) => setCraftQty(e.target.value)}
              />
              {craftInfo && (Number(craftQty) || 0) > craftInfo.stock_qty && (
                <div style={{ fontSize: 12, color: 'var(--danger, #e5484d)', marginTop: 6 }}>
                  На складе только {craftInfo.stock_qty} шт {craftInfo.source_kind === 'animal_product' ? 'продукции' : 'растений'}
                </div>
              )}
              <button
                className="fm-btn"
                style={{ width: '100%', marginTop: 14 }}
                disabled={busy || !craftProduct || (Number(craftQty) || 0) < 1 || (craftInfo ? (Number(craftQty) || 0) > craftInfo.stock_qty : true)}
                onClick={doIssueNorm}
              >
                Выдать норму
              </button>
            </>
          )}
        </Modal>
      )}

      {/* Модалка дома ведьмы */}
      {houseModal && (
        <Modal title={`🏠 ${houseModal.name}`} onClose={() => setHouseModal(null)} wide>
          {!houseState ? (
            <p style={{ fontSize: 14, color: 'var(--text-muted)', textAlign: 'center' }}>Загрузка…</p>
          ) : houseState.phase === 'built' || houseDone !== null ? (
            houseDone === 'video' && houseBuildVideoUrl ? (
              <div style={{ textAlign: 'center', marginBottom: 12 }}>
                <video
                  ref={videoRef}
                  src={houseBuildVideoUrl}
                  autoPlay
                  muted
                  playsInline
                  style={{ width: '100%', maxHeight: '60vh', borderRadius: 8 }}
                  onEnded={() => setHouseDone('success')}
                  onError={() => setHouseDone('success')}
                />
                <button className="fm-btn fm-btn-sm fm-btn-outline" style={{ marginTop: 6 }} onClick={() => setHouseDone('success')}>
                  Пропустить видео
                </button>
              </div>
            ) : (
              <div style={{ textAlign: 'center' }}>
                <div style={{ fontSize: 52, lineHeight: 1, marginBottom: 10 }}>🏠🎉</div>
                <p style={{ fontSize: 15, color: 'var(--success)', fontWeight: 700, marginBottom: 8 }}>Дом ведьмы построен!</p>
                <p style={{ fontSize: 13, color: 'var(--text-secondary)', marginBottom: 14 }}>
                  В подарок начислено на склад: 5 штук растения 1 уровня и 5 штук товара 1 уровня.
                </p>
                <button className="fm-btn" style={{ width: '100%' }} onClick={() => { setHouseModal(null); setHouseDone(null); }}>
                  Ура!
                </button>
              </div>
            )
          ) : (
            <>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 8, marginBottom: 12 }}>
                {HOUSE_MATERIALS.map((m) => {
                  const got = houseState.collected.includes(m.code);
                  const active = houseState.current_material === m.code;
                  return (
                    <div key={m.code} style={{ textAlign: 'center', padding: 8, borderRadius: 10, border: `1px solid ${active ? 'var(--text-accent)' : 'var(--border)'}`, background: got ? 'rgba(111,174,74,0.15)' : 'var(--bg-secondary)' }}>
                      {houseMaterialUrls[m.code] ? (
                        <img src={houseMaterialUrls[m.code]!} alt="" style={{ width: '100%', maxWidth: 64, height: 'auto', objectFit: 'contain' }} />
                      ) : (
                        <div style={{ fontSize: 32, lineHeight: 1.2 }}>{m.emoji}</div>
                      )}
                      <div style={{ fontSize: 11, marginTop: 4 }}>{m.name}</div>
                      <div style={{ fontSize: 10, color: got ? 'var(--success)' : 'var(--text-muted)' }}>
                        {got ? '✓ собран' : active ? 'выпал' : '—'}
                      </div>
                    </div>
                  );
                })}
              </div>

              {houseState.current_material && (
                houseShowDice && diceVideoUrl ? (
                  <div style={{ textAlign: 'center', marginBottom: 12 }}>
                    <video
                      ref={videoRef}
                      src={diceVideoUrl}
                      autoPlay
                      muted
                      playsInline
                      style={{ width: '100%', maxHeight: '50vh', borderRadius: 8 }}
                      onEnded={() => setHouseShowDice(false)}
                      onError={() => setHouseShowDice(false)}
                    />
                    <button className="fm-btn fm-btn-sm fm-btn-outline" style={{ marginTop: 6 }} onClick={() => setHouseShowDice(false)}>
                      Пропустить видео
                    </button>
                  </div>
                ) : (
                  <>
                    <div style={{ textAlign: 'center', margin: '6px 0 10px' }}>
                      {diceFaceUrls[houseState.current_die ?? 1] ? (
                        <img src={diceFaceUrls[houseState.current_die ?? 1]!} alt="" style={{ width: '30vw', maxWidth: 140, height: 'auto' }} />
                      ) : (
                        <div style={{ fontSize: 56, lineHeight: 1.1 }}>{DICE_FACE_EMOJI[houseState.current_die ?? 1]}</div>
                      )}
                    </div>
                    <p style={{ fontSize: 14, textAlign: 'center', margin: '0 0 8px' }}>
                      Выпал материал:{' '}
                      <strong>
                        {HOUSE_MATERIALS.find((m) => m.code === houseState.current_material)?.name}
                      </strong>{' '}
                      · норма {houseState.current_required} ✝️
                    </p>
                    <StitchReportForm
                      contextType="house_material"
                      contextId={houseState.id}
                      required={houseState.current_required}
                      busy={busy}
                      onDone={async () => {
                        setMsg('✓ Стройматериал получен на склад!');
                        setHouseShowDice(false);
                        await reloadHouseState(houseModal.id);
                        await load();
                        await refresh();
                      }}
                    />
                  </>
                )
              )}

              {!houseState.current_material && houseState.collected.length < HOUSE_MATERIALS.length && (
                <>
                  <p style={{ fontSize: 13, color: 'var(--text-secondary)', marginBottom: 8 }}>
                    Собрано {houseState.collected.length} из {HOUSE_MATERIALS.length} стройматериалов.
                  </p>
                  <button className="fm-btn" style={{ width: '100%' }} disabled={busy} onClick={doHouseRequestMaterial}>
                    🎲 Собрать стройматериалы
                  </button>
                </>
              )}

              {!houseState.current_material && houseState.collected.length === HOUSE_MATERIALS.length && houseState.required === 0 && (
                <button className="fm-btn" style={{ width: '100%' }} disabled={busy} onClick={doHouseBuild}>
                  🏠 Построить дом
                </button>
              )}

              {houseState.required > 0 && (
                houseShowCards && cardVideoUrl ? (
                  <div style={{ textAlign: 'center', marginBottom: 12 }}>
                    <video
                      ref={videoRef}
                      src={cardVideoUrl}
                      autoPlay
                      muted
                      playsInline
                      style={{ width: '100%', maxHeight: '50vh', borderRadius: 8 }}
                      onEnded={() => setHouseShowCards(false)}
                      onError={() => setHouseShowCards(false)}
                    />
                    <button className="fm-btn fm-btn-sm fm-btn-outline" style={{ marginTop: 6 }} onClick={() => setHouseShowCards(false)}>
                      Пропустить видео
                    </button>
                  </div>
                ) : (
                  <>
                    {(() => {
                      let cards: { color: string; value: number; is_treasure: boolean }[] = [];
                      try { cards = houseState.cards_json ? JSON.parse(houseState.cards_json) : []; } catch {}
                      return (
                        <div style={{ display: 'flex', justifyContent: 'center', gap: 10, flexWrap: 'wrap', marginBottom: 10 }}>
                          {cards.map((c, i) => {
                            const cardImg = crystalCards.find(
                              (cc) => cc.color === c.color && cc.value === c.value && cc.is_treasure === c.is_treasure
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
                      );
                    })()}
                    <p style={{ fontSize: 16, fontWeight: 700, textAlign: 'center', margin: '8px 0', color: 'var(--text-accent)' }}>
                      Норма на постройку дома: {houseState.required} ✝️
                    </p>
                    <StitchReportForm
                      contextType="house_build"
                      contextId={houseState.id}
                      required={houseState.required}
                      buttonText="Построить дом"
                      busy={busy}
                      onDone={async () => {
                        await reloadHouseState(houseModal.id);
                        setHouseShowCards(false);
                        setHouseDone(houseBuildVideoUrl ? 'video' : 'success');
                        await load();
                        await refresh();
                      }}
                    />
                  </>
                )
              )}
            </>
          )}
        </Modal>
      )}

      {/* Модалка крафт-сессии: норма + отчёт о вышивке */}
      {activeCraft && (
        <Modal title="⚙️ Крафт товара" onClose={() => setActiveCraft(null)}>
          <div style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border)', borderRadius: 10, padding: '8px 10px', marginBottom: 10, fontSize: 13 }}>
            <div style={{ marginBottom: 4 }}>
              {activeCraft.product_emoji} {activeCraft.product_name} × {activeCraft.qty} · из {activeCraft.plant_name}
            </div>
            <div style={{ color: 'var(--text-accent)', fontWeight: 700 }}>
              Выданная норма: {activeCraft.required} ✝️
            </div>
          </div>
          <p style={{ fontSize: 12, color: 'var(--text-muted)', margin: '0 0 8px' }}>
            Вышейте норму целиком, сделайте фото и нажмите «Скрафтить». Можно закрыть окно и вернуться позже — крафт сохранится.
          </p>
          <StitchReportForm
            contextType="production"
            contextId={activeCraft.id}
            required={activeCraft.required}
            buttonText="Скрафтить"
            busy={busy}
            onDone={async () => {
              setMsg('✓ Товар получен!');
              setActiveCraft(null);
              await load(); await refresh();
              await reloadCraftSessions();
            }}
          />
        </Modal>
      )}

      {/* Модалка загона скотного двора */}
      {barnyardCell && (
        <Modal title="🐄 Скотный двор" onClose={() => setBarnyardCell(null)}>
          {!barnyardCell.barnyard || barnyardCell.barnyard.animal_id == null ? (
            <>
              <p style={{ fontSize: 13, color: 'var(--text-muted)', marginBottom: 10 }}>
                Выберите животное для заселения:
              </p>
              {barnyardAnimals.length === 0 ? (
                <div className="fm-card" style={{ color: 'var(--text-muted)' }}>Нет доступных животных. Обратитесь к админу.</div>
              ) : (
                <select className="fm-input" value={barnyardSel ?? ''} onChange={(e) => setBarnyardSel(Number(e.target.value))}>
                  {barnyardAnimals.map((a) => <option key={a.id} value={a.id}>{a.emoji} {a.name}</option>)}
                </select>
              )}
              <button className="fm-btn" style={{ width: '100%', marginTop: 14 }} disabled={busy || barnyardSel == null} onClick={doBarnyardInstall}>
                Установить
              </button>
            </>
          ) : barnyardCell.barnyard.status === 'building' ? (
            <>
              <div style={{ fontSize: 36, lineHeight: 1, marginBottom: 6 }}>{barnyardCell.barnyard.animal_emoji}</div>
              <div style={{ fontWeight: 600, marginBottom: 6 }}>{barnyardCell.barnyard.animal_name}</div>
              <div className="fm-progress" style={{ marginBottom: 6 }}>
                <div className="fm-progress-fill" style={{ width: `${barnyardCell.barnyard.required > 0 ? Math.min(100, Math.round((barnyardCell.barnyard.accumulated / barnyardCell.barnyard.required) * 100)) : 0}%` }} />
              </div>
              <div style={{ fontSize: 13, color: 'var(--text-secondary)', marginBottom: 8 }}>
                {barnyardCell.barnyard.accumulated}/{barnyardCell.barnyard.required} крестиков
              </div>
              <StitchReportForm
                contextType="animal_build"
                contextId={barnyardCell.barnyard.slot_id}
                required={Math.max(0, barnyardCell.barnyard.required - barnyardCell.barnyard.accumulated)}
                busy={busy}
                onDone={async () => { setMsg('✓ Зачтено!'); setBarnyardCell(null); await load(); await refresh(); }}
              />
            </>
          ) : (
            <>
              <div style={{ fontSize: 36, lineHeight: 1, marginBottom: 6 }}>{barnyardCell.barnyard.animal_emoji}</div>
              <div style={{ fontWeight: 600, marginBottom: 10 }}>{barnyardCell.barnyard.animal_name}</div>
              <button className="fm-btn" style={{ width: '100%' }} disabled={busy} onClick={doBarnyardProduce}>
                🥚 Получить продукцию
              </button>
            </>
          )}
        </Modal>
      )}

      {/* Модалка клетки питомца */}
      {petCell && (
        <Modal title="🐾 Питомец" onClose={() => setPetCell(null)}>
          {!petCell.pet ? (
            !petSettleResult ? (
              <>
                <p style={{ fontSize: 13, color: 'var(--text-muted)', marginBottom: 10 }}>
                  Выберите питомца для поселения:
                </p>
                {petCatalog.length === 0 ? (
                  <div className="fm-card" style={{ color: 'var(--text-muted)' }}>Нет доступных питомцев. Обратитесь к админу.</div>
                ) : (
                  <select className="fm-input" value={petSel ?? ''} onChange={(e) => setPetSel(Number(e.target.value))}>
                    {petCatalog.map((p) => <option key={p.id} value={p.id}>{p.emoji} {p.name}</option>)}
                  </select>
                )}
                <button className="fm-btn" style={{ width: '100%', marginTop: 14 }} disabled={busy || petSel == null} onClick={doPetSettle}>
                  Поселить
                </button>
              </>
            ) : (
              <>
                <p style={{ fontSize: 14, color: 'var(--text-secondary)', marginBottom: 10 }}>
                  Норма для {petSettleResult.pet_name}: {petSettleResult.required} крестиков.
                </p>
                <StitchReportForm
                  contextType="pet_settle"
                  contextId={petSettleResult.pet_id}
                  cellId={petCell.id}
                  required={petSettleResult.required}
                  busy={busy}
                  onDone={async () => { setMsg('✓ Зачтено!'); setPetCell(null); setPetSettleResult(null); await load(); await refresh(); }}
                />
              </>
            )
          ) : (
            <>
              <div style={{ fontSize: 40, lineHeight: 1, marginBottom: 6 }}>{petCell.pet.pet_emoji || '🐾'}</div>
              <div style={{ fontWeight: 600, marginBottom: 6 }}>{petCell.pet.pet_name}</div>
              {petCell.pet.bonus_description && (
                <div style={{ fontSize: 12, color: 'var(--text-secondary)' }}>{petCell.pet.bonus_description}</div>
              )}
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

const zoomBtn: React.CSSProperties = {
  width: 44, height: 44, borderRadius: 22,
  border: '1px solid rgba(255,255,255,0.25)',
  background: 'rgba(20,25,20,0.78)', color: '#f3ead0',
  fontSize: 20, lineHeight: 1, cursor: 'pointer',
  backdropFilter: 'blur(6px)', WebkitBackdropFilter: 'blur(6px)',
  display: 'flex', alignItems: 'center', justifyContent: 'center',
  padding: 0,
};
