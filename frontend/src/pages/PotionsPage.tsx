import { useCallback, useEffect, useState } from 'react';
import { useSession } from '../context/SessionContext';
import { api, type Cauldron, type InventoryItem, type PotionRecipe, type UserPotion } from '../api/endpoints';

const INGREDIENT_ICON: Record<string, string> = {
  plant: '🌿',
  product: '📦',
};

const INGREDIENT_LABEL: Record<string, string> = {
  plant: 'Растение',
  product: 'Товар',
};

const LEVEL_LABELS: Record<string, string> = {
  '1': 'Ⅰ',
  '2': 'Ⅱ',
  '3': 'Ⅲ',
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
  const [warehouseItems, setWarehouseItems] = useState<InventoryItem[]>([]);
  const [warehouseLoading, setWarehouseLoading] = useState(false);

  const [levelPage, setLevelPage] = useState(0);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [rec, pots] = await Promise.all([
        api.potionRecipes(),
        api.userPotions().catch(() => [] as UserPotion[]),
      ]);
      setRecipes(rec);
      setUserPotions(pots);
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
    setWarehouseSlot(slotIndex);
    setWarehouseKind(itemKind);
    setWarehouseOpen(true);
    setWarehouseLoading(true);
    try {
      const items = await api.inventory(itemKind);
      setWarehouseItems(items);
    } catch {
      setWarehouseItems([]);
    } finally {
      setWarehouseLoading(false);
    }
  }

  async function selectWarehouseItem(itemId: number) {
    if (warehouseSlot == null || !warehouseKind || !cauldron) return;
    setBusy(true);
    setMsg(null);
    try {
      const c = await api.fillCauldronSlot(cauldron.id, warehouseSlot, warehouseKind, itemId);
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
      setMsg(`✓ Зелье на складе! Бонус: ${potion.bonus_code || '—'}`);
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

  const cauldronMaterial = cauldron?.material === 'tin' ? 'олово' : cauldron?.material === 'silver' ? 'серебро' : cauldron?.material === 'gold' ? 'золото' : '';

  return (
    <div style={{ maxWidth: 'var(--shell-max-width)', margin: '0 auto', padding: 'var(--shell-pad)' }}>
      {msg && (
        <div className="fm-card" style={{ marginBottom: 10, fontSize: 14 }} role="status">{msg}</div>
      )}

      {loading ? (
        <div className="fm-card">Загрузка рецептов…</div>
      ) : (
        <>
          {cauldron ? (
            <div className="fm-card fm-rise" style={{ marginBottom: 14 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                <strong>{cauldron.recipe_name}</strong>
                <span className="fm-chip">{cauldron.status}</span>
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
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
              <button className="fm-card" disabled={safeLevelPage === 0} onClick={() => setLevelPage(safeLevelPage - 1)} style={{ cursor: safeLevelPage === 0 ? 'default' : 'pointer', opacity: safeLevelPage === 0 ? 0.4 : 1, padding: '6px 14px', fontSize: 18 }}>◀</button>
              <span style={{ fontWeight: 600 }}>
                {currentLevel === 'green' ? '🟢 Простые' : currentLevel === 'blue' ? '🔵 Средние' : currentLevel === 'violet' ? '🟣 Сложные' : currentLevel}
                {cauldronMaterial && ` (${cauldronMaterial})`}
              </span>
              <button className="fm-card" disabled={safeLevelPage >= totalLevelPages - 1} onClick={() => setLevelPage(safeLevelPage + 1)} style={{ cursor: safeLevelPage >= totalLevelPages - 1 ? 'default' : 'pointer', opacity: safeLevelPage >= totalLevelPages - 1 ? 0.4 : 1, padding: '6px 14px', fontSize: 18 }}>▶</button>
            </div>
          )}

          {sortedLevels.length === 0 ? (
            <div className="fm-card" style={{ color: 'var(--text-muted)' }}>Нет доступных рецептов.</div>
          ) : currentLevel ? (
            <div style={{ marginBottom: 14 }}>
              <h3 style={{ fontSize: 15, color: 'var(--text-secondary)', margin: '0 0 8px' }}>
                Уровень {LEVEL_LABELS[currentLevel] || currentLevel}
              </h3>
              <div className="fm-grid">
                {groupedByLevel[currentLevel].map((r) => (
                  <div key={r.id} className="fm-card fm-rise">
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                      <div>
                        <strong>{r.name}</strong>
                        <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>
                          {r.ingredient_slots.map((s) => INGREDIENT_ICON[s] || s).join(' ')} · {r.ingredient_slots.length} слота
                        </div>
                        {r.bonus_code && (
                          <div className="fm-chip" style={{ background: 'rgba(160,120,220,0.18)', marginTop: 4 }}>
                            Бонус: {r.bonus_code}
                          </div>
                        )}
                        <div className="fm-chip" style={{ background: 'rgba(224,168,62,0.18)', marginTop: 2 }}>
                          🪙 {r.reward_coins} монет
                        </div>
                      </div>
                    </div>
                    <button
                      className="fm-btn fm-btn-sm"
                      style={{ width: '100%', marginTop: 10 }}
                      disabled={busy || !!cauldron}
                      onClick={() => createCauldron(r.id)}
                    >
                      Установить рецепт и котёл
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
                  <div key={p.id} className="fm-card" style={{ opacity: p.activated ? 0.7 : 1 }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <div>
                        <strong>{p.potion_name}</strong>
                        {p.bonus_code && (
                          <div className="fm-chip" style={{ background: 'rgba(160,120,220,0.18)', marginTop: 4 }}>
                            {p.bonus_code}
                          </div>
                        )}
                      </div>
                      <span className="fm-chip">{p.activated ? 'Активно' : 'Неактивно'}</span>
                    </div>
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
                  onClick={() => selectWarehouseItem(item.item_id)}
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
