import { useCallback, useEffect, useMemo, useState } from 'react';
import { api, type Animal, type FieldCell, type FieldDetail, type Pet, type Plant, type PlantBed, type PetZone, type ProductionTemplate, type Tent } from '../api/endpoints';
import { mediaUrl } from '../api/media';

type Brush = 'bed' | 'pet' | 'tent' | 'barnyard';

interface Props {
  fieldId: number;
  onClose: () => void;
  onChanged?: () => void;
}

const KIND_FILL: Record<string, string> = {
  empty: 'transparent',
  tent: 'rgba(224,168,62,0.30)',
  pet: 'rgba(200,130,220,0.30)',
  barnyard: 'rgba(220,180,120,0.30)',
};

const TENT_KIND_LABEL: Record<string, string> = {};

function kindLabel(code: string, templates: ProductionTemplate[]) {
  return templates.find((pt) => pt.code === code)?.name || code;
}

export default function FieldEditor({ fieldId, onClose }: Props) {
  const [field, setField] = useState<FieldDetail | null>(null);
  const [allPlants, setAllPlants] = useState<Plant[]>([]);
  const [allAnimals, setAllAnimals] = useState<Animal[]>([]);
  const [allPets, setAllPets] = useState<Pet[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  const [brush, setBrush] = useState<Brush>('bed');
  const [multiDraft, setMultiDraft] = useState<Set<string>>(new Set());

  const [cols, setCols] = useState('');
  const [rows, setRows] = useState('');
  const [lockRatio, setLockRatio] = useState(false);
  const [name, setName] = useState('');
  const [minLevel, setMinLevel] = useState('');

  const [multiModal, setMultiModal] = useState<{ c1: number; r1: number; c2: number; r2: number } | null>(null);
  const [tentName, setTentName] = useState('');
  const [tentKind, setTentKind] = useState('alchemy');
  const [tentImage, setTentImage] = useState<File | null>(null);
  const [prodTemplates, setProdTemplates] = useState<ProductionTemplate[]>([]);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [fd, pl, pts, an, pt] = await Promise.all([api.adminGetField(fieldId), api.plants(), api.adminProductionTemplates(), api.adminAnimals(), api.adminPets()]);
      setField(fd);
      setAllPlants(pl);
      setProdTemplates(pts);
      setAllAnimals(an);
      setAllPets(pt);
      setMultiDraft(new Set());
      setCols(String(fd.cols));
      setRows(String(fd.rows));
      setName(fd.name);
      setMinLevel(String(fd.min_level ?? 0));
    } catch (e: any) {
      setMsg('✗ ' + (e?.response?.data?.detail || 'Ошибка загрузки'));
    } finally {
      setLoading(false);
    }
  }, [fieldId]);

  useEffect(() => { load(); }, [load]);

  const cellIndex = useMemo(() => {
    const idx = new Map<string, FieldCell>();
    field?.cells.forEach((c) => idx.set(`${c.col},${c.row}`, c));
    return idx;
  }, [field]);

  const tentRects = useMemo(() => {
    const map = new Map<number, Tent>();
    field?.tents?.forEach((t) => map.set(t.id, t));
    return map;
  }, [field]);

  const allowedPlantIds = useMemo(
    () => new Set(field?.plants.map((p) => p.id) ?? []),
    [field],
  );

  const allowedAnimalIds = useMemo(() => new Set(field?.animal_ids ?? []), [field]);
  const allowedPetIds = useMemo(() => new Set(field?.pet_ids ?? []), [field]);

  function cellSize() {
    if (!field) return 60;
    // Подгоняем под ширину контейнера (~ экран): ширина = min(80, viewport/cols).
    const maxByWidth = Math.floor((Math.min(window.innerWidth, 560) - 24) / field.cols);
    return Math.max(34, Math.min(80, maxByWidth));
  }

  // ── Кисти клеток: автосохранение одной клетки ──
  async function onCellClick(c: number, r: number) {
    const key = `${c},${r}`;
    const cell = cellIndex.get(key);
    if (cell?.kind === 'tent') return;
    if (brush === 'tent' || (brush === 'bed' && field?.plant_category === 'orchard') || (brush === 'pet' && field?.field_kind === 'lawn')) {
      setMultiDraft((prev) => {
        const next = new Set(prev);
        if (next.has(key)) next.delete(key); else next.add(key);
        return next;
      });
      return;
    }
    // Точечное автосохранение: клик кистью по клетке сразу меняет её kind.
    try {
      const updated = await api.adminSetCellKind(fieldId, c, r, brush);
      setField((prev) => prev ? {
        ...prev,
        cells: prev.cells.map((cc) => (cc.col === c && cc.row === r) ? { ...cc, kind: updated.kind } : cc),
      } : prev);
      setMsg('✓ Сохранено');
    } catch (e: any) {
      setMsg('✗ ' + (e?.response?.data?.detail || 'Ошибка'));
    }
  }

  // ── Сохранение размеров сетки / названия ──
  async function saveDims() {
    const newCols = Math.max(1, Math.min(30, Number(cols) || field!.cols));
    const newRows = Math.max(1, Math.min(30, Number(rows) || field!.rows));
    const newName = name.trim() || field!.name;
    const newMinLevel = Math.max(0, Math.min(16, Number(minLevel) || 0));
    if (newCols === field!.cols && newRows === field!.rows && newName === field!.name && newMinLevel === (field!.min_level ?? 0)) {
      setMsg('Нечего сохранять');
      return;
    }
    setBusy(true);
    setMsg(null);
    try {
      const fd = await api.adminUpdateField(fieldId, { name: newName, cols: newCols, rows: newRows, min_level: newMinLevel });
      setField(fd);
      setMultiDraft(new Set());
      setMsg('✓ Поле обновлено (сетка пересоздана)');
    } catch (e: any) {
      setMsg('✗ ' + (e?.response?.data?.detail || 'Ошибка'));
    } finally {
      setBusy(false);
    }
  }

  // ── Мульти-клеточное размещение (шатёр / грядка / питомец) ──
  function openMultiModal() {
    if (multiDraft.size === 0) { setMsg('✗ Выберите клетки'); return; }
    let c1 = Infinity, r1 = Infinity, c2 = -Infinity, r2 = -Infinity;
    for (const k of multiDraft) {
      const [c, r] = k.split(',').map(Number);
      c1 = Math.min(c1, c); c2 = Math.max(c2, c);
      r1 = Math.min(r1, r); r2 = Math.max(r2, r);
    }
    for (const t of field?.tents ?? []) {
      if (!(c2 < t.col1 || c1 > t.col2 || r2 < t.row1 || r1 > t.row2)) {
        setMsg('✗ Пересекается с шатром «' + t.name + '»');
        return;
      }
    }
    for (const pb of field?.plant_beds ?? []) {
      if (!(c2 < pb.col1 || c1 > pb.col2 || r2 < pb.row1 || r1 > pb.row2)) {
        setMsg('✗ Пересекается со слотом дерева');
        return;
      }
    }
    for (const pz of field?.pet_zones ?? []) {
      if (!(c2 < pz.col1 || c1 > pz.col2 || r2 < pz.row1 || r1 > pz.row2)) {
        setMsg('✗ Пересекается с зоной питомца');
        return;
      }
    }
    setTentName('');
    setTentKind(prodTemplates[0]?.code || 'alchemy');
    setTentImage(null);
    setMultiModal({ c1, r1, c2, r2 });
  }

  async function saveMulti() {
    if (!multiModal) return;
    setBusy(true);
    setMsg(null);
    try {
      if (brush === 'bed') {
        await api.adminCreatePlantBed(fieldId, multiModal.c1, multiModal.r1, multiModal.c2, multiModal.r2);
        setMsg('✓ Слот дерева размещён');
      } else if (brush === 'pet') {
        await api.adminCreatePetZone(fieldId, multiModal.c1, multiModal.r1, multiModal.c2, multiModal.r2);
        setMsg('✓ Зона питомца размещена');
      } else {
        await api.adminCreateTent(
          fieldId,
          { name: tentName, kind: tentKind, col1: multiModal.c1, row1: multiModal.r1, col2: multiModal.c2, row2: multiModal.r2 },
          tentImage || undefined,
        );
        setMsg('✓ Шатёр размещён');
      }
      setMultiModal(null);
      setMultiDraft(new Set());
      await load();
    } catch (e: any) {
      setMsg('✗ ' + (e?.response?.data?.detail || 'Ошибка'));
    } finally {
      setBusy(false);
    }
  }

  async function deleteTent(tentId: number) {
    if (!confirm('Удалить шатёр? Клетки освободятся.')) return;
    setBusy(true);
    try {
      await api.adminDeleteTent(fieldId, tentId);
      await load();
      setMsg('✓ Шатёр удалён');
    } catch (e: any) {
      setMsg('✗ ' + (e?.response?.data?.detail || 'Ошибка'));
    } finally {
      setBusy(false);
    }
  }

  async function deletePlantBed(bedId: number) {
    if (!confirm('Удалить слот дерева? Клетки освободятся.')) return;
    setBusy(true);
    try {
      await api.adminDeletePlantBed(fieldId, bedId);
      await load();
      setMsg('✓ Слот дерева удалён');
    } catch (e: any) {
      setMsg('✗ ' + (e?.response?.data?.detail || 'Ошибка'));
    } finally {
      setBusy(false);
    }
  }

  // ── Растения локации ──
  async function togglePlant(pid: number) {
    if (!field) return;
    const next = new Set(allowedPlantIds);
    if (next.has(pid)) next.delete(pid);
    else next.add(pid);
    setBusy(true);
    setMsg(null);
    try {
      await api.adminSetFieldPlants(fieldId, Array.from(next));
      await load();
    } catch (e: any) {
      setMsg('✗ ' + (e?.response?.data?.detail || 'Ошибка'));
    } finally {
      setBusy(false);
    }
  }

  // ── Животные локации (скотный двор) ──
  async function toggleAnimal(aid: number) {
    if (!field) return;
    const next = new Set(allowedAnimalIds);
    if (next.has(aid)) next.delete(aid);
    else next.add(aid);
    setBusy(true);
    setMsg(null);
    try {
      await api.adminSetFieldAnimals(fieldId, Array.from(next));
      await load();
    } catch (e: any) {
      setMsg('✗ ' + (e?.response?.data?.detail || 'Ошибка'));
    } finally {
      setBusy(false);
    }
  }

  // ── Питомцы локации (лужайка) ──
  async function togglePet(pid: number) {
    if (!field) return;
    const next = new Set(allowedPetIds);
    if (next.has(pid)) next.delete(pid);
    else next.add(pid);
    setBusy(true);
    setMsg(null);
    try {
      await api.adminSetFieldPets(fieldId, Array.from(next));
      await load();
    } catch (e: any) {
      setMsg('✗ ' + (e?.response?.data?.detail || 'Ошибка'));
    } finally {
      setBusy(false);
    }
  }

  if (loading || !field) {
    return (
      <Overlay onClose={onClose}>
        <div className="fm-card">Загрузка редактора…</div>
      </Overlay>
    );
  }

  const sz = cellSize();
  const W = field.cols * sz;
  const H = field.rows * sz;

  return (
    <Overlay onClose={onClose} wide>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
        <h2 style={{ margin: 0 }}>🗺️ {field.name}</h2>
        <button className="fm-btn fm-btn-xs fm-btn-outline" onClick={onClose}>✕</button>
      </div>

      {msg && <div className="fm-card" style={{ marginBottom: 10, fontSize: 14 }}>{msg}</div>}

      {/* Настройки поля: название + размеры сетки */}
      <div className="fm-card" style={{ marginBottom: 12 }}>
        <div style={{ fontSize: 13, color: 'var(--text-muted)', marginBottom: 8 }}>
          ⚙️ Параметры поля
        </div>
        <label style={lbl}>Название локации</label>
        <input className="fm-input" value={name} onChange={(e) => setName(e.target.value)} />
        <div style={{ display: 'flex', gap: 8, marginTop: 8 }}>
          <div style={{ flex: 1 }}>
            <label style={lbl}>Колонки</label>
            <input
              className="fm-input"
              type="number"
              min={1}
              max={30}
              value={cols}
              onChange={(e) => {
                setCols(e.target.value);
                if (lockRatio) {
                  const c = Number(e.target.value);
                  if (c > 0) setRows(String(Math.round(c * 3 / 4) || 1));
                }
              }}
            />
          </div>
          <div style={{ flex: 1 }}>
            <label style={lbl}>Строки</label>
            <input
              className="fm-input"
              type="number"
              min={1}
              max={30}
              value={rows}
              onChange={(e) => {
                setRows(e.target.value);
                if (lockRatio) {
                  const r = Number(e.target.value);
                  if (r > 0) setCols(String(Math.round(r * 4 / 3) || 1));
                }
              }}
            />
          </div>
        </div>
        <div style={{ marginTop: 8, maxWidth: 160 }}>
          <label style={lbl}>Мин. уровень для открытия</label>
          <input
            className="fm-input"
            type="number"
            min={0}
            max={16}
            value={minLevel}
            onChange={(e) => setMinLevel(e.target.value)}
          />
        </div>
        <label style={{ display: 'flex', alignItems: 'center', gap: 6, marginTop: 8, fontSize: 13, cursor: 'pointer' }}>
          <input type="checkbox" checked={lockRatio} onChange={(e) => setLockRatio(e.target.checked)} />
          Сохранить пропорции 4:3
        </label>
        <p style={{ fontSize: 11, color: 'var(--text-muted)', margin: '6px 0 0' }}>
          При смене размеров сетка пересоздаётся: клетки вне новых границ (кроме шатров) удаляются.
        </p>
        <button
          className="fm-btn"
          style={{ width: '100%', marginTop: 10 }}
          disabled={busy}
          onClick={saveDims}
        >
          💾 Сохранить параметры
        </button>
      </div>

      {/* Кисти */}
      {(() => {
        const isPlant = !!(field?.plant_category);
        const kind = field?.field_kind || '';
        if (isPlant) {
          const orchard = field?.plant_category === 'orchard';
          return (
            <div style={{ display: 'flex', gap: 6, marginBottom: 10 }}>
              <BrushBtn active={brush === 'bed'} onClick={() => setBrush('bed')}>{orchard ? '🌳 Садовое растение' : '🟩 Грядка'}</BrushBtn>
            </div>
          );
        }
        if (kind === 'house') {
          return (
            <div style={{ display: 'flex', gap: 6, marginBottom: 10 }}>
              <BrushBtn active={brush === 'tent'} onClick={() => setBrush('tent')}>⛺ Производство</BrushBtn>
            </div>
          );
        }
        if (kind === 'lawn') {
          return (
            <div style={{ display: 'flex', gap: 6, marginBottom: 10 }}>
              <BrushBtn active={brush === 'pet'} onClick={() => setBrush('pet')}>🐾 Питомец</BrushBtn>
            </div>
          );
        }
        if (kind === 'barnyard') {
          return (
            <div style={{ display: 'flex', gap: 6, marginBottom: 10 }}>
              <BrushBtn active={brush === 'barnyard'} onClick={() => setBrush('barnyard')}>🐄 Скотный двор</BrushBtn>
            </div>
          );
        }
        return (
          <div style={{ display: 'flex', gap: 6, marginBottom: 10, flexWrap: 'wrap' }}>
            <BrushBtn active={brush === 'bed'} onClick={() => setBrush('bed')}>🟩 Грядка</BrushBtn>
            <BrushBtn active={brush === 'pet'} onClick={() => setBrush('pet')}>🐾 Питомец</BrushBtn>
            <BrushBtn active={brush === 'barnyard'} onClick={() => setBrush('barnyard')}>🐄 Скотный двор</BrushBtn>
            <BrushBtn active={brush === 'tent'} onClick={() => setBrush('tent')}>⛺ Производство</BrushBtn>
          </div>
        );
      })()}
      <p style={{ fontSize: 12, color: 'var(--text-muted)', margin: '0 0 10px' }}>
        {brush === 'tent'
          ? 'Тапайте по клеткам для шатра, затем «Разместить шатёр».'
          : brush === 'bed' && field?.plant_category === 'orchard'
          ? 'Тапайте по клеткам под слот дерева (1…N), затем «Разместить слот дерева».'
          : brush === 'pet' && field?.field_kind === 'lawn'
          ? 'Тапайте по клеткам для питомца, затем «Разместить зону».'
          : 'Тапайте по клеткам — тип меняется сразу (повторный тап убирает).'}
      </p>

      {/* Сетка поверх картинки */}
      <div style={{ overflow: 'auto', marginBottom: 10, border: '1px solid var(--border)', borderRadius: 'var(--radius-sm)', background: '#0c1508' }}>
        <svg
          width={W}
          height={H}
          style={{ display: 'block' }}
        >
          {field.map_url && (
            <image href={mediaUrl(field.map_url)} x={0} y={0} width={W} height={H} preserveAspectRatio="none" pointerEvents="none" />
          )}
          {/* Заливка клеток по типу (только в пределах сетки) */}
          {field.cells.filter((c) => c.col < field.cols && c.row < field.rows).map((c) => {
            const key = `${c.col},${c.row}`;
            let fill: string;
            if (c.kind === 'tent') {
              fill = KIND_FILL.tent;
            } else {
              const isMultiCell = (brush === 'tent' || (brush === 'bed' && field?.plant_category === 'orchard') || (brush === 'pet' && field?.field_kind === 'lawn')) && multiDraft.has(key);
              if (isMultiCell) fill = KIND_FILL.tent;
              else fill = KIND_FILL[c.kind] ?? 'transparent';
            }
            return (
              <rect
                key={key}
                x={c.col * sz}
                y={c.row * sz}
                width={sz}
                height={sz}
                fill={fill}
                stroke={field.grid_color}
                strokeWidth={1}
              />
            );
          })}
          {/* Иконки шатров */}
          {field.tents?.map((t) => {
            const tw = (t.col2 - t.col1 + 1) * sz;
            const th = (t.row2 - t.row1 + 1) * sz;
            return (
              <g key={t.id}>
                {t.image_url && (
                  <image
                    href={mediaUrl(t.image_url)}
                    x={t.col1 * sz + 2}
                    y={t.row1 * sz + 2}
                    width={tw - 4}
                    height={th - 4}
                    preserveAspectRatio="xMidYMid meet"
                  />
                )}
                <text
                  x={t.col1 * sz + tw / 2}
                  y={t.row1 * sz + th / 2 + (t.image_url ? th / 2 - 4 : 4)}
                  fill="#fff"
                  fontSize={11}
                  textAnchor="middle"
                  style={{ pointerEvents: 'none', textShadow: '0 1px 2px #000' }}
                >
                  ⛺ {t.name}
                </text>
              </g>
            );
          })}
          {/* Иконки клеток по итоговому состоянию (драфт) */}
          {field.cells.map((c) => {
            const key = `${c.col},${c.row}`;
            let icon = '';
            if (c.kind === 'tent') return null;
            if (c.kind === 'bed') icon = '🟩';
            else if (c.kind === 'pet') icon = '🐾';
            else if (c.kind === 'barnyard') icon = '🐄';
            if (!icon) return null;
            return (
              <text
                key={`icon-${key}`}
                x={c.col * sz + sz / 2}
                y={c.row * sz + sz / 2 + sz * 0.18}
                fontSize={sz * 0.6}
                fill="#fff"
                textAnchor="middle"
                style={{ pointerEvents: 'none' }}
              >
                {icon}
              </text>
            );
          })}
          {/* События по клеткам */}
          {Array.from({ length: field.rows }).map((_, r) =>
            Array.from({ length: field.cols }).map((_, c) => (
              <rect
                key={`hit-${c}-${r}`}
                x={c * sz}
                y={r * sz}
                width={sz}
                height={sz}
                fill="transparent"
                style={{ cursor: (brush === 'tent' || (brush === 'bed' && field?.plant_category === 'orchard') || (brush === 'pet' && field?.field_kind === 'lawn')) ? 'crosshair' : 'pointer' }}
                onClick={() => onCellClick(c, r)}
              />
            )),
          )}
        </svg>
      </div>

      {(brush === 'tent' || (brush === 'bed' && field?.plant_category === 'orchard') || (brush === 'pet' && field?.field_kind === 'lawn')) && (
        <button className="fm-btn" style={{ width: '100%', marginBottom: 14 }} disabled={busy || multiDraft.size === 0} onClick={openMultiModal}>
          {brush === 'tent' ? '⛺ Разместить шатёр' : brush === 'bed' ? '🌳 Разместить слот дерева' : '🐾 Разместить зону'} ({multiDraft.size})
        </button>
      )}

      {/* Шатры */}
      {field.tents && field.tents.length > 0 && (
        <>
          <h3>⛺ Шатры</h3>
          <div className="fm-grid" style={{ marginBottom: 14 }}>
            {field.tents.map((t) => (
              <div key={t.id} className="fm-card">
                <strong>⛺ {t.name}</strong>
                <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>{kindLabel(t.kind, prodTemplates)}</div>
                <div style={{ fontSize: 12, color: 'var(--text-secondary)' }}>
                  {t.col2 - t.col1 + 1}×{t.row2 - t.row1 + 1}
                </div>
                <button className="fm-btn fm-btn-sm fm-btn-danger" style={{ marginTop: 8, width: '100%' }} disabled={busy} onClick={() => deleteTent(t.id)}>
                  Удалить
                </button>
              </div>
            ))}
          </div>
        </>
      )}

      {/* Садовые слоты (деревья) */}
      {field.plant_beds && field.plant_beds.length > 0 && (
        <>
          <h3>🌳 Слоты деревьев</h3>
          <div className="fm-grid" style={{ marginBottom: 14 }}>
            {field.plant_beds.map((pb) => (
              <div key={pb.id} className="fm-card">
                <strong>🌳 Слот дерева</strong>
                <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>
                  {pb.plant_name ? `Занят: ${pb.plant_name}` : 'Свободен'}
                </div>
                <div style={{ fontSize: 12, color: 'var(--text-secondary)' }}>
                  {pb.col2 - pb.col1 + 1}×{pb.row2 - pb.row1 + 1}
                </div>
                <button className="fm-btn fm-btn-sm fm-btn-danger" style={{ marginTop: 8, width: '100%' }} disabled={busy} onClick={() => deletePlantBed(pb.id)}>
                  Удалить
                </button>
              </div>
            ))}
          </div>
        </>
      )}

      {/* Привязка объектов локации */}
      {field?.field_kind === 'barnyard' ? (
        <>
          <h3>🐄 Животные локации</h3>
          <p style={{ fontSize: 12, color: 'var(--text-muted)', margin: '0 0 8px' }}>
            Отметьте животных, доступных для заселения игроками в скотном дворе.
          </p>
          <div className="fm-grid">
            {allAnimals.map((a) => (
              <label key={a.id} className="fm-card" style={{ cursor: 'pointer' }}>
                <input
                  type="checkbox"
                  checked={allowedAnimalIds.has(a.id)}
                  disabled={busy}
                  onChange={() => toggleAnimal(a.id)}
                  style={{ marginRight: 8 }}
                />
                {a.emoji} {a.name}
              </label>
            ))}
          </div>
        </>
      ) : field?.field_kind === 'lawn' ? (
        <>
          <h3>🐾 Питомцы локации</h3>
          <p style={{ fontSize: 12, color: 'var(--text-muted)', margin: '0 0 8px' }}>
            Отметьте питомцев, доступных для поселения игроками на лужайке.
          </p>
          <div className="fm-grid">
            {allPets.map((p) => (
              <label key={p.id} className="fm-card" style={{ cursor: 'pointer' }}>
                <input
                  type="checkbox"
                  checked={allowedPetIds.has(p.id)}
                  disabled={busy}
                  onChange={() => togglePet(p.id)}
                  style={{ marginRight: 8 }}
                />
                {p.emoji} {p.name}
              </label>
            ))}
          </div>
        </>
      ) : (
        <>
          <h3>🌱 Растения локации</h3>
          <p style={{ fontSize: 12, color: 'var(--text-muted)', margin: '0 0 8px' }}>
            Отметьте растения, доступные для посадки игроками в этой локации.
          </p>
          <div className="fm-grid">
            {allPlants
              .filter((p) => !field?.plant_category || p.category === field.plant_category)
              .map((p) => (
                <label key={p.id} className="fm-card" style={{ cursor: 'pointer' }}>
                  <input
                    type="checkbox"
                    checked={allowedPlantIds.has(p.id)}
                    disabled={busy}
                    onChange={() => togglePlant(p.id)}
                    style={{ marginRight: 8 }}
                  />
                  {p.emoji} {p.name}
                </label>
              ))}
          </div>
        </>
      )}

      {/* Модалка создания мульти-зоны */}
      {multiModal && (
        <div style={modalOverlay}>
          <div className="fm-card fm-rise" onClick={(e) => e.stopPropagation()} style={{ maxWidth: 'calc(var(--shell-max-width) * 0.7)' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
              <h3 style={{ margin: 0 }}>
                {brush === 'tent' ? '⛺ Разместить шатёр' : brush === 'bed' ? '🌳 Разместить слот дерева' : '🐾 Разместить зону питомца'}
              </h3>
              <button className="fm-btn fm-btn-xs fm-btn-outline" onClick={() => setMultiModal(null)}>✕</button>
            </div>
            <p style={{ fontSize: 13, color: 'var(--text-muted)' }}>
              Область: {multiModal.c2 - multiModal.c1 + 1}×{multiModal.r2 - multiModal.r1 + 1} клеток
            </p>
            {brush === 'tent' ? (
              <>
                <label style={lbl}>Название</label>
                <input className="fm-input" value={tentName} onChange={(e) => setTentName(e.target.value)} placeholder="Стол зельеварения" />
                <label style={lbl}>Тип</label>
                <select className="fm-input" value={tentKind} onChange={(e) => setTentKind(e.target.value)}>
                  {prodTemplates.map((pt) => (
                    <option key={pt.code} value={pt.code}>{pt.emoji} {pt.name} ({pt.required} ✝️/цикл)</option>
                  ))}
                  <option value="witch_house">🏠 Дом ведьмы (стройка по материалам)</option>
                </select>
                <label style={lbl}>Картинка шатра (необязательно)</label>
                <input type="file" accept="image/*" onChange={(e) => setTentImage(e.target.files?.[0] || null)} />
              </>
            ) : (
              <p style={{ fontSize: 13, color: 'var(--text-secondary)' }}>
                {brush === 'bed' ? 'Слот садового дерева: игрок сажает сюда 1 дерево (на весь прямоугольник).' : 'Мульти-клеточная зона для питомца.'}
              </p>
            )}
            <button className="fm-btn" style={{ width: '100%', marginTop: 14 }} disabled={busy || (brush === 'tent' && !tentName.trim())} onClick={saveMulti}>
              Разместить
            </button>
          </div>
        </div>
      )}
    </Overlay>
  );
}

const lbl: React.CSSProperties = { display: 'block', margin: '10px 0 6px', fontSize: 14 };
const modalOverlay: React.CSSProperties = {
  position: 'fixed', inset: 0, zIndex: 70, background: 'rgba(0,0,0,0.6)',
  display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 16,
};

function BrushBtn({ active, onClick, children }: { active: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <button className={active ? 'fm-btn' : 'fm-btn fm-btn-outline'} onClick={onClick} style={{ flex: 1, minWidth: 110 }}>
      {children}
    </button>
  );
}

function Overlay({ onClose, wide, children }: { onClose: () => void; wide?: boolean; children: React.ReactNode }) {
  return (
    <div
      style={{
        position: 'fixed', inset: 0, zIndex: 60, background: 'rgba(0,0,0,0.7)',
        backdropFilter: 'blur(3px)', overflowY: 'auto',
        padding: 'calc(var(--vk-inset-top, 0px) + 12px) 12px 24px',
      }}
    >
      <div
        className="fm-card fm-rise"
        onClick={(e) => e.stopPropagation()}
        style={{ maxWidth: wide ? 600 : 460, margin: '0 auto' }}
      >
        {children}
      </div>
    </div>
  );
}



