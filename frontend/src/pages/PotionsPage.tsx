import { useCallback, useEffect, useState } from 'react';
import { useSession } from '../context/SessionContext';
import { api, potionBonusLabel, cauldronMaterialFor, CAULDRON_MATERIAL_LABELS, POTION_INGREDIENT_ICONS as INGREDIENT_ICON, POTION_INGREDIENT_LABELS as INGREDIENT_LABEL, type Cauldron, type SlotWarehouseItem, type PotionRecipe, type UserPotion } from '../api/endpoints';
import { mediaUrl } from '../api/media';
import Toast from '../components/Toast';
import SpritePedestal from '../components/SpritePedestal';

function ingredientIcons(slots: string[]): string {
  const counts = new Map<string, number>();
  for (const s of slots) counts.set(s, (counts.get(s) || 0) + 1);
  return Array.from(counts.entries())
    .map(([s, n]) => `${INGREDIENT_ICON[s] || '❓'}${n > 1 ? `×${n}` : ''}`)
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

export default function PotionsPage() {
  const { refresh, loading: sessionLoading } = useSession();
  const [recipes, setRecipes] = useState<PotionRecipe[]>([]);
  const [cauldron, setCauldron] = useState<Cauldron | null>(null);
  const [userPotions, setUserPotions] = useState<UserPotion[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  const [warehouseOpen, setWarehouseOpen] = useState(false);
  const [warehouseSlot, setWarehouseSlot] = useState<number | null>(null);
  const [warehouseKind, setWarehouseKind] = useState<string | null>(null);
  const [warehouseItems, setWarehouseItems] = useState<SlotWarehouseItem[]>([]);
  const [warehouseLoading, setWarehouseLoading] = useState(false);

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
      const [rec, pots, active] = await Promise.all([
        api.potionRecipes(),
        api.userPotions().catch(() => [] as UserPotion[]),
        api.activeCauldron().catch(() => null),
      ]);
      setRecipes(rec);
      setUserPotions(pots);
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

  async function openWarehouse(slotIndex: number, itemKind: string) {
    if (!cauldron) return;
    setWarehouseSlot(slotIndex);
    setWarehouseKind(itemKind);
    setWarehouseOpen(true);
    setWarehouseLoading(true);
    try {
      const items = await api.cauldronSlotWarehouse(cauldron.id, slotIndex);
      setWarehouseItems(items);
    } catch {
      setWarehouseItems([]);
    } finally {
      setWarehouseLoading(false);
    }
  }

  async function selectWarehouseItem(itemKind: string, itemId: number) {
    if (warehouseSlot == null || !cauldron) return;
    setBusy(true);
    setMsg(null);
    try {
      const c = await api.fillCauldronSlot(cauldron.id, warehouseSlot, itemKind, itemId);
      setCauldron(c);
      setWarehouseOpen(false);
      setWarehouseSlot(null);
      setWarehouseKind(null);
    } catch (e: any) {
      setMsg('✗ ' + (e?.response?.data?.detail || 'Ошибка'));
    } finally {
      setBusy(false);
    }
  }

  async function clearSlot(slotIndex: number) {
    if (!cauldron) return;
    setBusy(true);
    setMsg(null);
    try {
      const c = await api.clearCauldronSlot(cauldron.id, slotIndex);
      setCauldron(c);
    } catch (e: any) {
      setMsg('✗ ' + (e?.response?.data?.detail || 'Ошибка'));
    } finally {
      setBusy(false);
    }
  }

  async function brew() {
    if (!cauldron) return;
    setBusy(true);
    setMsg(null);
    try {
      const potion = await api.brewCauldron(cauldron.id);
      setCauldron(null);
      const brewed = recipes.find((r) => r.id === potion.recipe_id);
      setMsg(`✓ Зелье на складе! Бонус: ${potionBonusLabel(brewed?.bonus_code) || '—'}`);
      const pots = await api.userPotions();
      setUserPotions(pots);
      await refresh();
    } catch (e: any) {
      setMsg('✗ ' + (e?.response?.data?.detail || 'Ошибка'));
    } finally {
      setBusy(false);
    }
  }

  async function activatePotion(id: number) {
    setBusy(true);
    setMsg(null);
    try {
      await api.activatePotion(id);
      setMsg('✓ Бонус активирован!');
      const pots = await api.userPotions();
      setUserPotions(pots);
      await refresh();
    } catch (e: any) {
      setMsg('✗ ' + (e?.response?.data?.detail || 'Ошибка'));
    } finally {
      setBusy(false);
    }
  }

  const allSlotsFilled = cauldron && cauldron.slots.length === cauldron.capacity && cauldron.slots.every((s) => s.item_id);

  const sortedLevels = Object.keys(groupedByLevel).sort((a, b) => Number(a) - Number(b));
  const totalLevelPages = sortedLevels.length;
  const safeLevelPage = Math.max(0, Math.min(levelPage, Math.max(0, totalLevelPages - 1)));
  const currentLevel = sortedLevels[safeLevelPage];

  const cauldronStatus = cauldron ? CAULDRON_STATUS[cauldron.status] || { label: cauldron.status, color: 'var(--text-muted)' } : null;

  return (
    <div style={{ maxWidth: 'var(--shell-max-width)', margin: '0 auto', padding: 'var(--shell-pad)' }}>
      {msg && <Toast text={msg} onClose={() => setMsg(null)} />}

      {loading ? (
        <div className="fm-card">Загрузка рецептов…</div>
      ) : (
        <>
          {cauldron ? (
            <div className="fm-card fm-rise" style={{ marginBottom: 14 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 8, marginBottom: 8 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 10, minWidth: 0 }}>
                  <CauldronView material={cauldron.material} imageUrl={cauldronImages[cauldron.material] || null} height={56} />
                  <div style={{ minWidth: 0 }}>
                    <strong style={{ display: 'block' }}>{cauldron.recipe_name}</strong>
                    <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>
                      {CAULDRON_MATERIAL_LABELS[cauldron.material] || cauldron.material} · {cauldron.capacity} ингр.
                    </span>
                  </div>
                </div>
                {cauldronStatus && (
                  <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6, fontSize: 13, whiteSpace: 'nowrap', color: cauldronStatus.color }}>
                    <span style={{ width: 8, height: 8, borderRadius: '50%', background: cauldronStatus.color, flexShrink: 0 }} />
                    {cauldronStatus.label}
                  </span>
                )}
              </div>

              <div className="fm-grid" style={{ gridTemplateColumns: `repeat(${cauldron.capacity}, 1fr)` }}>
                {Array.from({ length: cauldron.capacity }).map((_, i) => {
                  const slot = cauldron.slots.find((s) => s.slot_index === i);
                  const filled = slot && slot.item_id;
                  const recipe = recipes.find((r) => r.id === cauldron.recipe_id);
                  const slotKind = recipe?.ingredient_slots?.[i] || 'plant';

                  return (
                    <div
                      key={i}
                      className="fm-card"
                      style={{
                        textAlign: 'center',
                        cursor: filled ? 'pointer' : 'pointer',
                        background: filled ? 'rgba(111,174,74,0.18)' : 'rgba(255,255,255,0.04)',
                        position: 'relative',
                      }}
                      onClick={() => {
                        if (filled) {
                          clearSlot(i);
                        } else {
                          openWarehouse(i, slotKind);
                        }
                      }}
                    >
                      <div style={{ fontSize: 24, marginBottom: 2 }}>
                        {filled ? '✅' : INGREDIENT_ICON[slotKind] || '❓'}
                      </div>
                      <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>
                        {filled ? 'Нажатие очистит' : INGREDIENT_LABEL[slotKind] || slotKind}
                      </div>
                    </div>
                  );
                })}
              </div>

              {allSlotsFilled && (
                <button
                  className="fm-btn"
                  style={{ width: '100%', marginTop: 12 }}
                  disabled={busy}
                  onClick={brew}
                >
                  🧪 Сварить зелье
                </button>
              )}
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
                          <span style={{ fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.3 }}>
                            {CAULDRON_MATERIAL_LABELS[material]}
                            <span style={{ color: 'var(--text-muted)' }}> · {r.ingredient_slots.length} ингр.</span>
                          </span>
                        </div>
                      );
                    })()}
                    <div
                      style={{
                        display: 'flex',
                        justifyContent: 'space-between',
                        alignItems: 'center',
                        gap: 8,
                        fontSize: 13,
                        borderTop: '1px solid var(--border)',
                        paddingTop: 8,
                      }}
                    >
                      <span style={{ color: 'var(--text-muted)' }}>{ingredientIcons(r.ingredient_slots)}</span>
                      <span style={{ color: 'var(--accent-warm)', fontWeight: 600, whiteSpace: 'nowrap' }}>🪙 {r.reward_coins}</span>
                    </div>
                    {r.bonus_code && (
                      <div
                        style={{
                          marginTop: 8,
                          fontSize: 13,
                          textAlign: 'left',
                          borderLeft: '3px solid #a078dc',
                          paddingLeft: 8,
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
                      className="fm-btn fm-btn-sm"
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

          {userPotions.length > 0 && (
            <>
              <h2 style={{ fontSize: 16, margin: '18px 0 10px' }}>Мои зелья</h2>
              <div className="fm-grid">
                {userPotions.map((p) => (
                  <div key={p.id} className="fm-card" style={{ textAlign: 'center', opacity: p.activated ? 0.7 : 1 }}>
                    {p.image_url && (
                      <SpritePedestal url={mediaUrl(p.image_url)} height={96} onZoom={setZoomedImg} />
                    )}
                    <strong style={{ display: 'block', marginBottom: 8 }}>{p.potion_name}</strong>
                    {(p.bonus_description || p.bonus_code) && (
                      <div
                        style={{
                          fontSize: 13,
                          textAlign: 'left',
                          borderLeft: '3px solid #a078dc',
                          paddingLeft: 8,
                          color: '#c9a6f2',
                        }}
                      >
                        ⚡ {p.bonus_description || p.bonus_code}
                      </div>
                    )}
                    <div
                      style={{
                        marginTop: 8,
                        fontSize: 13,
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        gap: 6,
                        color: p.activated ? 'var(--success)' : 'var(--text-muted)',
                      }}
                    >
                      <span
                        style={{
                          width: 8,
                          height: 8,
                          borderRadius: '50%',
                          background: p.activated ? 'var(--success)' : 'var(--text-muted)',
                          flexShrink: 0,
                        }}
                      />
                      {p.activated ? 'Активно' : 'Неактивно'}
                    </div>
                    {p.description && (
                      <p style={{ fontSize: 13, color: 'var(--text-secondary)', margin: '8px 0 0' }}>
                        {p.description}
                      </p>
                    )}
                    {!p.activated && (
                      <button
                        className="fm-btn fm-btn-sm"
                        style={{ width: '100%', marginTop: 8 }}
                        disabled={busy}
                        onClick={() => activatePotion(p.id)}
                      >
                        Активировать бонус
                      </button>
                    )}
                  </div>
                ))}
              </div>
            </>
          )}
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

      {warehouseOpen && (
        <Modal title={warehouseKind ? `Выбрать: ${INGREDIENT_LABEL[warehouseKind] || warehouseKind}` : 'Склад'} onClose={() => { setWarehouseOpen(false); setWarehouseSlot(null); setWarehouseKind(null); }}>
          {warehouseLoading ? (
            <div style={{ color: 'var(--text-muted)' }}>Загрузка склада…</div>
          ) : warehouseItems.length === 0 ? (
            <div style={{ color: 'var(--text-muted)' }}>Нет подходящих предметов на складе.</div>
          ) : (
            <div className="fm-grid">
              {warehouseItems.map((item) => (
                <div
                  key={item.item_id}
                  className="fm-card fm-rise"
                  style={{ cursor: 'pointer' }}
                  onClick={() => selectWarehouseItem(item.item_kind, item.item_id)}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <span>{item.item_emoji} {item.item_name}</span>
                    <span className="fm-chip">×{item.qty}</span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </Modal>
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

function Modal({ title, children, onClose }: { title: string; children: React.ReactNode; onClose: () => void }) {
  return (
    <div
      style={{
        position: 'fixed', inset: 0, zIndex: 60,
        background: 'rgba(0,0,0,0.6)', backdropFilter: 'blur(3px)',
        display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 16,
      }}
    >
      <div
        className="fm-card fm-rise"
        onClick={(e) => e.stopPropagation()}
        style={{ width: '100%', maxWidth: 'calc(var(--shell-max-width) * 0.767)', maxHeight: '85vh', overflowY: 'auto' }}
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
