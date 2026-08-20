import { useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { useSession } from '../context/SessionContext';
import { api, POTION_INGREDIENT_ICONS as ING_ICON, POTION_INGREDIENT_LABELS as ING_LABEL, potionBonusLabel, cauldronMaterialFor, CAULDRON_MATERIAL_LABELS, type BreweryZoneView, type Cauldron, type FieldDetail, type FieldInfo, type PotionRecipe, type Product, type SlotWarehouseItem } from '../api/endpoints';
import { mediaUrl } from '../api/media';
import LocationMap from '../components/LocationMap';
import Toast from '../components/Toast';
import SpritePedestal from '../components/SpritePedestal';
import { confirmDialog } from '../components/Confirm';

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

export default function BreweryHubPage() {
  const nav = useNavigate();
  const { loading: sessionLoading } = useSession();
  const [fields, setFields] = useState<FieldInfo[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (sessionLoading) return;
    setLoading(true);
    api.fields()
      .then((all) => setFields(all.filter((f) => f.field_kind === 'brewery')))
      .catch(() => setFields([]))
      .finally(() => setLoading(false));
  }, [sessionLoading]);

  return (
    <div style={{ maxWidth: 'var(--shell-max-width)', margin: '0 auto', padding: 'var(--shell-pad)' }}>
      <h1 style={{ fontSize: 20, margin: '0 0 10px' }}>🧪 Зельеварение</h1>

      <h2 style={{ fontSize: 16, marginBottom: 10 }}>Зельеварни</h2>
      {loading ? (
        <div className="fm-card">Загрузка…</div>
      ) : fields.length === 0 ? (
        <div className="fm-card" style={{ color: 'var(--text-muted)' }}>Зельеварен пока нет.</div>
      ) : (
        <div className="fm-grid" style={{ marginBottom: 16 }}>
          {fields.map((f) => (
            <button key={f.id} className="fm-card fm-rise" style={{ fontSize: 13, textAlign: 'left', cursor: 'pointer' }} onClick={() => nav(`/brewery/${f.id}`)}>
              <strong>🧪 {f.name}</strong>
              <div style={{ color: 'var(--text-muted)', marginTop: 2 }}>{f.cols}×{f.rows} клеток</div>
            </button>
          ))}
        </div>
      )}

      <PotionsCatalog />
    </div>
  );
}

function ingredientIcons(slots: string[]): string {
  const counts = new Map<string, number>();
  for (const s of slots) counts.set(s, (counts.get(s) || 0) + 1);
  return Array.from(counts.entries())
    .map(([s, n]) => `${ING_ICON[s] || '❓'}${n > 1 ? `×${n}` : ''}`)
    .join(' ');
}

const LEVEL_LABELS: Record<string, string> = {
  green: '🟢 Простые',
  blue: '🔵 Средние',
  violet: '🟣 Сложные',
};

const CAULDRON_STATUS: Record<string, { label: string; color: string }> = {
  empty: { label: 'Ждёт ингредиенты', color: 'var(--text-muted)' },
  filling: { label: 'Наполняется', color: 'var(--accent-warm)' },
  done: { label: 'Готов', color: 'var(--success)' },
};

function PotionsCatalog() {
  const { loading: sessionLoading } = useSession();
  const [recipes, setRecipes] = useState<PotionRecipe[]>([]);
  const [cauldron, setCauldron] = useState<Cauldron | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  const [levelPage, setLevelPage] = useState(0);
  const [zoomedImg, setZoomedImg] = useState<string | null>(null);
  const [cauldronImages, setCauldronImages] = useState<Record<string, string | null>>({});

  useEffect(() => {
    const materials = ['tin', 'silver', 'gold'];
    Promise.all(
      materials.map(async (m) => {
        try {
          const gm = await api.gameMediaByCode(`cauldron_${m}`);
          return [m, gm.url ? mediaUrl(gm.url) : null] as const;
        } catch {
          return [m, null] as const;
        }
      }),
    ).then((entries) => setCauldronImages(Object.fromEntries(entries)));
  }, []);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [rec, active] = await Promise.all([
        api.potionRecipes(),
        api.activeCauldron().catch(() => null),
      ]);
      setRecipes(rec);
      setCauldron(active);
    } catch (e: any) {
      setMsg('✗ ' + (e?.response?.data?.detail || 'Ошибка загрузки'));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { if (!sessionLoading) load(); }, [load, sessionLoading]);

  const groupedByLevel = recipes.reduce<Record<string, PotionRecipe[]>>((acc, r) => {
    const lv = r.level || '1';
    if (!acc[lv]) acc[lv] = [];
    acc[lv].push(r);
    return acc;
  }, {});

  async function createCauldron(recipeId: number) {
    setBusy(true);
    setMsg(null);
    try {
      const c = await api.createCauldron(recipeId);
      setCauldron(c);
      setMsg('✓ Котёл установлен!');
    } catch (e: any) {
      setMsg('✗ ' + (e?.response?.data?.detail || 'Ошибка'));
    } finally {
      setBusy(false);
    }
  }

  const sortedLevels = Object.keys(groupedByLevel).sort((a, b) => Number(a) - Number(b));
  const totalLevelPages = sortedLevels.length;
  const safeLevelPage = Math.max(0, Math.min(levelPage, Math.max(0, totalLevelPages - 1)));
  const currentLevel = sortedLevels[safeLevelPage];

  const cauldronStatus = cauldron ? CAULDRON_STATUS[cauldron.status] || { label: cauldron.status, color: 'var(--text-muted)' } : null;

  return (
    <div>
      {msg && <Toast text={msg} onClose={() => setMsg(null)} />}

      {loading ? (
        <div className="fm-card">Загрузка рецептов…</div>
      ) : (
        <>
          {cauldron ? (
            <div className="fm-card fm-rise" style={{ marginBottom: 14 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 8 }}>
                <CauldronView material={cauldron.material} imageUrl={mediaUrl(cauldron.image_url) || cauldronImages[cauldron.material] || null} height={56} />
                <div style={{ minWidth: 0, flex: 1 }}>
                  <strong style={{ display: 'block' }}>{cauldron.recipe_name}</strong>
                  <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>
                    {CAULDRON_MATERIAL_LABELS[cauldron.material] || cauldron.material} · {cauldron.capacity} ингр.
                  </div>
                  {cauldronStatus && (
                    <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 13, color: cauldronStatus.color, marginTop: 4 }}>
                      <span style={{ width: 8, height: 8, borderRadius: '50%', background: cauldronStatus.color, flexShrink: 0 }} />
                      {cauldronStatus.label}
                    </div>
                  )}
                </div>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(88px, 1fr))', gap: 8 }}>
                {Array.from({ length: cauldron.capacity }).map((_, i) => {
                  const slot = cauldron.slots.find((s) => s.slot_index === i);
                  const filled = !!slot && slot.item_id != null;
                  const recipe = recipes.find((r) => r.id === cauldron.recipe_id);
                  const slotKind = recipe?.ingredient_slots?.[i] || 'plant';

                  return (
                    <div
                      key={i}
                      className="fm-card"
                      style={{
                        textAlign: 'center',
                        background: filled ? 'rgba(111,174,74,0.18)' : 'rgba(255,255,255,0.04)',
                      }}
                    >
                      {filled && slot.item_image ? (
                        <img src={mediaUrl(slot.item_image)} alt="" style={{ height: 40, maxWidth: '100%', objectFit: 'contain', marginBottom: 2 }} />
                      ) : (
                        <div style={{ fontSize: 24, marginBottom: 2 }}>
                          {filled ? (slot.item_emoji || '✅') : ING_ICON[slotKind] || '❓'}
                        </div>
                      )}
                      <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>
                        {filled ? (slot.item_name || 'Загружено') : (ING_LABEL[slotKind] || slotKind)}
                      </div>
                    </div>
                  );
                })}
              </div>

              {(() => {
                const recipe = recipes.find((r) => r.id === cauldron.recipe_id);
                if (!recipe) return null;
                return (
                  <div style={{ marginTop: 10, fontSize: 13, borderTop: '1px solid var(--border)', paddingTop: 8 }}>
                    <div style={{ color: 'var(--accent-warm)', fontWeight: 600 }}>🪙 Награда: {recipe.reward_coins}</div>
                    {recipe.bonus_code && (
                      <div style={{ color: '#c9a6f2', marginTop: 4 }}>⚡ Бонус: {potionBonusLabel(recipe.bonus_code)}</div>
                    )}
                  </div>
                );
              })()}
            </div>
          ) : null}

          <h2 style={{ fontSize: 16, marginBottom: 10 }}>Рецепты</h2>

          {totalLevelPages > 1 && (
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10, background: 'linear-gradient(180deg, var(--leaf) 0%, var(--grass) 100%)', border: '1px solid var(--grass-deep)', borderRadius: 'var(--radius-md)', padding: '8px 10px', color: '#1a2414' }}>
              <button disabled={safeLevelPage === 0} onClick={() => setLevelPage(safeLevelPage - 1)} style={{ cursor: safeLevelPage === 0 ? 'default' : 'pointer', opacity: safeLevelPage === 0 ? 0.4 : 1, padding: '6px 14px', fontSize: 18, background: 'transparent', border: 'none', color: 'inherit' }}>◀</button>
              <span style={{ fontWeight: 600 }}>
                {LEVEL_LABELS[currentLevel] || currentLevel}
              </span>
              <button disabled={safeLevelPage >= totalLevelPages - 1} onClick={() => setLevelPage(safeLevelPage + 1)} style={{ cursor: safeLevelPage >= totalLevelPages - 1 ? 'default' : 'pointer', opacity: safeLevelPage >= totalLevelPages - 1 ? 0.4 : 1, padding: '6px 14px', fontSize: 18, background: 'transparent', border: 'none', color: 'inherit' }}>▶</button>
            </div>
          )}

          {sortedLevels.length === 0 ? (
            <div className="fm-card" style={{ color: 'var(--text-muted)' }}>Нет доступных рецептов.</div>
          ) : currentLevel ? (
            <div style={{ marginBottom: 14 }}>
              <div className="fm-grid">
                {groupedByLevel[currentLevel].map((r) => (
                  <div key={r.id} className="fm-card fm-rise" style={{ textAlign: 'center' }}>
                    {r.image_url && (
                      <SpritePedestal url={mediaUrl(r.image_url)} height={120} onZoom={setZoomedImg} />
                    )}
                    <strong style={{ display: 'block', marginBottom: 8 }}>{r.name}</strong>
                    {(() => {
                      const material = cauldronMaterialFor(r.ingredient_slots);
                      return (
                        <div
                          style={{
                            display: 'flex',
                            alignItems: 'center',
                            gap: 8,
                            padding: '6px 8px',
                            marginBottom: 8,
                            background: 'var(--surface-strong)',
                            border: '1px solid var(--border)',
                            borderRadius: 'var(--radius-md)',
                            textAlign: 'left',
                          }}
                        >
                          <CauldronView material={material} imageUrl={cauldronImages[material] || null} height={44} />
                          <span style={{ fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.3, flex: 1, minWidth: 0 }}>
                            {CAULDRON_MATERIAL_LABELS[material]}
                            <span style={{ color: 'var(--text-muted)' }}> · {r.ingredient_slots.length} ингр.</span>
                          </span>
                        </div>
                      );
                    })()}
                    <div
                      style={{
                        fontSize: 13,
                        borderTop: '1px solid var(--border)',
                        paddingTop: 8,
                      }}
                    >
                      <div style={{ color: 'var(--accent-warm)', fontWeight: 600, whiteSpace: 'nowrap' }}>🪙 {r.reward_coins}</div>
                      <div style={{ color: 'var(--text-muted)', marginTop: 4 }}>{ingredientIcons(r.ingredient_slots)}</div>
                    </div>
                    {r.bonus_code && (
                      <div
                        style={{
                          marginTop: 8,
                          fontSize: 13,
                          textAlign: 'left',
                          color: '#c9a6f2',
                        }}
                      >
                        ⚡ {potionBonusLabel(r.bonus_code)}
                      </div>
                    )}
                    {r.description && (
                      <p style={{ fontSize: 13, color: 'var(--text-secondary)', margin: '8px 0 0' }}>
                        {r.description}
                      </p>
                    )}
                    <button
                      className="fm-btn fm-btn-sm fm-btn-wrap"
                      style={{ width: '100%', marginTop: 10 }}
                      disabled={busy || !!cauldron}
                      onClick={() => createCauldron(r.id)}
                    >
                      Установить котёл
                    </button>
                  </div>
                ))}
              </div>
            </div>
          ) : null}
        </>
      )}

      {zoomedImg && (
        <div
          style={{ position: 'fixed', inset: 0, zIndex: 80, background: 'rgba(0,0,0,0.7)', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 16 }}
          onClick={() => setZoomedImg(null)}
        >
          <img src={zoomedImg} alt="" style={{ maxWidth: '90vw', maxHeight: '80vh', borderRadius: 10 }} />
        </div>
      )}
    </div>
  );
}

const CAULDRON_FALLBACK_COLORS: Record<string, string> = {
  tin: '#9aa3ad',
  silver: '#c8d2dc',
  gold: '#e0b34a',
};

function CauldronView({ material, imageUrl, height }: { material: string; imageUrl: string | null; height: number }) {
  if (imageUrl) {
    return (
      <img src={imageUrl} alt="" style={{ height, maxWidth: 96, objectFit: 'contain', flexShrink: 0 }} />
    );
  }
  const color = CAULDRON_FALLBACK_COLORS[material] || CAULDRON_FALLBACK_COLORS.tin;
  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        width: height,
        height,
        flexShrink: 0,
        fontSize: Math.round(height * 0.55),
        background: `radial-gradient(circle, ${color}33 0%, ${color}11 100%)`,
        border: `1px solid ${color}66`,
        borderRadius: 'var(--radius-md)',
      }}
    >
      🍲
    </div>
  );
}

export function BreweryScenePage() {
  const { id } = useParams<{ id: string }>();
  const nav = useNavigate();
  const { refresh } = useSession();
  const [field, setField] = useState<FieldDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  const [brewPickRecipe, setBrewPickRecipe] = useState(false);
  const [brewCardModal, setBrewCardModal] = useState<BreweryZoneView | null>(null);
  const [brewCauldronModal, setBrewCauldronModal] = useState(false);
  const [brewSlotIndex, setBrewSlotIndex] = useState<number | null>(null);
  const [brewWarehouse, setBrewWarehouse] = useState<SlotWarehouseItem[]>([]);
  const [brewWarehouseLoading, setBrewWarehouseLoading] = useState(false);
  const [brewPlantItems, setBrewPlantItems] = useState<Record<number, { name: string | null; image: string | null }>>({});
  const [brewProductItems, setBrewProductItems] = useState<Record<number, { name: string | null; image: string | null }>>({});
  const [brewVideoUrl, setBrewVideoUrl] = useState<string | null>(null);
  const [brewVideoOpen, setBrewVideoOpen] = useState(false);
  const [pendingBrewMsg, setPendingBrewMsg] = useState<string | null>(null);
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
    api.gameMediaByCode('potion_brew')
      .then((gm) => { if (gm.url) setBrewVideoUrl(mediaUrl(gm.url)); })
      .catch(() => {});
  }, []);

  useEffect(() => {
    Promise.all([
      api.plants().catch(() => [] as any[]),
      api.products().catch(() => [] as Product[]),
    ]).then(([pls, prds]) => {
      setBrewPlantItems(Object.fromEntries(pls.map((p) => [p.id, { name: p.name, image: p.image_harvested_url || p.image_grown_url || p.image_url || null }])));
      setBrewProductItems(Object.fromEntries(prds.map((p) => [p.id, { name: p.name, image: p.image_url || null }])));
    });
  }, []);

  useEffect(() => {
    if (!msg) return;
    const t = setTimeout(() => setMsg(null), 4000);
    return () => clearTimeout(t);
  }, [msg]);

  const activeCauldron = field?.active_cauldron ?? null;
  const brewCauldronZone = (field?.brewery_zones ?? []).find((z) => z.zone_kind === 'cauldron');
  const brewJarZone = (field?.brewery_zones ?? []).find((z) => z.zone_kind === 'jar');
  const brewIngredientZones = useMemo(
    () => (field?.brewery_zones ?? [])
      .filter((z) => z.zone_kind === 'ingredient')
      .slice()
      .sort((a, b) => (a.row1 - b.row1) || (a.col1 - b.col1)),
    [field],
  );
  const brewCardZones = (field?.brewery_zones ?? []).filter((z) => z.zone_kind === 'recipe_card');
  const brewActiveRecipe = field?.potion_recipes?.find((r) => r.id === activeCauldron?.recipe_id) ?? null;
  const brewAllSlotsFilled = !!activeCauldron && activeCauldron.slots.length > 0 && activeCauldron.slots.every((s) => s.item_id != null);

  function brewSlotItem(slotType: string | null | undefined, itemId: number | null | undefined): { name: string | null; image: string | null } | null {
    if (itemId == null || !slotType) return null;
    if (slotType === 'plant' || slotType === 'plant_garden' || slotType === 'plant_orchard') {
      return brewPlantItems[itemId] ?? null;
    }
    return brewProductItems[itemId] ?? null;
  }

  async function installBrewCauldron(recipeId: number) {
    setBusy(true); setMsg(null);
    try {
      await api.createCauldron(recipeId);
      setBrewPickRecipe(false);
      setBrewCardModal(null);
      setMsg('✓ Котёл установлен!');
      await load(); await refresh();
    } catch (e: any) {
      setMsg('✗ ' + (e?.response?.data?.detail || 'Ошибка'));
    } finally { setBusy(false); }
  }

  async function openBrewSlot(slotIndex: number) {
    if (!activeCauldron) return;
    setBrewSlotIndex(slotIndex);
    setBrewWarehouse([]);
    setBrewWarehouseLoading(true);
    try {
      const items = await api.cauldronSlotWarehouse(activeCauldron.id, slotIndex);
      setBrewWarehouse(items);
    } catch {
      setBrewWarehouse([]);
    } finally {
      setBrewWarehouseLoading(false);
    }
  }

  async function fillBrewSlot(itemKind: string, itemId: number) {
    if (!activeCauldron || brewSlotIndex == null) return;
    setBusy(true); setMsg(null);
    try {
      await api.fillCauldronSlot(activeCauldron.id, brewSlotIndex, itemKind, itemId);
      setBrewSlotIndex(null);
      await load();
    } catch (e: any) {
      setMsg('✗ ' + (e?.response?.data?.detail || 'Ошибка'));
    } finally { setBusy(false); }
  }

  async function clearBrewSlot(slotIndex: number) {
    if (!activeCauldron) return;
    setBusy(true); setMsg(null);
    try {
      await api.clearCauldronSlot(activeCauldron.id, slotIndex);
      await load();
    } catch (e: any) {
      setMsg('✗ ' + (e?.response?.data?.detail || 'Ошибка'));
    } finally { setBusy(false); }
  }

  async function brewNow() {
    if (!activeCauldron) return;
    const name = activeCauldron.recipe_name ?? '';
    setBusy(true); setMsg(null);
    try {
      await api.brewCauldron(activeCauldron.id);
    } catch (e: any) {
      setMsg('✗ ' + (e?.response?.data?.detail || 'Ошибка'));
      setBusy(false);
      return;
    }
    setBusy(false);
    setBrewCauldronModal(false);
    const okMsg = `✓ Зелье «${name}» сварено!`;
    if (brewVideoUrl) {
      setPendingBrewMsg(okMsg);
      setBrewVideoOpen(true);
    } else {
      setMsg(okMsg);
    }
    await load(); await refresh();
  }

  function endBrewVideo() {
    setBrewVideoOpen(false);
    if (pendingBrewMsg) {
      setMsg(pendingBrewMsg);
      setPendingBrewMsg(null);
    }
  }

  if (loading && !field) {
    return (
      <div style={{ maxWidth: 'var(--shell-max-width)', margin: '0 auto', padding: 'var(--shell-pad)' }}>
        <div className="fm-card">Загрузка зельеварни…</div>
      </div>
    );
  }

  return (
    <>
      <LocationMap mapUrl={field?.map_url ?? null} name={field?.name ?? ''} emoji="🧪" onBack={() => nav('/brewery')} backLabel="Зельеварение">
        {field && (
          <>
            {brewCauldronZone && (() => {
              const spanCols = brewCauldronZone.col2 - brewCauldronZone.col1 + 1;
              const spanRows = brewCauldronZone.row2 - brewCauldronZone.row1 + 1;
              return (
                <div
                  style={{
                    position: 'absolute', inset: 0, pointerEvents: 'none', display: 'grid',
                    gridTemplateColumns: `repeat(${field.cols}, 1fr)`,
                    gridTemplateRows: `repeat(${field.rows}, 1fr)`,
                  }}
                >
                  <div
                    onClick={() => {
                      if (activeCauldron) setBrewCauldronModal(true);
                      else setBrewPickRecipe(true);
                    }}
                    style={{
                      gridColumn: `${brewCauldronZone.col1 + 1} / span ${spanCols}`,
                      gridRow: `${brewCauldronZone.row1 + 1} / span ${spanRows}`,
                      position: 'relative', display: 'flex', flexDirection: 'column',
                      alignItems: 'center', justifyContent: 'center',
                      padding: 4, overflow: 'hidden', borderRadius: 6,
                      border: activeCauldron ? 'none' : '2px dashed rgba(160,120,220,0.7)',
                      cursor: 'pointer', touchAction: 'manipulation', pointerEvents: 'auto',
                    }}
                  >
                    {activeCauldron && brewCauldronZone.image_url && (
                      <img src={mediaUrl(brewCauldronZone.image_url)} alt="" style={{ position: 'absolute', inset: 0, width: '100%', height: '100%', objectFit: 'contain', pointerEvents: 'none' }} />
                    )}
                    {activeCauldron ? (
                      <div style={{ position: 'absolute', left: 2, right: 2, bottom: 1, fontSize: 'clamp(9px,2.2vw,13px)', color: '#e6d9ff', textAlign: 'center', textShadow: '0 1px 3px #000', fontWeight: 600, background: 'rgba(10,16,8,0.45)', borderRadius: 4, padding: '0 4px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                        🍲 {activeCauldron.recipe_name ?? 'Котёл'}
                      </div>
                    ) : (
                      <div style={{ fontSize: 'clamp(10px,2.4vw,14px)', color: '#e6d9ff', textAlign: 'center', textShadow: '0 1px 3px #000', fontWeight: 600, lineHeight: 1.15 }}>
                        🍲 Место котла
                        <div style={{ fontSize: 10, opacity: 0.85 }}>установить</div>
                      </div>
                    )}
                  </div>
                </div>
              );
            })()}

            {brewJarZone && (() => {
              const spanCols = brewJarZone.col2 - brewJarZone.col1 + 1;
              const spanRows = brewJarZone.row2 - brewJarZone.row1 + 1;
              const jarImg = brewActiveRecipe?.image_url ?? brewCardZones.find((z) => z.recipe_id === activeCauldron?.recipe_id)?.recipe_image ?? null;
              return (
                <div
                  style={{
                    position: 'absolute', inset: 0, pointerEvents: 'none', display: 'grid',
                    gridTemplateColumns: `repeat(${field.cols}, 1fr)`,
                    gridTemplateRows: `repeat(${field.rows}, 1fr)`,
                  }}
                >
                  <div
                    style={{
                      gridColumn: `${brewJarZone.col1 + 1} / span ${spanCols}`,
                      gridRow: `${brewJarZone.row1 + 1} / span ${spanRows}`,
                      position: 'relative', display: 'flex', flexDirection: 'column',
                      alignItems: 'center', justifyContent: 'center',
                      padding: 4, overflow: 'hidden', borderRadius: 6,
                      border: activeCauldron ? 'none' : '1px dashed rgba(160,120,220,0.45)',
                      pointerEvents: 'none',
                    }}
                  >
                    {activeCauldron && jarImg && (
                      <img src={mediaUrl(jarImg)} alt="" style={{ position: 'absolute', inset: 0, width: '100%', height: '100%', objectFit: 'contain', pointerEvents: 'none' }} />
                    )}
                    {activeCauldron && !jarImg && (
                      <div style={{ fontSize: '9vw', lineHeight: 1, opacity: 0.9 }}>🧪</div>
                    )}
                  </div>
                </div>
              );
            })()}

            {brewIngredientZones.map((z, i) => {
              const slot = activeCauldron?.slots.find((s) => s.slot_index === i) ?? null;
              const slotType = brewActiveRecipe?.ingredient_slots?.[i] ?? null;
              const filled = slot?.item_id != null;
              return (
                <div
                  key={`bzi-${z.id}`}
                  style={{
                    position: 'absolute', inset: 0, pointerEvents: 'none', display: 'grid',
                    gridTemplateColumns: `repeat(${field.cols}, 1fr)`,
                    gridTemplateRows: `repeat(${field.rows}, 1fr)`,
                  }}
                >
                  <div
                    onClick={async () => {
                      if (!activeCauldron || !slot) return;
                      if (filled) {
                        const placed = brewSlotItem(slotType, slot?.item_id);
                        const ok = await confirmDialog(
                          placed?.name ? `Убрать «${placed.name}» из котла?` : 'Убрать ингредиент из котла?',
                          'Убрать ингредиент',
                        );
                        if (ok) clearBrewSlot(i);
                      } else {
                        openBrewSlot(i);
                      }
                    }}
                    style={{
                      gridColumn: `${z.col1 + 1} / span 1`,
                      gridRow: `${z.row1 + 1} / span 1`,
                      position: 'relative', display: 'flex', flexDirection: 'column',
                      alignItems: 'center', justifyContent: 'center',
                      borderRadius: 6, overflow: 'hidden',
                      border: activeCauldron && slot ? '1px solid rgba(160,120,220,0.55)' : '1px dashed rgba(160,120,220,0.3)',
                      background: filled ? 'rgba(111,174,74,0.22)' : 'rgba(30,20,50,0.30)',
                      cursor: activeCauldron && slot ? 'pointer' : 'default',
                      touchAction: 'manipulation', pointerEvents: activeCauldron && slot ? 'auto' : 'none',
                    }}
                  >
                    {(() => {
                      const placed = filled ? brewSlotItem(slotType, slot?.item_id) : null;
                      if (placed && placed.image) {
                        return (
                          <>
                            <img
                              src={mediaUrl(placed.image)}
                              alt=""
                              style={{ width: '100%', flex: 1, minHeight: 0, objectFit: 'contain', padding: '2px 2px 0', pointerEvents: 'none' }}
                            />
                            <div
                              style={{
                                fontSize: 9, lineHeight: 1.25, color: '#e6d9ff',
                                background: 'rgba(26,16,46,0.85)',
                                border: '1px solid rgba(160,120,220,0.65)',
                                borderRadius: 4, padding: '1px 4px',
                                margin: '0 2px 2px', maxWidth: 'calc(100% - 4px)',
                                overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                                pointerEvents: 'none', textAlign: 'center',
                              }}
                            >
                              {placed.name}
                            </div>
                          </>
                        );
                      }
                      return (
                        <>
                          <div style={{ fontSize: 'clamp(14px,4vw,24px)', lineHeight: 1, pointerEvents: 'none', display: 'flex', alignItems: 'center', justifyContent: 'center', width: '100%' }}>
                            {filled ? '✅' : slotType ? (ING_ICON[slotType] || '❓') : '▫️'}
                          </div>
                          {activeCauldron && slot && (
                            <div style={{ fontSize: 8, color: '#e6d9ff', textShadow: '0 1px 2px #000', pointerEvents: 'none', textAlign: 'center', maxWidth: '100%', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                              {filled ? 'убрать' : (slotType ? (ING_LABEL[slotType] || slotType) : '')}
                            </div>
                          )}
                        </>
                      );
                    })()}
                  </div>
                </div>
              );
            })}

            {brewCardZones.map((z) => {
              const spanCols = z.col2 - z.col1 + 1;
              const spanRows = z.row2 - z.row1 + 1;
              const cardImg = brewActiveRecipe?.card_image_url || brewActiveRecipe?.image_url || null;
              return (
                <div
                  key={`bzc-${z.id}`}
                  style={{
                    position: 'absolute', inset: 0, pointerEvents: 'none', display: 'grid',
                    gridTemplateColumns: `repeat(${field.cols}, 1fr)`,
                    gridTemplateRows: `repeat(${field.rows}, 1fr)`,
                  }}
                >
                  <div
                    onClick={() => (activeCauldron ? setBrewCardModal(z) : setBrewPickRecipe(true))}
                    style={{
                      gridColumn: `${z.col1 + 1} / span ${spanCols}`,
                      gridRow: `${z.row1 + 1} / span ${spanRows}`,
                      position: 'relative', display: 'flex', flexDirection: 'column',
                      alignItems: 'center', justifyContent: 'center',
                      padding: 2, overflow: 'hidden', borderRadius: 6,
                      border: '1px dashed rgba(160,120,220,0.4)',
                      cursor: 'pointer', touchAction: 'manipulation', pointerEvents: 'auto',
                    }}
                  >
                    {cardImg && (
                      <img src={mediaUrl(cardImg)} alt="" style={{ position: 'absolute', inset: 0, width: '100%', height: '100%', objectFit: 'contain', pointerEvents: 'none' }} />
                    )}
                    {!cardImg && (
                      <div style={{ fontSize: 'clamp(10px,2.4vw,14px)', color: '#e6d9ff', textAlign: 'center', textShadow: '0 1px 3px #000', fontWeight: 600 }}>
                        🃏 Выбрать зелье
                      </div>
                    )}
                  </div>
                </div>
              );
            })}
          </>
        )}
      </LocationMap>

      {msg && <Toast text={msg} onClose={() => setMsg(null)} />}

      {brewPickRecipe && field && (
        <Modal title="🍲 Установить котёл" onClose={() => setBrewPickRecipe(false)}>
          {activeCauldron && (
            <div className="fm-card" style={{ marginBottom: 10, fontSize: 13 }}>
              Уже стоит котёл с рецептом «{activeCauldron.recipe_name}». Сначала сварите или очистите его.
            </div>
          )}
          <p style={{ fontSize: 13, color: 'var(--text-muted)' }}>
            Выберите зелье из привязанных к этой зельеварне:
          </p>
          {(field.potion_recipes ?? []).length === 0 ? (
            <div className="fm-card" style={{ color: 'var(--text-muted)' }}>В этой зельеварне нет привязанных зелий.</div>
          ) : (
            <div className="fm-grid">
              {(field.potion_recipes ?? []).map((r) => (
                <div key={r.id} className="fm-card fm-rise" style={{ textAlign: 'center', cursor: activeCauldron ? 'default' : 'pointer', opacity: activeCauldron ? 0.6 : 1 }} onClick={() => { if (!activeCauldron) installBrewCauldron(r.id); }}>
                  {r.image_url && <img src={mediaUrl(r.image_url)} alt="" style={{ height: 72, maxWidth: '100%', objectFit: 'contain', marginBottom: 6 }} />}
                  <strong style={{ display: 'block', fontSize: 13, marginBottom: 4 }}>{r.name}</strong>
                  <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>{r.ingredient_slots.length} ингр. · 🪙 {r.reward_coins}</div>
                </div>
              ))}
            </div>
          )}
        </Modal>
      )}

      {brewCardModal && field && (() => {
        const r = activeCauldron ? ((field.potion_recipes ?? []).find((x) => x.id === activeCauldron.recipe_id) ?? null) : null;
        const cardImg = r?.card_image_url || r?.image_url || null;
        return (
          <Modal title={`🃏 ${r?.name ?? activeCauldron?.recipe_name ?? 'Рецепт'}`} onClose={() => setBrewCardModal(null)}>
            {cardImg && (
              <img src={mediaUrl(cardImg)} alt="" style={{ width: '100%', maxHeight: 260, objectFit: 'contain', marginBottom: 10, borderRadius: 8 }} onClick={() => setZoomedImg(mediaUrl(cardImg!))} />
            )}
            {r && (
              <>
                <div style={{ fontSize: 13, color: 'var(--text-secondary)', marginBottom: 6 }}>
                  {r.ingredient_slots.map((s) => ING_ICON[s] || '❓').join(' ')} · {r.ingredient_slots.length} ингредиентов · 🪙 {r.reward_coins}
                </div>
                {r.bonus_code && (
                  <div style={{ fontSize: 13, borderLeft: '3px solid #a078dc', paddingLeft: 8, color: '#c9a6f2', marginBottom: 6 }}>
                    ⚡ {potionBonusLabel(r.bonus_code)}
                  </div>
                )}
                {r.description && <p style={{ fontSize: 13, color: 'var(--text-secondary)', margin: '6px 0' }}>{r.description}</p>}
              </>
            )}
            {activeCauldron && (
              <div className="fm-card" style={{ fontSize: 13 }}>
                Это зелье сейчас варится в вашем котле.
              </div>
            )}
          </Modal>
        );
      })()}

      {brewCauldronModal && activeCauldron && (
        <Modal title={`🍲 ${activeCauldron.recipe_name ?? 'Котёл'}`} onClose={() => setBrewCauldronModal(false)}>
          <div style={{ fontSize: 13, color: 'var(--text-muted)', marginBottom: 8 }}>
            Слоты: {activeCauldron.slots.filter((s) => s.item_id != null).length}/{activeCauldron.slots.length} заполнено.
            Тапайте по окошкам на карте, чтобы добавить или убрать ингредиенты.
          </div>
          <div className="fm-grid" style={{ marginBottom: 10 }}>
            {activeCauldron.slots.map((s) => {
              const slotType = brewActiveRecipe?.ingredient_slots?.[s.slot_index] ?? null;
              return (
                <div key={s.slot_index} className="fm-card" style={{ textAlign: 'center', fontSize: 13, background: s.item_id != null ? 'rgba(111,174,74,0.18)' : undefined }}>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: 30 }}>
                    {(() => {
                      const placed = s.item_id != null ? brewSlotItem(slotType, s.item_id) : null;
                      if (placed && placed.image) {
                        return <img src={mediaUrl(placed.image)} alt="" style={{ maxHeight: 28, maxWidth: '90%', objectFit: 'contain' }} />;
                      }
                      return s.item_id != null ? '✅' : (slotType ? (ING_ICON[slotType] || '❓') : '▫️');
                    })()}
                  </div>
                  <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>
                    {(() => {
                      const placed = s.item_id != null ? brewSlotItem(slotType, s.item_id) : null;
                      return placed && placed.name ? placed.name : (slotType ? (ING_LABEL[slotType] || slotType) : 'слот');
                    })()}
                  </div>
                </div>
              );
            })}
          </div>
          {brewAllSlotsFilled ? (
            <button className="fm-btn" style={{ width: '100%' }} disabled={busy} onClick={brewNow}>🧪 Сварить зелье</button>
          ) : (
            <div className="fm-card" style={{ fontSize: 13, color: 'var(--text-muted)' }}>Заполните все окошки ингредиентов на карте.</div>
          )}
        </Modal>
      )}

      {brewVideoOpen && brewVideoUrl && (
        <Modal title="🧪 Варка зелья" onClose={endBrewVideo}>
          <video
            src={brewVideoUrl}
            autoPlay
            muted
            playsInline
            style={{ width: '100%', maxHeight: '55vh', borderRadius: 8 }}
            onEnded={endBrewVideo}
            onError={endBrewVideo}
          />
          <button className="fm-btn fm-btn-sm fm-btn-outline" style={{ marginTop: 6 }} onClick={endBrewVideo}>
            Пропустить видео
          </button>
        </Modal>
      )}

      {brewSlotIndex != null && activeCauldron && (() => {
        const slotType = brewActiveRecipe?.ingredient_slots?.[brewSlotIndex] ?? null;
        return (
          <Modal title={slotType ? `Выбрать: ${ING_LABEL[slotType] || slotType}` : 'Выбор ингредиента'} onClose={() => setBrewSlotIndex(null)}>
            {brewWarehouseLoading ? (
              <div style={{ color: 'var(--text-muted)' }}>Загрузка склада…</div>
            ) : brewWarehouse.length === 0 ? (
              <div className="fm-card" style={{ color: 'var(--text-muted)' }}>Нет подходящих предметов на складе.</div>
            ) : (
              <div className="fm-grid">
                {brewWarehouse.map((item) => (
                  <div key={`${item.item_kind}-${item.item_id}`} className="fm-card fm-rise" style={{ cursor: 'pointer' }} onClick={() => fillBrewSlot(item.item_kind, item.item_id)}>
                    {item.item_image ? (
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                        <img src={mediaUrl(item.item_image)} alt="" style={{ height: 44, maxWidth: 60, objectFit: 'contain', flexShrink: 0 }} />
                        <div style={{ minWidth: 0, flex: 1 }}>
                          <div style={{ fontSize: 13, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{item.item_name}</div>
                          <span className="fm-chip">×{item.qty}</span>
                        </div>
                      </div>
                    ) : (
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                        <span>{item.item_emoji} {item.item_name}</span>
                        <span className="fm-chip">×{item.qty}</span>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </Modal>
        );
      })()}

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
