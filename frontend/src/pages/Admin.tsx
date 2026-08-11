import { useCallback, useEffect, useRef, useState } from 'react';
import { useSession } from '../context/SessionContext';
import { api, type AdminOrder, type Animal, type FieldDetail, type FieldInfo, type LevelGate, type LevelGateCreate, type OrderTemplate, type OrderTemplateCreate, type Pet, type Plant, type Player, type PlayerDetail, type PotionRecipe, type PotionRecipeCreate, type Product, type ProductionTemplate, type Setting, type StitchReport } from '../api/endpoints';
import { mediaUrl } from '../api/media';
import FieldEditor from '../components/FieldEditor';
import CrystalStandardEditor from '../components/CrystalStandardEditor';

const SETTING_FIELDS: { key: string; label: string; hint: string }[] = [
  { key: 'auto_credit', label: 'Авто-зачёт вышивки (0/1)', hint: '1 — крестики начисляются сразу без модерации' },
  { key: 'default_plant_qty', label: 'Кол-во растений в заказе (1–50)', hint: 'По умолчанию при посадке' },
  { key: 'production_required', label: 'Норма цикла производства', hint: 'Крестики за один цикл крафта' },
  { key: 'order_reward_per_unit', label: 'Награда за единицу заказа', hint: 'Монет за 1 товар' },
  { key: 'production_norm_lvl1', label: 'Норма переработки ур.1', hint: 'Крестиков на 1 растение 1 уровня' },
  { key: 'production_norm_lvl2', label: 'Норма переработки ур.2', hint: 'Крестиков на 1 растение 2 уровня' },
  { key: 'production_norm_lvl3', label: 'Норма переработки ур.3', hint: 'Крестиков на 1 растение 3 уровня' },
  { key: 'study_norm_lvl1', label: 'Норма изучения ур.1', hint: 'Крестиков на изучение рецепта 1 уровня' },
  { key: 'study_norm_lvl2', label: 'Норма изучения ур.2', hint: 'Крестиков на изучение рецепта 2 уровня' },
  { key: 'study_norm_lvl3', label: 'Норма изучения ур.3', hint: 'Крестиков на изучение рецепта 3 уровня' },
  { key: 'animal_production_norm', label: 'Норма продукции животного', hint: 'За 1 ед. продукции (умножается на кубик)' },
  { key: 'sale_price_ratio', label: 'Коэфф. продажи излишков (0.01–1.0)', hint: 'Доля от полной цены (0.5 = ½)' },
  { key: 'crystal_rate_variant', label: 'Вариант таблицы норм (1–8)', hint: 'Пресет для глобальных норм кристаллов' },
];

export default function AdminPage() {
  const [tab, setTab] = useState<'players' | 'settings' | 'fields' | 'orders' | 'plants' | 'animals' | 'pets' | 'products' | 'productions' | 'order-templates' | 'levels' | 'potion-recipes'>('players');
  const [players, setPlayers] = useState<Player[]>([]);
  const [allPlayers, setAllPlayers] = useState<Player[]>([]);
  const [playerSearch, setPlayerSearch] = useState('');
  const [playerPage, setPlayerPage] = useState(0);
  const PER_PAGE = 100;
  const searchTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  function doSearch(q: string) {
    if (searchTimer.current) clearTimeout(searchTimer.current);
    searchTimer.current = setTimeout(() => {
      const s = q.trim().toLowerCase();
      let filtered: Player[];
      if (!s) {
        filtered = allPlayers;
      } else {
        const num = Number(s);
        if (Number.isFinite(num) && String(num) === s) {
          filtered = allPlayers.filter((p) => p.vk_id === num);
        } else {
          filtered = allPlayers.filter((p) =>
            String(p.vk_id).includes(s) ||
            p.first_name.toLowerCase().includes(s) ||
            p.last_name.toLowerCase().includes(s) ||
            `${p.first_name} ${p.last_name}`.toLowerCase().includes(s)
          );
        }
      }
      setPlayers(filtered);
      setPlayerPage(0);
    }, 150);
  }
  const [selectedPlayer, setSelectedPlayer] = useState<Player | null>(null);
  const [playerDetail, setPlayerDetail] = useState<PlayerDetail | null>(null);
  const [playerReports, setPlayerReports] = useState<StitchReport[]>([]);
  const [playerTab, setPlayerTab] = useState<'overview' | 'reports'>('overview');
  const [viewField, setViewField] = useState<FieldDetail | null>(null);
  const [playerFields, setPlayerFields] = useState<FieldInfo[]>([]);
  const [settings, setSettings] = useState<Record<string, string>>({});
  const { loading: sessionLoading } = useSession();
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  // ── Карты-локации ──
  const [fields, setFields] = useState<FieldInfo[]>([]);
  const [allPlants, setAllPlants] = useState<Plant[]>([]);
  const [editorFieldId, setEditorFieldId] = useState<number | null>(null);
  const [showCreate, setShowCreate] = useState(false);
  const [newName, setNewName] = useState('');
  const [newCols, setNewCols] = useState('6');
  const [newRows, setNewRows] = useState('4');
  const [lockRatio, setLockRatio] = useState(false);

  // ── Каталог ──
  const [plants, setPlants] = useState<Plant[]>([]);
  const [animals, setAnimals] = useState<Animal[]>([]);
  const [pets, setPets] = useState<Pet[]>([]);
  const [catalogProducts, setCatalogProducts] = useState<Product[]>([]);
  const [prodTemplates, setProdTemplates] = useState<ProductionTemplate[]>([]);
  const [adminOrders, setAdminOrders] = useState<AdminOrder[]>([]);
  const [products, setProducts] = useState<Product[]>([]);
  const [catForm, setCatForm] = useState<Record<string, string>>({});
  const [editingId, setEditingId] = useState<number | null>(null);
  const [formOpen, setFormOpen] = useState(false);

  // ── Шаблоны заказов ──
  const [orderTemplates, setOrderTemplates] = useState<OrderTemplate[]>([]);
  const [tplForm, setTplForm] = useState<Partial<OrderTemplateCreate>>({ source_kind: 'plant', source_id: 0, product_id: 0, qty: 1, reward_coins: 5 });
  const [tplEditingId, setTplEditingId] = useState<number | null>(null);

  // ── Уровни ──
  const [levels, setLevels] = useState<LevelGate[]>([]);
  const [levelForm, setLevelForm] = useState<LevelGateCreate>({ variant: 1, level: 1, coins_required: 800, plots_required: 2 });
  const [levelVariant, setLevelVariant] = useState(1);

  // ── Рецепты зелий ──
  const [potionRecipes, setPotionRecipes] = useState<PotionRecipe[]>([]);
  const [potionForm, setPotionForm] = useState<PotionRecipeCreate>({ name: '', level: 'green', ingredient_slots: [], bonus_code: null, reward_coins: 100 });
  const [potionEditingId, setPotionEditingId] = useState<number | null>(null);
  const [potionSlotInput, setPotionSlotInput] = useState('');

  // ── Фон ──
  const [bgUrl, setBgUrl] = useState('');
  const [bgInput, setBgInput] = useState('');

  // ── Заказы: создание/редактирование ──
  const [orderFormOpen, setOrderFormOpen] = useState(false);
  const [orderEditingId, setOrderEditingId] = useState<number | null>(null);
  const [orderForm, setOrderForm] = useState<Record<string, string>>({});

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [plys, setMap, flds, pls, anm, pts, ords, prods, catProds, ptsTmpl] = await Promise.all([
        api.adminPlayers().catch(() => [] as Player[]),
        Promise.all(
          SETTING_FIELDS.map((f) => api.getSetting(f.key).then((s) => [s.key, s.value] as [string, string])),
        ).catch(() => [] as [string, string][]),
        api.adminFields().catch(() => [] as FieldInfo[]),
        api.plants().catch(() => [] as Plant[]),
        api.adminAnimals().catch(() => [] as Animal[]),
        api.adminPets().catch(() => [] as Pet[]),
        api.adminOrders().catch(() => [] as AdminOrder[]),
        api.products().catch(() => [] as Product[]),
        api.adminProducts().catch(() => [] as Product[]),
        api.adminProductionTemplates().catch(() => [] as ProductionTemplate[]),
      ]);
      setPlayers(plys);
      setAllPlayers(plys);
      setSettings(Object.fromEntries(setMap));
      setFields(flds);
      setAllPlants(pls);
      setPlants(pls);
      setAnimals(anm);
      setPets(pts);
      setAdminOrders(ords);
      setProducts(prods);
      setCatalogProducts(catProds);
      setProdTemplates(ptsTmpl);
      loadOrderTemplates();
      loadBg();
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { if (!sessionLoading) load(); }, [load, sessionLoading]);

  async function selectPlayer(p: Player) {
    setSelectedPlayer(p);
    setPlayerTab('overview');
    setViewField(null);
    setMsg(null);
    try {
      const detail = await api.adminPlayerDetail(p.vk_id);
      setPlayerDetail(detail);
    } catch {
      setPlayerDetail(null);
    }
    try {
      const reps = await api.adminPlayerReports(p.vk_id);
      setPlayerReports(reps);
    } catch {
      setPlayerReports([]);
    }
    try {
      const flds = await api.fields();
      setPlayerFields(flds);
    } catch {
      setPlayerFields([]);
    }
  }

  async function openPlayerField(fieldId: number) {
    if (!selectedPlayer) return;
    setBusy(true);
    try {
      const fd = await api.adminPlayerField(selectedPlayer.vk_id, fieldId);
      setViewField(fd);
    } catch (e: any) {
      setMsg('✗ ' + (e?.response?.data?.detail || 'Ошибка'));
    } finally {
      setBusy(false);
    }
  }

  async function reviewReport(id: number, action: 'accept' | 'reject') {
    setBusy(true);
    setMsg(null);
    try {
      await api.reviewReport(id, action);
      setMsg('✓ ' + (action === 'accept' ? 'Зачтено' : 'Отклонено'));
      if (selectedPlayer) {
        const reps = await api.adminPlayerReports(selectedPlayer.vk_id);
        setPlayerReports(reps);
      }
      await load();
    } catch (e: any) {
      setMsg('✗ ' + (e?.response?.data?.detail || 'Ошибка'));
    } finally {
      setBusy(false);
    }
  }

  async function saveSetting(key: string, value: string) {
    setBusy(true);
    setMsg(null);
    try {
      await api.updateSetting(key, value);
      setMsg('✓ Настройка сохранена');
      await load();
    } catch (e: any) {
      setMsg('✗ ' + (e?.response?.data?.detail || 'Ошибка'));
    } finally {
      setBusy(false);
    }
  }

  async function createField() {
    const name = newName.trim();
    if (!name) return;
    setBusy(true); setMsg(null);
    try {
      await api.adminCreateField(name, Number(newCols) || 6, Number(newRows) || 4);
      setMsg('✓ Локация создана');
      setShowCreate(false); setNewName('');
      await load();
    } catch (e: any) {
      setMsg('✗ ' + (e?.response?.data?.detail || 'Ошибка'));
    } finally { setBusy(false); }
  }

  async function deleteField(id: number) {
    if (!confirm('Удалить локацию со всеми клетками и шатрами?')) return;
    setBusy(true); setMsg(null);
    try {
      await api.adminDeleteField(id);
      setMsg('✓ Локация удалена');
      await load();
    } catch (e: any) {
      setMsg('✗ ' + (e?.response?.data?.detail || 'Ошибка'));
    } finally { setBusy(false); }
  }

  async function uploadMap(id: number, file: File) {
    setBusy(true); setMsg(null);
    try {
      await api.adminUploadFieldMap(id, file);
      setMsg('✓ Карта загружена');
      await load();
    } catch (e: any) {
      setMsg('✗ ' + (e?.response?.data?.detail || 'Ошибка'));
    } finally { setBusy(false); }
  }

  // ── Каталог: CRUD ──
  function startCreate() { setCatForm({}); setEditingId(null); setFormOpen(true); }
  function startEdit(item: Record<string, any>) { setCatForm({ ...item }); setEditingId(item.id); setFormOpen(true); }
  function cancelForm() { setEditingId(null); setCatForm({}); setFormOpen(false); }

  async function savePlant() {
    if (!catForm.name?.trim()) return;
    setBusy(true); setMsg(null);
    try {
      if (editingId) await api.adminUpdatePlant(editingId, catForm);
      else await api.adminCreatePlant(catForm as any);
      setMsg('✓ Сохранено');
      cancelForm();
      await load();
    } catch (e: any) { setMsg('✗ ' + (e?.response?.data?.detail || 'Ошибка')); }
    finally { setBusy(false); }
  }

  async function deletePlant(id: number) {
    if (!confirm('Удалить растение?')) return;
    setBusy(true); setMsg(null);
    try { await api.adminDeletePlant(id); await load(); setMsg('✓ Удалено'); }
    catch (e: any) { setMsg('✗ ' + (e?.response?.data?.detail || 'Ошибка')); }
    finally { setBusy(false); }
  }

  async function saveAnimal() {
    if (!catForm.name?.trim()) return;
    setBusy(true); setMsg(null);
    try {
      if (editingId) await api.adminUpdateAnimal(editingId, catForm);
      else await api.adminCreateAnimal(catForm as any);
      setMsg('✓ Сохранено');
      cancelForm();
      await load();
    } catch (e: any) { setMsg('✗ ' + (e?.response?.data?.detail || 'Ошибка')); }
    finally { setBusy(false); }
  }

  async function deleteAnimal(id: number) {
    if (!confirm('Удалить животное?')) return;
    setBusy(true); setMsg(null);
    try { await api.adminDeleteAnimal(id); await load(); setMsg('✓ Удалено'); }
    catch (e: any) { setMsg('✗ ' + (e?.response?.data?.detail || 'Ошибка')); }
    finally { setBusy(false); }
  }

  async function savePet() {
    if (!catForm.name?.trim()) return;
    setBusy(true); setMsg(null);
    try {
      if (editingId) await api.adminUpdatePet(editingId, catForm);
      else await api.adminCreatePet(catForm as any);
      setMsg('✓ Сохранено');
      cancelForm();
      await load();
    } catch (e: any) { setMsg('✗ ' + (e?.response?.data?.detail || 'Ошибка')); }
    finally { setBusy(false); }
  }

  async function cancelOrder(id: number) {
    if (!confirm('Отменить заказ?')) return;
    setBusy(true); setMsg(null);
    try { await api.adminCancelOrder(id); await load(); setMsg('✓ Отменён'); }
    catch (e: any) { setMsg('✗ ' + (e?.response?.data?.detail || 'Ошибка')); }
    finally { setBusy(false); }
  }

  async function deleteOrder(id: number) {
    if (!confirm('Удалить заказ?')) return;
    setBusy(true); setMsg(null);
    try { await api.adminDeleteOrder(id); await load(); setMsg('✓ Удалён'); }
    catch (e: any) { setMsg('✗ ' + (e?.response?.data?.detail || 'Ошибка')); }
    finally { setBusy(false); }
  }

  // ── Заказы: создание и редактирование ──
  function startCreateOrder() {
    setOrderForm({ product_id: '', qty: '' });
    setOrderEditingId(null);
    setOrderFormOpen(true);
  }

  function startEditOrder(o: AdminOrder) {
    setOrderForm({
      product_id: String(o.product_id),
      qty: String(o.qty),
      reward_coins: String(o.reward_coins),
      customer: o.customer || '',
      status: o.status,
      name: o.name || '',
    });
    setOrderEditingId(o.id);
    setOrderFormOpen(true);
  }

  async function saveOrder() {
    const pid = Number(orderForm.product_id);
    const q = orderForm.qty ? Number(orderForm.qty) : undefined;
    if (!pid) return;
    setBusy(true); setMsg(null);
    try {
      if (orderEditingId !== null) {
        await api.adminUpdateOrder(orderEditingId, {
          product_id: pid || undefined,
          qty: q,
          reward_coins: orderForm.reward_coins ? Number(orderForm.reward_coins) : undefined,
          customer: orderForm.customer || undefined,
          status: orderForm.status || undefined,
          name: orderForm.name || undefined,
        });
        setMsg('✓ Заказ обновлён');
      } else {
        await api.adminGenerateOrder(pid, q);
        setMsg('✓ Заказ создан');
      }
      setOrderFormOpen(false);
      setOrderEditingId(null);
      await load();
    } catch (e: any) { setMsg('✗ ' + (e?.response?.data?.detail || 'Ошибка')); }
    finally { setBusy(false); }
  }

  async function deletePet(id: number) {
    if (!confirm('Удалить питомца?')) return;
    setBusy(true); setMsg(null);
    try { await api.adminDeletePet(id); await load(); setMsg('✓ Удалено'); }
    catch (e: any) { setMsg('✗ ' + (e?.response?.data?.detail || 'Ошибка')); }
    finally { setBusy(false); }
  }

  async function saveProduct() {
    if (!catForm.name?.trim()) return;
    setBusy(true); setMsg(null);
    try {
      if (editingId) await api.adminUpdateProduct(editingId, catForm);
      else await api.adminCreateProduct(catForm as any);
      setMsg('✓ Сохранено');
      cancelForm();
      await load();
    } catch (e: any) { setMsg('✗ ' + (e?.response?.data?.detail || 'Ошибка')); }
    finally { setBusy(false); }
  }

  async function deleteProduct(id: number) {
    if (!confirm('Удалить товар?')) return;
    setBusy(true); setMsg(null);
    try { await api.adminDeleteProduct(id); await load(); setMsg('✓ Удалено'); }
    catch (e: any) { setMsg('✗ ' + (e?.response?.data?.detail || 'Ошибка')); }
    finally { setBusy(false); }
  }

  async function saveProduction() {
    if (!catForm.name?.trim()) return;
    setBusy(true); setMsg(null);
    try {
      if (editingId) await api.adminUpdateProductionTemplate(editingId, catForm);
      else await api.adminCreateProductionTemplate(catForm as any);
      setMsg('✓ Сохранено');
      cancelForm();
      await load();
    } catch (e: any) { setMsg('✗ ' + (e?.response?.data?.detail || 'Ошибка')); }
    finally { setBusy(false); }
  }

  async function deleteProduction(id: number) {
    if (!confirm('Удалить производство?')) return;
    setBusy(true); setMsg(null);
    try { await api.adminDeleteProductionTemplate(id); await load(); setMsg('✓ Удалено'); }
    catch (e: any) { setMsg('✗ ' + (e?.response?.data?.detail || 'Ошибка')); }
    finally { setBusy(false); }
  }

  // ── Шаблоны заказов ──
  async function loadOrderTemplates() {
    try { setOrderTemplates(await api.adminOrderTemplates()); }
    catch { /* ignore */ }
  }
  async function saveOrderTemplate() {
    if (!tplForm.source_kind || !tplForm.source_id || !tplForm.product_id || !tplForm.qty) { setMsg('✗ Заполните все поля'); return; }
    setBusy(true); setMsg(null);
    try {
      if (tplEditingId) { await api.adminUpdateOrderTemplate(tplEditingId, tplForm as OrderTemplateCreate); }
      else { await api.adminCreateOrderTemplate(tplForm as OrderTemplateCreate); }
      await loadOrderTemplates();
      setTplForm({ source_kind: 'plant', source_id: 0, product_id: 0, qty: 1, reward_coins: 5 });
      setTplEditingId(null);
      setMsg('✓ Сохранено');
    } catch (e: any) { setMsg('✗ ' + (e?.response?.data?.detail || 'Ошибка')); }
    finally { setBusy(false); }
  }
  async function deleteOrderTemplate(id: number) {
    if (!confirm('Удалить шаблон?')) return;
    setBusy(true); setMsg(null);
    try { await api.adminDeleteOrderTemplate(id); await loadOrderTemplates(); setMsg('✓ Удалено'); }
    catch (e: any) { setMsg('✗ ' + (e?.response?.data?.detail || 'Ошибка')); }
    finally { setBusy(false); }
  }

  function renderOrderTemplates() {
    return (
      <div>
        <h2>📋 Шаблоны заказов</h2>
        <div className="fm-card" style={{ marginBottom: 10 }}>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 8 }}>
            <select className="fm-input" value={tplForm.source_kind || 'plant'} onChange={(e) => setTplForm({ ...tplForm, source_kind: e.target.value })}>
              <option value="plant">Растение</option>
              <option value="animal">Животное</option>
              <option value="product">Товар</option>
              <option value="potion">Зелье</option>
            </select>
            <input className="fm-input" type="number" placeholder="source_id" value={tplForm.source_id || ''} onChange={(e) => setTplForm({ ...tplForm, source_id: Number(e.target.value) })} />
            <select className="fm-input" value={tplForm.product_id || ''} onChange={(e) => setTplForm({ ...tplForm, product_id: Number(e.target.value) })}>
              <option value="">Товар</option>
              {products.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
            </select>
            <input className="fm-input" type="number" placeholder="Кол-во" value={tplForm.qty || ''} onChange={(e) => setTplForm({ ...tplForm, qty: Number(e.target.value) })} style={{ width: 80 }} />
            <input className="fm-input" type="number" placeholder="Монет" value={tplForm.reward_coins || ''} onChange={(e) => setTplForm({ ...tplForm, reward_coins: Number(e.target.value) })} style={{ width: 80 }} />
            <input className="fm-input" placeholder="Покупатель" value={tplForm.customer || ''} onChange={(e) => setTplForm({ ...tplForm, customer: e.target.value })} style={{ width: 120 }} />
            <input className="fm-input" placeholder="Название" value={tplForm.name || ''} onChange={(e) => setTplForm({ ...tplForm, name: e.target.value })} style={{ width: 140 }} />
          </div>
          <button className="fm-btn" disabled={busy} onClick={saveOrderTemplate}>
            {tplEditingId ? '✎ Сохранить' : '➕ Создать'}
          </button>
          {tplEditingId && <button className="fm-btn" style={{ marginLeft: 6 }} onClick={() => { setTplEditingId(null); setTplForm({ source_kind: 'plant', source_id: 0, product_id: 0, qty: 1, reward_coins: 5 }); }}>Отмена</button>}
        </div>
        <table className="fm-table" style={{ width: '100%' }}>
          <thead><tr><th>ID</th><th>Тип</th><th>source_id</th><th>Товар</th><th>Кол-во</th><th>Монет</th><th>Покупатель</th><th></th></tr></thead>
          <tbody>
            {orderTemplates.map((t) => (
              <tr key={t.id}>
                <td>{t.id}</td><td>{t.source_kind}</td><td>{t.source_id}</td>
                <td>{products.find((p) => p.id === t.product_id)?.name || t.product_id}</td>
                <td>{t.qty}</td><td>{t.reward_coins}</td><td>{t.customer || '—'}</td>
                <td>
                  <button className="fm-btn fm-btn-sm" onClick={() => { setTplEditingId(t.id); setTplForm({ source_kind: t.source_kind, source_id: t.source_id, product_id: t.product_id, qty: t.qty, reward_coins: t.reward_coins, customer: t.customer, name: t.name }); }}>✎</button>
                  <button className="fm-btn fm-btn-sm" style={{ marginLeft: 4 }} onClick={() => deleteOrderTemplate(t.id)}>🗑</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    );
  }

  // ── Уровни ──
  async function loadLevels(v?: number) {
    try { setLevels(await api.adminLevels(v ?? levelVariant)); }
    catch { /* ignore */ }
  }
  async function saveLevel() {
    setBusy(true); setMsg(null);
    try {
      await api.adminSetLevel(levelForm);
      await loadLevels();
      setMsg('✓ Сохранено');
    } catch (e: any) { setMsg('✗ ' + (e?.response?.data?.detail || 'Ошибка')); }
    finally { setBusy(false); }
  }
  async function deleteLevel(variant: number, level: number) {
    if (!confirm(`Удалить уровень ${level} варианта ${variant}?`)) return;
    setBusy(true); setMsg(null);
    try { await api.adminDeleteLevel(variant, level); await loadLevels(); setMsg('✓ Удалено'); }
    catch (e: any) { setMsg('✗ ' + (e?.response?.data?.detail || 'Ошибка')); }
    finally { setBusy(false); }
  }

  function renderLevels() {
    return (
      <div>
        <h2>📊 Уровни (маршрутный лист)</h2>
        <div style={{ marginBottom: 10, display: 'flex', gap: 8 }}>
          {[1, 2, 3, 4].map((v) => (
            <button key={v} className={`fm-btn fm-btn-sm`} style={{ fontWeight: levelVariant === v ? 'bold' : 'normal' }} onClick={() => { setLevelVariant(v); loadLevels(v); }}>
              Вариант {v}
            </button>
          ))}
        </div>
        <div className="fm-card" style={{ marginBottom: 10, display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          <input className="fm-input" type="number" placeholder="Уровень (1-16)" value={levelForm.level || ''} onChange={(e) => setLevelForm({ ...levelForm, level: Number(e.target.value) })} style={{ width: 80 }} />
          <input className="fm-input" type="number" placeholder="Монет" value={levelForm.coins_required || ''} onChange={(e) => setLevelForm({ ...levelForm, coins_required: Number(e.target.value) })} style={{ width: 100 }} />
          <input className="fm-input" type="number" placeholder="Грядок" value={levelForm.plots_required || ''} onChange={(e) => setLevelForm({ ...levelForm, plots_required: Number(e.target.value) })} style={{ width: 80 }} />
          <button className="fm-btn" disabled={busy} onClick={saveLevel}>💾 Сохранить</button>
        </div>
        <table className="fm-table" style={{ width: '100%' }}>
          <thead><tr><th>Вариант</th><th>Уровень</th><th>Монет</th><th>Грядок</th><th></th></tr></thead>
          <tbody>
            {levels.map((l) => (
              <tr key={`${l.variant}-${l.level}`}>
                <td>{l.variant}</td><td>{l.level}</td><td>{l.coins_required}</td><td>{l.plots_required}</td>
                <td>
                  <button className="fm-btn fm-btn-sm" onClick={() => { setLevelForm({ variant: l.variant, level: l.level, coins_required: l.coins_required, plots_required: l.plots_required, rewards: l.rewards }); }}>✎</button>
                  <button className="fm-btn fm-btn-sm" style={{ marginLeft: 4 }} onClick={() => deleteLevel(l.variant, l.level)}>🗑</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    );
  }

  // ── Рецепты зелий ──
  async function loadPotionRecipes() {
    try { setPotionRecipes(await api.adminPotionRecipes()); }
    catch { /* ignore */ }
  }
  async function savePotionRecipe() {
    if (!potionForm.name) { setMsg('✗ Введите название'); return; }
    setBusy(true); setMsg(null);
    try {
      if (potionEditingId) { await api.adminUpdatePotionRecipe(potionEditingId, potionForm); }
      else { await api.adminCreatePotionRecipe(potionForm); }
      await loadPotionRecipes();
      setPotionForm({ name: '', level: 'green', ingredient_slots: [], bonus_code: null, reward_coins: 100 });
      setPotionEditingId(null);
      setMsg('✓ Сохранено');
    } catch (e: any) { setMsg('✗ ' + (e?.response?.data?.detail || 'Ошибка')); }
    finally { setBusy(false); }
  }
  async function deletePotionRecipe(id: number) {
    if (!confirm('Удалить рецепт?')) return;
    setBusy(true); setMsg(null);
    try { await api.adminDeletePotionRecipe(id); await loadPotionRecipes(); setMsg('✓ Удалено'); }
    catch (e: any) { setMsg('✗ ' + (e?.response?.data?.detail || 'Ошибка')); }
    finally { setBusy(false); }
  }

  function renderPotionRecipes() {
    return (
      <div>
        <h2>🧪 Рецепты зелий</h2>
        <div className="fm-card" style={{ marginBottom: 10 }}>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 8 }}>
            <input className="fm-input" placeholder="Название" value={potionForm.name} onChange={(e) => setPotionForm({ ...potionForm, name: e.target.value })} />
            <select className="fm-input" value={potionForm.level} onChange={(e) => setPotionForm({ ...potionForm, level: e.target.value })}>
              <option value="green">🟢 Простое</option>
              <option value="blue">🔵 Среднее</option>
              <option value="violet">🟣 Сложное</option>
            </select>
            <input className="fm-input" type="number" placeholder="Монет" value={potionForm.reward_coins || ''} onChange={(e) => setPotionForm({ ...potionForm, reward_coins: Number(e.target.value) })} style={{ width: 80 }} />
            <select className="fm-input" value={potionForm.bonus_code || ''} onChange={(e) => setPotionForm({ ...potionForm, bonus_code: e.target.value || null })}>
              <option value="">Без бонуса</option>
              <option value="double_garden_harvest">🟢 ×2 грядка</option>
              <option value="double_orchard_harvest">🟢 ×2 сад</option>
              <option value="double_animal_product">🟢 ×2 животное</option>
              <option value="skip_plant_stitch">🟢 Без отшива</option>
              <option value="early_level_up">🟢 +1 уровень</option>
              <option value="double_order_reward">🟢 ×2 заказ</option>
              <option value="free_pet">🔵 Питомец</option>
              <option value="extra_barnyard_slot">🔵 +1 загон</option>
              <option value="bonus_sewing_product">🔵 +1 портниха</option>
              <option value="bonus_workshop_product">🔵 +1 мастерская</option>
              <option value="bonus_alchemy_product">🔵 +1 зельеварение</option>
              <option value="skip_animal_stitch">🟣 Без отшива жив.</option>
              <option value="unlock_garden_l3">🟣 Грядка 3 ур.</option>
              <option value="unlock_orchard_l3">🟣 Сад 3 ур.</option>
              <option value="partial_order">🟣 Неполный заказ</option>
            </select>
          </div>
          <div style={{ marginBottom: 8, display: 'flex', gap: 6, alignItems: 'center' }}>
            <span style={{ fontSize: 13 }}>Ингредиенты:</span>
            <input className="fm-input" placeholder="тип (plant_garden, alchemy, ...)" value={potionSlotInput} onChange={(e) => setPotionSlotInput(e.target.value)} style={{ width: 200 }} />
            <button className="fm-btn fm-btn-sm" onClick={() => { if (potionSlotInput.trim()) { setPotionForm({ ...potionForm, ingredient_slots: [...potionForm.ingredient_slots, potionSlotInput.trim()] }); setPotionSlotInput(''); } }}>+</button>
          </div>
          <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap', marginBottom: 8 }}>
            {potionForm.ingredient_slots.map((s, i) => (
              <span key={i} className="fm-card" style={{ padding: '2px 8px', fontSize: 13, cursor: 'pointer' }} onClick={() => setPotionForm({ ...potionForm, ingredient_slots: potionForm.ingredient_slots.filter((_, j) => j !== i) })}>
                {s} ✕
              </span>
            ))}
          </div>
          <button className="fm-btn" disabled={busy} onClick={savePotionRecipe}>
            {potionEditingId ? '✎ Сохранить' : '➕ Создать'}
          </button>
          {potionEditingId && <button className="fm-btn" style={{ marginLeft: 6 }} onClick={() => { setPotionEditingId(null); setPotionForm({ name: '', level: 'green', ingredient_slots: [], bonus_code: null, reward_coins: 100 }); }}>Отмена</button>}
        </div>
        <table className="fm-table" style={{ width: '100%' }}>
          <thead><tr><th>ID</th><th>Название</th><th>Уровень</th><th>Слотов</th><th>Бонус</th><th></th></tr></thead>
          <tbody>
            {potionRecipes.map((r) => (
              <tr key={r.id}>
                <td>{r.id}</td><td>{r.name}</td><td>{r.level}</td>
                <td>{r.ingredient_slots.join(', ')}</td><td>{r.bonus_code || '—'}</td>
                <td>
                  <button className="fm-btn fm-btn-sm" onClick={() => { setPotionEditingId(r.id); setPotionForm({ name: r.name, level: r.level, ingredient_slots: r.ingredient_slots, bonus_code: r.bonus_code, reward_coins: r.reward_coins }); }}>✎</button>
                  <button className="fm-btn fm-btn-sm" style={{ marginLeft: 4 }} onClick={() => deletePotionRecipe(r.id)}>🗑</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    );
  }

  // ── Фон ──
  async function loadBg() {
    try { const data = await api.getBackground(); setBgUrl(data.url); setBgInput(data.url); }
    catch { /* ignore */ }
  }
  async function saveBg() {
    setBusy(true); setMsg(null);
    try { const data = await api.setBackground(bgInput); setBgUrl(data.url); setMsg('✓ Фон обновлён'); }
    catch (e: any) { setMsg('✗ ' + (e?.response?.data?.detail || 'Ошибка')); }
    finally { setBusy(false); }
  }

  async function uploadPlantImage(id: number, file: File) {
    setBusy(true); setMsg(null);
    try { await api.adminUploadPlantImage(id, file); await load(); setMsg('✓ Изображение загружено'); }
    catch (e: any) { setMsg('✗ ' + (e?.response?.data?.detail || 'Ошибка')); }
    finally { setBusy(false); }
  }
  async function uploadPlantImageYoung(id: number, file: File) {
    setBusy(true); setMsg(null);
    try { await api.adminUploadPlantImageYoung(id, file); await load(); setMsg('✓ Молодое растение загружено'); }
    catch (e: any) { setMsg('✗ ' + (e?.response?.data?.detail || 'Ошибка')); }
    finally { setBusy(false); }
  }
  async function uploadPlantImageGrown(id: number, file: File) {
    setBusy(true); setMsg(null);
    try { await api.adminUploadPlantImageGrown(id, file); await load(); setMsg('✓ Созревшее растение загружено'); }
    catch (e: any) { setMsg('✗ ' + (e?.response?.data?.detail || 'Ошибка')); }
    finally { setBusy(false); }
  }
  async function uploadAnimalImage(id: number, file: File) {
    setBusy(true); setMsg(null);
    try { await api.adminUploadAnimalImage(id, file); await load(); setMsg('✓ Изображение загружено'); }
    catch (e: any) { setMsg('✗ ' + (e?.response?.data?.detail || 'Ошибка')); }
    finally { setBusy(false); }
  }
  async function uploadPetImage(id: number, file: File) {
    setBusy(true); setMsg(null);
    try { await api.adminUploadPetImage(id, file); await load(); setMsg('✓ Изображение загружено'); }
    catch (e: any) { setMsg('✗ ' + (e?.response?.data?.detail || 'Ошибка')); }
    finally { setBusy(false); }
  }

  return (
    <div style={{ maxWidth: 600, margin: '0 auto', padding: 'var(--shell-pad)' }}>
      <h1 style={{ textAlign: 'center' }}>⚙️ Управление</h1>

      <div style={{ display: 'flex', gap: 6, marginBottom: 14, flexWrap: 'wrap' }}>
        <TabBtn active={tab === 'players'} onClick={() => setTab('players')}>👥 Игроки</TabBtn>
        <TabBtn active={tab === 'settings'} onClick={() => setTab('settings')}>🔧 Настройки</TabBtn>
        <TabBtn active={tab === 'fields'} onClick={() => setTab('fields')}>🗺️ Карты</TabBtn>
        <TabBtn active={tab === 'orders'} onClick={() => setTab('orders')}>🧺 Заказы</TabBtn>
        <TabBtn active={tab === 'plants'} onClick={() => setTab('plants')}>🌱 Растения</TabBtn>
        <TabBtn active={tab === 'animals'} onClick={() => setTab('animals')}>🐄 Животные</TabBtn>
        <TabBtn active={tab === 'pets'} onClick={() => setTab('pets')}>🐾 Питомцы</TabBtn>
        <TabBtn active={tab === 'products'} onClick={() => setTab('products')}>📦 Товары</TabBtn>
        <TabBtn active={tab === 'productions'} onClick={() => setTab('productions')}>🏭 Производства</TabBtn>
        <TabBtn active={tab === 'order-templates'} onClick={() => { setTab('order-templates'); loadOrderTemplates(); }}>📋 Шаблоны заказов</TabBtn>
        <TabBtn active={tab === 'levels'} onClick={() => { setTab('levels'); loadLevels(); }}>📊 Уровни</TabBtn>
        <TabBtn active={tab === 'potion-recipes'} onClick={() => { setTab('potion-recipes'); loadPotionRecipes(); }}>🧪 Рецепты зелий</TabBtn>
      </div>

      {msg && <div className="fm-card" style={{ marginBottom: 10, fontSize: 14 }}>{msg}</div>}

      {loading ? (
        <div className="fm-card">Загрузка…</div>
      ) : (
        <>
          {tab === 'players' && (
            <>
              {selectedPlayer ? (
                <div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 14 }}>
                    <button className="fm-btn fm-btn-sm fm-btn-outline" onClick={() => { setSelectedPlayer(null); setPlayerDetail(null); setPlayerReports([]); }}>← Назад</button>
                    <h2 style={{ margin: 0, fontSize: 18 }}>
                      {selectedPlayer.first_name || selectedPlayer.last_name ? `${selectedPlayer.first_name} ${selectedPlayer.last_name}`.trim() : `#${selectedPlayer.vk_id}`}
                    </h2>
                  </div>
                  <div className="fm-card" style={{ marginBottom: 14, fontSize: 13 }}>
                    <div>ID: {selectedPlayer.vk_id} · Роль: {selectedPlayer.role}</div>
                    <div>Крестики: {selectedPlayer.crosses_balance} (всего {selectedPlayer.crosses_total}) · Монеты: {selectedPlayer.coins} · Раунд: {selectedPlayer.round}</div>
                  </div>

                  <div style={{ display: 'flex', gap: 6, marginBottom: 14 }}>
                    <TabBtn active={playerTab === 'overview'} onClick={() => setPlayerTab('overview')}>🏡 Хозяйство</TabBtn>
                    <TabBtn active={playerTab === 'reports'} onClick={() => setPlayerTab('reports')}>📷 Отчёты ({selectedPlayer.reports_total})</TabBtn>
                  </div>

                  {playerTab === 'overview' && playerDetail && (
                    <div>
                      <h3 style={{ marginTop: 0 }}>🗺️ Карты</h3>
                      {playerFields.length === 0 ? (
                        <div className="fm-card" style={{ color: 'var(--text-muted)', fontSize: 13 }}>Нет полей.</div>
                      ) : (
                        <div className="fm-grid">
                          {playerFields.map((f) => (
                            <button key={f.id} className="fm-card fm-rise" style={{ fontSize: 13, textAlign: 'left', cursor: 'pointer' }} onClick={() => openPlayerField(f.id)}>
                              <strong>🗺️ {f.name}</strong>
                              <div style={{ color: 'var(--text-muted)', marginTop: 2 }}>{f.cols}×{f.rows} клеток</div>
                            </button>
                          ))}
                        </div>
                      )}

                      <h3 style={{ marginTop: 16 }}>🌱 Грядки ({playerDetail.plots.length})</h3>
                      {playerDetail.plots.length === 0 ? (
                        <div className="fm-card" style={{ color: 'var(--text-muted)', fontSize: 13 }}>Нет грядок.</div>
                      ) : (
                        <div className="fm-grid">
                          {playerDetail.plots.map((plot) => (
                            <div key={plot.id} className="fm-card fm-rise" style={{ fontSize: 13 }}>
                              <strong>{plot.plant_emoji} {plot.plant_name} ×{plot.qty}</strong>
                              <div style={{ color: 'var(--text-muted)', marginTop: 2 }}>
                                {plot.status === 'grown' ? '✅ Выращена' : '🌱 В процессе'}
                              </div>
                              <div style={{ fontSize: 12, marginTop: 2 }}>
                                {plot.accumulated}/{plot.required} ✝️
                                {plot.crystal_color && <> · {plot.crystal_color} ×{plot.crystal_count}</>}
                              </div>
                            </div>
                          ))}
                        </div>
                      )}

                      <h3 style={{ marginTop: 16 }}>🏭 Производства ({playerDetail.productions.length})</h3>
                      {playerDetail.productions.length === 0 ? (
                        <div className="fm-card" style={{ color: 'var(--text-muted)', fontSize: 13 }}>Нет производств.</div>
                      ) : (
                        <div className="fm-grid">
                          {playerDetail.productions.map((pr) => (
                            <div key={pr.id} className="fm-card fm-rise" style={{ fontSize: 13 }}>
                              <strong>{pr.name}</strong>
                              <div style={{ color: 'var(--text-muted)', marginTop: 2 }}>{pr.kind}</div>
                              <div style={{ fontSize: 12, marginTop: 2 }}>
                                {pr.accumulated}/{pr.required} ✝️
                              </div>
                            </div>
                          ))}
                        </div>
                      )}

                      <h3 style={{ marginTop: 16 }}>📦 Склад ({playerDetail.inventory.length})</h3>
                      {playerDetail.inventory.length === 0 ? (
                        <div className="fm-card" style={{ color: 'var(--text-muted)', fontSize: 13 }}>Пусто.</div>
                      ) : (
                        <div className="fm-grid">
                          {playerDetail.inventory.map((inv) => (
                            <div key={inv.item_id} className="fm-card fm-rise" style={{ fontSize: 13 }}>
                              <strong>{inv.item_emoji} {inv.item_name}</strong>
                              <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 2 }}>
                                ×{inv.qty} · {inv.item_code}
                              </div>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  )}

                  {playerTab === 'reports' && (
                    <div>
                      {playerReports.length === 0 ? (
                        <div className="fm-card" style={{ color: 'var(--text-muted)' }}>Отчётов нет.</div>
                      ) : (
                        <div className="fm-grid">
                          {playerReports.map((r) => (
                            <div key={r.id} className="fm-card fm-rise">
                              <div style={{ display: 'flex', gap: 10 }}>
                                {r.photo_after_url && (
                                  <img src={mediaUrl(r.photo_after_url)} alt="" style={{ width: 60, height: 60, objectFit: 'cover', borderRadius: 'var(--radius-sm)' }} />
                                )}
                                <div style={{ flex: 1 }}>
                                  <strong>✝️ {r.amount}</strong>
                                  {r.note && <div style={{ fontSize: 13 }}>{r.note}</div>}
                                  <span className="fm-chip" style={{ marginTop: 4, fontSize: 11 }}>
                                    {r.status === 'accepted' ? '✓ зачтено' : r.status === 'pending' ? '⏳ ждёт' : '✖ отклонено'}
                                  </span>
                                </div>
                              </div>
                              {r.status === 'pending' && (
                                <div style={{ display: 'flex', gap: 6, marginTop: 8 }}>
                                  <button className="fm-btn fm-btn-sm" style={{ flex: 1 }} disabled={busy} onClick={() => reviewReport(r.id, 'accept')}>Зачесть</button>
                                  <button className="fm-btn fm-btn-sm fm-btn-danger" disabled={busy} onClick={() => reviewReport(r.id, 'reject')}>Отклонить</button>
                                </div>
                              )}
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  )}
                </div>
              ) : (
                <div>
                  <h2 style={{ marginTop: 0 }}>👥 Игроки</h2>
                  <div style={{ marginBottom: 12 }}>
                    <input
                      className="fm-input"
                      type="text"
                      placeholder="Поиск по ID или имени…"
                      value={playerSearch}
                      onChange={(e) => { setPlayerSearch(e.target.value); doSearch(e.target.value); }}
                    />
                  </div>
                  {players.length === 0 ? (
                    <div className="fm-card" style={{ color: 'var(--text-muted)' }}>Игроков нет.</div>
                  ) : (
                    <>
                      <div className="fm-card" style={{ overflowX: 'auto', padding: 0 }}>
                        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
                          <thead>
                            <tr style={{ borderBottom: '1px solid var(--border)' }}>
                              <th style={{ padding: '8px 12px', textAlign: 'left' }}>Игрок</th>
                              <th style={{ padding: '8px 12px', textAlign: 'right' }}>✝️</th>
                              <th style={{ padding: '8px 12px', textAlign: 'right' }}>🪙</th>
                              <th style={{ padding: '8px 12px', textAlign: 'right' }}>📷</th>
                            </tr>
                          </thead>
                          <tbody>
                            {players.slice(playerPage * PER_PAGE, (playerPage + 1) * PER_PAGE).map((p) => (
                              <tr
                                key={p.vk_id}
                                onClick={() => selectPlayer(p)}
                                style={{ cursor: 'pointer', borderBottom: '1px solid var(--border)' }}
                                className="fm-rise"
                              >
                                <td style={{ padding: '8px 12px' }}>
                                  <strong>{p.first_name || p.last_name ? `${p.first_name} ${p.last_name}`.trim() : `#${p.vk_id}`}</strong>
                                  <span style={{ color: 'var(--text-muted)', marginLeft: 8, fontSize: 11 }}>{p.role}</span>
                                </td>
                                <td style={{ padding: '8px 12px', textAlign: 'right' }}>{p.crosses_balance}</td>
                                <td style={{ padding: '8px 12px', textAlign: 'right' }}>{p.coins}</td>
                                <td style={{ padding: '8px 12px', textAlign: 'right' }}>{p.reports_total}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                      {players.length > PER_PAGE && (
                        <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', gap: 12, marginTop: 10, fontSize: 13 }}>
                          <button className="fm-btn fm-btn-sm fm-btn-outline" disabled={playerPage === 0} onClick={() => setPlayerPage((p) => p - 1)}>← Назад</button>
                          <span style={{ color: 'var(--text-muted)' }}>{playerPage + 1} / {Math.ceil(players.length / PER_PAGE)}</span>
                          <button className="fm-btn fm-btn-sm fm-btn-outline" disabled={playerPage >= Math.ceil(players.length / PER_PAGE) - 1} onClick={() => setPlayerPage((p) => p + 1)}>Вперёд →</button>
                        </div>
                      )}
                    </>
                  )}
                </div>
              )}
            </>
          )}

          {/* Полноэкранный просмотр поля игрока (админ) */}
          {viewField && (
            <div style={{ position: 'fixed', inset: 0, zIndex: 100, background: '#1a1a2e', display: 'flex', flexDirection: 'column' }}>
              <div style={{ padding: '10px var(--shell-pad)', display: 'flex', alignItems: 'center', gap: 10, background: 'rgba(0,0,0,0.4)', flexShrink: 0 }}>
                <button className="fm-btn fm-btn-sm fm-btn-outline" onClick={() => setViewField(null)} style={{ color: '#fff', borderColor: '#fff' }}>← Назад</button>
                <span style={{ color: '#ccc', fontSize: 14 }}>{viewField.name} · {viewField.cols}×{viewField.rows}</span>
              </div>
              <div style={{ flex: 1, position: 'relative', overflow: 'auto' }}>
                <FieldGridView field={viewField} />
              </div>
            </div>
          )}

          {tab === 'settings' && (
            <>
              <CrystalStandardEditor disabled={busy} />
              <div className="fm-grid">
                {SETTING_FIELDS.map((f) => (
                  <SettingRow key={f.key} field={f} value={settings[f.key] ?? ''} disabled={busy} onSave={(v) => saveSetting(f.key, v)} />
                ))}
              </div>
              <div className="fm-card" style={{ marginTop: 10 }}>
                <h3>🖼️ Нейтральный фон</h3>
                <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                  <input className="fm-input" style={{ flex: 1 }} placeholder="URL фона" value={bgInput} onChange={(e) => setBgInput(e.target.value)} />
                  <button className="fm-btn" disabled={busy} onClick={saveBg}>💾</button>
                </div>
                {bgUrl && <img src={bgUrl} alt="Фон" style={{ maxWidth: 200, marginTop: 8, borderRadius: 8 }} />}
              </div>
            </>
          )}

          {tab === 'fields' && (
            <>
              {editorFieldId !== null ? (
                <FieldEditor fieldId={editorFieldId} onClose={() => setEditorFieldId(null)} />
              ) : (
                <>
                  <button className="fm-btn" style={{ width: '100%', marginBottom: 14 }} disabled={busy} onClick={() => setShowCreate(true)}>
                    ➕ Создать локацию
                  </button>
                  {fields.length === 0 ? (
                    <div className="fm-card" style={{ color: 'var(--text-muted)' }}>Локаций пока нет.</div>
                  ) : (
                    <div className="fm-grid">
                      {fields.map((f) => (
                        <div key={f.id} className="fm-card fm-rise">
                          <strong style={{ fontSize: 16 }}>🗺️ {f.name}</strong>
                          <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 4 }}>{f.cols}×{f.rows} клеток</div>
                          {f.map_url && <img src={mediaUrl(f.map_url)} alt="" style={{ width: '100%', marginTop: 8, borderRadius: 'var(--radius-sm)' }} />}
                          <div style={{ display: 'flex', flexDirection: 'column', gap: 6, marginTop: 8 }}>
                            <button className="fm-btn fm-btn-sm" disabled={busy} onClick={() => setEditorFieldId(f.id)}>✎ Редактировать</button>
                            <label className="fm-btn fm-btn-sm fm-btn-outline" style={{ cursor: 'pointer' }}>
                              {f.map_url ? '🖼️ Сменить картинку' : '🖼️ Загрузить карту'}
                              <input type="file" accept="image/*" style={{ display: 'none' }} onChange={(e) => { const file = e.target.files?.[0]; if (file) uploadMap(f.id, file); }} />
                            </label>
                            <button className="fm-btn fm-btn-sm fm-btn-danger" disabled={busy} onClick={() => deleteField(f.id)}>Удалить</button>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                  {showCreate && (
                    <div onClick={() => setShowCreate(false)} style={{ position: 'fixed', inset: 0, zIndex: 60, background: 'rgba(0,0,0,0.6)', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 16 }}>
                      <div className="fm-card fm-rise" onClick={(e) => e.stopPropagation()} style={{ width: '100%', maxWidth: 380 }}>
                        <h3 style={{ marginTop: 0 }}>➕ Новая локация</h3>
                        <label style={{ display: 'block', margin: '8px 0 6px', fontSize: 14 }}>Название</label>
                        <input className="fm-input" value={newName} onChange={(e) => setNewName(e.target.value)} placeholder="Огород" />
                        <div style={{ display: 'flex', gap: 8, marginTop: 10 }}>
                          <div style={{ flex: 1 }}>
                            <label style={{ display: 'block', marginBottom: 6, fontSize: 14 }}>Колонки</label>
                            <input className="fm-input" type="number" min={1} max={30} value={newCols} onChange={(e) => { setNewCols(e.target.value); if (lockRatio) { const c = Number(e.target.value); if (c > 0) setNewRows(String(Math.round(c * 3 / 4) || 1)); } }} />
                          </div>
                          <div style={{ flex: 1 }}>
                            <label style={{ display: 'block', marginBottom: 6, fontSize: 14 }}>Строки</label>
                            <input className="fm-input" type="number" min={1} max={30} value={newRows} onChange={(e) => { setNewRows(e.target.value); if (lockRatio) { const r = Number(e.target.value); if (r > 0) setNewCols(String(Math.round(r * 4 / 3) || 1)); } }} />
                          </div>
                        </div>
                        <label style={{ display: 'flex', alignItems: 'center', gap: 6, marginTop: 8, fontSize: 13, cursor: 'pointer' }}>
                          <input type="checkbox" checked={lockRatio} onChange={(e) => setLockRatio(e.target.checked)} />
                          Сохранить пропорции 4:3
                        </label>
                        <button className="fm-btn" style={{ width: '100%', marginTop: 14 }} disabled={busy || !newName.trim()} onClick={createField}>Создать</button>
                      </div>
                    </div>
                  )}
                </>
              )}
            </>
          )}

          {tab === 'plants' && (
            <CatalogTab title="🌱 Растения" items={plants} busy={busy} form={catForm} formOpen={formOpen} editingId={editingId} onFormChange={setCatForm} onCreate={startCreate} onEdit={startEdit} onCancel={cancelForm} onSave={savePlant} onDelete={deletePlant} onUploadImage={uploadPlantImage} onUploadImageYoung={uploadPlantImageYoung} onUploadImageGrown={uploadPlantImageGrown}
              fields={[{ key: 'name', label: 'Название', ph: 'Джекобоб' }, { key: 'level', label: 'Уровень', ph: '1', type: 'number' }, { key: 'norm_per_crystal', label: 'Норма/кристалл', ph: '100', type: 'number' }, { key: 'bonus_text', label: 'Бонус (текст)', ph: 'Гриб' }, { key: 'bonus_kind', label: 'Тип бонуса', ph: 'image' }, { key: 'description', label: 'Описание', ph: 'Грибы' }]}
            />
          )}

          {tab === 'animals' && (
            <CatalogTab title="🐄 Животные" items={animals} busy={busy} form={catForm} formOpen={formOpen} editingId={editingId} onFormChange={setCatForm} onCreate={startCreate} onEdit={startEdit} onCancel={cancelForm} onSave={saveAnimal} onDelete={deleteAnimal} onUploadImage={uploadAnimalImage}
              fields={[{ key: 'name', label: 'Название', ph: 'Единорог' }, { key: 'product_name', label: 'Продукция', ph: 'Рог единорога' }, { key: 'sort_order', label: 'Порядок', ph: '0', type: 'number' }]}
            />
          )}

          {tab === 'pets' && (
            <CatalogTab title="🐾 Питомцы" items={pets} busy={busy} form={catForm} formOpen={formOpen} editingId={editingId} onFormChange={setCatForm} onCreate={startCreate} onEdit={startEdit} onCancel={cancelForm} onSave={savePet} onDelete={deletePet} onUploadImage={uploadPetImage}
              fields={[{ key: 'name', label: 'Название', ph: 'Лис Сильварис' }, { key: 'bonus_description', label: 'Бонус', ph: 'Собирает +1 с каждого вида дерева' }]}
            />
          )}

          {tab === 'products' && (
            <CatalogTab title="📦 Товары" items={catalogProducts} busy={busy} form={catForm} formOpen={formOpen} editingId={editingId} onFormChange={setCatForm} onCreate={startCreate} onEdit={startEdit} onCancel={cancelForm} onSave={saveProduct} onDelete={deleteProduct} onUploadImage={async () => {}}
              fields={[{ key: 'name', label: 'Название', ph: 'Яд' }, { key: 'stars', label: 'Звёзды', ph: '1', type: 'number' }, { key: 'production_kind', label: 'Производство', ph: '', options: prodTemplates.map((pt) => ({ value: pt.code, label: `${pt.emoji || ''} ${pt.name}` })) }]}
            />
          )}

          {tab === 'productions' && (
            <CatalogTab title="🏭 Производства" items={prodTemplates} busy={busy} form={catForm} formOpen={formOpen} editingId={editingId} onFormChange={setCatForm} onCreate={startCreate} onEdit={startEdit} onCancel={cancelForm} onSave={saveProduction} onDelete={deleteProduction} onUploadImage={async () => {}}
              fields={[{ key: 'name', label: 'Название', ph: 'Стол зельеварения' }, { key: 'required', label: 'Крестиков на цикл', ph: '500', type: 'number' }]}
            />
          )}

          {tab === 'order-templates' && renderOrderTemplates()}
          {tab === 'levels' && renderLevels()}
          {tab === 'potion-recipes' && renderPotionRecipes()}

          {tab === 'orders' && (
            <div>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
                <h2 style={{ margin: 0 }}>🧺 Все заказы</h2>
                <button className="fm-btn fm-btn-sm" disabled={busy} onClick={startCreateOrder}>
                  ➕ Создать заказ
                </button>
              </div>

              {orderFormOpen && (
                <div className="fm-card" style={{ marginBottom: 10 }}>
                  <h3 style={{ marginTop: 0 }}>{orderEditingId ? '✎ Редактировать заказ' : '➕ Создать заказ'}</h3>
                  <div style={{ marginBottom: 8 }}>
                    <label style={{ display: 'block', marginBottom: 4, fontSize: 13 }}>Товар</label>
                    <select className="fm-input" value={orderForm.product_id || ''} onChange={(e) => setOrderForm({ ...orderForm, product_id: e.target.value })}>
                      <option value="">— выберите —</option>
                      {products.map((p) => (
                        <option key={p.id} value={String(p.id)}>{p.emoji} {p.name} ({p.code})</option>
                      ))}
                    </select>
                  </div>
                  <div style={{ marginBottom: 8 }}>
                    <label style={{ display: 'block', marginBottom: 4, fontSize: 13 }}>Количество (1–20)</label>
                    <input className="fm-input" type="number" min={1} max={20} value={orderForm.qty || ''} onChange={(e) => setOrderForm({ ...orderForm, qty: e.target.value })} placeholder="оставьте пустым для дефолта" />
                  </div>
                  {orderEditingId !== null && (
                    <>
                      <div style={{ marginBottom: 8 }}>
                        <label style={{ display: 'block', marginBottom: 4, fontSize: 13 }}>Награда (монет)</label>
                        <input className="fm-input" type="number" value={orderForm.reward_coins || ''} onChange={(e) => setOrderForm({ ...orderForm, reward_coins: e.target.value })} />
                      </div>
                      <div style={{ marginBottom: 8 }}>
                        <label style={{ display: 'block', marginBottom: 4, fontSize: 13 }}>Заказчик</label>
                        <input className="fm-input" value={orderForm.customer || ''} onChange={(e) => setOrderForm({ ...orderForm, customer: e.target.value })} />
                      </div>
                      <div style={{ marginBottom: 8 }}>
                        <label style={{ display: 'block', marginBottom: 4, fontSize: 13 }}>Статус</label>
                        <select className="fm-input" value={orderForm.status || ''} onChange={(e) => setOrderForm({ ...orderForm, status: e.target.value })}>
                          <option value="open">Открыт</option>
                          <option value="fulfilled">Выполнен</option>
                          <option value="cancelled">Отменён</option>
                        </select>
                      </div>
                      <div style={{ marginBottom: 8 }}>
                        <label style={{ display: 'block', marginBottom: 4, fontSize: 13 }}>Название (на карточке)</label>
                        <input className="fm-input" value={orderForm.name || ''} onChange={(e) => setOrderForm({ ...orderForm, name: e.target.value })} />
                      </div>
                    </>
                  )}
                  <div style={{ display: 'flex', gap: 8 }}>
                    <button className="fm-btn" disabled={busy} onClick={saveOrder}>💾 Сохранить</button>
                    <button className="fm-btn fm-btn-outline" disabled={busy} onClick={() => { setOrderFormOpen(false); setOrderEditingId(null); }}>Отмена</button>
                  </div>
                </div>
              )}

              {adminOrders.length === 0 ? (
                <div className="fm-card" style={{ color: 'var(--text-muted)' }}>Заказов нет.</div>
              ) : (
                <div className="fm-grid">
                  {adminOrders.map((o) => (
                    <div key={o.id} className="fm-card fm-rise">
                      <div style={{ display: 'flex', gap: 8, alignItems: 'flex-start' }}>
                        {o.image_url && (
                          <img src={mediaUrl(o.image_url)} alt="" style={{ width: 48, height: 48, objectFit: 'cover', borderRadius: 'var(--radius-sm)', flexShrink: 0 }} />
                        )}
                        <div style={{ flex: 1 }}>
                          <strong>{o.product_emoji} {o.product_name} ×{o.qty}</strong>
                          {o.name && <div style={{ fontSize: 13, color: 'var(--text-secondary)', marginTop: 2 }}>{o.name}</div>}
                          <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 4 }}>
                            {o.customer || '—'} · 🪙 {o.reward_coins} монет
                          </div>
                          <div style={{ display: 'flex', gap: 6, marginTop: 8 }}>
                            <button className="fm-btn fm-btn-xs" disabled={busy} onClick={() => startEditOrder(o)}>✎</button>
                            {o.status === 'open' && (
                              <button className="fm-btn fm-btn-xs fm-btn-danger" disabled={busy} onClick={() => cancelOrder(o.id)}>
                                ✖️
                              </button>
                            )}
                            <button className="fm-btn fm-btn-xs fm-btn-danger" disabled={busy} onClick={() => deleteOrder(o.id)}>
                              🗑
                            </button>
                            <label className="fm-btn fm-btn-xs fm-btn-outline" style={{ cursor: 'pointer' }}>
                              🖼️
                              <input type="file" accept="image/*" style={{ display: 'none' }}
                                onChange={async (e) => {
                                  const file = e.target.files?.[0];
                                  if (file) {
                                    setBusy(true); setMsg(null);
                                    try { await api.adminUploadOrderImage(o.id, file); await load(); setMsg('✓ Картинка загружена'); }
                                    catch (e2: any) { setMsg('✗ ' + (e2?.response?.data?.detail || 'Ошибка')); }
                                    finally { setBusy(false); }
                                  }
                                }}
                              />
                            </label>
                          </div>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </>
      )}
    </div>
  );
}

function SettingRow({
  field,
  value,
  disabled,
  onSave,
}: {
  field: { key: string; label: string; hint: string };
  value: string;
  disabled: boolean;
  onSave: (v: string) => void;
}) {
  const [v, setV] = useState(value);
  useEffect(() => { setV(value); }, [value]);
  return (
    <div className="fm-card fm-rise">
      <strong style={{ fontSize: 15 }}>{field.label}</strong>
      <div style={{ fontSize: 12, color: 'var(--text-muted)', margin: '4px 0 8px' }}>{field.hint}</div>
      <div style={{ display: 'flex', gap: 6 }}>
        <input className="fm-input" value={v} onChange={(e) => setV(e.target.value)} />
        <button className="fm-btn fm-btn-sm" disabled={disabled || v === value} onClick={() => onSave(v)}>
          OK
        </button>
      </div>
    </div>
  );
}

function TabBtn({ active, onClick, children }: { active: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <button className={active ? 'fm-btn' : 'fm-btn fm-btn-outline'} onClick={onClick} style={{ fontSize: 13, padding: '6px 10px' }}>
      {children}
    </button>
  );
}

interface CatField { key: string; label: string; ph: string; type?: string; options?: { value: string; label: string }[] }

function CatalogTab({
  title, items, busy, form, formOpen, editingId, onFormChange, onCreate, onEdit, onCancel, onSave, onDelete, onUploadImage, onUploadImageYoung, onUploadImageGrown, fields,
}: {
  title: string;
  items: any[];
  busy: boolean;
  form: Record<string, string>;
  formOpen: boolean;
  editingId: number | null;
  onFormChange: (f: Record<string, string>) => void;
  onCreate: () => void;
  onEdit: (item: any) => void;
  onCancel: () => void;
  onSave: () => void;
  onDelete: (id: number) => void;
  onUploadImage: (id: number, file: File) => Promise<void>;
  onUploadImageYoung?: (id: number, file: File) => Promise<void>;
  onUploadImageGrown?: (id: number, file: File) => Promise<void>;
  fields: CatField[];
}) {
  return (
    <>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
        <h2 style={{ margin: 0 }}>{title}</h2>
        <button className="fm-btn fm-btn-sm" disabled={busy} onClick={onCreate}>
          ➕ Добавить
        </button>
      </div>

      {formOpen && (
        <div className="fm-card" style={{ marginBottom: 10 }}>
          <h3 style={{ marginTop: 0 }}>{editingId ? '✎ Редактировать' : '➕ Создать'}</h3>
          {fields.map((f) => (
            <div key={f.key} style={{ marginBottom: 8 }}>
              <label style={{ display: 'block', marginBottom: 4, fontSize: 13 }}>{f.label}</label>
              {f.options ? (
                <select className="fm-input" value={form[f.key] || ''} onChange={(e) => onFormChange({ ...form, [f.key]: e.target.value })}>
                  <option value="">—</option>
                  {f.options.map((opt) => (
                    <option key={opt.value} value={opt.value}>{opt.label}</option>
                  ))}
                </select>
              ) : (
                <input
                  className="fm-input"
                  type={f.type || 'text'}
                  value={form[f.key] || ''}
                  onChange={(e) => onFormChange({ ...form, [f.key]: e.target.value })}
                  placeholder={f.ph}
                />
              )}
            </div>
          ))}
          <div style={{ display: 'flex', gap: 8 }}>
            <button className="fm-btn" disabled={busy} onClick={onSave}>💾 Сохранить</button>
            <button className="fm-btn fm-btn-outline" disabled={busy} onClick={onCancel}>Отмена</button>
          </div>
        </div>
      )}

      {items.length === 0 ? (
        <div className="fm-card" style={{ color: 'var(--text-muted)' }}>Пусто. Нажмите «Добавить».</div>
      ) : (
        <div className="fm-grid">
          {items.map((item) => {
            const hasStageImgs = onUploadImageYoung && (item.image_young_url || item.image_grown_url);
            return (
              <div key={item.id} className="fm-card fm-rise">
                <div style={{ marginBottom: 4 }}>
                  <strong style={{ wordBreak: 'break-word' }}>{item.emoji} {item.name}</strong>
                  <div style={{ fontSize: 12, color: 'var(--text-muted)', wordBreak: 'break-all' }}>{item.code}</div>
                </div>
                {hasStageImgs ? (
                  <div style={{ display: 'flex', gap: 8, marginBottom: 6 }}>
                    <div style={{ textAlign: 'center' }}>
                      {item.image_young_url && (
                        <img src={mediaUrl(item.image_young_url)} alt="молодое" style={{ width: 56, height: 56, objectFit: 'cover', borderRadius: 'var(--radius-sm)', display: 'block' }} />
                      )}
                      <div style={{ fontSize: 10, color: 'var(--text-muted)', marginTop: 2 }}>молодое</div>
                    </div>
                    <div style={{ textAlign: 'center' }}>
                      {item.image_grown_url && (
                        <img src={mediaUrl(item.image_grown_url)} alt="созревшее" style={{ width: 56, height: 56, objectFit: 'cover', borderRadius: 'var(--radius-sm)', display: 'block' }} />
                      )}
                      <div style={{ fontSize: 10, color: 'var(--text-muted)', marginTop: 2 }}>созревшее</div>
                    </div>
                  </div>
                ) : item.image_url ? (
                  <img src={mediaUrl(item.image_url)} alt="" style={{ width: 56, height: 56, objectFit: 'cover', borderRadius: 'var(--radius-sm)', marginBottom: 6 }} />
                ) : null}
                {onUploadImageYoung ? (
                  <div style={{ display: 'flex', gap: 4, marginTop: 8 }}>
                    <button className="fm-btn fm-btn-xs" disabled={busy} onClick={() => onEdit(item)}>✎</button>
                    <label className="fm-btn fm-btn-xs fm-btn-outline" title="Загрузить молодое растение" style={{ cursor: 'pointer' }}>
                      🌱
                      <input type="file" accept="image/*" style={{ display: 'none' }}
                        onChange={async (e) => { const f = e.target.files?.[0]; if (f && onUploadImageYoung) await onUploadImageYoung(item.id, f); }}
                      />
                    </label>
                    <label className="fm-btn fm-btn-xs fm-btn-outline" title="Загрузить созревшее растение" style={{ cursor: 'pointer' }}>
                      🌾
                      <input type="file" accept="image/*" style={{ display: 'none' }}
                        onChange={async (e) => { const f = e.target.files?.[0]; if (f && onUploadImageGrown) await onUploadImageGrown(item.id, f); }}
                      />
                    </label>
                    <button className="fm-btn fm-btn-xs fm-btn-danger" disabled={busy} onClick={() => onDelete(item.id)}>✕</button>
                  </div>
                ) : (
                  <div style={{ display: 'flex', gap: 4, marginTop: 8 }}>
                    <button className="fm-btn fm-btn-xs" disabled={busy} onClick={() => onEdit(item)}>✎</button>
                    <label className="fm-btn fm-btn-xs fm-btn-outline" title="Загрузить изображение" style={{ cursor: 'pointer' }}>
                      🖼️
                      <input type="file" accept="image/*" style={{ display: 'none' }}
                        onChange={async (e) => {
                          const file = e.target.files?.[0];
                          if (file) { await onUploadImage(item.id, file); }
                        }}
                      />
                    </label>
                    <button className="fm-btn fm-btn-xs fm-btn-danger" disabled={busy} onClick={() => onDelete(item.id)}>✕</button>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </>
  );
}


function FieldGridView({ field }: { field: FieldDetail }) {
  const grid = (() => {
    const g: (FieldDetail['cells'][number] | null)[][] = [];
    for (let r = 0; r < field.rows; r++) {
      const row: (FieldDetail['cells'][number] | null)[] = [];
      for (let c = 0; c < field.cols; c++) {
        row.push(field.cells.find((x) => x.col === c && x.row === r) ?? null);
      }
      g.push(row);
    }
    return g;
  })();

  const KIND_FILL: Record<string, string> = {
    empty: 'transparent',
    tent: 'rgba(224,168,62,0.15)',
    pet: 'rgba(200,130,220,0.15)',
    barnyard: 'rgba(220,180,120,0.15)',
  };

  return (
    <div style={{ width: '100%', height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
      <div style={{ position: 'relative', width: '100%', maxWidth: 800, aspectRatio: `${field.cols}/${field.rows}` }}>
        {field.map_url && (
          <img src={mediaUrl(field.map_url)} alt="" style={{ position: 'absolute', inset: 0, width: '100%', height: '100%', objectFit: 'cover', borderRadius: 4 }} />
        )}
        <div style={{ position: 'absolute', inset: 0, display: 'grid', gridTemplateColumns: `repeat(${field.cols}, 1fr)`, gridTemplateRows: `repeat(${field.rows}, 1fr)` }}>
          {grid.flatMap((row, ri) =>
            row.map((cell, ci) => {
              const key = `${ri}-${ci}`;
              const fill = KIND_FILL[cell?.kind || 'empty'] || 'transparent';
              return (
                <div
                  key={key}
                  style={{
                    border: `1px solid ${field.grid_color || 'rgba(255,255,255,0.08)'}`,
                    background: fill,
                    display: 'flex', alignItems: 'center', justifyContent: 'center', overflow: 'hidden',
                    position: 'relative',
                  }}
                >
                  {cell?.kind === 'bed' && cell.occupant_user_id != null && cell.plant_image_grown && cell.plot?.status === 'grown' && (
                    <img src={mediaUrl(cell.plant_image_grown)} alt="" style={{ width: '85%', height: '85%', objectFit: 'contain', opacity: 0.9 }} />
                  )}
                  {cell?.kind === 'bed' && cell.occupant_user_id != null && cell.plant_image_young && cell.plot?.status === 'planted' && (
                    <img src={mediaUrl(cell.plant_image_young)} alt="" style={{ width: '60%', height: '60%', objectFit: 'contain', opacity: 0.7 }} />
                  )}
                  {cell?.kind === 'pet' && (
                    <div style={{ fontSize: '3vw', opacity: 0.5 }}>🐾</div>
                  )}
                  {cell?.kind === 'barnyard' && (
                    <div style={{ fontSize: '3vw', opacity: 0.5 }}>🐄</div>
                  )}
                </div>
              );
            })
          )}
        </div>
        {field.tents?.map((t) => {
          const spanCols = t.col2 - t.col1 + 1;
          const spanRows = t.row2 - t.row1 + 1;
          return (
            <div key={`tent-${t.id}`} style={{ position: 'absolute', inset: 0, pointerEvents: 'none', display: 'grid', gridTemplateColumns: `repeat(${field.cols}, 1fr)`, gridTemplateRows: `repeat(${field.rows}, 1fr)` }}>
              <div style={{ gridColumn: `${t.col1 + 1} / span ${spanCols}`, gridRow: `${t.row1 + 1} / span ${spanRows}`, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 4, padding: 6, borderRadius: 6, background: 'rgba(224,168,62,0.12)', overflow: 'hidden' }}>
                {t.image_url && (
                  <img src={mediaUrl(t.image_url)} alt="" style={{ maxWidth: '80%', maxHeight: '50%', objectFit: 'contain' }} />
                )}
                <div style={{ fontSize: 'clamp(10px,2.2vw,14px)', color: '#ffe9b0', textAlign: 'center', textShadow: '0 1px 3px #000', lineHeight: 1.15, fontWeight: 600 }}>
                  ⛺ {t.name}
                </div>
                {t.build_status === 'planted' && (
                  <div style={{ fontSize: 10, color: '#ffd98a' }}>{t.accumulated}/{t.required}</div>
                )}
                {t.build_status === 'slot' && (
                  <div style={{ fontSize: 10, color: '#ccc' }}>слот</div>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
