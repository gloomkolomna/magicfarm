import { useCallback, useEffect, useRef, useState } from 'react';
import { useSession } from '../context/SessionContext';
import { api, BODY_PARTS, BODY_PART_LABELS, LOCATION_TITLES, potionBonusLabel, potionIngredientLabel, type AdminOrder, type AdminRecipe, type AllowedPlayer, type Animal, type Achievement, type AchievementKind, type ClinicAnimalType, type CocktailItemIn, type CocktailRecipeAdmin, type CrystalCard, type Customer, type Disease, type FieldDetail, type FieldInfo, type GameMedia, type Ingredient,   type LevelGate, type LogEntry, UNLOCK_OPTIONS, type Patient, type Pet, type Plant, type Player, type PlayerDetail, type PotionRecipe, type PotionRecipeCreate, type Product, type ProductionTemplate, type Remedy, type Setting, type StitchReport, type StorySlide, type Lesson, type DlcLocation } from '../api/endpoints';
import { compressImage, mediaUrl } from '../api/media';
import FieldEditor from '../components/FieldEditor';
import FieldGridView from '../components/FieldGridView';
import Toast from '../components/Toast';
import CrystalStandardEditor from '../components/CrystalStandardEditor';
import { confirmDialog } from '../components/Confirm';
import SpritePedestal from '../components/SpritePedestal';

const PLAYER_STATUS_META: Record<string, { label: string; emoji: string }> = {
  active: { label: 'активен', emoji: '🟢' },
  blocked: { label: 'заблокирован', emoji: '🚫' },
  readonly: { label: 'только просмотр', emoji: '👁' },
};

const BONUS_KIND_OPTIONS = [
  { value: 'harvest_orchard', label: '🍎 +1 к урожаю сада' },
  { value: 'harvest_plot', label: '🌱 +1 к урожаю грядки' },
  { value: 'order_coins', label: '💰 +5 монет к заказу' },
  { value: 'craft_bonus', label: '🏭 +1 товар при крафте' },
  { value: 'animal_product', label: '🐄 +1 продукция животного' },
];

const CARDS_DRAW_OPTIONS = [
  { value: '3', label: '3 карты' },
  { value: '4', label: '4 карты' },
  { value: '5', label: '5 карт' },
];

function fmtMsk(iso: string): string {
  const hasZone = /(Z|[+-]\d{2}:?\d{2})$/.test(iso);
  const d = new Date(hasZone ? iso : iso + 'Z');
  return d.toLocaleString('ru-RU', { timeZone: 'Europe/Moscow' });
}

const SURCHARGE_OPTIONS = [
  { value: '30', label: '30 монет' },
  { value: '35', label: '35 монет' },
  { value: '40', label: '40 монет' },
];

const SETTING_FIELDS: { key: string; label: string; hint: string }[] = [
  { key: 'auto_credit', label: 'Авто-зачёт вышивки (0/1)', hint: '1 — крестики начисляются сразу без модерации' },
  { key: 'default_plant_qty', label: 'Кол-во растений в заказе (1–50)', hint: 'По умолчанию при посадке' },
  { key: 'production_required', label: 'Норма цикла производства', hint: 'Крестики за один цикл крафта' },
  { key: 'order_reward_per_unit', label: 'Награда за единицу заказа', hint: 'Монет за 1 товар' },
  { key: 'sale_price_ratio', label: 'Коэфф. продажи излишков (0.01–1.0)', hint: 'Доля от полной цены (0.5 = ½)' },
  { key: 'customer_max_orders', label: 'Лимит активных заказов заказчика (0–50)', hint: 'Заказчики с этим числом открытых заказов скрываются при создании заказа' },
];

function matchesAny(item: unknown, q: string): boolean {
  const s = q.trim().toLowerCase();
  if (!s) return true;
  const stack: unknown[] = [item];
  while (stack.length) {
    const v = stack.pop();
    if (v == null) continue;
    if (typeof v === 'object') {
      Object.values(v as Record<string, unknown>).forEach((x) => stack.push(x));
      continue;
    }
    if (String(v).toLowerCase().includes(s)) return true;
  }
  return false;
}

export default function AdminPage() {
  const [tab, setTab] = useState<'players' | 'settings' | 'fields' | 'orders' | 'plants' | 'animals' | 'pets' | 'products' | 'productions' | 'recipes' | 'customers' | 'levels' | 'potion-recipes' | 'cocktail-recipes' | 'media' | 'crystal-cards' | 'achievements' | 'logs' | 'ingredients' | 'infirmary' | 'story' | 'lessons'>('players');
  const [players, setPlayers] = useState<Player[]>([]);
  const [allPlayers, setAllPlayers] = useState<Player[]>([]);
  const [playerSearch, setPlayerSearch] = useState('');
  const [playerPage, setPlayerPage] = useState(0);
  const PER_PAGE = 100;
  const searchTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  function doSearch(q: string) {
    if (searchTimer.current) clearTimeout(searchTimer.current);
    searchTimer.current = setTimeout(() => {
      setPlayers(q.trim() ? allPlayers.filter((p) => matchesAny(p, q)) : allPlayers);
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
  const [accessPlayers, setAccessPlayers] = useState<AllowedPlayer[]>([]);
  const [accessLink, setAccessLink] = useState('');
  const [lockedLocations, setLockedLocationsState] = useState<string[]>([]);
  const { loading: sessionLoading } = useSession();
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  // ── Предыстория ──
  const [storySlides, setStorySlides] = useState<StorySlide[]>([]);
  const [dlcLocations, setDlcLocations] = useState<DlcLocation[]>([]);
  const [storyForm, setStoryForm] = useState<{ text: string; sort_order: string; location_code: string }>({ text: '', sort_order: '0', location_code: '' });
  const [storyEditingId, setStoryEditingId] = useState<number | null>(null);
  const [storyImage, setStoryImage] = useState<File | null>(null);

  // ── Видео-уроки ──
  const [lessons, setLessons] = useState<Lesson[]>([]);
  const [lessonForm, setLessonForm] = useState<{ title: string; description: string; sort_order: string }>({ title: '', description: '', sort_order: '0' });
  const [lessonEditingId, setLessonEditingId] = useState<number | null>(null);
  const [lessonVideo, setLessonVideo] = useState<File | null>(null);
  const [lessonImage, setLessonImage] = useState<File | null>(null);

  // ── Карты-локации ──
  const [fields, setFields] = useState<FieldInfo[]>([]);
  const [allPlants, setAllPlants] = useState<Plant[]>([]);
  const [editorFieldId, setEditorFieldId] = useState<number | null>(null);
  const [showCreate, setShowCreate] = useState(false);
  const [newName, setNewName] = useState('');
  const [newCols, setNewCols] = useState('6');
  const [newRows, setNewRows] = useState('4');
  const [lockRatio, setLockRatio] = useState(false);
  const [newFieldKind, setNewFieldKind] = useState('');
  const [newPlantCategory, setNewPlantCategory] = useState('');
  const [newMinLevel, setNewMinLevel] = useState('0');

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

  useEffect(() => {
    setFormOpen(false);
    setEditingId(null);
    setCatForm({});
  }, [tab]);

  useEffect(() => {
    const r = loadedRef.current;
    if (tab === 'players' && !r.has('access')) { r.add('access'); api.adminAccessPlayers().then(setAccessPlayers).catch(() => {}); }
    if (tab === 'settings' && !r.has('locked-locations')) { r.add('locked-locations'); api.getLockedLocations().then((res) => setLockedLocationsState(res.codes)).catch(() => {}); }
    if (tab === 'plants' && !r.has('plants')) { r.add('plants'); api.plants().then(setPlants).catch(() => {}); }
    if (tab === 'animals' && !r.has('animals')) { r.add('animals'); api.adminAnimals().then(setAnimals).catch(() => {}); }
    if (tab === 'pets' && !r.has('pets')) { r.add('pets'); api.adminPets().then(setPets).catch(() => {}); }
    if (tab === 'products' && !r.has('products')) {
      r.add('products');
      Promise.all([
        api.adminProducts().catch(() => [] as Product[]),
        api.adminProductionTemplates().catch(() => [] as ProductionTemplate[]),
        api.plants().catch(() => [] as Plant[]),
        api.adminAnimals().catch(() => [] as Animal[]),
        api.adminPets().catch(() => [] as Pet[]),
      ]).then(([prods, tpls, pls, anm, pts]) => {
        setCatalogProducts(prods);
        setProdTemplates(tpls);
        setPlants(pls);
        setAnimals(anm);
        setPets(pts);
      });
    }
    if (tab === 'productions' && !r.has('productions')) { r.add('productions'); api.adminProductionTemplates().then(setProdTemplates).catch(() => {}); }
    if (tab === 'media' && !r.has('media')) { r.add('media'); api.adminGameMedia().then(setGameMedia).catch(() => {}); }
    if (tab === 'story' && !r.has('story')) {
      r.add('story');
      api.adminStorySlides().then(setStorySlides).catch(() => {});
      api.adminDlcLocations().then(setDlcLocations).catch(() => {});
    }
    if (tab === 'lessons' && !r.has('lessons')) { r.add('lessons'); api.adminLessons().then(setLessons).catch(() => {}); }
    if (tab === 'crystal-cards' && !r.has('crystal-cards')) { r.add('crystal-cards'); api.adminCrystalCards().then(setCrystalCards).catch(() => {}); }
    if ((tab === 'orders' || tab === 'customers') && !r.has('orders')) {
      r.add('orders');
      Promise.all([
        api.adminOrders().catch(() => [] as AdminOrder[]),
        api.products().catch(() => [] as Product[]),
      ]).then(([ords, prods]) => { setAdminOrders(ords); setProducts(prods); });
    }
    if ((tab === 'orders' || tab === 'customers') && !r.has('customers')) {
      r.add('customers');
      api.adminCustomers().then(setCustomers).catch(() => {});
    }
  }, [tab]);

  // ── Уровни ──
  const [levels, setLevels] = useState<LevelGate[]>([]);
  const [levelForm, setLevelForm] = useState({ level: 0, coins_required: 0, plots_required: 0, unlock_type: '' });
  const [levelImage, setLevelImage] = useState<File | null>(null);
  const [levelImageLevel, setLevelImageLevel] = useState(0);

  // ── Логи ──
  const LOG_PAGE = 100;
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [logFilter, setLogFilter] = useState({ source: '', level: '', q: '', user_id: '' });
  const [logOffset, setLogOffset] = useState(0);
  const [logHasMore, setLogHasMore] = useState(false);
  const [expandedLog, setExpandedLog] = useState<number | null>(null);
  const logSearchTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  async function loadLogs(append = false) {
    try {
      const off = append ? logOffset : 0;
      const rows = await api.adminLogs({
        source: logFilter.source || undefined,
        level: logFilter.level || undefined,
        q: logFilter.q.trim() || undefined,
        user_id: logFilter.user_id.trim() ? Number(logFilter.user_id) : undefined,
        limit: LOG_PAGE,
        offset: off,
      });
      setLogs((prev) => (append ? [...prev, ...rows] : rows));
      setLogOffset(off + rows.length);
      setLogHasMore(rows.length === LOG_PAGE);
    } catch { /* ignore */ }
  }

  async function clearLogs() {
    if (!(await confirmDialog('Удалить ВСЕ логи безвозвратно?'))) return;
    setBusy(true); setMsg(null);
    try {
      await api.adminClearLogs();
      setLogs([]); setLogOffset(0); setLogHasMore(false); setExpandedLog(null);
      setMsg('✓ Логи очищены');
    } catch (e: any) { setMsg('✗ ' + (e?.response?.data?.detail || 'Ошибка')); }
    finally { setBusy(false); }
  }

  useEffect(() => {
    if (tab !== 'logs') return;
    if (logSearchTimer.current) clearTimeout(logSearchTimer.current);
    logSearchTimer.current = setTimeout(() => { loadLogs(false); }, 300);
    return () => { if (logSearchTimer.current) clearTimeout(logSearchTimer.current); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tab, logFilter]);

  // ── Рецепты зелий ──
  const [potionRecipes, setPotionRecipes] = useState<PotionRecipe[]>([]);
  const [potionForm, setPotionForm] = useState<PotionRecipeCreate>({ name: '', level: 'green', ingredient_slots: [], bonus_code: null, reward_coins: 100, description: '' });
  const [potionEditingId, setPotionEditingId] = useState<number | null>(null);
  const [potionSlotInput, setPotionSlotInput] = useState('');

  // ── Коктейли ──
  const [cocktailRecipes, setCocktailRecipes] = useState<CocktailRecipeAdmin[]>([]);
  const [cocktailForm, setCocktailForm] = useState<{ name: string; description: string; patient_id: string; items: CocktailItemIn[] }>({ name: '', description: '', patient_id: '', items: [] });
  const [cocktailEditingId, setCocktailEditingId] = useState<number | null>(null);
  const [cocktailPickKind, setCocktailPickKind] = useState<'product' | 'plant' | 'ingredient' | 'remedy'>('product');
  const [cocktailPickId, setCocktailPickId] = useState<string>('');
  const [cocktailPickQty, setCocktailPickQty] = useState('1');

  // ── Ингредиенты (аптека) ──
  const [ingredients, setIngredients] = useState<Ingredient[]>([]);
  const [ingForm, setIngForm] = useState<{ name: string; description: string; sort_order: string }>({ name: '', description: '', sort_order: '0' });
  const [ingEditingId, setIngEditingId] = useState<number | null>(null);

  // ── Лечебница: мази, болезни, пациенты ──
  const [remedies, setRemedies] = useState<Remedy[]>([]);
  const [remedyForm, setRemedyForm] = useState<{ name: string; description: string; items: { ingredient_id: number | null; plant_id: number | null; qty: number }[] }>({ name: '', description: '', items: [] });
  const [remedyPickKind, setRemedyPickKind] = useState<'ingredient' | 'plant'>('ingredient');
  const [remedyPickId, setRemedyPickId] = useState<number | ''>('');
  const [remedyPickQty, setRemedyPickQty] = useState('1');
  const [remedyEditingId, setRemedyEditingId] = useState<number | null>(null);
  const [diseases, setDiseases] = useState<Disease[]>([]);
  const [diseaseForm, setDiseaseForm] = useState<{ name: string; description: string; remedyId: string; symptoms: { part_code: string; text: string }[] }>({ name: '', description: '', remedyId: '', symptoms: [] });
  const [diseaseSymPart, setDiseaseSymPart] = useState('');
  const [diseaseSymText, setDiseaseSymText] = useState('');
  const [diseaseEditingId, setDiseaseEditingId] = useState<number | null>(null);
  const [patients, setPatients] = useState<Patient[]>([]);
  const [animalTypes, setAnimalTypes] = useState<ClinicAnimalType[]>([]);
  const [infirmaryBg, setInfirmaryBg] = useState<string>('');
  const [animalTypeForm, setAnimalTypeForm] = useState<{ name: string; emoji: string }>({ name: '', emoji: '' });
  const [animalTypeEditingId, setAnimalTypeEditingId] = useState<number | null>(null);
  const [patientForm, setPatientForm] = useState<{ name: string; level: string; diseaseId: string; animalTypeId: string }>({ name: '', level: '1', diseaseId: '', animalTypeId: '' });
  const [patientEditingId, setPatientEditingId] = useState<number | null>(null);
  const [infirmaryTab, setInfirmaryTab] = useState<'remedies' | 'diseases' | 'types' | 'locations'>('remedies');

  // ── Рецепты библиотеки ──
  const [recipes, setRecipes] = useState<AdminRecipe[]>([]);
  const [recipeForm, setRecipeForm] = useState({ source_kind: 'plant', plant_id: '', source_product_id: '', product_id: '', level: '1' });
  const [recipeEditingId, setRecipeEditingId] = useState<number | null>(null);

  const MEDIA_TYPES: { code: string; kind: string; label: string }[] = [
    { code: 'card_shuffle', kind: 'video', label: '🎴 Видео перетасовки карт' },
    { code: 'dice_roll', kind: 'video', label: '🎲 Видео броска кубика' },
    { code: 'dice_face_1', kind: 'image', label: '⚀ Грань кубика 1' },
    { code: 'dice_face_2', kind: 'image', label: '⚁ Грань кубика 2' },
    { code: 'dice_face_3', kind: 'image', label: '⚂ Грань кубика 3' },
    { code: 'dice_face_4', kind: 'image', label: '⚃ Грань кубика 4' },
    { code: 'dice_face_5', kind: 'image', label: '⚄ Грань кубика 5' },
    { code: 'dice_face_6', kind: 'image', label: '⚅ Грань кубика 6' },
    { code: 'house_build_video', kind: 'video', label: '🏠 Видео постройки дома ведьмы' },
    { code: 'house_built_image', kind: 'image', label: '🏠 Картинка финала дома ведьмы' },
    { code: 'house_material_glass', kind: 'image', label: '🪟 Стройматериал: стекло' },
    { code: 'house_material_wood', kind: 'image', label: '🪵 Стройматериал: древесина' },
    { code: 'house_material_nails', kind: 'image', label: '🔩 Стройматериал: гвозди' },
    { code: 'house_material_pipes', kind: 'image', label: '🚰 Стройматериал: трубы' },
    { code: 'house_material_bricks', kind: 'image', label: '🧱 Стройматериал: кирпичи' },
    { code: 'house_material_paint', kind: 'image', label: '🎨 Стройматериал: краска' },
    { code: 'cauldron_tin', kind: 'image', label: '🍲 Котёл: оловянный (4 ингредиента)' },
    { code: 'cauldron_silver', kind: 'image', label: '🍲 Котёл: серебряный (5 ингредиентов)' },
    { code: 'cauldron_gold', kind: 'image', label: '🍲 Котёл: золотой (6 ингредиентов)' },
    { code: 'potion_brew', kind: 'video', label: '🧪 Видео варки зелья' },
    { code: 'infirmary_book', kind: 'image', label: '📖 Иконка книги лечебницы' },
    { code: 'remedy_heal', kind: 'video', label: '💊 Видео лечения животного' },
  ];

  const [gameMedia, setGameMedia] = useState<GameMedia[]>([]);
  const [mediaTypeSel, setMediaTypeSel] = useState('');

  const [crystalCards, setCrystalCards] = useState<CrystalCard[]>([]);

  // ── Достижения ──
  const [achievements, setAchievements] = useState<Achievement[]>([]);
  const [achKinds, setAchKinds] = useState<AchievementKind[]>([]);
  const [achForm, setAchForm] = useState({ name: '', condition_kind: '', condition_value: '1', production_code: '' });
  const [achEditingId, setAchEditingId] = useState<number | null>(null);
  const [achImage, setAchImage] = useState<File | null>(null);

  // ── Заказчики ──
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [customerForm, setCustomerForm] = useState('');
  const [customerEditingId, setCustomerEditingId] = useState<number | null>(null);
  const customerNames = customers.map((c) => c.name);
  const rawCustomerMax = Number(settings['customer_max_orders']);
  const customerMaxOrders = Number.isFinite(rawCustomerMax) ? rawCustomerMax : 3;
  const freeCustomerNames = customers.filter((c) => c.open_orders_count < customerMaxOrders).map((c) => c.name);

  // ── Фон ──
  const [bgUrl, setBgUrl] = useState('');
  const [bgInput, setBgInput] = useState('');

  // ── Заказы: создание/редактирование ──
  const [orderFormOpen, setOrderFormOpen] = useState(false);
  const [orderEditingId, setOrderEditingId] = useState<number | null>(null);
  const [orderForm, setOrderForm] = useState<Record<string, string>>({});
  const [orderImage, setOrderImage] = useState<File | null>(null);
  const orderCustomerOptions = orderForm.customer && !freeCustomerNames.includes(orderForm.customer)
    ? [orderForm.customer, ...freeCustomerNames]
    : freeCustomerNames;

  const loadedRef = useRef<Set<string>>(new Set());

  const loadCore = useCallback(async () => {
    setLoading(true);
    try {
      const [plys, setMap, flds, pls] = await Promise.all([
        api.adminPlayers().catch(() => [] as Player[]),
        Promise.all(
          SETTING_FIELDS.map((f) => api.getSetting(f.key).then((s) => [s.key, s.value] as [string, string])),
        ).catch(() => [] as [string, string][]),
        api.adminFields().catch(() => [] as FieldInfo[]),
        api.plants().catch(() => [] as Plant[]),
      ]);
      setPlayers(plys);
      setAllPlayers(plys);
      setSettings(Object.fromEntries(setMap));
      setFields(flds);
      setAllPlants(pls);
    } finally {
      setLoading(false);
    }
  }, []);

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
      loadBg();
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { if (!sessionLoading) loadCore(); }, [loadCore, sessionLoading]);

  useEffect(() => {
    const prevent = (e: Event) => e.preventDefault();
    document.addEventListener('submit', prevent);
    return () => document.removeEventListener('submit', prevent);
  }, []);

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

  async function restartPlayer() {
    if (!selectedPlayer) return;
    if (!(await confirmDialog(`Удалить ВЕСЬ прогресс игрока #${selectedPlayer.vk_id} (грядки, склад, заказы, отчёты, достижения, нормы)?`))) return;
    if (!(await confirmDialog('Точно? Действие необратимо.'))) return;
    setBusy(true); setMsg(null);
    try {
      const updated = await api.adminRestartPlayer(selectedPlayer.vk_id);
      setSelectedPlayer(updated);
      setPlayerReports([]);
      setPlayerDetail(null);
      try { setPlayerDetail(await api.adminPlayerDetail(selectedPlayer.vk_id)); } catch {}
      setMsg('✓ Игрок перезапущен: прогресс обнулён');
    } catch (e: any) {
      setMsg('✗ ' + (e?.response?.data?.detail || 'Ошибка'));
    } finally {
      setBusy(false);
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

  async function reloadPlayerDetail() {
    if (!selectedPlayer) return;
    try { setPlayerDetail(await api.adminPlayerDetail(selectedPlayer.vk_id)); } catch {}
  }

  async function addAccessPlayer() {
    const link = accessLink.trim();
    if (!link) return;
    setBusy(true); setMsg(null);
    try {
      const added = await api.adminAddAccessPlayer(link);
      setMsg(`✓ Игрок #${added.vk_id} получил доступ`);
      setAccessLink('');
      setAccessPlayers(await api.adminAccessPlayers());
    } catch (e: any) {
      setMsg('✗ ' + (e?.response?.data?.detail || 'Ошибка'));
    } finally {
      setBusy(false);
    }
  }

  async function removeAccessPlayer(vkId: number) {
    if (!(await confirmDialog(`Убрать игрока #${vkId} из списка доступа? Он сразу потеряет вход.`))) return;
    setBusy(true); setMsg(null);
    try {
      await api.adminDeleteAccessPlayer(vkId);
      setAccessPlayers((prev) => prev.filter((p) => p.vk_id !== vkId));
      setMsg('✓ Доступ убран');
    } catch (e: any) {
      setMsg('✗ ' + (e?.response?.data?.detail || 'Ошибка'));
    } finally {
      setBusy(false);
    }
  }

  async function toggleLockedLocation(code: string) {
    setBusy(true); setMsg(null);
    try {
      const next = lockedLocations.includes(code)
        ? lockedLocations.filter((c) => c !== code)
        : [...lockedLocations, code];
      const res = await api.setLockedLocations(next);
      setLockedLocationsState(res.codes);
      setMsg('✓ Сохранено');
    } catch (e: any) {
      setMsg('✗ ' + (e?.response?.data?.detail || 'Ошибка'));
    } finally {
      setBusy(false);
    }
  }

  async function togglePlayerDlc(vkId: number, code: string, granted: boolean) {
    setBusy(true); setMsg(null);
    try {
      if (granted) {
        await api.adminRevokeDlc(vkId, code);
        setMsg('✓ Дополнение забрано');
      } else {
        await api.adminGrantDlc(vkId, code);
        setMsg('✓ Дополнение выдано');
      }
      await reloadPlayerDetail();
    } catch (e: any) {
      setMsg('✗ ' + (e?.response?.data?.detail || 'Ошибка'));
    } finally {
      setBusy(false);
    }
  }

  async function setPlayerStatus(vkId: number, status: string) {
    setBusy(true); setMsg(null);
    try {
      const updated = await api.adminSetPlayerStatus(vkId, status);
      if (selectedPlayer?.vk_id === vkId) setSelectedPlayer(updated);
      const patch = (p: Player) => (p.vk_id === vkId ? { ...p, status: updated.status } : p);
      setPlayers((prev) => prev.map(patch));
      setAllPlayers((prev) => prev.map(patch));
      setMsg(`✓ Статус: ${PLAYER_STATUS_META[updated.status]?.label ?? updated.status}`);
    } catch (e: any) {
      setMsg('✗ ' + (e?.response?.data?.detail || 'Ошибка'));
    } finally {
      setBusy(false);
    }
  }

  async function deletePlayerAccount() {
    if (!selectedPlayer) return;
    if (!(await confirmDialog(`Удалить игрока #${selectedPlayer.vk_id} ПОЛНОСТЬЮ (профиль, весь прогресс, фото-отчёты, доступ)?`))) return;
    if (!(await confirmDialog('Точно? Восстановить будет невозможно.'))) return;
    setBusy(true); setMsg(null);
    try {
      await api.adminDeletePlayer(selectedPlayer.vk_id);
      setMsg('✓ Игрок удалён');
      setSelectedPlayer(null);
      setPlayerDetail(null);
      setPlayerReports([]);
      try {
        const list = await api.adminPlayers();
        setAllPlayers(list);
        setPlayers(list);
      } catch {}
      try { setAccessPlayers(await api.adminAccessPlayers()); } catch {}
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
      await api.adminCreateField(name, Number(newCols) || 6, Number(newRows) || 4, newPlantCategory || null, Number(newMinLevel) || 0, newFieldKind || null);
      setMsg('✓ Локация создана');
      setShowCreate(false); setNewName(''); setNewFieldKind(''); setNewPlantCategory(''); setNewMinLevel('0');
      await load();
    } catch (e: any) {
      setMsg('✗ ' + (e?.response?.data?.detail || 'Ошибка'));
    } finally { setBusy(false); }
  }

  async function deleteField(id: number) {
    if (!(await confirmDialog('Удалить локацию со всеми клетками и шатрами?'))) return;
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
  function startCreate() { setCatForm({ name: '' }); setEditingId(null); setFormOpen(true); }
  function startEdit(item: Record<string, any>) { const f: Record<string, string> = {}; for (const [k, v] of Object.entries(item)) f[k] = v == null ? '' : String(v); setCatForm(f); setEditingId(item.id); setFormOpen(true); }
  async function cancelForm() {
    if (!catForm.name?.trim() && editingId) {
      if (tab === 'plants') try { await api.adminDeletePlant(editingId); } catch {}
      else if (tab === 'animals') try { await api.adminDeleteAnimal(editingId); } catch {}
      else if (tab === 'pets') try { await api.adminDeletePet(editingId); } catch {}
      else if (tab === 'products') try { await api.adminDeleteProduct(editingId); } catch {}
      else if (tab === 'productions') try { await api.adminDeleteProductionTemplate(editingId); } catch {}
    }
    setEditingId(null); setCatForm({}); setFormOpen(false);
  }

  async function savePlant() {
    if (!catForm.name?.trim()) return;
    setBusy(true); setMsg(null);
    try {
      if (editingId) { await api.adminUpdatePlant(editingId, catForm); }
      else { const created = await api.adminCreatePlant(catForm as any); setEditingId(created.id); }
      setMsg('✓ Сохранено');
      await load();
    } catch (e: any) { setMsg('✗ ' + (e?.response?.data?.detail || 'Ошибка')); }
    finally { setBusy(false); }
  }

  async function deletePlant(id: number) {
    if (!(await confirmDialog('Удалить растение?'))) return;
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
      else { const created = await api.adminCreateAnimal(catForm as any); setEditingId(created.id); }
      setMsg('✓ Сохранено');
      await load();
    } catch (e: any) { setMsg('✗ ' + (e?.response?.data?.detail || 'Ошибка')); }
    finally { setBusy(false); }
  }

  async function deleteAnimal(id: number) {
    if (!(await confirmDialog('Удалить животное?'))) return;
    setBusy(true); setMsg(null);
    try { await api.adminDeleteAnimal(id); await load(); setMsg('✓ Удалено'); }
    catch (e: any) { setMsg('✗ ' + (e?.response?.data?.detail || 'Ошибка')); }
    finally { setBusy(false); }
  }

  async function savePet() {
    if (!catForm.name?.trim()) return;
    setBusy(true); setMsg(null);
    try {
      const data = { ...catForm };
      if (data.bonus_kind) {
        const opt = BONUS_KIND_OPTIONS.find(o => o.value === data.bonus_kind);
        if (opt) data.bonus_description = opt.label;
      }
      if (editingId) await api.adminUpdatePet(editingId, data);
      else { const created = await api.adminCreatePet(data as any); setEditingId(created.id); }
      setMsg('✓ Сохранено');
      await load();
    } catch (e: any) { setMsg('✗ ' + (e?.response?.data?.detail || 'Ошибка')); }
    finally { setBusy(false); }
  }

  async function cancelOrder(id: number) {
    if (!(await confirmDialog('Отменить заказ?'))) return;
    setBusy(true); setMsg(null);
    try { await api.adminCancelOrder(id); await load(); setMsg('✓ Отменён'); }
    catch (e: any) { setMsg('✗ ' + (e?.response?.data?.detail || 'Ошибка')); }
    finally { setBusy(false); }
  }

  async function deleteOrder(id: number) {
    if (!(await confirmDialog('Удалить заказ?'))) return;
    setBusy(true); setMsg(null);
    try { await api.adminDeleteOrder(id); await load(); setMsg('✓ Удалён'); }
    catch (e: any) { setMsg('✗ ' + (e?.response?.data?.detail || 'Ошибка')); }
    finally { setBusy(false); }
  }

  // ── Заказы: создание и редактирование ──
  function startCreateOrder() {
    setOrderForm({ kind: 'product', product_id: '', potion_recipe_id: '', qty: '', customer: '' });
    setOrderImage(null);
    setOrderEditingId(null);
    setOrderFormOpen(true);
    api.adminCustomers().then(setCustomers).catch(() => {});
    if (potionRecipes.length === 0) loadPotionRecipes();
  }

  function startEditOrder(o: AdminOrder) {
    setOrderForm({
      kind: o.potion_recipe_id != null ? 'potion' : 'product',
      product_id: o.product_id != null ? String(o.product_id) : '',
      potion_recipe_id: o.potion_recipe_id != null ? String(o.potion_recipe_id) : '',
      qty: String(o.qty),
      reward_coins: String(o.reward_coins),
      customer: o.customer || '',
      customer_phrase: o.customer_phrase || '',
      name: o.name || '',
    });
    setOrderEditingId(o.id);
    setOrderFormOpen(true);
    api.adminCustomers().then(setCustomers).catch(() => {});
    if (potionRecipes.length === 0) loadPotionRecipes();
  }

  async function saveOrder() {
    const isPotion = orderForm.kind === 'potion';
    const pid = Number(orderForm.product_id);
    const prid = Number(orderForm.potion_recipe_id);
    const q = orderForm.qty ? Number(orderForm.qty) : undefined;
    const customer = orderForm.customer || undefined;
    if (isPotion ? !prid : !pid) return;
    setBusy(true); setMsg(null);
    try {
      let targetId = orderEditingId;
      if (orderEditingId !== null) {
        await api.adminUpdateOrder(orderEditingId, {
          product_id: isPotion ? undefined : (pid || undefined),
          qty: isPotion ? undefined : q,
          reward_coins: orderForm.reward_coins ? Number(orderForm.reward_coins) : undefined,
          customer: customer,
          customer_phrase: orderForm.customer_phrase ?? undefined,
          name: orderForm.name || undefined,
        });
        setMsg('✓ Заказ обновлён');
      } else if (isPotion) {
        const created = await api.adminGenerateOrder(null, undefined, customer ?? null, orderForm.customer_phrase?.trim() || undefined, prid);
        targetId = created.id;
        setMsg('✓ Заказ на зелье создан');
      } else {
        const created = await api.adminGenerateOrder(pid, q, customer ?? null, orderForm.customer_phrase?.trim() || undefined);
        targetId = created.id;
        setMsg('✓ Заказ создан');
      }
      if (targetId && orderImage) {
        await api.adminUploadOrderImage(targetId, orderImage);
      }
      setOrderFormOpen(false);
      setOrderEditingId(null);
      setOrderImage(null);
      await load();
      api.adminCustomers().then(setCustomers).catch(() => {});
    } catch (e: any) { setMsg('✗ ' + (e?.response?.data?.detail || 'Ошибка')); }
    finally { setBusy(false); }
  }

  async function deletePet(id: number) {
    if (!(await confirmDialog('Удалить питомца?'))) return;
    setBusy(true); setMsg(null);
    try { await api.adminDeletePet(id); await load(); setMsg('✓ Удалено'); }
    catch (e: any) { setMsg('✗ ' + (e?.response?.data?.detail || 'Ошибка')); }
    finally { setBusy(false); }
  }

  async function saveProduct() {
    if (!catForm.name?.trim()) return;
    if (!catForm.production_kind) { setMsg('✗ Укажите производство'); return; }
    if (!catForm.plant_id && !catForm.animal_id && !catForm.pet_id) { setMsg('✗ Укажите растение, животное или питомца'); return; }
    setBusy(true); setMsg(null);
    try {
      const data: Record<string, any> = { ...catForm };
      for (const k of ['plant_id', 'animal_id', 'pet_id']) {
        data[k] = (data[k] === '' || data[k] == null) ? null : Number(data[k]);
      }
      if (data.stars === '' || data.stars == null) delete data.stars;
      else data.stars = Number(data.stars);
      if (editingId) await api.adminUpdateProduct(editingId, data);
      else { const created = await api.adminCreateProduct(data as any); setEditingId(created.id); }
      setMsg('✓ Сохранено');
      await load();
    } catch (e: any) { setMsg('✗ ' + (e?.response?.data?.detail || 'Ошибка')); }
    finally { setBusy(false); }
  }

  async function deleteProduct(id: number) {
    if (!(await confirmDialog('Удалить товар?'))) return;
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
      else { const created = await api.adminCreateProductionTemplate(catForm as any); setEditingId(created.id); }
      setMsg('✓ Сохранено');
      await load();
    } catch (e: any) { setMsg('✗ ' + (e?.response?.data?.detail || 'Ошибка')); }
    finally { setBusy(false); }
  }

  async function deleteProduction(id: number) {
    if (!(await confirmDialog('Удалить производство?'))) return;
    setBusy(true); setMsg(null);
    try { await api.adminDeleteProductionTemplate(id); await load(); setMsg('✓ Удалено'); }
    catch (e: any) { setMsg('✗ ' + (e?.response?.data?.detail || 'Ошибка')); }
    finally { setBusy(false); }
  }

  // ── Заказчики ──
  async function loadCustomers() {
    try { setCustomers(await api.adminCustomers()); }
    catch { /* ignore */ }
  }
  async function saveCustomer() {
    const name = customerForm.trim();
    if (!name) { setMsg('✗ Введите имя заказчика'); return; }
    setBusy(true); setMsg(null);
    try {
      if (customerEditingId) { await api.adminUpdateCustomer(customerEditingId, name); }
      else { await api.adminCreateCustomer(name); }
      await loadCustomers();
      setCustomerForm('');
      setCustomerEditingId(null);
      setMsg('✓ Сохранено');
    } catch (e: any) { setMsg('✗ ' + (e?.response?.data?.detail || 'Ошибка')); }
    finally { setBusy(false); }
  }
  async function deleteCustomer(id: number) {
    if (!(await confirmDialog('Удалить заказчика?'))) return;
    setBusy(true); setMsg(null);
    try { await api.adminDeleteCustomer(id); await loadCustomers(); setMsg('✓ Удалено'); }
    catch (e: any) { setMsg('✗ ' + (e?.response?.data?.detail || 'Ошибка')); }
    finally { setBusy(false); }
  }
  async function uploadCustomerImage(id: number, file: File) {
    setBusy(true); setMsg(null);
    try {
      await api.adminUploadCustomerImage(id, file);
      await loadCustomers();
      setMsg('✓ Фото загружено');
    } catch (e: any) { setMsg('✗ ' + (e?.response?.data?.detail || 'Ошибка')); }
    finally { setBusy(false); }
  }

  function renderCustomers() {
    return (
      <div>
        <h2>🧑 Заказчики</h2>
        <div className="fm-card" style={{ marginBottom: 10, display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
          <input
            className="fm-input"
            placeholder="Имя заказчика"
            value={customerForm}
            onChange={(e) => setCustomerForm(e.target.value)}
            style={{ maxWidth: 280 }}
          />
          <button type="button" className="fm-btn" disabled={busy} onClick={saveCustomer}>
            {customerEditingId ? '✎ Сохранить' : '➕ Добавить'}
          </button>
          {customerEditingId && (
            <button type="button" className="fm-btn fm-btn-outline" onClick={() => { setCustomerEditingId(null); setCustomerForm(''); }}>Отмена</button>
          )}
        </div>
        <table className="fm-table" style={{ width: '100%' }}>
          <thead><tr><th>ID</th><th>Имя</th><th>Открытых заказов</th><th>Фото</th><th></th></tr></thead>
          <tbody>
            {shownCustomers.map((c) => (
              <tr key={c.id} style={c.open_orders_count >= customerMaxOrders ? { opacity: 0.5 } : undefined}>
                <td>{c.id}</td>
                <td>{c.name}</td>
                <td>{c.open_orders_count}{c.open_orders_count >= customerMaxOrders ? ' (лимит)' : ''}</td>
                <td>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                    {c.image_url && <img src={mediaUrl(c.image_url)} alt="" style={{ width: 36, height: 36, objectFit: 'cover', borderRadius: 4 }} />}
                    <label className="fm-btn fm-btn-sm" style={{ cursor: 'pointer', margin: 0 }}>
                      🖼
                      <input type="file" accept="image/*" hidden onChange={(e) => {
                        const f = e.target.files?.[0];
                        if (f) uploadCustomerImage(c.id, f);
                        e.target.value = '';
                      }} />
                    </label>
                  </div>
                </td>
                <td>
                  <button type="button" className="fm-btn fm-btn-sm" onClick={() => { setCustomerEditingId(c.id); setCustomerForm(c.name); }}>✎</button>
                  <button type="button" className="fm-btn fm-btn-sm" style={{ marginLeft: 4 }} onClick={() => deleteCustomer(c.id)}>🗑</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {qActive && shownCustomers.length === 0 && <div className="fm-card" style={{ color: 'var(--text-muted)', marginTop: 8 }}>{NO_MATCH}</div>}
      </div>
    );
  }

  // ── Уровни ──
  async function loadLevels() {
    try { setLevels(await api.adminLevels()); }
    catch { /* ignore */ }
  }
  async function saveLevel() {
    setBusy(true); setMsg(null);
    try {
      await api.adminSetLevel(levelForm.level, levelForm.coins_required, levelForm.plots_required, levelForm.unlock_type || null);
      await loadLevels();
      setMsg('✓ Сохранено');
    } catch (e: any) { setMsg('✗ ' + (e?.response?.data?.detail || 'Ошибка')); }
    finally { setBusy(false); }
  }
  async function uploadLevelImage() {
    if (!levelImage) { setMsg('✗ Выберите файл'); return; }
    setBusy(true); setMsg(null);
    try {
      await api.adminUploadLevelImage(levelImageLevel, levelImage);
      setLevelImage(null);
      await loadLevels();
      setMsg('✓ Изображение загружено');
    } catch (e: any) { setMsg('✗ ' + (e?.response?.data?.detail || 'Ошибка')); }
    finally { setBusy(false); }
  }
  async function deleteLevel(level: number) {
    if (!(await confirmDialog(`Удалить уровень ${level}?`))) return;
    setBusy(true); setMsg(null);
    try { await api.adminDeleteLevel(level); await loadLevels(); setMsg('✓ Удалено'); }
    catch (e: any) { setMsg('✗ ' + (e?.response?.data?.detail || 'Ошибка')); }
    finally { setBusy(false); }
  }

  function renderLevels() {
    return (
      <div>
        <h2>📊 Уровни (маршрутный лист)</h2>
        <div className="fm-card" style={{ marginBottom: 10, display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
          <input className="fm-input" type="number" placeholder="Уровень (0-16)" value={levelForm.level} onChange={(e) => setLevelForm({ ...levelForm, level: Number(e.target.value) })} style={{ width: 80 }} />
          <input className="fm-input" type="number" placeholder="Монет" value={levelForm.coins_required || ''} onChange={(e) => setLevelForm({ ...levelForm, coins_required: Number(e.target.value) })} style={{ width: 100 }} />
          <input className="fm-input" type="number" placeholder="Грядок" value={levelForm.plots_required || ''} onChange={(e) => setLevelForm({ ...levelForm, plots_required: Number(e.target.value) })} style={{ width: 80 }} />
          <select className="fm-input" value={levelForm.unlock_type} onChange={(e) => setLevelForm({ ...levelForm, unlock_type: e.target.value })} style={{ width: 200 }}>
            <option value="">— Что разблокируется —</option>
            {UNLOCK_OPTIONS.map((opt) => (
              <option key={opt} value={opt}>{opt}</option>
            ))}
          </select>
          <button type="button" className="fm-btn" disabled={busy} onClick={saveLevel}>💾 Сохранить</button>
        </div>
        <div className="fm-card" style={{ marginBottom: 10, display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
          <input className="fm-input" type="number" placeholder="Уровень" value={levelImageLevel} onChange={(e) => setLevelImageLevel(Number(e.target.value))} style={{ width: 80 }} />
          <input type="file" accept="image/*" onChange={(e) => setLevelImage(e.target.files?.[0] || null)} style={{ fontSize: 13 }} />
          <button type="button" className="fm-btn fm-btn-sm" disabled={busy || !levelImage} onClick={uploadLevelImage}>🖼 Загрузить картинку</button>
        </div>
        <table className="fm-table" style={{ width: '100%' }}>
          <thead><tr><th>Уровень</th><th>Картинка</th><th>Монет</th><th>Грядок</th><th>Разблокировка</th><th></th></tr></thead>
          <tbody>
            {shownLevels.map((l) => (
              <tr key={l.level}>
                <td>{l.level}</td>
                <td>{l.image_url ? <img src={mediaUrl(l.image_url)} alt="" style={{ maxWidth: 60, maxHeight: 40, borderRadius: 4 }} /> : '—'}</td>
                <td>{l.coins_required}</td>
                <td>{l.plots_required}</td>
                <td>{l.unlock_type || '—'}</td>
                <td>
                  <button type="button" className="fm-btn fm-btn-sm" onClick={() => { setLevelForm({ level: l.level, coins_required: l.coins_required, plots_required: l.plots_required, unlock_type: l.unlock_type || '' }); }}>✎</button>
                  <button type="button" className="fm-btn fm-btn-sm" style={{ marginLeft: 4 }} onClick={() => deleteLevel(l.level)}>🗑</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {qActive && shownLevels.length === 0 && <div className="fm-card" style={{ color: 'var(--text-muted)', marginTop: 8 }}>{NO_MATCH}</div>}
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
      setPotionForm({ name: '', level: 'green', ingredient_slots: [], bonus_code: null, reward_coins: 100, description: '' });
      setPotionEditingId(null);
      setMsg('✓ Сохранено');
    } catch (e: any) { setMsg('✗ ' + (e?.response?.data?.detail || 'Ошибка')); }
    finally { setBusy(false); }
  }
  async function uploadPotionImage(id: number, file: File) {
    setBusy(true); setMsg(null);
    try {
      await api.adminUploadPotionImage(id, file);
      await loadPotionRecipes();
      setMsg('✓ Картинка зелья загружена');
    } catch (e: any) { setMsg('✗ ' + (e?.response?.data?.detail || 'Ошибка')); }
    finally { setBusy(false); }
  }
  async function uploadPotionCardImage(id: number, file: File) {
    setBusy(true); setMsg(null);
    try {
      await api.adminUploadPotionCardImage(id, file);
      await loadPotionRecipes();
      setMsg('✓ Карточка рецепта загружена');
    } catch (e: any) { setMsg('✗ ' + (e?.response?.data?.detail || 'Ошибка')); }
    finally { setBusy(false); }
  }

  async function deletePotionRecipe(id: number) {
    if (!(await confirmDialog('Удалить рецепт?'))) return;
    setBusy(true); setMsg(null);
    try { await api.adminDeletePotionRecipe(id); await loadPotionRecipes(); setMsg('✓ Удалено'); }
    catch (e: any) { setMsg('✗ ' + (e?.response?.data?.detail || 'Ошибка')); }
    finally { setBusy(false); }
  }

  // ── Коктейли ──
  async function loadCocktailRecipes() {
    try {
      const [cr, pr, pl, ing, rem, pat] = await Promise.all([
        api.adminCocktailRecipes(),
        api.adminProducts().catch(() => [] as Product[]),
        api.adminPlants().catch(() => [] as Plant[]),
        api.adminIngredients().catch(() => [] as Ingredient[]),
        api.adminRemedies().catch(() => [] as Remedy[]),
        api.adminPatients().catch(() => [] as Patient[]),
      ]);
      setCocktailRecipes(cr);
      setProducts(pr);
      setPlants(pl);
      setIngredients(ing);
      setRemedies(rem);
      setPatients(pat);
    } catch { /* ignore */ }
  }
  async function saveCocktailRecipe() {
    if (!cocktailForm.name.trim()) { setMsg('✗ Введите название'); return; }
    setBusy(true); setMsg(null);
    try {
      const data = {
        name: cocktailForm.name.trim(),
        description: cocktailForm.description || null,
        patient_id: cocktailForm.patient_id ? Number(cocktailForm.patient_id) : null,
        items: cocktailForm.items,
      };
      if (cocktailEditingId) await api.adminUpdateCocktailRecipe(cocktailEditingId, data);
      else await api.adminCreateCocktailRecipe(data);
      await loadCocktailRecipes();
      setCocktailForm({ name: '', description: '', patient_id: '', items: [] });
      setCocktailEditingId(null);
      setMsg('✓ Сохранено');
    } catch (e: any) { setMsg('✗ ' + (e?.response?.data?.detail || 'Ошибка')); }
    finally { setBusy(false); }
  }
  function addCocktailItem() {
    const itemId = Number(cocktailPickId);
    if (!itemId) { setMsg('✗ Выберите предмет'); return; }
    const qty = Number(cocktailPickQty);
    if (!qty || qty < 1) { setMsg('✗ Укажите количество'); return; }
    if (cocktailForm.items.some((i) => i.kind === cocktailPickKind && i.item_id === itemId)) {
      setMsg('✗ Этот предмет уже добавлен');
      return;
    }
    setCocktailForm({ ...cocktailForm, items: [...cocktailForm.items, { kind: cocktailPickKind, item_id: itemId, qty }] });
    setCocktailPickId('');
    setCocktailPickQty('1');
  }
  async function uploadCocktailImage(id: number, file: File) {
    setBusy(true); setMsg(null);
    try {
      await api.adminUploadCocktailImage(id, file);
      await loadCocktailRecipes();
      setMsg('✓ Картинка коктейля загружена');
    } catch (e: any) { setMsg('✗ ' + (e?.response?.data?.detail || 'Ошибка')); }
    finally { setBusy(false); }
  }
  async function uploadCocktailCardImage(id: number, file: File) {
    setBusy(true); setMsg(null);
    try {
      await api.adminUploadCocktailCardImage(id, file);
      await loadCocktailRecipes();
      setMsg('✓ Карточка коктейля загружена');
    } catch (e: any) { setMsg('✗ ' + (e?.response?.data?.detail || 'Ошибка')); }
    finally { setBusy(false); }
  }
  async function deleteCocktailRecipe(id: number) {
    if (!(await confirmDialog('Удалить рецепт коктейля?'))) return;
    setBusy(true); setMsg(null);
    try { await api.adminDeleteCocktailRecipe(id); await loadCocktailRecipes(); setMsg('✓ Удалено'); }
    catch (e: any) { setMsg('✗ ' + (e?.response?.data?.detail || 'Ошибка')); }
    finally { setBusy(false); }
  }

  function cocktailItemName(kind: string, id: number): string {
    if (kind === 'product') return products.find((p) => p.id === id)?.name ?? `#${id}`;
    if (kind === 'plant') return plants.find((p) => p.id === id)?.name ?? `#${id}`;
    if (kind === 'ingredient') return ingredients.find((i) => i.id === id)?.name ?? `#${id}`;
    if (kind === 'remedy') return remedies.find((r) => r.id === id)?.name ?? `#${id}`;
    return `#${id}`;
  }

  // ── Ингредиенты (аптека) ──
  async function loadIngredients() {
    try { setIngredients(await api.adminIngredients()); }
    catch { /* ignore */ }
  }
  async function saveIngredient() {
    if (!ingForm.name.trim()) { setMsg('✗ Введите название'); return; }
    setBusy(true); setMsg(null);
    try {
      const data = {
        name: ingForm.name.trim(),
        description: ingForm.description || null,
        sort_order: Number(ingForm.sort_order) || 0,
      };
      if (ingEditingId) { await api.adminUpdateIngredient(ingEditingId, data); }
      else { await api.adminCreateIngredient(data); }
      await loadIngredients();
      setIngForm({ name: '', description: '', sort_order: '0' });
      setIngEditingId(null);
      setMsg('✓ Сохранено');
    } catch (e: any) { setMsg('✗ ' + (e?.response?.data?.detail || 'Ошибка')); }
    finally { setBusy(false); }
  }
  async function uploadIngredientImage(id: number, file: File) {
    setBusy(true); setMsg(null);
    try {
      await api.adminUploadIngredientImage(id, file);
      await loadIngredients();
      setMsg('✓ Картинка загружена');
    } catch (e: any) { setMsg('✗ ' + (e?.response?.data?.detail || 'Ошибка')); }
    finally { setBusy(false); }
  }
  async function deleteIngredient(id: number) {
    if (!(await confirmDialog('Удалить ингредиент?'))) return;
    setBusy(true); setMsg(null);
    try { await api.adminDeleteIngredient(id); await loadIngredients(); setMsg('✓ Удалено'); }
    catch (e: any) { setMsg('✗ ' + (e?.response?.data?.detail || 'Ошибка')); }
    finally { setBusy(false); }
  }

  function renderIngredients() {
    return (
      <div>
        <h2>⚗️ Ингредиенты</h2>
        <div className="fm-card" style={{ marginBottom: 10 }}>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 8 }}>
            <input className="fm-input" placeholder="Название" value={ingForm.name} onChange={(e) => setIngForm({ ...ingForm, name: e.target.value })} />
            <input className="fm-input" type="number" placeholder="Порядок" value={ingForm.sort_order} onChange={(e) => setIngForm({ ...ingForm, sort_order: e.target.value })} style={{ width: 80 }} />
          </div>
          <div style={{ marginBottom: 8 }}>
            <label style={{ display: 'block', marginBottom: 4, fontSize: 13 }}>Описание</label>
            <textarea
              className="fm-input"
              value={ingForm.description}
              onChange={(e) => setIngForm({ ...ingForm, description: e.target.value })}
              rows={2}
              style={{ width: '100%' }}
            />
          </div>
          {ingEditingId && (
            <label className="fm-btn fm-btn-sm fm-btn-outline" style={{ cursor: 'pointer', marginBottom: 8, display: 'inline-flex', alignItems: 'center', gap: 6 }}>
              🖼 Картинка
              <input type="file" accept="image/*" style={{ display: 'none' }}
                onChange={(e) => { const f = e.target.files?.[0]; if (f) uploadIngredientImage(ingEditingId, f); }}
              />
            </label>
          )}
          <button type="button" className="fm-btn" disabled={busy} onClick={saveIngredient}>
            {ingEditingId ? '✎ Сохранить' : '➕ Создать'}
          </button>
          {ingEditingId && <button type="button" className="fm-btn" style={{ marginLeft: 6 }} onClick={() => { setIngEditingId(null); setIngForm({ name: '', description: '', sort_order: '0' }); }}>Отмена</button>}
        </div>
        <table className="fm-table" style={{ width: '100%' }}>
          <thead><tr><th>ID</th><th>Картинка</th><th>Название</th><th>Код</th><th>Описание</th><th>Порядок</th><th></th></tr></thead>
          <tbody>
            {shownIngredients.map((ing) => (
              <tr key={ing.id}>
                <td>{ing.id}</td>
                <td>
                  {ing.image_url
                    ? <img src={mediaUrl(ing.image_url)} alt="" style={{ width: 34, height: 34, objectFit: 'cover', borderRadius: 6 }} />
                    : <span style={{ fontSize: 22 }}>⚗️</span>}
                </td>
                <td><strong>{ing.name}</strong></td>
                <td style={{ color: 'var(--text-muted)', fontSize: 12 }}>{ing.code}</td>
                <td style={{ color: 'var(--text-muted)', fontSize: 13 }}>{ing.description || '—'}</td>
                <td>{ing.sort_order}</td>
                <td style={{ whiteSpace: 'nowrap' }}>
                  <button type="button" className="fm-btn fm-btn-xs" onClick={() => { setIngEditingId(ing.id); setIngForm({ name: ing.name, description: ing.description || '', sort_order: String(ing.sort_order) }); }}>✎</button>{' '}
                  <button type="button" className="fm-btn fm-btn-xs fm-btn-danger" onClick={() => deleteIngredient(ing.id)}>✕</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {qActive && shownIngredients.length === 0 && <div className="fm-card" style={{ color: 'var(--text-muted)', marginTop: 8 }}>{NO_MATCH}</div>}
      </div>
    );
  }

  // ── Лечебница: мази, болезни, пациенты ──
  async function saveDisease() {
    if (!diseaseForm.name.trim()) { setMsg('✗ Введите название'); return; }
    setBusy(true); setMsg(null);
    try {
      const data = { name: diseaseForm.name.trim(), description: diseaseForm.description || null, remedy_id: diseaseForm.remedyId ? Number(diseaseForm.remedyId) : null, symptoms: diseaseForm.symptoms };
      if (diseaseEditingId) await api.adminUpdateDisease(diseaseEditingId, data);
      else await api.adminCreateDisease(data);
      await loadInfirmary();
      setDiseaseForm({ name: '', description: '', remedyId: '', symptoms: [] });
      setDiseaseEditingId(null);
      setMsg('✓ Сохранено');
    } catch (e: any) { setMsg('✗ ' + (e?.response?.data?.detail || 'Ошибка')); }
    finally { setBusy(false); }
  }
  function addDiseaseSymptom() {
    if (!diseaseSymPart || !diseaseSymText.trim()) { setMsg('✗ Выберите часть тела и впишите симптом'); return; }
    if (diseaseForm.symptoms.some((s) => s.part_code === diseaseSymPart)) { setMsg('✗ Эта часть тела уже добавлена'); return; }
    setDiseaseForm({ ...diseaseForm, symptoms: [...diseaseForm.symptoms, { part_code: diseaseSymPart, text: diseaseSymText.trim() }] });
    setDiseaseSymPart('');
    setDiseaseSymText('');
  }
  async function loadInfirmary() {
    try {
      const [r, d, p, at, ing, bg] = await Promise.all([
        api.adminRemedies(), api.adminDiseases(), api.adminPatients(),
        api.adminAnimalTypes().catch(() => [] as ClinicAnimalType[]),
        api.ingredients().catch(() => [] as Ingredient[]),
        api.getInfirmaryBackground().catch(() => ({ url: '' })),
      ]);
      setRemedies(r); setDiseases(d); setPatients(p); setAnimalTypes(at); setIngredients(ing);
      setInfirmaryBg(bg.url || '');
    } catch { /* ignore */ }
  }
  async function saveRemedy() {
    if (!remedyForm.name.trim()) { setMsg('✗ Введите название'); return; }
    if (remedyForm.items.length === 0) { setMsg('✗ Добавьте хотя бы один ингредиент'); return; }
    setBusy(true); setMsg(null);
    try {
      const data = { name: remedyForm.name.trim(), description: remedyForm.description || null, recipe_items: remedyForm.items };
      if (remedyEditingId) await api.adminUpdateRemedy(remedyEditingId, data);
      else await api.adminCreateRemedy(data);
      await loadInfirmary();
      setRemedyForm({ name: '', description: '', items: [] });
      setRemedyEditingId(null);
      setMsg('✓ Сохранено');
    } catch (e: any) { setMsg('✗ ' + (e?.response?.data?.detail || 'Ошибка')); }
    finally { setBusy(false); }
  }
  function addRemedyItem() {
    if (remedyPickId === '') { setMsg('✗ Выберите источник'); return; }
    const qty = Number(remedyPickQty);
    if (!qty || qty < 1) { setMsg('✗ Укажите количество'); return; }
    const item = remedyPickKind === 'ingredient'
      ? { ingredient_id: Number(remedyPickId), plant_id: null, qty }
      : { ingredient_id: null, plant_id: Number(remedyPickId), qty };
    if (remedyForm.items.some((i) => i.ingredient_id === item.ingredient_id && i.plant_id === item.plant_id)) {
      setMsg('✗ Этот источник уже добавлен');
      return;
    }
    setRemedyForm({ ...remedyForm, items: [...remedyForm.items, item] });
    setRemedyPickId('');
    setRemedyPickQty('1');
  }
  async function deleteRemedy(id: number) {
    if (!(await confirmDialog('Удалить мазь?'))) return;
    setBusy(true); setMsg(null);
    try { await api.adminDeleteRemedy(id); await loadInfirmary(); setMsg('✓ Удалено'); }
    catch (e: any) { setMsg('✗ ' + (e?.response?.data?.detail || 'Ошибка')); }
    finally { setBusy(false); }
  }
  async function uploadDiseaseImage(id: number, file: File) {
    setBusy(true); setMsg(null);
    try {
      await api.adminUploadDiseaseImage(id, file);
      await loadInfirmary();
      setMsg('✓ Изображение болезни загружено');
    } catch (e: any) { setMsg('✗ ' + (e?.response?.data?.detail || 'Ошибка')); }
    finally { setBusy(false); }
  }
  async function deleteDisease(id: number) {
    if (!(await confirmDialog('Удалить болезнь?'))) return;
    setBusy(true); setMsg(null);
    try { await api.adminDeleteDisease(id); await loadInfirmary(); setMsg('✓ Удалено'); }
    catch (e: any) { setMsg('✗ ' + (e?.response?.data?.detail || 'Ошибка')); }
    finally { setBusy(false); }
  }
  async function savePatient() {
    if (!patientForm.name.trim()) { setMsg('✗ Введите название'); return; }
    setBusy(true); setMsg(null);
    try {
      const data = { name: patientForm.name.trim(), level: Number(patientForm.level) || 1, disease_id: patientForm.diseaseId ? Number(patientForm.diseaseId) : null, animal_type_id: patientForm.animalTypeId ? Number(patientForm.animalTypeId) : null };
      if (patientEditingId) await api.adminUpdatePatient(patientEditingId, data);
      else await api.adminCreatePatient(data);
      await loadInfirmary();
      setPatientForm({ name: '', level: '1', diseaseId: '', animalTypeId: '' });
      setPatientEditingId(null);
      setMsg('✓ Сохранено (созданы 3 сцены: больное / на лечении / здоровое)');
    } catch (e: any) { setMsg('✗ ' + (e?.response?.data?.detail || 'Ошибка')); }
    finally { setBusy(false); }
  }
  async function deletePatient(id: number) {
    if (!(await confirmDialog('Удалить пациента и его сцены?'))) return;
    setBusy(true); setMsg(null);
    try { await api.adminDeletePatient(id); await loadInfirmary(); setMsg('✓ Удалено'); }
    catch (e: any) { setMsg('✗ ' + (e?.response?.data?.detail || 'Ошибка')); }
    finally { setBusy(false); }
  }
  async function saveAnimalType() {
    if (!animalTypeForm.name.trim()) { setMsg('✗ Введите название'); return; }
    setBusy(true); setMsg(null);
    try {
      const data = { name: animalTypeForm.name.trim(), emoji: animalTypeForm.emoji || null };
      if (animalTypeEditingId) await api.adminUpdateAnimalType(animalTypeEditingId, data);
      else await api.adminCreateAnimalType(data);
      await loadInfirmary();
      setAnimalTypeForm({ name: '', emoji: '' });
      setAnimalTypeEditingId(null);
      setMsg('✓ Тип сохранён');
    } catch (e: any) { setMsg('✗ ' + (e?.response?.data?.detail || 'Ошибка')); }
    finally { setBusy(false); }
  }
  async function deleteAnimalType(id: number) {
    if (!(await confirmDialog('Удалить тип животного?'))) return;
    setBusy(true); setMsg(null);
    try { await api.adminDeleteAnimalType(id); await loadInfirmary(); setMsg('✓ Удалено'); }
    catch (e: any) { setMsg('✗ ' + (e?.response?.data?.detail || 'Ошибка')); }
    finally { setBusy(false); }
  }
  async function uploadPatientCardImage(id: number, file: File) {
    setBusy(true); setMsg(null);
    try {
      await api.adminUploadPatientCardImage(id, file);
      await loadInfirmary();
      setMsg('✓ Картинка загружена');
    } catch (e: any) { setMsg('✗ ' + (e?.response?.data?.detail || 'Ошибка')); }
    finally { setBusy(false); }
  }
  async function uploadPatientAnimalImage(id: number, file: File) {
    setBusy(true); setMsg(null);
    try {
      await api.adminUploadPatientAnimalImage(id, file);
      await loadInfirmary();
      setMsg('✓ Изображение животного загружено');
    } catch (e: any) { setMsg('✗ ' + (e?.response?.data?.detail || 'Ошибка')); }
    finally { setBusy(false); }
  }
  async function uploadSceneImage(fieldId: number, file: File) {
    setBusy(true); setMsg(null);
    try {
      await api.adminUploadFieldMap(fieldId, file);
      await loadInfirmary();
      setMsg('✓ Картинка сцены загружена');
    } catch (e: any) { setMsg('✗ ' + (e?.response?.data?.detail || 'Ошибка')); }
    finally { setBusy(false); }
  }
  async function uploadInfirmaryBg(file: File) {
    setBusy(true); setMsg(null);
    try {
      const res = await api.adminUploadInfirmaryBackground(file);
      setInfirmaryBg(res.url);
      setMsg('✓ Фон лечебницы загружен');
    } catch (e: any) { setMsg('✗ ' + (e?.response?.data?.detail || 'Ошибка')); }
    finally { setBusy(false); }
  }

  function renderInfirmary() {
    return (
      <div>
        <h2>🌲 Лечебница</h2>
        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginBottom: 12 }}>
          <TabBtn active={infirmaryTab === 'remedies'} onClick={() => setInfirmaryTab('remedies')}>🧴 Мази</TabBtn>
          <TabBtn active={infirmaryTab === 'diseases'} onClick={() => setInfirmaryTab('diseases')}>🦠 Болезни</TabBtn>
          <TabBtn active={infirmaryTab === 'types'} onClick={() => setInfirmaryTab('types')}>🐾 Типы животных</TabBtn>
          <TabBtn active={infirmaryTab === 'locations'} onClick={() => setInfirmaryTab('locations')}>🌲 Локации Лечебницы</TabBtn>
        </div>

        {infirmaryTab === 'remedies' && (<>
        <div className="fm-card" style={{ marginBottom: 10 }}>
          <h3 style={{ marginTop: 0 }}>Мази (состав)</h3>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 8 }}>
            <input className="fm-input" placeholder="Название" value={remedyForm.name} onChange={(e) => setRemedyForm({ ...remedyForm, name: e.target.value })} />
          </div>
          <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', alignItems: 'center', marginBottom: 8 }}>
            <select className="fm-input" value={remedyPickKind} onChange={(e) => { setRemedyPickKind(e.target.value as 'ingredient' | 'plant'); setRemedyPickId(''); }} style={{ width: 150 }}>
              <option value="ingredient">⚗️ Аптекарский</option>
              <option value="plant">🌱 Растение</option>
            </select>
            <select className="fm-input" value={remedyPickId} onChange={(e) => setRemedyPickId(e.target.value ? Number(e.target.value) : '')} style={{ minWidth: 160 }}>
              <option value="">— выберите —</option>
              {remedyPickKind === 'ingredient'
                ? ingredients.map((i) => <option key={i.id} value={i.id}>{i.name}</option>)
                : plants.map((p) => <option key={p.id} value={p.id}>{p.emoji || '🌱'} {p.name}</option>)}
            </select>
            <input className="fm-input" type="number" min={1} value={remedyPickQty} onChange={(e) => setRemedyPickQty(e.target.value)} style={{ width: 70 }} />
            <button type="button" className="fm-btn fm-btn-sm" onClick={addRemedyItem}>+</button>
          </div>
          {remedyForm.items.length > 0 && (
            <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap', marginBottom: 8 }}>
              {remedyForm.items.map((it, idx) => {
                const label = it.ingredient_id != null
                  ? ingredients.find((x) => x.id === it.ingredient_id)?.name || `#${it.ingredient_id}`
                  : plants.find((x) => x.id === it.plant_id)?.name || `#${it.plant_id}`;
                return (
                  <span key={idx} className="fm-card" style={{ padding: '2px 8px', fontSize: 13, cursor: 'pointer' }} onClick={() => setRemedyForm({ ...remedyForm, items: remedyForm.items.filter((_, j) => j !== idx) })}>
                    {label} ×{it.qty} ✕
                  </span>
                );
              })}
            </div>
          )}
          <button type="button" className="fm-btn" disabled={busy} onClick={saveRemedy}>{remedyEditingId ? '✎ Сохранить' : '➕ Создать'}</button>
          {remedyEditingId && <button type="button" className="fm-btn" style={{ marginLeft: 6 }} onClick={() => { setRemedyEditingId(null); setRemedyForm({ name: '', description: '', items: [] }); }}>Отмена</button>}
        </div>
        <table className="fm-table" style={{ width: '100%', marginBottom: 16 }}>
          <thead><tr><th>ID</th><th>Название</th><th>Состав</th><th></th></tr></thead>
          <tbody>
            {remedies.map((r) => (
              <tr key={r.id}>
                <td>{r.id}</td>
                <td><strong>{r.name}</strong></td>
                <td style={{ fontSize: 12, color: 'var(--text-muted)' }}>{r.recipe_items.map((i) => `${i.ingredient_name || i.plant_name || i.ingredient_id} ×${i.qty}`).join(', ') || '—'}</td>
                <td style={{ whiteSpace: 'nowrap' }}>
                  <button type="button" className="fm-btn fm-btn-xs" onClick={() => { setRemedyEditingId(r.id); setRemedyForm({ name: r.name, description: r.description || '', items: r.recipe_items.map((i) => ({ ingredient_id: i.ingredient_id, plant_id: i.plant_id, qty: i.qty })) }); }}>✎</button>{' '}
                  <button type="button" className="fm-btn fm-btn-xs fm-btn-danger" onClick={() => deleteRemedy(r.id)}>✕</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        </>)}

        {infirmaryTab === 'diseases' && (<>
        <div className="fm-card" style={{ marginBottom: 10 }}>
          <h3 style={{ marginTop: 0 }}>Болезни (симптомы)</h3>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 8 }}>
            <input className="fm-input" placeholder="Название" value={diseaseForm.name} onChange={(e) => setDiseaseForm({ ...diseaseForm, name: e.target.value })} />
            <select className="fm-input" value={diseaseForm.remedyId} onChange={(e) => setDiseaseForm({ ...diseaseForm, remedyId: e.target.value })}>
              <option value="">— мазь —</option>
              {remedies.map((r) => <option key={r.id} value={r.id}>{r.name}</option>)}
            </select>
          </div>
          <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', alignItems: 'center', marginBottom: 8 }}>
            <select className="fm-input" value={diseaseSymPart} onChange={(e) => setDiseaseSymPart(e.target.value)} style={{ width: 140 }}>
              <option value="">— часть тела —</option>
              {BODY_PARTS.map((p) => <option key={p.code} value={p.code}>{p.label}</option>)}
            </select>
            <input className="fm-input" placeholder="Симптом (например: горячий нос)" value={diseaseSymText} onChange={(e) => setDiseaseSymText(e.target.value)} style={{ flex: 1, minWidth: 160 }} />
            <button type="button" className="fm-btn fm-btn-sm" onClick={addDiseaseSymptom}>+</button>
          </div>
          {diseaseForm.symptoms.length > 0 && (
            <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap', marginBottom: 8 }}>
              {diseaseForm.symptoms.map((s, idx) => (
                <span key={idx} className="fm-card" style={{ padding: '2px 8px', fontSize: 13, cursor: 'pointer' }} onClick={() => setDiseaseForm({ ...diseaseForm, symptoms: diseaseForm.symptoms.filter((_, j) => j !== idx) })}>
                  {BODY_PART_LABELS[s.part_code] || s.part_code}: {s.text} ✕
                </span>
              ))}
            </div>
          )}
          <button type="button" className="fm-btn" disabled={busy} onClick={saveDisease}>{diseaseEditingId ? '✎ Сохранить' : '➕ Создать'}</button>
          {diseaseEditingId && <button type="button" className="fm-btn" style={{ marginLeft: 6 }} onClick={() => { setDiseaseEditingId(null); setDiseaseForm({ name: '', description: '', remedyId: '', symptoms: [] }); }}>Отмена</button>}
        </div>
        <table className="fm-table" style={{ width: '100%', marginBottom: 16 }}>
          <thead><tr><th>ID</th><th>Название</th><th>Мазь</th><th>Симптомы</th><th>Изображение</th><th></th></tr></thead>
          <tbody>
            {diseases.map((d) => (
              <tr key={d.id}>
                <td>{d.id}</td>
                <td><strong>{d.name}</strong></td>
                <td style={{ fontSize: 12 }}>{d.remedy_name || '—'}</td>
                <td style={{ fontSize: 12, color: 'var(--text-muted)' }}>{d.symptoms.map((s) => `${BODY_PART_LABELS[s.part_code] || s.part_code}: ${s.text}`).join('; ') || '—'}</td>
                <td style={{ whiteSpace: 'nowrap' }}>
                  <span title="Изображение болезни">{d.image_url ? '🖼️✓' : '🖼️✗'}</span>{' '}
                  <label className="fm-btn fm-btn-xs fm-btn-outline" title="Загрузить изображение болезни" style={{ cursor: 'pointer' }}>⬆<input type="file" accept="image/*" style={{ display: 'none' }} onChange={(e) => { const f = e.target.files?.[0]; if (f) uploadDiseaseImage(d.id, f); }} /></label>
                </td>
                <td style={{ whiteSpace: 'nowrap' }}>
                  <button type="button" className="fm-btn fm-btn-xs" onClick={() => { setDiseaseEditingId(d.id); setDiseaseForm({ name: d.name, description: d.description || '', remedyId: d.remedy_id ? String(d.remedy_id) : '', symptoms: d.symptoms.map((s) => ({ part_code: s.part_code, text: s.text })) }); }}>✎</button>{' '}
                  <button type="button" className="fm-btn fm-btn-xs fm-btn-danger" onClick={() => deleteDisease(d.id)}>✕</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        </>)}

        {infirmaryTab === 'types' && (<>
        <div className="fm-card" style={{ marginBottom: 10 }}>
          <h3 style={{ marginTop: 0 }}>🐾 Типы животных лечебницы</h3>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 8 }}>
            <input className="fm-input" placeholder="Название (например, Лис)" value={animalTypeForm.name} onChange={(e) => setAnimalTypeForm({ ...animalTypeForm, name: e.target.value })} />
            <input className="fm-input" placeholder="Эмодзи" value={animalTypeForm.emoji} onChange={(e) => setAnimalTypeForm({ ...animalTypeForm, emoji: e.target.value })} style={{ width: 80 }} />
          </div>
          <button type="button" className="fm-btn" disabled={busy} onClick={saveAnimalType}>{animalTypeEditingId ? '✎ Сохранить' : '➕ Создать'}</button>
          {animalTypeEditingId && <button type="button" className="fm-btn" style={{ marginLeft: 6 }} onClick={() => { setAnimalTypeEditingId(null); setAnimalTypeForm({ name: '', emoji: '' }); }}>Отмена</button>}
          <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginTop: 10 }}>
            {animalTypes.map((t) => (
              <span key={t.id} className="fm-card" style={{ padding: '4px 10px', fontSize: 13 }}>
                {t.emoji || '🐾'} {t.name}{' '}
                <button type="button" className="fm-btn fm-btn-xs" style={{ marginLeft: 6 }} onClick={() => { setAnimalTypeEditingId(t.id); setAnimalTypeForm({ name: t.name, emoji: t.emoji || '' }); }}>✎</button>
                <button type="button" className="fm-btn fm-btn-xs fm-btn-danger" onClick={() => deleteAnimalType(t.id)}>✕</button>
              </span>
            ))}
            {animalTypes.length === 0 && <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>Типов пока нет.</span>}
          </div>
        </div>
        </>)}

        {infirmaryTab === 'locations' && (<>
        <div className="fm-card" style={{ marginBottom: 10 }}>
          <h3 style={{ marginTop: 0 }}>🖼️ Фон лечебницы</h3>
          <p style={{ fontSize: 12, color: 'var(--text-muted)', margin: '0 0 8px' }}>
            Изображение будет задним фоном для лечебницы и её подстраниц: сцен, лаборатории снадобий, поляны и лавки.
          </p>
          {infirmaryBg && (
            <img src={infirmaryBg} alt="Фон лечебницы" style={{ maxWidth: 200, maxHeight: 120, objectFit: 'cover', borderRadius: 8, marginBottom: 8, display: 'block' }} />
          )}
          <label className="fm-btn" style={{ cursor: 'pointer', display: 'inline-block' }}>⬆ Загрузить фон<input type="file" accept="image/*" style={{ display: 'none' }} onChange={(e) => { const f = e.target.files?.[0]; if (f) uploadInfirmaryBg(f); }} /></label>
        </div>

        <div className="fm-card" style={{ marginBottom: 10 }}>
          <h3 style={{ marginTop: 0 }}>🌲 Локации Лечебницы</h3>
          <p style={{ fontSize: 12, color: 'var(--text-muted)', margin: '0 0 8px' }}>
            При создании животного автоматически появятся три локации-сцены: больное, на лечении, здоровое. Для каждой сцены загрузите картинку и откройте редактор, чтобы разместить части тела и книгу.
          </p>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 8 }}>
            <input className="fm-input" placeholder="Название" value={patientForm.name} onChange={(e) => setPatientForm({ ...patientForm, name: e.target.value })} />
            <select className="fm-input" value={patientForm.animalTypeId} onChange={(e) => setPatientForm({ ...patientForm, animalTypeId: e.target.value })}>
              <option value="">— тип животного —</option>
              {animalTypes.map((t) => <option key={t.id} value={t.id}>{t.emoji || '🐾'} {t.name}</option>)}
            </select>
            <select className="fm-input" value={patientForm.level} onChange={(e) => setPatientForm({ ...patientForm, level: e.target.value })}>
              <option value="1">Уровень 1</option>
              <option value="2">Уровень 2</option>
              <option value="3">Уровень 3</option>
            </select>
            <select className="fm-input" value={patientForm.diseaseId} onChange={(e) => setPatientForm({ ...patientForm, diseaseId: e.target.value })}>
              <option value="">— болезнь —</option>
              {diseases.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
            </select>
          </div>
          <button type="button" className="fm-btn" disabled={busy} onClick={savePatient}>{patientEditingId ? '✎ Сохранить' : '➕ Создать животное'}</button>
          {patientEditingId && <button type="button" className="fm-btn" style={{ marginLeft: 6 }} onClick={() => { setPatientEditingId(null); setPatientForm({ name: '', level: '1', diseaseId: '', animalTypeId: '' }); }}>Отмена</button>}
        </div>
        <table className="fm-table" style={{ width: '100%' }}>
          <thead><tr><th>ID</th><th>Название</th><th>Тип</th><th>Ур.</th><th>Болезнь</th><th>Сцены</th><th>Изображения</th><th></th></tr></thead>
          <tbody>
            {patients.map((p) => (
              <tr key={p.id}>
                <td>{p.id}</td>
                <td><strong>{p.name}</strong></td>
                <td style={{ fontSize: 12 }}>{p.animal_type_emoji || ''} {p.animal_type_name || '—'}</td>
                <td>{p.level}</td>
                <td style={{ fontSize: 12 }}>{p.disease_name || '—'}</td>
                <td>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                    {p.scenes.map((sc) => (
                      <div key={sc.field_id} style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: 12 }}>
                        <span>{sc.stage === 'sick' ? '🤒' : sc.stage === 'treating' ? '🏥' : '✅'}</span>
                        <span style={{ minWidth: 90 }}>{sc.stage === 'sick' ? 'Больное' : sc.stage === 'treating' ? 'На лечении' : 'Здоровое'}</span>
                        <span style={{ fontSize: 12 }} title="Изображение сцены">{sc.map_url ? '🖼️✓' : '🖼️✗'}</span>
                        <label className="fm-btn fm-btn-xs fm-btn-outline" title="Картинка сцены" style={{ cursor: 'pointer', marginRight: 2 }}>⬆<input type="file" accept="image/*" style={{ display: 'none' }} onChange={(e) => { const f = e.target.files?.[0]; if (f) uploadSceneImage(sc.field_id, f); }} /></label>
                        <button type="button" className="fm-btn fm-btn-xs" onClick={() => { setEditorFieldId(sc.field_id); }}>✎ Разметить</button>
                      </div>
                    ))}
                  </div>
                </td>
                <td style={{ whiteSpace: 'nowrap' }}>
                  <span title="Изображение животного">{p.animal_image_url ? '🐾✓' : '🐾✗'}</span>{' '}
                  <label className="fm-btn fm-btn-xs fm-btn-outline" title="Изображение животного" style={{ cursor: 'pointer', marginRight: 2 }}>⬆<input type="file" accept="image/*" style={{ display: 'none' }} onChange={(e) => { const f = e.target.files?.[0]; if (f) uploadPatientAnimalImage(p.id, f); }} /></label>
                  <label className="fm-btn fm-btn-xs fm-btn-outline" title="Карточка коллекции" style={{ cursor: 'pointer' }}>🃏<input type="file" accept="image/*" style={{ display: 'none' }} onChange={(e) => { const f = e.target.files?.[0]; if (f) uploadPatientCardImage(p.id, f); }} /></label>
                </td>
                <td style={{ whiteSpace: 'nowrap' }}>
                  <button type="button" className="fm-btn fm-btn-xs" onClick={() => { setPatientEditingId(p.id); setPatientForm({ name: p.name, level: String(p.level), diseaseId: p.disease_id ? String(p.disease_id) : '', animalTypeId: p.animal_type_id ? String(p.animal_type_id) : '' }); }}>✎</button>{' '}
                  <button type="button" className="fm-btn fm-btn-xs fm-btn-danger" onClick={() => deletePatient(p.id)}>✕</button>
                </td>
              </tr>
            ))}
            {patients.length === 0 && (
              <tr><td colSpan={8} style={{ color: 'var(--text-muted)' }}>Животных лечебницы пока нет.</td></tr>
            )}
          </tbody>
        </table>
        </>)}
      </div>
    );
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
            <select className="fm-input" value={potionSlotInput} onChange={(e) => setPotionSlotInput(e.target.value)}>
              <option value="">— тип ингредиента —</option>
              <option value="plant_garden">🌱 Растение (грядка)</option>
              <option value="plant_orchard">🍎 Растение (сад)</option>
              <option value="animal_product">🐄 Продукция животного</option>
              <option value="workshop">🔨 Товар мастерской</option>
              <option value="sewing">🧵 Товар портнихи</option>
              <option value="alchemy">🔮 Товар зельеварения</option>
              <option value="barnyard">🏚️ Товар скотного двора</option>
            </select>
            <button type="button" className="fm-btn fm-btn-sm" onClick={() => { if (potionSlotInput.trim()) { setPotionForm({ ...potionForm, ingredient_slots: [...potionForm.ingredient_slots, potionSlotInput.trim()] }); setPotionSlotInput(''); } }}>+</button>
          </div>
          <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap', marginBottom: 8 }}>
            {potionForm.ingredient_slots.map((s, i) => (
              <span key={i} className="fm-card" style={{ padding: '2px 8px', fontSize: 13, cursor: 'pointer' }} onClick={() => setPotionForm({ ...potionForm, ingredient_slots: potionForm.ingredient_slots.filter((_, j) => j !== i) })}>
                {potionIngredientLabel(s)} ✕
              </span>
            ))}
          </div>
          <div style={{ marginBottom: 8 }}>
            <label style={{ display: 'block', marginBottom: 4, fontSize: 13 }}>Описание действия зелья</label>
            <textarea
              className="fm-input"
              value={potionForm.description || ''}
              onChange={(e) => setPotionForm({ ...potionForm, description: e.target.value })}
              placeholder="Например: удваивает урожай с одной грядки"
              rows={2}
              style={{ width: '100%' }}
            />
          </div>
          {potionEditingId && (
            <>
              <label className="fm-btn fm-btn-sm fm-btn-outline" style={{ cursor: 'pointer', marginBottom: 8, display: 'inline-flex', alignItems: 'center', gap: 6 }}>
                🖼 Картинка зелья
                <input type="file" accept="image/*" style={{ display: 'none' }}
                  onChange={(e) => { const f = e.target.files?.[0]; if (f) uploadPotionImage(potionEditingId, f); }}
                />
              </label>
              <label className="fm-btn fm-btn-sm fm-btn-outline" style={{ cursor: 'pointer', marginBottom: 8, marginLeft: 6, display: 'inline-flex', alignItems: 'center', gap: 6 }}>
                🃏 Карточка рецепта
                <input type="file" accept="image/*" style={{ display: 'none' }}
                  onChange={(e) => { const f = e.target.files?.[0]; if (f) uploadPotionCardImage(potionEditingId, f); }}
                />
              </label>
            </>
          )}
          <button type="button" className="fm-btn" disabled={busy} onClick={savePotionRecipe}>
            {potionEditingId ? '✎ Сохранить' : '➕ Создать'}
          </button>
          {potionEditingId && <button type="button" className="fm-btn" style={{ marginLeft: 6 }} onClick={() => { setPotionEditingId(null); setPotionForm({ name: '', level: 'green', ingredient_slots: [], bonus_code: null, reward_coins: 100, description: '' }); }}>Отмена</button>}
        </div>
        <table className="fm-table" style={{ width: '100%' }}>
          <thead><tr><th>ID</th><th>Название</th><th>Уровень</th><th>Слотов</th><th>Бонус</th><th>Описание</th><th></th></tr></thead>
          <tbody>
            {shownPotionRecipes.map((r) => (
              <tr key={r.id}>
                <td>{r.id}</td>
                <td>
                  {r.image_url && <img src={mediaUrl(r.image_url)} alt="" style={{ width: 28, height: 28, objectFit: 'cover', borderRadius: 4, marginRight: 4, verticalAlign: 'middle' }} />}
                  {r.card_image_url && <img src={mediaUrl(r.card_image_url)} alt="" style={{ width: 28, height: 28, objectFit: 'cover', borderRadius: 4, marginRight: 4, verticalAlign: 'middle', border: '1px solid var(--border)' }} />}
                  {r.name}
                </td>
                <td>{r.level}</td>
                <td>{r.ingredient_slots.map(potionIngredientLabel).join(', ')}</td>
                <td>{potionBonusLabel(r.bonus_code) || '—'}</td>
                <td style={{ maxWidth: 220 }}>{r.description || '—'}</td>
                <td>
                  <button type="button" className="fm-btn fm-btn-sm" onClick={() => { setPotionEditingId(r.id); setPotionForm({ name: r.name, level: r.level, ingredient_slots: r.ingredient_slots, bonus_code: r.bonus_code, reward_coins: r.reward_coins, description: r.description || '' }); }}>✎</button>
                  <button type="button" className="fm-btn fm-btn-sm" style={{ marginLeft: 4 }} onClick={() => deletePotionRecipe(r.id)}>🗑</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {qActive && shownPotionRecipes.length === 0 && <div className="fm-card" style={{ color: 'var(--text-muted)', marginTop: 8 }}>{NO_MATCH}</div>}
      </div>
    );
  }

  function renderCocktailRecipes() {
    const pickOptions = cocktailPickKind === 'product' ? products
      : cocktailPickKind === 'plant' ? plants
      : cocktailPickKind === 'ingredient' ? ingredients
      : remedies;
    return (
      <div>
        <h2>🍸 Рецепты коктейлей</h2>
        <div className="fm-card" style={{ marginBottom: 10 }}>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 8 }}>
            <input className="fm-input" placeholder="Название" value={cocktailForm.name} onChange={(e) => setCocktailForm({ ...cocktailForm, name: e.target.value })} />
            <select className="fm-input" value={cocktailForm.patient_id} onChange={(e) => setCocktailForm({ ...cocktailForm, patient_id: e.target.value })}>
              <option value="">Открыт сразу (без животного)</option>
              {patients.map((p) => (
                <option key={p.id} value={p.id}>🔓 Животное: {p.name}</option>
              ))}
            </select>
          </div>
          <div style={{ marginBottom: 8 }}>
            <label style={{ display: 'block', marginBottom: 4, fontSize: 13 }}>Ингредиенты коктейля (точные предметы)</label>
            <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginBottom: 6 }}>
              <select className="fm-input" value={cocktailPickKind} onChange={(e) => { setCocktailPickKind(e.target.value as any); setCocktailPickId(''); }}>
                <option value="product">📦 Товар</option>
                <option value="plant">🌱 Растение</option>
                <option value="ingredient">🌾 Ингредиент</option>
                <option value="remedy">⚗️ Лекарство</option>
              </select>
              <select className="fm-input" value={cocktailPickId} onChange={(e) => setCocktailPickId(e.target.value)}>
                <option value="">— предмет —</option>
                {pickOptions.map((o: any) => (
                  <option key={o.id} value={o.id}>{o.name}</option>
                ))}
              </select>
              <input className="fm-input" type="number" min={1} value={cocktailPickQty} onChange={(e) => setCocktailPickQty(e.target.value)} style={{ width: 70 }} />
              <button type="button" className="fm-btn fm-btn-sm" onClick={addCocktailItem}>+</button>
            </div>
            <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
              {cocktailForm.items.map((it, i) => (
                <span key={i} className="fm-card" style={{ padding: '2px 8px', fontSize: 13, cursor: 'pointer' }} onClick={() => setCocktailForm({ ...cocktailForm, items: cocktailForm.items.filter((_, j) => j !== i) })}>
                  {cocktailItemName(it.kind, it.item_id)} ×{it.qty} ✕
                </span>
              ))}
            </div>
          </div>
          <div style={{ marginBottom: 8 }}>
            <label style={{ display: 'block', marginBottom: 4, fontSize: 13 }}>Описание коктейля</label>
            <textarea
              className="fm-input"
              value={cocktailForm.description}
              onChange={(e) => setCocktailForm({ ...cocktailForm, description: e.target.value })}
              placeholder="Например: освежающий лесной коктейль"
              rows={2}
              style={{ width: '100%' }}
            />
          </div>
          {cocktailEditingId && (
            <>
              <label className="fm-btn fm-btn-sm fm-btn-outline" style={{ cursor: 'pointer', marginBottom: 8, display: 'inline-flex', alignItems: 'center', gap: 6 }}>
                🖼 Картинка коктейля
                <input type="file" accept="image/*" style={{ display: 'none' }}
                  onChange={(e) => { const f = e.target.files?.[0]; if (f) uploadCocktailImage(cocktailEditingId, f); }}
                />
              </label>
              <label className="fm-btn fm-btn-sm fm-btn-outline" style={{ cursor: 'pointer', marginBottom: 8, marginLeft: 6, display: 'inline-flex', alignItems: 'center', gap: 6 }}>
                🃏 Карточка рецепта
                <input type="file" accept="image/*" style={{ display: 'none' }}
                  onChange={(e) => { const f = e.target.files?.[0]; if (f) uploadCocktailCardImage(cocktailEditingId, f); }}
                />
              </label>
            </>
          )}
          <button type="button" className="fm-btn" disabled={busy} onClick={saveCocktailRecipe}>
            {cocktailEditingId ? '✎ Сохранить' : '➕ Создать'}
          </button>
          {cocktailEditingId && <button type="button" className="fm-btn" style={{ marginLeft: 6 }} onClick={() => { setCocktailEditingId(null); setCocktailForm({ name: '', description: '', patient_id: '', items: [] }); }}>Отмена</button>}
        </div>
        <table className="fm-table" style={{ width: '100%' }}>
          <thead><tr><th>ID</th><th>Название</th><th>Животное</th><th>Состав</th><th></th></tr></thead>
          <tbody>
            {shownCocktailRecipes.map((r) => (
              <tr key={r.id}>
                <td>{r.id}</td>
                <td>
                  {r.image_url && <img src={mediaUrl(r.image_url)} alt="" style={{ width: 28, height: 28, objectFit: 'cover', borderRadius: 4, marginRight: 4, verticalAlign: 'middle' }} />}
                  {r.card_image_url && <img src={mediaUrl(r.card_image_url)} alt="" style={{ width: 28, height: 28, objectFit: 'cover', borderRadius: 4, marginRight: 4, verticalAlign: 'middle', border: '1px solid var(--border)' }} />}
                  {r.name}
                </td>
                <td>{r.patient_name || '—'}</td>
                <td style={{ maxWidth: 260 }}>{r.items.map((i) => `${i.name || i.kind} ×${i.qty}`).join(', ')}</td>
                <td>
                  <button type="button" className="fm-btn fm-btn-sm" onClick={() => { setCocktailEditingId(r.id); setCocktailForm({ name: r.name, description: r.description || '', patient_id: r.patient_id != null ? String(r.patient_id) : '', items: r.items.map((i) => ({ kind: i.kind, item_id: i.item_id, qty: i.qty })) }); }}>✎</button>
                  <button type="button" className="fm-btn fm-btn-sm" style={{ marginLeft: 4 }} onClick={() => deleteCocktailRecipe(r.id)}>🗑</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {qActive && shownCocktailRecipes.length === 0 && <div className="fm-card" style={{ color: 'var(--text-muted)', marginTop: 8 }}>{NO_MATCH}</div>}
      </div>
    );
  }

  // ── Рецепты библиотеки ──
  async function loadRecipes() {
    try {
      const [rcs, pls, prods] = await Promise.all([
        api.adminRecipes().catch(() => [] as AdminRecipe[]),
        api.plants().catch(() => [] as Plant[]),
        api.adminProducts().catch(() => [] as Product[]),
      ]);
      setRecipes(rcs);
      setPlants(pls);
      setCatalogProducts(prods);
    } catch { /* ignore */ }
  }
  async function saveRecipe() {
    const productId = Number(recipeForm.product_id);
    if (!productId) { setMsg('✗ Выберите товар'); return; }
    const plantId = recipeForm.source_kind === 'plant' ? Number(recipeForm.plant_id) || null : null;
    const sourceProductId = recipeForm.source_kind === 'animal_product' ? Number(recipeForm.source_product_id) || null : null;
    if (!plantId && !sourceProductId) {
      setMsg(recipeForm.source_kind === 'plant' ? '✗ Выберите растение' : '✗ Выберите продукцию животного');
      return;
    }
    setBusy(true); setMsg(null);
    try {
      const data = { plant_id: plantId, source_product_id: sourceProductId, product_id: productId, level: Number(recipeForm.level) };
      if (recipeEditingId) { await api.adminUpdateRecipe(recipeEditingId, data); }
      else { await api.adminCreateRecipe(data); }
      await loadRecipes();
      setRecipeForm({ source_kind: 'plant', plant_id: '', source_product_id: '', product_id: '', level: '1' });
      setRecipeEditingId(null);
      setMsg('✓ Сохранено');
    } catch (e: any) { setMsg('✗ ' + (e?.response?.data?.detail || 'Ошибка')); }
    finally { setBusy(false); }
  }
  async function deleteRecipe(id: number) {
    if (!(await confirmDialog('Удалить рецепт?'))) return;
    setBusy(true); setMsg(null);
    try { await api.adminDeleteRecipe(id); await loadRecipes(); setMsg('✓ Удалено'); }
    catch (e: any) { setMsg('✗ ' + (e?.response?.data?.detail || 'Ошибка')); }
    finally { setBusy(false); }
  }

  function renderRecipes() {
    const recipePlants = plants.filter((p) => !recipes.some((r) => r.plant_id === p.id) || String(p.id) === recipeForm.plant_id);
    const animalProducts = catalogProducts.filter(
      (p) => p.animal_id != null
        && (!recipes.some((r) => r.source_product_id === p.id) || String(p.id) === recipeForm.source_product_id)
    );
    return (
      <div>
        <h2>📚 Рецепты библиотеки</h2>
        <div className="fm-card" style={{ marginBottom: 10 }}>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 8 }}>
            <select className="fm-input" value={recipeForm.source_kind} onChange={(e) => setRecipeForm({ ...recipeForm, source_kind: e.target.value })}>
              <option value="plant">🌱 Из растения</option>
              <option value="animal_product">🥚 Из продукции животного</option>
            </select>
            {recipeForm.source_kind === 'plant' ? (
              <select className="fm-input" value={recipeForm.plant_id} onChange={(e) => setRecipeForm({ ...recipeForm, plant_id: e.target.value })}>
                <option value="">— растение —</option>
                {(recipeEditingId ? plants : recipePlants).map((p) => (
                  <option key={p.id} value={String(p.id)}>{p.emoji || '🌱'} {p.name}</option>
                ))}
              </select>
            ) : (
              <select className="fm-input" value={recipeForm.source_product_id} onChange={(e) => setRecipeForm({ ...recipeForm, source_product_id: e.target.value })}>
                <option value="">— продукция животного —</option>
                {animalProducts.map((p) => (
                  <option key={p.id} value={String(p.id)}>{p.emoji || '🥚'} {p.name}</option>
                ))}
              </select>
            )}
            <select className="fm-input" value={recipeForm.product_id} onChange={(e) => setRecipeForm({ ...recipeForm, product_id: e.target.value })}>
              <option value="">— товар —</option>
              {catalogProducts.map((p) => (
                <option key={p.id} value={String(p.id)}>{p.emoji || '📦'} {p.name}</option>
              ))}
            </select>
            <select className="fm-input" value={recipeForm.level} onChange={(e) => setRecipeForm({ ...recipeForm, level: e.target.value })}>
              <option value="1">1 уровень</option>
              <option value="2">2 уровень</option>
              <option value="3">3 уровень</option>
            </select>
          </div>
          <button type="button" className="fm-btn" disabled={busy} onClick={saveRecipe}>
            {recipeEditingId ? '✎ Сохранить' : '➕ Создать'}
          </button>
          {recipeEditingId && <button type="button" className="fm-btn" style={{ marginLeft: 6 }} onClick={() => { setRecipeEditingId(null); setRecipeForm({ source_kind: 'plant', plant_id: '', source_product_id: '', product_id: '', level: '1' }); }}>Отмена</button>}
        </div>
        <table className="fm-table" style={{ width: '100%' }}>
          <thead><tr><th>ID</th><th>Источник</th><th>Товар</th><th>Уровень</th><th></th></tr></thead>
          <tbody>
            {shownRecipes.map((r) => (
              <tr key={r.id}>
                <td>{r.id}</td>
                <td>{r.source_product_id != null
                  ? <>{r.source_product_emoji || '🥚'} {r.source_product_name}</>
                  : <>{r.plant_emoji || '🌱'} {r.plant_name}</>}</td>
                <td>{r.product_emoji || '📦'} {r.product_name}</td>
                <td>{r.level}</td>
                <td>
                  <button type="button" className="fm-btn fm-btn-sm" onClick={() => { setRecipeEditingId(r.id); setRecipeForm({
                    source_kind: r.source_product_id != null ? 'animal_product' : 'plant',
                    plant_id: r.plant_id != null ? String(r.plant_id) : '',
                    source_product_id: r.source_product_id != null ? String(r.source_product_id) : '',
                    product_id: String(r.product_id),
                    level: String(r.level),
                  }); }}>✎</button>
                  <button type="button" className="fm-btn fm-btn-sm" style={{ marginLeft: 4 }} onClick={() => deleteRecipe(r.id)}>🗑</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {qActive && shownRecipes.length === 0 && <div className="fm-card" style={{ color: 'var(--text-muted)', marginTop: 8 }}>{NO_MATCH}</div>}
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
  async function uploadPlantImageHarvested(id: number, file: File) {
    setBusy(true); setMsg(null);
    try { await api.adminUploadPlantImageHarvested(id, file); await load(); setMsg('✓ Выращенное растение загружено'); }
    catch (e: any) { setMsg('✗ ' + (e?.response?.data?.detail || 'Ошибка')); }
    finally { setBusy(false); }
  }
  async function uploadAnimalImage(id: number, file: File) {
    setBusy(true); setMsg(null);
    try { await api.adminUploadAnimalImage(id, file); await load(); setMsg('✓ Изображение загружено'); }
    catch (e: any) { setMsg('✗ ' + (e?.response?.data?.detail || 'Ошибка')); }
    finally { setBusy(false); }
  }
  async function uploadAnimalEmptyPenImage(id: number, file: File) {
    setBusy(true); setMsg(null);
    try { await api.adminUploadAnimalEmptyPenImage(id, file); await load(); setMsg('✓ Загон загружен'); }
    catch (e: any) { setMsg('✗ ' + (e?.response?.data?.detail || 'Ошибка')); }
    finally { setBusy(false); }
  }
  async function uploadAnimalPenImage(id: number, file: File) {
    setBusy(true); setMsg(null);
    try { await api.adminUploadAnimalPenImage(id, file); await load(); setMsg('✓ Выращенное (загон с животным) загружено'); }
    catch (e: any) { setMsg('✗ ' + (e?.response?.data?.detail || 'Ошибка')); }
    finally { setBusy(false); }
  }
  async function uploadPetImage(id: number, file: File) {
    setBusy(true); setMsg(null);
    try { await api.adminUploadPetImage(id, file); await load(); setMsg('✓ Изображение загружено'); }
    catch (e: any) { setMsg('✗ ' + (e?.response?.data?.detail || 'Ошибка')); }
    finally { setBusy(false); }
  }

  async function uploadProductionImage(id: number, file: File) {
    setBusy(true); setMsg(null);
    try { await api.adminUploadProductionTemplateImage(id, file); await load(); setMsg('✓ Изображение загружено'); }
    catch (e: any) { setMsg('✗ ' + (e?.response?.data?.detail || 'Ошибка')); }
    finally { setBusy(false); }
  }

  async function uploadProductImage(id: number, file: File) {
    setBusy(true); setMsg(null);
    try { await api.adminUploadProductImage(id, file); await load(); setMsg('✓ Изображение загружено'); }
    catch (e: any) { setMsg('✗ ' + (e?.response?.data?.detail || 'Ошибка')); }
    finally { setBusy(false); }
  }

  async function saveGameMedia() {
    const mt = MEDIA_TYPES.find(m => m.code === mediaTypeSel);
    if (!mt) { setMsg('✗ Выберите тип'); return; }
    setBusy(true); setMsg(null);
    try {
      await api.adminCreateGameMedia({ code: mt.code, kind: mt.kind });
      setMediaTypeSel('');
      const list = await api.adminGameMedia();
      setGameMedia(list);
      setMsg('✓ Создано');
    } catch (e: any) { setMsg('✗ ' + (e?.response?.data?.detail || 'Ошибка')); }
    finally { setBusy(false); }
  }

  async function deleteGameMedia(id: number) {
    if (!(await confirmDialog('Удалить медиа?'))) return;
    setBusy(true); setMsg(null);
    try { await api.adminDeleteGameMedia(id); setGameMedia(await api.adminGameMedia()); setMsg('✓ Удалено'); }
    catch (e: any) { setMsg('✗ ' + (e?.response?.data?.detail || 'Ошибка')); }
    finally { setBusy(false); }
  }

  async function uploadGameMediaFile(id: number, file: File) {
    setBusy(true); setMsg(null);
    try { await api.adminUploadGameMedia(id, file); setGameMedia(await api.adminGameMedia()); setMsg('✓ Файл загружен'); }
    catch (e: any) { setMsg('✗ ' + (e?.response?.data?.detail || 'Ошибка')); }
    finally { setBusy(false); }
  }

  // ── Предыстория ──
  async function saveStorySlide() {
    if (!storyForm.text.trim()) { setMsg('✗ Введите текст'); return; }
    setBusy(true); setMsg(null);
    try {
      const data = { text: storyForm.text.trim(), sort_order: Number(storyForm.sort_order) || 0, location_code: storyForm.location_code || null };
      let savedId: number;
      if (storyEditingId) {
        await api.adminUpdateStorySlide(storyEditingId, data);
        savedId = storyEditingId;
      } else {
        savedId = (await api.adminCreateStorySlide(data)).id;
      }
      if (storyImage) {
        await api.adminUploadStorySlideImage(savedId, storyImage);
      }
      setMsg('✓ Слайд сохранён');
      setStoryForm({ text: '', sort_order: '0', location_code: '' });
      setStoryImage(null);
      setStoryEditingId(null);
      setStorySlides(await api.adminStorySlides());
    } catch (e: any) { setMsg('✗ ' + (e?.response?.data?.detail || 'Ошибка')); }
    finally { setBusy(false); }
  }

  async function uploadStoryImage(id: number, file: File) {
    setBusy(true); setMsg(null);
    try { await api.adminUploadStorySlideImage(id, file); setStorySlides(await api.adminStorySlides()); setMsg('✓ Картинка загружена'); }
    catch (e: any) { setMsg('✗ ' + (e?.response?.data?.detail || 'Ошибка')); }
    finally { setBusy(false); }
  }

  async function deleteStorySlide(id: number) {
    if (!(await confirmDialog('Удалить слайд предыстории?'))) return;
    setBusy(true); setMsg(null);
    try { await api.adminDeleteStorySlide(id); setStorySlides(await api.adminStorySlides()); setMsg('✓ Удалено'); }
    catch (e: any) { setMsg('✗ ' + (e?.response?.data?.detail || 'Ошибка')); }
    finally { setBusy(false); }
  }

  // ── Видео-уроки ──
  async function saveLesson() {
    if (!lessonForm.title.trim()) { setMsg('✗ Введите название'); return; }
    setBusy(true); setMsg(null);
    try {
      const data = { title: lessonForm.title.trim(), description: lessonForm.description.trim() || null, sort_order: Number(lessonForm.sort_order) || 0 };
      let savedId: number;
      if (lessonEditingId) {
        await api.adminUpdateLesson(lessonEditingId, data);
        savedId = lessonEditingId;
      } else {
        savedId = (await api.adminCreateLesson(data)).id;
      }
      if (lessonVideo) await api.adminUploadLessonVideo(savedId, lessonVideo);
      if (lessonImage) await api.adminUploadLessonImage(savedId, lessonImage);
      setMsg('✓ Урок сохранён');
      setLessonForm({ title: '', description: '', sort_order: '0' });
      setLessonVideo(null);
      setLessonImage(null);
      setLessonEditingId(null);
      setLessons(await api.adminLessons());
    } catch (e: any) { setMsg('✗ ' + (e?.response?.data?.detail || 'Ошибка')); }
    finally { setBusy(false); }
  }

  async function uploadLessonVideo(id: number, file: File) {
    setBusy(true); setMsg(null);
    try { await api.adminUploadLessonVideo(id, file); setLessons(await api.adminLessons()); setMsg('✓ Видео загружено'); }
    catch (e: any) { setMsg('✗ ' + (e?.response?.data?.detail || 'Ошибка')); }
    finally { setBusy(false); }
  }

  async function uploadLessonImage(id: number, file: File) {
    setBusy(true); setMsg(null);
    try { await api.adminUploadLessonImage(id, file); setLessons(await api.adminLessons()); setMsg('✓ Фото загружено'); }
    catch (e: any) { setMsg('✗ ' + (e?.response?.data?.detail || 'Ошибка')); }
    finally { setBusy(false); }
  }

  async function deleteLesson(id: number) {
    if (!(await confirmDialog('Удалить урок?'))) return;
    setBusy(true); setMsg(null);
    try { await api.adminDeleteLesson(id); setLessons(await api.adminLessons()); setMsg('✓ Удалено'); }
    catch (e: any) { setMsg('✗ ' + (e?.response?.data?.detail || 'Ошибка')); }
    finally { setBusy(false); }
  }

  async function uploadCrystalCardImage(id: number, file: File) {
    setBusy(true); setMsg(null);
    try { await api.adminUploadCrystalCardImage(id, file); setCrystalCards(await api.adminCrystalCards()); setMsg('✓ Картинка загружена'); }
    catch (e: any) { setMsg('✗ ' + (e?.response?.data?.detail || 'Ошибка')); }
    finally { setBusy(false); }
  }

  // ── Достижения ──
  async function loadAchievements() {
    try {
      const [list, kinds] = await Promise.all([api.adminAchievements(), api.adminAchievementKinds()]);
      setAchievements(list);
      setAchKinds(kinds);
    } catch { /* ignore */ }
  }
  async function saveAchievement() {
    if (!achForm.name.trim() || !achForm.condition_kind.trim()) { setMsg('✗ Заполните название и условие'); return; }
    setBusy(true); setMsg(null);
    try {
      const data: any = { name: achForm.name, condition_kind: achForm.condition_kind, condition_value: Number(achForm.condition_value) || 1 };
      if (achForm.production_code) data.production_code = achForm.production_code;
      let targetId = achEditingId;
      if (targetId) { await api.adminUpdateAchievement(targetId, data); }
      else {
        const created = await api.adminCreateAchievement(data);
        targetId = created.id;
      }
      if (targetId && achImage) {
        await api.adminUploadAchievementImage(targetId, achImage);
      }
      await loadAchievements();
      setAchForm({ name: '', condition_kind: '', condition_value: '1', production_code: '' });
      setAchEditingId(null);
      setAchImage(null);
      setMsg('✓ Сохранено');
    } catch (e: any) { setMsg('✗ ' + (e?.response?.data?.detail || 'Ошибка')); }
    finally { setBusy(false); }
  }
  async function deleteAchievement(id: number) {
    if (!(await confirmDialog('Удалить достижение?'))) return;
    setBusy(true); setMsg(null);
    try { await api.adminDeleteAchievement(id); await loadAchievements(); setMsg('✓ Удалено'); }
    catch (e: any) { setMsg('✗ ' + (e?.response?.data?.detail || 'Ошибка')); }
    finally { setBusy(false); }
  }
  async function uploadAchImage(id: number, file: File) {
    setBusy(true); setMsg(null);
    try { await api.adminUploadAchievementImage(id, file); await loadAchievements(); setMsg('✓ Картинка загружена'); }
    catch (e: any) { setMsg('✗ ' + (e?.response?.data?.detail || 'Ошибка')); }
    finally { setBusy(false); }
  }

  const [tabQuery, setTabQuery] = useState<Record<string, string>>({});
  const query = tabQuery[tab] || '';
  const setQuery = (v: string) => setTabQuery((m) => ({ ...m, [tab]: v }));
  const qActive = query.trim().length > 0;
  const fl = <T,>(items: T[]): T[] => (qActive ? items.filter((it) => matchesAny(it, query)) : items);

  const [plantLevelFilter, setPlantLevelFilter] = useState('');
  const plantLevels = Array.from(new Set(plants.map((p) => p.level))).sort((a, b) => a - b);

  const shownOrders = fl(adminOrders);
  const shownFields = fl(fields);
  const shownPlants = fl(plants).filter((p) => !plantLevelFilter || String(p.level) === plantLevelFilter);
  const shownAnimals = fl(animals);
  const shownPets = fl(pets);
  const shownProducts = fl(catalogProducts);
  const shownProductions = fl(prodTemplates);
  const shownRecipes = fl(recipes);
  const shownCustomers = fl(customers);
  const shownLevels = fl(levels);
  const shownPotionRecipes = fl(potionRecipes);
  const shownCocktailRecipes = fl(cocktailRecipes);
  const shownIngredients = fl(ingredients);
  const shownMedia = fl(gameMedia);
  const shownCards = fl(crystalCards);
  const shownAchievements = fl(achievements);
  const shownStorySlides = fl(storySlides);
  const shownLessons = fl(lessons);
  const shownSettings = fl(SETTING_FIELDS);

  const totals: Record<string, { total: number; shown: number }> = {
    orders: { total: adminOrders.length, shown: shownOrders.length },
    fields: { total: fields.length, shown: shownFields.length },
    plants: { total: plants.length, shown: shownPlants.length },
    animals: { total: animals.length, shown: shownAnimals.length },
    pets: { total: pets.length, shown: shownPets.length },
    products: { total: catalogProducts.length, shown: shownProducts.length },
    productions: { total: prodTemplates.length, shown: shownProductions.length },
    recipes: { total: recipes.length, shown: shownRecipes.length },
    customers: { total: customers.length, shown: shownCustomers.length },
    levels: { total: levels.length, shown: shownLevels.length },
    'potion-recipes': { total: potionRecipes.length, shown: shownPotionRecipes.length },
    'cocktail-recipes': { total: cocktailRecipes.length, shown: shownCocktailRecipes.length },
    ingredients: { total: ingredients.length, shown: shownIngredients.length },
    media: { total: gameMedia.length, shown: shownMedia.length },
    'crystal-cards': { total: crystalCards.length, shown: shownCards.length },
    achievements: { total: achievements.length, shown: shownAchievements.length },
    story: { total: storySlides.length, shown: shownStorySlides.length },
    lessons: { total: lessons.length, shown: shownLessons.length },
    settings: { total: SETTING_FIELDS.length, shown: shownSettings.length },
  };

  const NO_MATCH = 'Ничего не найдено.';

  return (
    <div style={{ maxWidth: 'var(--shell-max-width)', margin: '0 auto', padding: 'var(--shell-pad)' }}>
      <div style={{ display: 'flex', gap: 6, marginBottom: 14, flexWrap: 'wrap' }}>
        <TabBtn active={tab === 'players'} onClick={() => setTab('players')}>👥 Игроки</TabBtn>
        <TabBtn active={tab === 'settings'} onClick={() => setTab('settings')}>🔧 Настройки</TabBtn>
        <TabBtn active={tab === 'fields'} onClick={() => setTab('fields')}>🗺️ Локации</TabBtn>
        <TabBtn active={tab === 'orders'} onClick={() => setTab('orders')}>🧺 Заказы</TabBtn>
        <TabBtn active={tab === 'plants'} onClick={() => setTab('plants')}>🌱 Растения</TabBtn>
        <TabBtn active={tab === 'animals'} onClick={() => setTab('animals')}>🐄 Животные</TabBtn>
        <TabBtn active={tab === 'pets'} onClick={() => setTab('pets')}>🐾 Питомцы</TabBtn>
        <TabBtn active={tab === 'products'} onClick={() => setTab('products')}>📦 Товары</TabBtn>
        <TabBtn active={tab === 'productions'} onClick={() => setTab('productions')}>🏭 Производства</TabBtn>
        <TabBtn active={tab === 'recipes'} onClick={() => { setTab('recipes'); loadRecipes(); }}>📚 Рецепты</TabBtn>
        <TabBtn active={tab === 'customers'} onClick={() => { setTab('customers'); loadCustomers(); }}>🧑 Заказчики</TabBtn>
        <TabBtn active={tab === 'levels'} onClick={() => { setTab('levels'); loadLevels(); }}>📊 Уровни</TabBtn>
        <TabBtn active={tab === 'potion-recipes'} onClick={() => { setTab('potion-recipes'); loadPotionRecipes(); }}>🧪 Рецепты зелий</TabBtn>
        <TabBtn active={tab === 'cocktail-recipes'} onClick={() => { setTab('cocktail-recipes'); loadCocktailRecipes(); }}>🍸 Коктейли</TabBtn>
        <TabBtn active={tab === 'ingredients'} onClick={() => { setTab('ingredients'); loadIngredients(); }}>⚗️ Ингредиенты</TabBtn>
        <TabBtn active={tab === 'infirmary'} onClick={() => { setTab('infirmary'); loadInfirmary(); }}>🌲 Лечебница</TabBtn>
        <TabBtn active={tab === 'media'} onClick={() => setTab('media')}>🎬 Медиа</TabBtn>
        <TabBtn active={tab === 'story'} onClick={() => setTab('story')}>📜 Предыстория</TabBtn>
        <TabBtn active={tab === 'lessons'} onClick={() => setTab('lessons')}>🎬 Уроки</TabBtn>
        <TabBtn active={tab === 'crystal-cards'} onClick={() => setTab('crystal-cards')}>🃏 Карты</TabBtn>
        <TabBtn active={tab === 'achievements'} onClick={() => { setTab('achievements'); loadAchievements(); }}>🏆 Достижения</TabBtn>
        <TabBtn active={tab === 'logs'} onClick={() => setTab('logs')}>📜 Логи</TabBtn>
      </div>

      {tab !== 'players' && tab !== 'logs' && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12, flexWrap: 'wrap' }}>
          <input
            className="fm-input"
            placeholder="🔍 Поиск по всем полям…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            style={{ flex: '1 1 200px', minWidth: 0 }}
          />
          {qActive && (
            <>
              <span style={{ fontSize: 12, color: 'var(--text-muted)', whiteSpace: 'nowrap', flexShrink: 0 }}>
                {totals[tab]?.shown ?? 0} из {totals[tab]?.total ?? 0}
              </span>
              <button type="button" className="fm-btn fm-btn-sm fm-btn-outline" style={{ flexShrink: 0 }} onClick={() => setQuery('')}>✕</button>
            </>
          )}
        </div>
      )}

      {msg && <Toast text={msg} onClose={() => setMsg(null)} />}

      {loading ? (
        <div className="fm-card">Загрузка…</div>
      ) : (
        <>
          {tab === 'players' && (
            <>
              {selectedPlayer ? (
                <div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 14, flexWrap: 'wrap' }}>
                    <button type="button" className="fm-btn fm-btn-sm fm-btn-outline" style={{ flexShrink: 0 }} onClick={() => { setSelectedPlayer(null); setPlayerDetail(null); setPlayerReports([]); }}>← Назад</button>
                    <h2 style={{ margin: 0, fontSize: 18, flex: '1 1 140px', minWidth: 0, overflowWrap: 'anywhere' }}>
                      {selectedPlayer.first_name || selectedPlayer.last_name ? `${selectedPlayer.first_name} ${selectedPlayer.last_name}`.trim() : `#${selectedPlayer.vk_id}`}
                    </h2>
                    <button type="button" className="fm-btn fm-btn-sm fm-btn-danger" style={{ flexShrink: 0 }} disabled={busy} onClick={restartPlayer}>
                      🔁 РЕСТАРТ
                    </button>
                    {selectedPlayer.role !== 'admin' && (
                      <button type="button" className="fm-btn fm-btn-sm fm-btn-danger" style={{ flexShrink: 0 }} disabled={busy} onClick={deletePlayerAccount}>
                        🗑 Удалить
                      </button>
                    )}
                  </div>
                  <div className="fm-card" style={{ marginBottom: 14, fontSize: 13 }}>
                    <div>ID: {selectedPlayer.vk_id} · Роль: {selectedPlayer.role} · Статус: {PLAYER_STATUS_META[selectedPlayer.status ?? 'active']?.emoji} {PLAYER_STATUS_META[selectedPlayer.status ?? 'active']?.label ?? selectedPlayer.status}</div>
                    <div>Крестики: {selectedPlayer.crosses_balance} (всего {selectedPlayer.crosses_total}) · Монеты: {selectedPlayer.coins} · Раунд: {selectedPlayer.round}</div>
                    {selectedPlayer.role !== 'admin' && (
                      <div style={{ marginTop: 8, display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                        {selectedPlayer.status !== 'blocked' && (
                          <button type="button" className="fm-btn fm-btn-sm fm-btn-danger" disabled={busy} onClick={() => setPlayerStatus(selectedPlayer.vk_id, 'blocked')}>
                            🚫 Заблокировать
                          </button>
                        )}
                        {selectedPlayer.status !== 'readonly' && (
                          <button type="button" className="fm-btn fm-btn-sm fm-btn-outline" disabled={busy} onClick={() => setPlayerStatus(selectedPlayer.vk_id, 'readonly')}>
                            👁 Только просмотр
                          </button>
                        )}
                        {selectedPlayer.status !== 'active' && (
                          <button type="button" className="fm-btn fm-btn-sm" disabled={busy} onClick={() => setPlayerStatus(selectedPlayer.vk_id, 'active')}>
                            ✅ Разблокировать
                          </button>
                        )}
                      </div>
                    )}
                    <div style={{ marginTop: 8, display: 'flex', gap: 6, flexWrap: 'wrap', alignItems: 'center' }}>
                      <span>Дополнения:</span>
                      {Object.entries(LOCATION_TITLES).map(([code, title]) => {
                        const granted = playerDetail?.dlc_locations?.includes(code);
                        return (
                          <button
                            key={code}
                            type="button"
                            className={granted ? 'fm-btn fm-btn-sm' : 'fm-btn fm-btn-sm fm-btn-outline'}
                            disabled={busy || !playerDetail}
                            onClick={() => togglePlayerDlc(selectedPlayer.vk_id, code, !!granted)}
                          >
                            {granted ? '✓ ' : ''}{title}
                          </button>
                        );
                      })}
                    </div>
                  </div>

                  <div style={{ display: 'flex', gap: 6, marginBottom: 14 }}>
                    <TabBtn active={playerTab === 'overview'} onClick={() => setPlayerTab('overview')}>🏡 Хозяйство</TabBtn>
                    <TabBtn active={playerTab === 'reports'} onClick={() => setPlayerTab('reports')}>📷 Отчёты ({selectedPlayer.reports_total})</TabBtn>
                  </div>

                  {playerTab === 'overview' && playerDetail && (
                    <div>
                      <h3 style={{ marginTop: 0 }}>🗺️ Локации</h3>
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
                                {plot.accumulated}/{plot.required} ❎{plot.norm_per_unit != null ? <> · {plot.norm_per_unit}/шт</> : null}
                                {plot.crystal_color && <> · {plot.crystal_color} ×{plot.crystal_count}</>}
                              </div>
                            </div>
                          ))}
                        </div>
                      )}

                      <h3 style={{ marginTop: 16 }}>❆ Цены 1 растения ({playerDetail.plant_norms?.length ?? 0})</h3>
                      {(playerDetail.plant_norms ?? []).length === 0 ? (
                        <div className="fm-card" style={{ color: 'var(--text-muted)', fontSize: 13 }}>Игрок ещё ничего не сажал.</div>
                      ) : (
                        <div className="fm-grid">
                          {(playerDetail.plant_norms ?? []).map((n) => (
                            <div key={n.plant_id} className="fm-card fm-rise" style={{ fontSize: 13 }}>
                              <strong>{n.plant_emoji} {n.plant_name}</strong>
                              <div style={{ color: 'var(--text-muted)', marginTop: 2, fontSize: 12 }}>Текущая цена: {n.norm_per_unit} ❎/шт</div>
                              <div style={{ marginTop: 6 }}>
                                <PlantNormEditor vkId={selectedPlayer.vk_id} plantId={n.plant_id} initial={n.norm_per_unit} onSaved={() => reloadPlayerDetail()} />
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
                                {pr.accumulated}/{pr.required} ❎
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

                      <h3 style={{ marginTop: 16 }}>🏚️ Загоны ({playerDetail.barnyard?.length ?? 0})</h3>
                      {(playerDetail.barnyard ?? []).length === 0 ? (
                        <div className="fm-card" style={{ color: 'var(--text-muted)', fontSize: 13 }}>Загонов нет.</div>
                      ) : (
                        <div className="fm-grid">
                          {(playerDetail.barnyard ?? []).map((b) => (
                            <div key={b.id} className="fm-card fm-rise" style={{ fontSize: 13, borderColor: b.is_ghost ? '#e05555' : undefined }}>
                              <strong>{b.animal_emoji || '🐾'} {b.animal_name ?? '— пусто —'}</strong>
                              <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 2 }}>
                                {b.is_ghost
                                  ? <span style={{ color: '#e05555' }}>⚠️ призрак: не отображается в игре</span>
                                  : <>клетка ({b.cell_col}, {b.cell_row})</>}
                              </div>
                              <div style={{ fontSize: 12, marginTop: 2 }}>
                                {b.status} · {b.accumulated}/{b.required} ❎
                              </div>
                              <button type="button" className="fm-btn fm-btn-xs fm-btn-danger" style={{ marginTop: 6 }} disabled={busy}
                                onClick={async () => {
                                  if (!selectedPlayer) return;
                                  if (!(await confirmDialog('Удалить загон игрока? Животное и прогресс будут потеряны.'))) return;
                                  setBusy(true);
                                  try {
                                    await api.adminDeletePlayerBarnyard(selectedPlayer.vk_id, b.id);
                                    setMsg('✓ Загон удалён');
                                    await reloadPlayerDetail();
                                  } catch (e: any) {
                                    setMsg('✗ ' + (e?.response?.data?.detail || 'Ошибка'));
                                  } finally { setBusy(false); }
                                }}>
                                🗑 Удалить
                              </button>
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
                          {playerReports.map((r) => {
                            const photo = r.photo_after_url || r.photo_after_thumb_url;
                            return (
                            <div key={r.id} className="fm-card fm-rise">
                              <div style={{ display: 'flex', gap: 10 }}>
                                {photo && (
                                  <img src={mediaUrl(photo)} alt="" style={{ width: 60, height: 60, objectFit: 'cover', borderRadius: 'var(--radius-sm)' }} />
                                )}
                                <div style={{ flex: 1 }}>
                                  <strong>❎ {r.amount}</strong>
                                  {r.note && <div style={{ fontSize: 13 }}>{r.note}</div>}
                                  <span className="fm-chip" style={{ marginTop: 4, fontSize: 11 }}>
                                    {r.status === 'accepted' ? '✓ зачтено' : r.status === 'pending' ? '⏳ ждёт' : '✖ отклонено'}
                                  </span>
                                </div>
                              </div>
                              {r.status === 'pending' && (
                                <div style={{ display: 'flex', gap: 6, marginTop: 8 }}>
                                  <button type="button" className="fm-btn fm-btn-sm" style={{ flex: 1 }} disabled={busy} onClick={() => reviewReport(r.id, 'accept')}>Зачесть</button>
                                  <button type="button" className="fm-btn fm-btn-sm fm-btn-danger" disabled={busy} onClick={() => reviewReport(r.id, 'reject')}>Отклонить</button>
                                </div>
                              )}
                            </div>
                            );
                          })}
                        </div>
                      )}
                    </div>
                  )}
                </div>
              ) : (
                <div>
                  <h2 style={{ marginTop: 0 }}>👥 Игроки</h2>
                  <div className="fm-card" style={{ marginBottom: 12 }}>
                    <h3 style={{ margin: '0 0 8px' }}>🔑 Доступ к игре</h3>
                    <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                      <input
                        className="fm-input"
                        style={{ flex: '1 1 220px', minWidth: 0 }}
                        placeholder="Ссылка ВК: https://vk.ru/id123 или vk.ru/имя"
                        value={accessLink}
                        onChange={(e) => setAccessLink(e.target.value)}
                      />
                      <button type="button" className="fm-btn fm-btn-sm" style={{ flexShrink: 0 }} disabled={busy || !accessLink.trim()} onClick={addAccessPlayer}>➕ Добавить</button>
                    </div>
                    {accessPlayers.length === 0 ? (
                      <div style={{ color: 'var(--text-muted)', fontSize: 13, marginTop: 8 }}>
                        Пока доступ есть только у администраторов. Добавьте игрока по ссылке ВК.
                      </div>
                    ) : (
                      <div className="fm-grid" style={{ marginTop: 10 }}>
                        {accessPlayers.map((p) => (
                          <div key={p.vk_id} className="fm-card fm-rise" style={{ fontSize: 13, display: 'flex', alignItems: 'center', gap: 8 }}>
                            <div style={{ flex: 1, minWidth: 0 }}>
                              <strong style={{ overflowWrap: 'anywhere' }}>
                                {p.first_name || p.last_name ? `${p.first_name} ${p.last_name}`.trim() : `#${p.vk_id}`}
                              </strong>
                              <div style={{ color: 'var(--text-muted)', fontSize: 12 }}>
                                #{p.vk_id}{p.screen_name ? ` · ${p.screen_name}` : ''}
                              </div>
                            </div>
                            <button type="button" className="fm-btn fm-btn-sm fm-btn-danger" disabled={busy} onClick={() => removeAccessPlayer(p.vk_id)}>✕</button>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                  <div style={{ marginBottom: 12 }}>
                    <input
                      className="fm-input"
                      type="text"
                      placeholder="Поиск по всем полям (ID, имя, роль, монеты…)"
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
                              <th style={{ padding: '8px 12px', textAlign: 'right' }}>❎</th>
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
                                  {p.status && p.status !== 'active' && (
                                    <span className="fm-chip" style={{ marginLeft: 6, fontSize: 11 }} title={PLAYER_STATUS_META[p.status]?.label}>
                                      {PLAYER_STATUS_META[p.status]?.emoji ?? p.status}
                                    </span>
                                  )}
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
                          <button type="button" className="fm-btn fm-btn-sm fm-btn-outline" disabled={playerPage === 0} onClick={() => setPlayerPage((p) => p - 1)}>← Назад</button>
                          <span style={{ color: 'var(--text-muted)' }}>{playerPage + 1} / {Math.ceil(players.length / PER_PAGE)}</span>
                          <button type="button" className="fm-btn fm-btn-sm fm-btn-outline" disabled={playerPage >= Math.ceil(players.length / PER_PAGE) - 1} onClick={() => setPlayerPage((p) => p + 1)}>Вперёд →</button>
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
                <button type="button" className="fm-btn fm-btn-sm fm-btn-outline" onClick={() => setViewField(null)} style={{ color: '#fff', borderColor: '#fff' }}>← Назад</button>
                <span style={{ color: '#ccc', fontSize: 14 }}>{viewField.name} · {viewField.cols}×{viewField.rows}</span>
              </div>
              <div style={{ flex: 1, position: 'relative', overflow: 'auto' }}>
                <FieldGridView field={viewField} playerVkId={selectedPlayer?.vk_id}
                  onResetNorm={async (plotId) => {
                    if (!selectedPlayer) return;
                    if (!(await confirmDialog('Сбросить норму? Игроку выпадут новые случайные карты.'))) return;
                    setBusy(true);
                    try {
                      await api.adminResetPlotNorm(selectedPlayer.vk_id, plotId);
                      setMsg('✓ Норма сброшена');
                      const fd = await api.adminPlayerField(selectedPlayer.vk_id, viewField!.id);
                      setViewField(fd);
                    } catch (e: any) {
                      setMsg('✗ ' + (e?.response?.data?.detail || 'Ошибка'));
                    } finally { setBusy(false); }
                  }}
                  onDeletePlot={async (plotId) => {
                    if (!selectedPlayer) return;
                    if (!(await confirmDialog('Удалить грядку игрока? Растение и прогресс будут потеряны.'))) return;
                    setBusy(true);
                    try {
                      await api.adminDeletePlayerPlot(selectedPlayer.vk_id, plotId);
                      setMsg('✓ Грядка удалена');
                      const fd = await api.adminPlayerField(selectedPlayer.vk_id, viewField!.id);
                      setViewField(fd);
                    } catch (e: any) {
                      setMsg('✗ ' + (e?.response?.data?.detail || 'Ошибка'));
                    } finally { setBusy(false); }
                  }}
                />
              </div>
            </div>
          )}

          {tab === 'settings' && (
            <>
              <CrystalStandardEditor disabled={busy} />
              <div className="fm-card" style={{ marginTop: 10 }}>
                <h3>🔒 Закрытые локации</h3>
                <div style={{ color: 'var(--text-muted)', fontSize: 13, marginBottom: 10 }}>
                  Закрытые локации видны игрокам с замком 🔒 и недоступны без дополнения. Админам всё доступно всегда. Дополнения выдаются в карточке игрока.
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                  {Object.entries(LOCATION_TITLES).map(([code, title]) => (
                    <label key={code} style={{ display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer' }}>
                      <input type="checkbox" checked={lockedLocations.includes(code)} disabled={busy} onChange={() => toggleLockedLocation(code)} />
                      <span>{title}</span>
                      <span style={{ color: 'var(--text-muted)', fontSize: 12 }}>
                        {lockedLocations.includes(code) ? 'закрыта 🔒' : 'открыта'}
                      </span>
                    </label>
                  ))}
                </div>
              </div>
              {shownSettings.length === 0 ? (
                <div className="fm-card" style={{ color: 'var(--text-muted)' }}>{NO_MATCH}</div>
              ) : (
                <div className="fm-grid">
                  {shownSettings.map((f) => (
                    <SettingRow key={f.key} field={f} value={settings[f.key] ?? ''} disabled={busy} onSave={(v) => saveSetting(f.key, v)} />
                  ))}
                </div>
              )}
              <div className="fm-card" style={{ marginTop: 10 }}>
                <h3>🖼️ Нейтральный фон</h3>
                <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
                  <input className="fm-input" style={{ flex: '1 1 220px', minWidth: 0 }} placeholder="URL фона" value={bgInput} onChange={(e) => setBgInput(e.target.value)} />
                  <button type="button" className="fm-btn fm-btn-sm" style={{ flexShrink: 0 }} disabled={busy} onClick={saveBg}>💾</button>
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
                  <button type="button" className="fm-btn" style={{ width: '100%', marginBottom: 14 }} disabled={busy} onClick={() => setShowCreate(true)}>
                    ➕ Создать локацию
                  </button>
                  {shownFields.length === 0 ? (
                    <div className="fm-card" style={{ color: 'var(--text-muted)' }}>{qActive ? NO_MATCH : 'Локаций пока нет.'}</div>
                  ) : (
                    <div className="fm-grid">
                      {shownFields.map((f) => (
                        <div key={f.id} className="fm-card fm-rise">
                          <strong style={{ fontSize: 16 }}>🗺️ {f.name}</strong>
                          <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 4 }}>{f.cols}×{f.rows} клеток</div>
                          {f.map_url && <img src={mediaUrl(f.map_url)} alt="" style={{ width: '100%', marginTop: 8, borderRadius: 'var(--radius-sm)' }} />}
                          <div style={{ display: 'flex', flexDirection: 'column', gap: 6, marginTop: 8 }}>
                            <button type="button" className="fm-btn fm-btn-sm" disabled={busy} onClick={() => setEditorFieldId(f.id)}>✎ Редактировать</button>
                            <label className="fm-btn fm-btn-sm fm-btn-outline" style={{ cursor: 'pointer' }}>
                              {f.map_url ? '🖼️ Сменить картинку' : '🖼️ Загрузить карту'}
                              <input type="file" accept="image/*" style={{ display: 'none' }} onChange={(e) => { const file = e.target.files?.[0]; if (file) uploadMap(f.id, file); }} />
                            </label>
                            <button type="button" className="fm-btn fm-btn-sm fm-btn-danger" disabled={busy} onClick={() => deleteField(f.id)}>Удалить</button>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                  {showCreate && (
                    <div style={{ position: 'fixed', inset: 0, zIndex: 60, background: 'rgba(0,0,0,0.6)', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 16 }}>
                      <div className="fm-card fm-rise" onClick={(e) => e.stopPropagation()} style={{ width: '100%', maxWidth: 'calc(var(--shell-max-width) * 0.633)' }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
                          <h3 style={{ margin: 0 }}>➕ Новая локация</h3>
                          <button type="button" className="fm-btn fm-btn-xs fm-btn-outline" onClick={() => setShowCreate(false)}>✕</button>
                        </div>
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
                        <div style={{ marginTop: 8 }}>
                          <label style={{ display: 'block', marginBottom: 4, fontSize: 14 }}>Тип локации</label>
                          <select className="fm-input" value={newFieldKind} onChange={(e) => setNewFieldKind(e.target.value)}>
                            <option value="">— без типа —</option>
                            <option value="garden_beds">🌱 Грядки</option>
                            <option value="orchard">🍎 Сад</option>
                            <option value="lawn">🌿 Лужайка</option>
                            <option value="house">🏠 Дом</option>
                            <option value="barnyard">🐄 Скотный двор</option>
                            <option value="library">📖 Библиотека</option>
                            <option value="brewery">🧪 Зельеварня</option>
                            <option value="meadow">🌿 Лесная поляна</option>
                            <option value="shop">🛒 Городская лавка</option>
                            <option value="infirmary">🌲 Лесная лечебница</option>
                            <option value="remedy_lab">⚗️ Лаборатория снадобий</option>
                            <option value="forest_bar">🍹 Лесной бар</option>
                          </select>
                        </div>
                        <div style={{ marginTop: 8 }}>
                          <label style={{ display: 'block', marginBottom: 4, fontSize: 14 }}>Категория растений</label>
                          <select className="fm-input" value={newPlantCategory} onChange={(e) => setNewPlantCategory(e.target.value)}>
                            <option value="">— любая —</option>
                            <option value="garden">🌱 Грядка</option>
                            <option value="orchard">🍎 Сад</option>
                          </select>
                        </div>
                        <div style={{ marginTop: 8 }}>
                          <label style={{ display: 'block', marginBottom: 4, fontSize: 14 }}>Мин. уровень для открытия</label>
                          <input className="fm-input" type="number" min={0} max={16} value={newMinLevel} onChange={(e) => setNewMinLevel(e.target.value)} />
                        </div>
                        <button type="button" className="fm-btn" style={{ width: '100%', marginTop: 14 }} disabled={busy || !newName.trim()} onClick={createField}>Создать</button>
                      </div>
                    </div>
                  )}
                </>
              )}
            </>
          )}

          {tab === 'plants' && (
            <>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10, flexWrap: 'wrap' }}>
                <label style={{ fontSize: 13, whiteSpace: 'nowrap' }}>Уровень:</label>
                <select className="fm-input" value={plantLevelFilter} onChange={(e) => setPlantLevelFilter(e.target.value)} style={{ maxWidth: 180 }}>
                  <option value="">— все уровни —</option>
                  {plantLevels.map((l) => (
                    <option key={l} value={String(l)}>Уровень {l}</option>
                  ))}
                </select>
                {plantLevelFilter && (
                  <button type="button" className="fm-btn fm-btn-sm fm-btn-outline" onClick={() => setPlantLevelFilter('')}>✕</button>
                )}
              </div>
              <CatalogTab title="🌱 Растения" items={shownPlants} busy={busy} form={catForm} formOpen={formOpen} editingId={editingId} onFormChange={setCatForm} onCreate={startCreate} onEdit={startEdit} onCancel={cancelForm} onSave={savePlant} onDelete={deletePlant} onUploadImage={uploadPlantImage} onUploadImageYoung={uploadPlantImageYoung} onUploadImageGrown={uploadPlantImageGrown} onUploadImageHarvested={uploadPlantImageHarvested} hideMainImage emptyText={qActive ? NO_MATCH : undefined} showLevel
                fields={[{ key: 'name', label: 'Название', ph: 'Джекобоб' }, { key: 'emoji', label: 'Эмодзи', ph: '🌱' }, { key: 'level', label: 'Уровень', ph: '1', type: 'number' }, { key: 'category', label: 'Категория', options: [{ value: 'garden', label: '🌱 Грядка' }, { value: 'orchard', label: '🍎 Сад' }] }, { key: 'description', label: 'Описание', ph: 'Грибы' }, { key: 'stitch_condition', label: 'Условие отшива', ph: 'Вышить на белой канве' }]}
              />
            </>
          )}

          {tab === 'animals' && (
            <CatalogTab title="🐄 Животные" items={shownAnimals} busy={busy} form={catForm} formOpen={formOpen} editingId={editingId} onFormChange={setCatForm} onCreate={startCreate} onEdit={startEdit} onCancel={cancelForm} onSave={saveAnimal} onDelete={deleteAnimal} onUploadImage={uploadAnimalImage} onUploadImageEmptyPen={uploadAnimalEmptyPenImage} onUploadImagePen={uploadAnimalPenImage} hideMainImage emptyText={qActive ? NO_MATCH : undefined}
              fields={[{ key: 'name', label: 'Название', ph: 'Единорог' }, { key: 'product_name', label: 'Продукция', ph: 'Рог единорога' }]}
            />
          )}

          {tab === 'pets' && (
            <CatalogTab title="🐾 Питомцы" items={shownPets} busy={busy} form={catForm} formOpen={formOpen} editingId={editingId} onFormChange={setCatForm} onCreate={startCreate} onEdit={startEdit} onCancel={cancelForm} onSave={savePet} onDelete={deletePet} onUploadImage={uploadPetImage} emptyText={qActive ? NO_MATCH : undefined}
              fields={[{ key: 'name', label: 'Название', ph: 'Лис Сильварис' }, { key: 'bonus_kind', label: 'Бонус', options: BONUS_KIND_OPTIONS }]}
              imageLabel="питомца"
            />
          )}

          {tab === 'products' && (
            <CatalogTab title="📦 Товары" items={shownProducts} busy={busy} form={catForm} formOpen={formOpen} editingId={editingId} onFormChange={setCatForm} onCreate={startCreate} onEdit={startEdit} onCancel={cancelForm} onSave={saveProduct} onDelete={deleteProduct} onUploadImage={uploadProductImage} emptyText={qActive ? NO_MATCH : undefined}
              fields={[
                { key: 'name', label: 'Название', ph: 'Яд' },
                { key: 'stars', label: 'Звёзды', ph: '1', type: 'number' },
                { key: 'production_kind', label: 'Производство', ph: '', options: prodTemplates.map((pt) => ({ value: pt.code, label: `${pt.emoji || ''} ${pt.name}` })) },
                { key: 'plant_id', label: 'Растение-источник', options: plants.filter((p) => !catalogProducts.some((x) => x.plant_id === p.id && x.id !== editingId)).map((p) => ({ value: String(p.id), label: `${p.emoji || ''} ${p.name}` })) },
                { key: 'animal_id', label: 'Животное-источник', options: animals.filter((a) => !catalogProducts.some((x) => x.animal_id === a.id && x.id !== editingId)).map((a) => ({ value: String(a.id), label: `${a.emoji || ''} ${a.name}` })) },
                { key: 'pet_id', label: 'Питомец-источник', options: pets.filter((pt) => !catalogProducts.some((x) => x.pet_id === pt.id && x.id !== editingId)).map((pt) => ({ value: String(pt.id), label: `${pt.emoji || ''} ${pt.name}` })) },
              ]}
            />
          )}

          {tab === 'productions' && (
            <CatalogTab title="🏭 Производства" items={shownProductions} busy={busy} form={catForm} formOpen={formOpen} editingId={editingId} onFormChange={setCatForm} onCreate={startCreate} onEdit={startEdit} onCancel={cancelForm} onSave={saveProduction} onDelete={deleteProduction} onUploadImage={uploadProductionImage} emptyText={qActive ? NO_MATCH : undefined}
              fields={[
                { key: 'name', label: 'Название', ph: 'Стол зельеварения' },
                { key: 'cards_to_draw', label: 'Карт для нормы', options: CARDS_DRAW_OPTIONS },
                { key: 'surcharge', label: 'Добавочная стоимость', options: SURCHARGE_OPTIONS },
                { key: 'processing_crystal', label: '💎 Кристалл переработки', ph: '0', type: 'number' },
              ]}
            />
          )}

          {tab === 'recipes' && renderRecipes()}
          {tab === 'customers' && renderCustomers()}
          {tab === 'levels' && renderLevels()}
          {tab === 'potion-recipes' && renderPotionRecipes()}
          {tab === 'cocktail-recipes' && renderCocktailRecipes()}
          {tab === 'ingredients' && renderIngredients()}
          {tab === 'infirmary' && (editorFieldId !== null ? (
            <FieldEditor fieldId={editorFieldId} onClose={() => setEditorFieldId(null)} />
          ) : renderInfirmary())}

          {tab === 'orders' && (
            <div>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
                <h2 style={{ margin: 0 }}>🧺 Все заказы</h2>
                <button type="button" className="fm-btn fm-btn-sm" disabled={busy} onClick={startCreateOrder}>
                  ➕ Создать заказ
                </button>
              </div>

              {orderFormOpen && (
                <div className="fm-card" style={{ marginBottom: 10 }}>
                  <h3 style={{ marginTop: 0 }}>{orderEditingId ? '✎ Редактировать заказ' : '➕ Создать заказ'}</h3>
                  {orderEditingId === null && (
                    <div style={{ marginBottom: 8 }}>
                      <label style={{ display: 'block', marginBottom: 4, fontSize: 13 }}>Тип заказа</label>
                      <select className="fm-input" value={orderForm.kind || 'product'} onChange={(e) => setOrderForm({ ...orderForm, kind: e.target.value })}>
                        <option value="product">📦 Товар</option>
                        <option value="potion">🧪 Зелье</option>
                      </select>
                    </div>
                  )}
                  {orderForm.kind === 'potion' ? (
                    <div style={{ marginBottom: 8 }}>
                      <label style={{ display: 'block', marginBottom: 4, fontSize: 13 }}>Зелье</label>
                      <select className="fm-input" value={orderForm.potion_recipe_id || ''} onChange={(e) => setOrderForm({ ...orderForm, potion_recipe_id: e.target.value })}>
                        <option value="">— выберите —</option>
                        {potionRecipes.map((r) => (
                          <option key={r.id} value={String(r.id)}>{r.name} ({r.level})</option>
                        ))}
                      </select>
                      <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 4 }}>
                        Заказ всегда на 1 зелье. Награда берётся из рецепта.
                      </div>
                    </div>
                  ) : (
                    <>
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
                    </>
                  )}
                  <div style={{ marginBottom: 8 }}>
                    <label style={{ display: 'block', marginBottom: 4, fontSize: 13 }}>Заказчик</label>
                    <select className="fm-input" value={orderForm.customer || ''} onChange={(e) => setOrderForm({ ...orderForm, customer: e.target.value })}>
                      <option value="">— не указан —</option>
                      {orderCustomerOptions.map((n) => (
                        <option key={n} value={n}>{n}</option>
                      ))}
                    </select>
                    {customers.some((c) => c.open_orders_count >= customerMaxOrders) && orderEditingId === null && (
                      <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 4 }}>
                        Заказчики с {customerMaxOrders} открытыми заказами скрыты
                      </div>
                    )}
                  </div>
                  <div style={{ marginBottom: 8 }}>
                    <label style={{ display: 'block', marginBottom: 4, fontSize: 13 }}>Реплика заказчика</label>
                    <textarea
                      className="fm-input"
                      rows={3}
                      value={orderForm.customer_phrase || ''}
                      onChange={(e) => setOrderForm({ ...orderForm, customer_phrase: e.target.value })}
                      placeholder="«Мне срочно нужны три склянки яда до заката!»"
                    />
                  </div>
                  {orderEditingId !== null && (
                    <>
                      <div style={{ marginBottom: 8 }}>
                        <label style={{ display: 'block', marginBottom: 4, fontSize: 13 }}>Награда (монет)</label>
                        <input className="fm-input" type="number" value={orderForm.reward_coins || ''} onChange={(e) => setOrderForm({ ...orderForm, reward_coins: e.target.value })} />
                      </div>
                      <div style={{ marginBottom: 8 }}>
                        <label style={{ display: 'block', marginBottom: 4, fontSize: 13 }}>Название (на карточке)</label>
                        <input className="fm-input" value={orderForm.name || ''} onChange={(e) => setOrderForm({ ...orderForm, name: e.target.value })} />
                      </div>
                    </>
                  )}
                  <div style={{ marginBottom: 8 }}>
                    <label style={{ display: 'block', marginBottom: 4, fontSize: 13 }}>Изображение</label>
                    <input type="file" accept="image/*" onChange={(e) => setOrderImage(e.target.files?.[0] ?? null)} style={{ fontSize: 13 }} />
                    {orderImage && <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 4 }}>{orderImage.name}</div>}
                  </div>
                  <div style={{ display: 'flex', gap: 8 }}>
                    <button type="button" className="fm-btn" disabled={busy} onClick={saveOrder}>💾 Сохранить</button>
                    <button type="button" className="fm-btn fm-btn-outline" disabled={busy} onClick={() => { setOrderFormOpen(false); setOrderEditingId(null); setOrderImage(null); }}>Отмена</button>
                  </div>
                </div>
              )}

              {shownOrders.length === 0 ? (
                <div className="fm-card" style={{ color: 'var(--text-muted)' }}>{qActive ? NO_MATCH : 'Заказов нет.'}</div>
              ) : (
                <div className="fm-grid">
                  {shownOrders.map((o) => {
                    return (
                      <div key={o.id} className="fm-card fm-rise" style={{ textAlign: 'center' }}>
                        <SpritePedestal url={o.image_url || o.product_image_url || o.potion_image_url ? mediaUrl(o.image_url || o.product_image_url || o.potion_image_url) : null} emoji={o.product_emoji} height={100} />
                        <strong style={{ display: 'block', marginBottom: 6 }}>{o.product_name} ×{o.qty}</strong>
                        {o.name && <div style={{ fontSize: 13, color: 'var(--text-secondary)', marginBottom: 6 }}>{o.name}</div>}
                        <div style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 4, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 5 }}>
                          {o.customer_image_url
                            ? <img src={mediaUrl(o.customer_image_url)} alt="" style={{ width: 20, height: 20, borderRadius: '50%', objectFit: 'cover' }} />
                            : o.customer ? <span>🧑</span> : null}
                          <span>{o.customer || '—'}</span>
                        </div>
                        {o.customer_phrase && (
                          <div style={{ fontSize: 12, fontStyle: 'italic', color: 'var(--text-secondary)', marginBottom: 8 }}>
                            «{(o.customer_phrase.length > 60 ? o.customer_phrase.slice(0, 60) + '…' : o.customer_phrase)}»
                          </div>
                        )}
                        <div
                          style={{
                            display: 'flex',
                            justifyContent: 'space-between',
                            alignItems: 'center',
                            gap: 8,
                            fontSize: 13,
                            borderTop: '1px solid var(--border)',
                            paddingTop: 8,
                            marginBottom: 8,
                          }}
                        >
                          <span style={{ color: 'var(--accent-warm)', fontWeight: 600, whiteSpace: 'nowrap' }}>🪙 {o.reward_coins}</span>
                        </div>
                        <div style={{ display: 'flex', gap: 6 }}>
                          <button type="button" className="fm-btn fm-btn-xs" style={{ flex: 1 }} disabled={busy} onClick={() => startEditOrder(o)}>✎</button>
                          {o.status === 'open' && (
                            <button type="button" className="fm-btn fm-btn-xs fm-btn-danger" style={{ flex: 1 }} disabled={busy} onClick={() => cancelOrder(o.id)}>
                              ✖️
                            </button>
                          )}
                          <button type="button" className="fm-btn fm-btn-xs fm-btn-danger" style={{ flex: 1 }} disabled={busy} onClick={() => deleteOrder(o.id)}>
                            🗑
                          </button>
                          <label className="fm-btn fm-btn-xs fm-btn-outline" style={{ cursor: 'pointer', flex: 1 }}>
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
                    );
                  })}
                </div>
              )}
            </div>
          )}

          {tab === 'media' && (
            <div>
              <h2 style={{ marginTop: 0 }}>🎬 Медиа (видео, картинки)</h2>
              <div className="fm-card" style={{ marginBottom: 10, display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'flex-end' }}>
                <div>
                  <label style={{ display: 'block', fontSize: 13, marginBottom: 2 }}>Тип медиа</label>
                  <select className="fm-input" value={mediaTypeSel} onChange={(e) => setMediaTypeSel(e.target.value)} style={{ width: 240 }}>
                    <option value="">— выберите —</option>
                    {MEDIA_TYPES.filter(mt => !gameMedia.some(gm => gm.code === mt.code)).map(mt => (
                      <option key={mt.code} value={mt.code}>{mt.label}</option>
                    ))}
                  </select>
                </div>
                <button type="button" className="fm-btn fm-btn-sm" disabled={busy || !mediaTypeSel} onClick={saveGameMedia}>➕ Создать</button>
              </div>
              <div className="fm-grid">
                {shownMedia.map((gm) => {
                  const label = MEDIA_TYPES.find(m => m.code === gm.code)?.label || gm.code;
                  return (
                    <div key={gm.id} className="fm-card fm-rise" style={{ fontSize: 13 }}>
                      <strong>{label}</strong>
                      <div style={{ color: 'var(--text-muted)', marginTop: 2 }}>{gm.kind}</div>
                      {gm.url ? (
                        <div style={{ marginTop: 4, fontSize: 12, color: '#5f8' }}>✓ Загружено</div>
                      ) : (
                        <div style={{ marginTop: 4, fontSize: 12, color: '#f88' }}>Файла нет</div>
                      )}
                      <div style={{ display: 'flex', gap: 4, marginTop: 6, flexWrap: 'wrap' }}>
                        <label className="fm-btn fm-btn-xs fm-btn-outline" style={{ cursor: 'pointer' }}>
                          📁
                          <input type="file" accept="image/*,video/*" style={{ display: 'none' }}
                            onChange={async (e) => { const f = e.target.files?.[0]; if (f) await uploadGameMediaFile(gm.id, f); }} />
                        </label>
                        <button type="button" className="fm-btn fm-btn-xs fm-btn-danger" disabled={busy} onClick={() => deleteGameMedia(gm.id)}>🗑</button>
                      </div>
                    </div>
                  );
                })}
              </div>
              {gameMedia.length === 0 && <div className="fm-card" style={{ color: 'var(--text-muted)', fontSize: 13 }}>Медиа пока нет. Выберите тип из списка и создайте запись для загрузки файла.</div>}
              {qActive && shownMedia.length === 0 && <div className="fm-card" style={{ color: 'var(--text-muted)', fontSize: 13 }}>{NO_MATCH}</div>}
            </div>
          )}

          {tab === 'story' && (
            <div>
              <h2 style={{ marginTop: 0 }}>📜 Предыстория</h2>
              <div className="fm-card" style={{ marginBottom: 10 }}>
                <label style={{ display: 'block', marginBottom: 4, fontSize: 13 }}>Текст слайда</label>
                <textarea className="fm-input" rows={4} value={storyForm.text} onChange={(e) => setStoryForm({ ...storyForm, text: e.target.value })} placeholder="Текст слайда предыстории…" />
                <label style={{ display: 'block', fontSize: 13, margin: '8px 0 4px' }}>Картинка слайда</label>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
                  <label className="fm-btn fm-btn-sm fm-btn-outline" style={{ cursor: 'pointer', flexShrink: 0 }}>
                    {storyImage ? '🖼️ Заменить' : '🖼️ Выбрать картинку'}
                    <input type="file" accept="image/*" hidden onChange={(e) => { setStoryImage(e.target.files?.[0] || null); e.target.value = ''; }} />
                  </label>
                  {storyImage && (
                    <>
                      <img src={URL.createObjectURL(storyImage)} alt="" style={{ height: 44, maxWidth: 120, objectFit: 'contain', borderRadius: 6 }} />
                      <button type="button" className="fm-btn fm-btn-xs fm-btn-danger" onClick={() => setStoryImage(null)}>✕</button>
                    </>
                  )}
                </div>
                <div style={{ display: 'flex', gap: 8, marginTop: 8, alignItems: 'flex-end', flexWrap: 'wrap' }}>
                  <div>
                    <label style={{ display: 'block', fontSize: 13, marginBottom: 2 }}>Локация (DLC)</label>
                    <select className="fm-input" value={storyForm.location_code} onChange={(e) => setStoryForm({ ...storyForm, location_code: e.target.value })} style={{ width: 200 }}>
                      <option value="">— общая предыстория —</option>
                      {dlcLocations.map((l) => <option key={l.code} value={l.code}>{l.name} ({l.code})</option>)}
                    </select>
                  </div>
                  <div>
                    <label style={{ display: 'block', fontSize: 13, marginBottom: 2 }}>Порядок</label>
                    <input className="fm-input" type="number" min={0} value={storyForm.sort_order} onChange={(e) => setStoryForm({ ...storyForm, sort_order: e.target.value })} style={{ width: 90 }} />
                  </div>
                  <button type="button" className="fm-btn" disabled={busy} onClick={saveStorySlide}>
                    {storyEditingId ? '✎ Сохранить' : '➕ Добавить слайд'}
                  </button>
                  {storyEditingId && (
                    <button type="button" className="fm-btn" onClick={() => { setStoryEditingId(null); setStoryForm({ text: '', sort_order: '0', location_code: '' }); setStoryImage(null); }}>Отмена</button>
                  )}
                </div>
                <p style={{ fontSize: 12, color: 'var(--text-muted)', margin: '8px 0 0' }}>
                  «Общая предыстория» показывается игроку один раз при входе, до настройки норм. Слайды DLC-локации показываются при первом открытии дополнения.
                </p>
              </div>
              <div className="fm-grid">
                {shownStorySlides.map((s) => (
                  <div key={s.id} className="fm-card fm-rise" style={{ fontSize: 13 }}>
                    {s.image_url && <img src={mediaUrl(s.image_url)} alt="" style={{ width: '100%', maxHeight: 120, objectFit: 'contain', borderRadius: 'var(--radius-sm)', marginBottom: 6 }} />}
                    <strong style={{ display: 'block', marginBottom: 4 }}>#{s.sort_order} {s.location_code ? `· ${s.location_code}` : ''}</strong>
                    <div style={{ whiteSpace: 'pre-wrap', color: 'var(--text-secondary)', marginBottom: 6 }}>{s.text || '—'}</div>
                    <div style={{ display: 'flex', gap: 4 }}>
                      <button type="button" className="fm-btn fm-btn-xs" disabled={busy} onClick={() => { setStoryEditingId(s.id); setStoryForm({ text: s.text || '', sort_order: String(s.sort_order), location_code: s.location_code || '' }); setStoryImage(null); }}>✎</button>
                      <label className="fm-btn fm-btn-xs fm-btn-outline" style={{ cursor: 'pointer' }}>
                        🖼️
                        <input type="file" accept="image/*" hidden onChange={(e) => { const f = e.target.files?.[0]; if (f) uploadStoryImage(s.id, f); e.target.value = ''; }} />
                      </label>
                      <button type="button" className="fm-btn fm-btn-xs fm-btn-danger" disabled={busy} onClick={() => deleteStorySlide(s.id)}>🗑</button>
                    </div>
                  </div>
                ))}
              </div>
              {storySlides.length === 0 && <div className="fm-card" style={{ color: 'var(--text-muted)', fontSize: 13 }}>Слайдов пока нет — добавьте предысторию.</div>}
              {qActive && shownStorySlides.length === 0 && <div className="fm-card" style={{ color: 'var(--text-muted)', fontSize: 13 }}>{NO_MATCH}</div>}
            </div>
          )}

          {tab === 'lessons' && (
            <div>
              <h2 style={{ marginTop: 0 }}>🎬 Видео-уроки</h2>
              <div className="fm-card" style={{ marginBottom: 10 }}>
                <label style={{ display: 'block', marginBottom: 4, fontSize: 13 }}>Название</label>
                <input className="fm-input" value={lessonForm.title} onChange={(e) => setLessonForm({ ...lessonForm, title: e.target.value })} placeholder="Например: как сажать растения" />
                <label style={{ display: 'block', margin: '8px 0 4px', fontSize: 13 }}>Описание</label>
                <textarea className="fm-input" rows={3} value={lessonForm.description} onChange={(e) => setLessonForm({ ...lessonForm, description: e.target.value })} placeholder="Короткое описание урока…" />
                <label style={{ display: 'block', fontSize: 13, margin: '8px 0 4px' }}>Видео урока</label>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
                  <label className="fm-btn fm-btn-sm fm-btn-outline" style={{ cursor: 'pointer', flexShrink: 0 }}>
                    {lessonVideo ? '🎬 Заменить' : '🎬 Выбрать видео'}
                    <input type="file" accept="video/*" hidden onChange={(e) => { setLessonVideo(e.target.files?.[0] || null); e.target.value = ''; }} />
                  </label>
                  {lessonVideo && (
                    <>
                      <video src={URL.createObjectURL(lessonVideo)} controls playsInline style={{ height: 48, maxWidth: 140, borderRadius: 6 }} />
                      <button type="button" className="fm-btn fm-btn-xs fm-btn-danger" onClick={() => setLessonVideo(null)}>✕</button>
                    </>
                  )}
                </div>
                <label style={{ display: 'block', fontSize: 13, margin: '8px 0 4px' }}>Фото-обложка урока</label>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
                  <label className="fm-btn fm-btn-sm fm-btn-outline" style={{ cursor: 'pointer', flexShrink: 0 }}>
                    {lessonImage ? '🖼️ Заменить' : '🖼️ Выбрать фото'}
                    <input type="file" accept="image/*" hidden onChange={(e) => { setLessonImage(e.target.files?.[0] || null); e.target.value = ''; }} />
                  </label>
                  {lessonImage && (
                    <>
                      <img src={URL.createObjectURL(lessonImage)} alt="" style={{ height: 48, maxWidth: 120, objectFit: 'contain', borderRadius: 6 }} />
                      <button type="button" className="fm-btn fm-btn-xs fm-btn-danger" onClick={() => setLessonImage(null)}>✕</button>
                    </>
                  )}
                </div>
                <div style={{ display: 'flex', gap: 8, marginTop: 8, alignItems: 'center', flexWrap: 'wrap' }}>
                  <div>
                    <label style={{ display: 'block', fontSize: 13, marginBottom: 2 }}>Порядок</label>
                    <input className="fm-input" type="number" min={0} value={lessonForm.sort_order} onChange={(e) => setLessonForm({ ...lessonForm, sort_order: e.target.value })} style={{ width: 90 }} />
                  </div>
                  <button type="button" className="fm-btn" disabled={busy} onClick={saveLesson} style={{ marginTop: 18 }}>
                    {lessonEditingId ? '✎ Сохранить' : '➕ Добавить урок'}
                  </button>
                  {lessonEditingId && (
                    <button type="button" className="fm-btn" style={{ marginTop: 18 }} onClick={() => { setLessonEditingId(null); setLessonForm({ title: '', description: '', sort_order: '0' }); setLessonVideo(null); setLessonImage(null); }}>Отмена</button>
                  )}
                </div>
              </div>
              <div className="fm-grid">
                {shownLessons.map((l) => (
                  <div key={l.id} className="fm-card fm-rise" style={{ fontSize: 13 }}>
                    <strong>{l.title}</strong>
                    {l.image_url && <img src={mediaUrl(l.image_url)} alt="" style={{ width: '100%', maxHeight: 90, objectFit: 'contain', borderRadius: 8, marginTop: 6 }} />}
                    {l.video_url && (
                      <video src={mediaUrl(l.video_url)} controls playsInline style={{ width: '100%', maxHeight: 160, borderRadius: 8, marginTop: 6, marginBottom: 6 }} />
                    )}
                    <div style={{ color: 'var(--text-secondary)', marginTop: 4, whiteSpace: 'pre-wrap' }}>{l.description || '—'}</div>
                    <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 4 }}>#{l.sort_order}</div>
                    <div style={{ display: 'flex', gap: 4, marginTop: 6 }}>
                      <button type="button" className="fm-btn fm-btn-xs" disabled={busy} onClick={() => { setLessonEditingId(l.id); setLessonForm({ title: l.title, description: l.description || '', sort_order: String(l.sort_order) }); setLessonVideo(null); setLessonImage(null); }}>✎</button>
                      <label className="fm-btn fm-btn-xs fm-btn-outline" style={{ cursor: 'pointer' }}>
                        🎬
                        <input type="file" accept="video/*" hidden onChange={(e) => { const f = e.target.files?.[0]; if (f) uploadLessonVideo(l.id, f); e.target.value = ''; }} />
                      </label>
                      <label className="fm-btn fm-btn-xs fm-btn-outline" style={{ cursor: 'pointer' }}>
                        🖼️
                        <input type="file" accept="image/*" hidden onChange={(e) => { const f = e.target.files?.[0]; if (f) uploadLessonImage(l.id, f); e.target.value = ''; }} />
                      </label>
                      <button type="button" className="fm-btn fm-btn-xs fm-btn-danger" disabled={busy} onClick={() => deleteLesson(l.id)}>🗑</button>
                    </div>
                  </div>
                ))}
              </div>
              {lessons.length === 0 && <div className="fm-card" style={{ color: 'var(--text-muted)', fontSize: 13 }}>Уроков пока нет.</div>}
              {qActive && shownLessons.length === 0 && <div className="fm-card" style={{ color: 'var(--text-muted)', fontSize: 13 }}>{NO_MATCH}</div>}
            </div>
          )}

          {tab === 'achievements' && (
            <div>
              <h2 style={{ marginTop: 0 }}>🏆 Достижения</h2>
              <div className="fm-card" style={{ marginBottom: 10 }}>
                <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 8, alignItems: 'center' }}>
                  <input className="fm-input" placeholder="Название" value={achForm.name} onChange={(e) => setAchForm({ ...achForm, name: e.target.value })} style={{ width: 160 }} />
                  <select className="fm-input" value={achForm.condition_kind} onChange={(e) => setAchForm({ ...achForm, condition_kind: e.target.value })} style={{ width: 180 }}>
                    <option value="">— тип условия —</option>
                    {achKinds.map((k) => <option key={k.kind} value={k.kind}>{k.label}</option>)}
                  </select>
                  {achForm.condition_kind === 'tents_count' && (
                    <select className="fm-input" value={achForm.production_code || ''} onChange={(e) => setAchForm({ ...achForm, production_code: e.target.value })} style={{ width: 180 }}>
                      <option value="">— любой шатёр —</option>
                      {prodTemplates.map((pt) => <option key={pt.code} value={pt.code}>{pt.emoji || ''} {pt.name}</option>)}
                    </select>
                  )}
                  <input className="fm-input" type="number" placeholder="Значение" value={achForm.condition_value} onChange={(e) => setAchForm({ ...achForm, condition_value: e.target.value })} style={{ width: 80 }} />
                </div>
                {(() => { const k = achKinds.find((x) => x.kind === achForm.condition_kind); return k?.hint ? <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 8 }}>{k.hint}</div> : null; })()}
                {achEditingId && (() => { const cur = achievements.find((x) => x.id === achEditingId); return cur?.image_url ? <img src={mediaUrl(cur.image_url)} alt="" style={{ width: 56, height: 56, objectFit: 'cover', borderRadius: 'var(--radius-sm)', marginBottom: 8 }} /> : null; })()}
                <div style={{ marginBottom: 8 }}>
                  <input type="file" accept="image/*" onChange={(e) => setAchImage(e.target.files?.[0] ?? null)} style={{ fontSize: 13 }} />
                  {achImage && <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 4 }}>{achImage.name}</div>}
                </div>
                <button type="button" className="fm-btn" disabled={busy} onClick={saveAchievement}>
                  {achEditingId ? '✎ Сохранить' : '➕ Создать'}
                </button>
                {achEditingId && <button type="button" className="fm-btn" style={{ marginLeft: 6 }} onClick={() => { setAchEditingId(null); setAchForm({ name: '', condition_kind: '', condition_value: '1', production_code: '' }); setAchImage(null); }}>Отмена</button>}
              </div>
              <div className="fm-grid">
                {shownAchievements.map((a) => (
                  <div key={a.id} className="fm-card fm-rise" style={{ fontSize: 13 }}>
                    {a.image_url && <img src={mediaUrl(a.image_url)} alt="" style={{ width: 56, height: 56, objectFit: 'cover', borderRadius: 'var(--radius-sm)', marginBottom: 6 }} />}
                    <strong>{a.name}</strong>
                    <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>{achKinds.find((x) => x.kind === a.condition_kind)?.label ?? a.condition_kind}: {a.condition_value}</div>
                    <div style={{ display: 'flex', gap: 4, marginTop: 6 }}>
                      <button type="button" className="fm-btn fm-btn-xs" disabled={busy} onClick={() => { setAchEditingId(a.id); setAchForm({ name: a.name, condition_kind: a.condition_kind, condition_value: String(a.condition_value), production_code: a.production_code || '' }); setAchImage(null); }}>✎</button>
                      <label className="fm-btn fm-btn-xs fm-btn-outline" style={{ cursor: 'pointer' }}>
                        🖼️
                        <input type="file" accept="image/*" hidden onChange={(e) => { const f = e.target.files?.[0]; if (f) uploadAchImage(a.id, f); e.target.value = ''; }} />
                      </label>
                      <button type="button" className="fm-btn fm-btn-xs fm-btn-danger" disabled={busy} onClick={() => deleteAchievement(a.id)}>🗑</button>
                    </div>
                  </div>
                ))}
              </div>
              {achievements.length === 0 && <div className="fm-card" style={{ color: 'var(--text-muted)', fontSize: 13 }}>Достижений пока нет.</div>}
              {qActive && shownAchievements.length === 0 && <div className="fm-card" style={{ color: 'var(--text-muted)', fontSize: 13 }}>{NO_MATCH}</div>}
            </div>
          )}

          {tab === 'crystal-cards' && (
            <div>
              <h2 style={{ marginTop: 0 }}>🃏 Карты кристаллов ({shownCards.length}{qActive ? ` из ${crystalCards.length}` : ''})</h2>
              <div className="fm-grid">
                {shownCards.map((card) => (
                  <div key={card.id} className="fm-card fm-rise" style={{ fontSize: 13, textAlign: 'center' }}>
                    {card.image_url ? (
                      <img src={mediaUrl(card.image_url)} alt="" style={{ width: 80, height: 80, objectFit: 'contain', marginBottom: 4 }} />
                    ) : (
                      <div style={{ width: 80, height: 80, background: 'var(--bg-card)', borderRadius: 'var(--radius-sm)', margin: '0 auto 4px', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 24 }}>
                        {card.is_treasure ? '💎' : card.color === 'green' ? '🟢' : card.color === 'blue' ? '🔵' : '🟣'}
                      </div>
                    )}
                    <div>
                      {card.is_treasure ? 'Сокровище' : `${card.color} ×${card.value}`}
                    </div>
                    <label className="fm-btn fm-btn-xs fm-btn-outline" style={{ cursor: 'pointer', marginTop: 4 }}>
                      🖼️
                      <input type="file" accept="image/*" style={{ display: 'none' }}
                        onChange={async (e) => { const f = e.target.files?.[0]; if (f) await uploadCrystalCardImage(card.id, f); }} />
                    </label>
                  </div>
                ))}
              </div>
            </div>
          )}

          {tab === 'logs' && (
            <div>
              <h2 style={{ marginTop: 0 }}>📜 Логи фермы</h2>
              <div className="fm-card" style={{ marginBottom: 10, display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
                <select className="fm-input" value={logFilter.source} onChange={(e) => setLogFilter({ ...logFilter, source: e.target.value })} style={{ width: 130 }}>
                  <option value="">Источник: все</option>
                  <option value="server">🖥 Сервер</option>
                  <option value="vk">🟢 ВК</option>
                </select>
                <select className="fm-input" value={logFilter.level} onChange={(e) => setLogFilter({ ...logFilter, level: e.target.value })} style={{ width: 140 }}>
                  <option value="">Уровень: все</option>
                  <option value="error">Ошибка</option>
                  <option value="warn">Предупреждение</option>
                </select>
                <input className="fm-input" placeholder="user_id" value={logFilter.user_id} onChange={(e) => setLogFilter({ ...logFilter, user_id: e.target.value })} style={{ width: 90 }} />
                <input className="fm-input" placeholder="Поиск (путь / событие / текст)" value={logFilter.q} onChange={(e) => setLogFilter({ ...logFilter, q: e.target.value })} style={{ flex: 1, minWidth: 180 }} />
                <button type="button" className="fm-btn" disabled={busy} onClick={() => { setLogOffset(0); loadLogs(false); }}>🔄 Обновить</button>
                <button type="button" className="fm-btn fm-btn-danger" disabled={busy} onClick={clearLogs}>🗑 Очистить</button>
              </div>

              {logs.length === 0 && <div className="fm-card" style={{ color: 'var(--text-muted)', fontSize: 13 }}>Логов пока нет.</div>}

              <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                {logs.filter((l) => l.level !== 'info').map((l) => {
                  const lvlColor = l.level === 'error' ? '#e55' : l.level === 'warn' ? '#e90' : 'var(--text-muted)';
                  const srcColor = l.source === 'vk' ? '#3a7a4f' : '#3a5a7a';
                  return (
                    <div key={l.id} className="fm-card" style={{ padding: 10, fontSize: 13, cursor: l.details ? 'pointer' : 'default' }} onClick={() => l.details && setExpandedLog(expandedLog === l.id ? null : l.id)}>
                      <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
                        <span style={{ fontSize: 11, color: 'var(--text-muted)', fontFamily: 'monospace' }}>{fmtMsk(l.created_at)}</span>
                        <span style={{ background: srcColor, color: '#fff', borderRadius: 4, padding: '1px 6px', fontSize: 11 }}>{l.source === 'vk' ? 'VK' : 'СЕРВ'}</span>
                        <span style={{ color: lvlColor, fontWeight: 600, fontSize: 11 }}>{l.level.toUpperCase()}</span>
                        {l.status_code != null && <span style={{ fontSize: 11, fontFamily: 'monospace' }}>{l.status_code}</span>}
                        <span style={{ fontFamily: 'monospace', fontSize: 12 }}>{l.method} {l.path}</span>
                        {l.event && <span style={{ fontSize: 11, color: 'var(--text-secondary)' }}>· {l.event}</span>}
                        {l.user_id != null && <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>· u{l.user_id}</span>}
                      </div>
                      {l.message && <div style={{ marginTop: 4, color: 'var(--text-secondary)' }}>{l.message}</div>}
                      {expandedLog === l.id && l.details && (
                        <pre style={{ marginTop: 6, whiteSpace: 'pre-wrap', wordBreak: 'break-word', fontSize: 11, background: 'rgba(0,0,0,0.25)', padding: 8, borderRadius: 6 }}>{l.details}</pre>
                      )}
                    </div>
                  );
                })}
              </div>

              {logHasMore && (
                <div style={{ textAlign: 'center', marginTop: 10 }}>
                  <button type="button" className="fm-btn fm-btn-outline" disabled={busy} onClick={() => loadLogs(true)}>Показать ещё</button>
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
      <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
        <input className="fm-input" style={{ flex: '1 1 180px', minWidth: 0 }} value={v} onChange={(e) => setV(e.target.value)} />
        <button type="button" className="fm-btn fm-btn-sm" style={{ flexShrink: 0 }} disabled={disabled || v === value} onClick={() => onSave(v)}>
          OK
        </button>
      </div>
    </div>
  );
}

function PlantNormEditor({ vkId, plantId, initial, onSaved }: { vkId: number; plantId: number; initial: number; onSaved: () => void }) {
  const [val, setVal] = useState(String(initial));
  const [busy, setBusy] = useState(false);
  return (
    <div style={{ display: 'flex', gap: 4, alignItems: 'center', flexWrap: 'wrap' }}>
      <input
        className="fm-input"
        type="number"
        min={0}
        value={val}
        onChange={(e) => setVal(e.target.value)}
        style={{ width: 80 }}
        aria-label="Цена 1 растения"
      />
      <button
        className="fm-btn fm-btn-sm"
        disabled={busy}
        onClick={async () => {
          setBusy(true);
          try {
            await api.adminSetPlantNorm(vkId, plantId, Math.max(0, Number(val) || 0));
            onSaved();
          } finally {
            setBusy(false);
          }
        }}
      >
        💾
      </button>
    </div>
  );
}

function TabBtn({ active, onClick, children }: { active: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <button type="button" className={active ? 'fm-btn fm-btn-sm' : 'fm-btn fm-btn-sm fm-btn-outline'} onClick={onClick}>
      {children}
    </button>
  );
}

interface CatField { key: string; label: string; ph?: string; type?: string; options?: { value: string; label: string }[] }

function CatalogTab({
  title, items, busy, form, formOpen, editingId, onFormChange, onCreate, onEdit, onCancel, onSave, onDelete, onUploadImage, onUploadImageYoung, onUploadImageGrown, onUploadImageEmptyPen, onUploadImagePen, onUploadImageHarvested, fields, imageLabel = 'Изображение', hideMainImage = false, emptyText, showLevel = false,
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
  onUploadImageEmptyPen?: (id: number, file: File) => Promise<void>;
  onUploadImagePen?: (id: number, file: File) => Promise<void>;
  onUploadImageHarvested?: (id: number, file: File) => Promise<void>;
  fields: CatField[];
  imageLabel?: string;
  hideMainImage?: boolean;
  emptyText?: string;
  showLevel?: boolean;
}) {
  const [pendingUpload, setPendingUpload] = useState<{ file: File; cb: (id: number, f: File) => Promise<void> } | null>(null);

  useEffect(() => {
    if (pendingUpload && editingId) {
      pendingUpload.cb(editingId, pendingUpload.file).catch(() => {});
      setPendingUpload(null);
    }
  }, [editingId, pendingUpload]);

  async function handleFile(f: File | undefined, cb: (id: number, f: File) => Promise<void>) {
    if (!f) return;
    const compressed = await compressImage(f);
    if (!editingId) {
      if (!form.name?.trim()) onFormChange({ ...form, name: 'Новое' });
      setPendingUpload({ file: compressed, cb });
      onSave();
    } else {
      await cb(editingId, compressed);
    }
  }

  return (
    <>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
        <h2 style={{ margin: 0 }}>{title}</h2>
        <button type="button" className="fm-btn fm-btn-sm" disabled={busy} onClick={onCreate}>
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
            <button type="button" className="fm-btn" disabled={busy} onClick={onSave}>💾 Сохранить</button>
            <button type="button" className="fm-btn fm-btn-outline" disabled={busy} onClick={onCancel}>Отмена</button>
          </div>
          <div style={{ marginTop: 10, display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            {!hideMainImage && (
              <label className="fm-btn fm-btn-sm fm-btn-outline" style={{ cursor: 'pointer' }}>
                🖼️ {imageLabel}
                <input type="file" accept="image/*" hidden onChange={(e) => handleFile(e.target.files?.[0], onUploadImage)} />
              </label>
            )}
            {onUploadImageYoung && (
              <label className="fm-btn fm-btn-sm fm-btn-outline" style={{ cursor: 'pointer' }}>
                🌱 Молодое
                <input type="file" accept="image/*" hidden onChange={(e) => handleFile(e.target.files?.[0], onUploadImageYoung!)} />
              </label>
            )}
            {onUploadImageGrown && (
              <label className="fm-btn fm-btn-sm fm-btn-outline" style={{ cursor: 'pointer' }}>
                🌳 Созревшее
                <input type="file" accept="image/*" hidden onChange={(e) => handleFile(e.target.files?.[0], onUploadImageGrown!)} />
              </label>
            )}
            {onUploadImageHarvested && (
              <label className="fm-btn fm-btn-sm fm-btn-outline" style={{ cursor: 'pointer' }}>
                🧺 Выращенное
                <input type="file" accept="image/*" hidden onChange={(e) => handleFile(e.target.files?.[0], onUploadImageHarvested!)} />
              </label>
            )}
            {onUploadImageEmptyPen && (
              <label className="fm-btn fm-btn-sm fm-btn-outline" style={{ cursor: 'pointer' }}>
                🏚️ Загон
                <input type="file" accept="image/*" hidden onChange={(e) => handleFile(e.target.files?.[0], onUploadImageEmptyPen!)} />
              </label>
            )}
            {onUploadImagePen && (
              <label className="fm-btn fm-btn-sm fm-btn-outline" style={{ cursor: 'pointer' }}>
                🐄 Выращенное
                <input type="file" accept="image/*" hidden onChange={(e) => handleFile(e.target.files?.[0], onUploadImagePen!)} />
              </label>
            )}
          </div>
        </div>
      )}

      {items.length === 0 ? (
        <div className="fm-card" style={{ color: 'var(--text-muted)' }}>{emptyText ?? 'Пусто. Нажмите «Добавить».'}</div>
      ) : (
        <div className="fm-grid">
          {items.map((item) => {
            return (
              <div key={item.id} className="fm-card fm-rise">
                <div style={{ marginBottom: 4 }}>
                  <strong style={{ wordBreak: 'break-word' }}>{item.emoji || '❔'} {item.name}</strong>
                  <div style={{ fontSize: 12, color: 'var(--text-muted)', wordBreak: 'break-all' }}>{item.code}</div>
                  {showLevel && item.level != null && (
                    <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginTop: 2 }}>Уровень {item.level}</div>
                  )}
                </div>
                {!hideMainImage && item.image_url && (
                  <img src={mediaUrl(item.image_url)} alt="" style={{ width: 56, height: 56, objectFit: 'cover', borderRadius: 'var(--radius-sm)', marginBottom: 6 }} />
                )}
                {(item.image_young_url || item.image_grown_url || item.image_harvested_url) && (
                  <div style={{ display: 'flex', gap: 8, marginBottom: 6, flexWrap: 'wrap' }}>
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
                    <div style={{ textAlign: 'center' }}>
                      {item.image_harvested_url && (
                        <img src={mediaUrl(item.image_harvested_url)} alt="выращенное" style={{ width: 56, height: 56, objectFit: 'cover', borderRadius: 'var(--radius-sm)', display: 'block' }} />
                      )}
                      <div style={{ fontSize: 10, color: 'var(--text-muted)', marginTop: 2 }}>выращенное</div>
                    </div>
                  </div>
                )}
                {(item.image_empty_pen_url || item.image_pen_url) && (
                  <div style={{ display: 'flex', gap: 8, marginBottom: 6, flexWrap: 'wrap' }}>
                    {item.image_empty_pen_url && (
                      <div style={{ textAlign: 'center' }}>
                        <img src={mediaUrl(item.image_empty_pen_url)} alt="пустой загон" style={{ width: 48, height: 48, objectFit: 'cover', borderRadius: 'var(--radius-sm)' }} />
                        <div style={{ fontSize: 9, color: 'var(--text-muted)' }}>загон</div>
                      </div>
                    )}
                    {item.image_pen_url && (
                      <div style={{ textAlign: 'center' }}>
                        <img src={mediaUrl(item.image_pen_url)} alt="загон с животным" style={{ width: 48, height: 48, objectFit: 'cover', borderRadius: 'var(--radius-sm)' }} />
                        <div style={{ fontSize: 9, color: 'var(--text-muted)' }}>с животным</div>
                      </div>
                    )}
                    {item.image_harvested_url && (
                      <div style={{ textAlign: 'center' }}>
                        <img src={mediaUrl(item.image_harvested_url)} alt="выращенное" style={{ width: 48, height: 48, objectFit: 'cover', borderRadius: 'var(--radius-sm)' }} />
                        <div style={{ fontSize: 9, color: 'var(--text-muted)' }}>выращенное</div>
                      </div>
                    )}
                  </div>
                )}
                {onUploadImageYoung ? (
                  <div style={{ display: 'flex', gap: 4, marginTop: 8, flexWrap: 'wrap' }}>
                    <button type="button" className="fm-btn fm-btn-xs" disabled={busy} onClick={() => onEdit(item)}>✎</button>
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
                    {onUploadImageHarvested && (
                      <label className="fm-btn fm-btn-xs fm-btn-outline" title="Загрузить выращенное растение" style={{ cursor: 'pointer' }}>
                        🧺
                        <input type="file" accept="image/*" style={{ display: 'none' }}
                          onChange={async (e) => { const f = e.target.files?.[0]; if (f && onUploadImageHarvested) await onUploadImageHarvested(item.id, f); }}
                        />
                      </label>
                    )}
                    <button type="button" className="fm-btn fm-btn-xs fm-btn-danger" disabled={busy} onClick={() => onDelete(item.id)}>✕</button>
                  </div>
                ) : (
                  <div style={{ display: 'flex', gap: 4, marginTop: 8, flexWrap: 'wrap' }}>
                    <button type="button" className="fm-btn fm-btn-xs" disabled={busy} onClick={() => onEdit(item)}>✎</button>
                    {!hideMainImage && (
                      <label className="fm-btn fm-btn-xs fm-btn-outline" title="Загрузить изображение" style={{ cursor: 'pointer' }}>
                        🖼️
                        <input type="file" accept="image/*" style={{ display: 'none' }}
                          onChange={async (e) => {
                            const file = e.target.files?.[0];
                            if (file) { await onUploadImage(item.id, file); }
                          }}
                        />
                      </label>
                    )}
                    <button type="button" className="fm-btn fm-btn-xs fm-btn-danger" disabled={busy} onClick={() => onDelete(item.id)}>✕</button>
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

