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
  active: { label: 'Р°РєС‚РёРІРµРЅ', emoji: 'рџџў' },
  blocked: { label: 'Р·Р°Р±Р»РѕРєРёСЂРѕРІР°РЅ', emoji: 'рџљ«' },
  readonly: { label: 'С‚РѕР»СЊРєРѕ РїСЂРѕСЃРјРѕС‚СЂ', emoji: 'рџ‘Ѓ' },
};

const BONUS_KIND_OPTIONS = [
  { value: 'harvest_orchard', label: 'рџЌЋ +1 Рє СѓСЂРѕР¶Р°СЋ СЃР°РґР°' },
  { value: 'harvest_plot', label: 'рџЊ± +1 Рє СѓСЂРѕР¶Р°СЋ РіСЂСЏРґРєРё' },
  { value: 'order_coins', label: 'рџ’° +5 РјРѕРЅРµС‚ Рє Р·Р°РєР°Р·Сѓ' },
  { value: 'craft_bonus', label: 'рџЏ­ +1 С‚РѕРІР°СЂ РїСЂРё РєСЂР°С„С‚Рµ' },
  { value: 'animal_product', label: 'рџђ„ +1 РїСЂРѕРґСѓРєС†РёСЏ Р¶РёРІРѕС‚РЅРѕРіРѕ' },
];

const CARDS_DRAW_OPTIONS = [
  { value: '3', label: '3 РєР°СЂС‚С‹' },
  { value: '4', label: '4 РєР°СЂС‚С‹' },
  { value: '5', label: '5 РєР°СЂС‚' },
];

function fmtMsk(iso: string): string {
  const hasZone = /(Z|[+-]\d{2}:?\d{2})$/.test(iso);
  const d = new Date(hasZone ? iso : iso + 'Z');
  return d.toLocaleString('ru-RU', { timeZone: 'Europe/Moscow' });
}

const SURCHARGE_OPTIONS = [
  { value: '30', label: '30 РјРѕРЅРµС‚' },
  { value: '35', label: '35 РјРѕРЅРµС‚' },
  { value: '40', label: '40 РјРѕРЅРµС‚' },
];

const SETTING_FIELDS: { key: string; label: string; hint: string }[] = [
  { key: 'auto_credit', label: 'РђРІС‚Рѕ-Р·Р°С‡С‘С‚ РІС‹С€РёРІРєРё (0/1)', hint: '1 вЂ” РєСЂРµСЃС‚РёРєРё РЅР°С‡РёСЃР»СЏСЋС‚СЃСЏ СЃСЂР°Р·Сѓ Р±РµР· РјРѕРґРµСЂР°С†РёРё' },
  { key: 'default_plant_qty', label: 'РљРѕР»-РІРѕ СЂР°СЃС‚РµРЅРёР№ РІ Р·Р°РєР°Р·Рµ (1вЂ“50)', hint: 'РџРѕ СѓРјРѕР»С‡Р°РЅРёСЋ РїСЂРё РїРѕСЃР°РґРєРµ' },
  { key: 'production_required', label: 'РќРѕСЂРјР° С†РёРєР»Р° РїСЂРѕРёР·РІРѕРґСЃС‚РІР°', hint: 'РљСЂРµСЃС‚РёРєРё Р·Р° РѕРґРёРЅ С†РёРєР» РєСЂР°С„С‚Р°' },
  { key: 'order_reward_per_unit', label: 'РќР°РіСЂР°РґР° Р·Р° РµРґРёРЅРёС†Сѓ Р·Р°РєР°Р·Р°', hint: 'РњРѕРЅРµС‚ Р·Р° 1 С‚РѕРІР°СЂ' },
  { key: 'sale_price_ratio', label: 'РљРѕСЌС„С„. РїСЂРѕРґР°Р¶Рё РёР·Р»РёС€РєРѕРІ (0.01вЂ“1.0)', hint: 'Р”РѕР»СЏ РѕС‚ РїРѕР»РЅРѕР№ С†РµРЅС‹ (0.5 = ВЅ)' },
  { key: 'customer_max_orders', label: 'Р›РёРјРёС‚ Р°РєС‚РёРІРЅС‹С… Р·Р°РєР°Р·РѕРІ Р·Р°РєР°Р·С‡РёРєР° (0вЂ“50)', hint: 'Р—Р°РєР°Р·С‡РёРєРё СЃ СЌС‚РёРј С‡РёСЃР»РѕРј РѕС‚РєСЂС‹С‚С‹С… Р·Р°РєР°Р·РѕРІ СЃРєСЂС‹РІР°СЋС‚СЃСЏ РїСЂРё СЃРѕР·РґР°РЅРёРё Р·Р°РєР°Р·Р°' },
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

  // в”Ђв”Ђ РџСЂРµРґС‹СЃС‚РѕСЂРёСЏ в”Ђв”Ђ
  const [storySlides, setStorySlides] = useState<StorySlide[]>([]);
  const [dlcLocations, setDlcLocations] = useState<DlcLocation[]>([]);
  const [storyForm, setStoryForm] = useState<{ text: string; sort_order: string; location_code: string }>({ text: '', sort_order: '0', location_code: '' });
  const [storyEditingId, setStoryEditingId] = useState<number | null>(null);

  // в”Ђв”Ђ Р’РёРґРµРѕ-СѓСЂРѕРєРё в”Ђв”Ђ
  const [lessons, setLessons] = useState<Lesson[]>([]);
  const [lessonForm, setLessonForm] = useState<{ title: string; description: string; sort_order: string }>({ title: '', description: '', sort_order: '0' });
  const [lessonEditingId, setLessonEditingId] = useState<number | null>(null);

  // в”Ђв”Ђ РљР°СЂС‚С‹-Р»РѕРєР°С†РёРё в”Ђв”Ђ
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

  // в”Ђв”Ђ РљР°С‚Р°Р»РѕРі в”Ђв”Ђ
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

  // в”Ђв”Ђ РЈСЂРѕРІРЅРё в”Ђв”Ђ
  const [levels, setLevels] = useState<LevelGate[]>([]);
  const [levelForm, setLevelForm] = useState({ level: 0, coins_required: 0, plots_required: 0, unlock_type: '' });
  const [levelImage, setLevelImage] = useState<File | null>(null);
  const [levelImageLevel, setLevelImageLevel] = useState(0);

  // в”Ђв”Ђ Р›РѕРіРё в”Ђв”Ђ
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
    if (!(await confirmDialog('РЈРґР°Р»РёС‚СЊ Р’РЎР• Р»РѕРіРё Р±РµР·РІРѕР·РІСЂР°С‚РЅРѕ?'))) return;
    setBusy(true); setMsg(null);
    try {
      await api.adminClearLogs();
      setLogs([]); setLogOffset(0); setLogHasMore(false); setExpandedLog(null);
      setMsg('вњ“ Р›РѕРіРё РѕС‡РёС‰РµРЅС‹');
    } catch (e: any) { setMsg('вњ— ' + (e?.response?.data?.detail || 'РћС€РёР±РєР°')); }
    finally { setBusy(false); }
  }

  useEffect(() => {
    if (tab !== 'logs') return;
    if (logSearchTimer.current) clearTimeout(logSearchTimer.current);
    logSearchTimer.current = setTimeout(() => { loadLogs(false); }, 300);
    return () => { if (logSearchTimer.current) clearTimeout(logSearchTimer.current); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tab, logFilter]);

  // в”Ђв”Ђ Р РµС†РµРїС‚С‹ Р·РµР»РёР№ в”Ђв”Ђ
  const [potionRecipes, setPotionRecipes] = useState<PotionRecipe[]>([]);
  const [potionForm, setPotionForm] = useState<PotionRecipeCreate>({ name: '', level: 'green', ingredient_slots: [], bonus_code: null, reward_coins: 100, description: '' });
  const [potionEditingId, setPotionEditingId] = useState<number | null>(null);
  const [potionSlotInput, setPotionSlotInput] = useState('');

  // в”Ђв”Ђ РљРѕРєС‚РµР№Р»Рё в”Ђв”Ђ
  const [cocktailRecipes, setCocktailRecipes] = useState<CocktailRecipeAdmin[]>([]);
  const [cocktailForm, setCocktailForm] = useState<{ name: string; description: string; patient_id: string; items: CocktailItemIn[] }>({ name: '', description: '', patient_id: '', items: [] });
  const [cocktailEditingId, setCocktailEditingId] = useState<number | null>(null);
  const [cocktailPickKind, setCocktailPickKind] = useState<'product' | 'plant' | 'ingredient' | 'remedy'>('product');
  const [cocktailPickId, setCocktailPickId] = useState<string>('');
  const [cocktailPickQty, setCocktailPickQty] = useState('1');

  // в”Ђв”Ђ РРЅРіСЂРµРґРёРµРЅС‚С‹ (Р°РїС‚РµРєР°) в”Ђв”Ђ
  const [ingredients, setIngredients] = useState<Ingredient[]>([]);
  const [ingForm, setIngForm] = useState<{ name: string; description: string; sort_order: string }>({ name: '', description: '', sort_order: '0' });
  const [ingEditingId, setIngEditingId] = useState<number | null>(null);

  // в”Ђв”Ђ Р›РµС‡РµР±РЅРёС†Р°: РјР°Р·Рё, Р±РѕР»РµР·РЅРё, РїР°С†РёРµРЅС‚С‹ в”Ђв”Ђ
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

  // в”Ђв”Ђ Р РµС†РµРїС‚С‹ Р±РёР±Р»РёРѕС‚РµРєРё в”Ђв”Ђ
  const [recipes, setRecipes] = useState<AdminRecipe[]>([]);
  const [recipeForm, setRecipeForm] = useState({ source_kind: 'plant', plant_id: '', source_product_id: '', product_id: '', level: '1' });
  const [recipeEditingId, setRecipeEditingId] = useState<number | null>(null);

  const MEDIA_TYPES: { code: string; kind: string; label: string }[] = [
    { code: 'card_shuffle', kind: 'video', label: 'рџЋґ Р’РёРґРµРѕ РїРµСЂРµС‚Р°СЃРѕРІРєРё РєР°СЂС‚' },
    { code: 'dice_roll', kind: 'video', label: 'рџЋІ Р’РёРґРµРѕ Р±СЂРѕСЃРєР° РєСѓР±РёРєР°' },
    { code: 'dice_face_1', kind: 'image', label: 'вљЂ Р“СЂР°РЅСЊ РєСѓР±РёРєР° 1' },
    { code: 'dice_face_2', kind: 'image', label: 'вљЃ Р“СЂР°РЅСЊ РєСѓР±РёРєР° 2' },
    { code: 'dice_face_3', kind: 'image', label: 'вљ‚ Р“СЂР°РЅСЊ РєСѓР±РёРєР° 3' },
    { code: 'dice_face_4', kind: 'image', label: 'вљѓ Р“СЂР°РЅСЊ РєСѓР±РёРєР° 4' },
    { code: 'dice_face_5', kind: 'image', label: 'вљ„ Р“СЂР°РЅСЊ РєСѓР±РёРєР° 5' },
    { code: 'dice_face_6', kind: 'image', label: 'вљ… Р“СЂР°РЅСЊ РєСѓР±РёРєР° 6' },
    { code: 'house_build_video', kind: 'video', label: 'рџЏ  Р’РёРґРµРѕ РїРѕСЃС‚СЂРѕР№РєРё РґРѕРјР° РІРµРґСЊРјС‹' },
    { code: 'house_built_image', kind: 'image', label: 'рџЏ  РљР°СЂС‚РёРЅРєР° С„РёРЅР°Р»Р° РґРѕРјР° РІРµРґСЊРјС‹' },
    { code: 'house_material_glass', kind: 'image', label: 'рџЄџ РЎС‚СЂРѕР№РјР°С‚РµСЂРёР°Р»: СЃС‚РµРєР»Рѕ' },
    { code: 'house_material_wood', kind: 'image', label: 'рџЄµ РЎС‚СЂРѕР№РјР°С‚РµСЂРёР°Р»: РґСЂРµРІРµСЃРёРЅР°' },
    { code: 'house_material_nails', kind: 'image', label: 'рџ”© РЎС‚СЂРѕР№РјР°С‚РµСЂРёР°Р»: РіРІРѕР·РґРё' },
    { code: 'house_material_pipes', kind: 'image', label: 'рџљ° РЎС‚СЂРѕР№РјР°С‚РµСЂРёР°Р»: С‚СЂСѓР±С‹' },
    { code: 'house_material_bricks', kind: 'image', label: 'рџ§± РЎС‚СЂРѕР№РјР°С‚РµСЂРёР°Р»: РєРёСЂРїРёС‡Рё' },
    { code: 'house_material_paint', kind: 'image', label: 'рџЋЁ РЎС‚СЂРѕР№РјР°С‚РµСЂРёР°Р»: РєСЂР°СЃРєР°' },
    { code: 'cauldron_tin', kind: 'image', label: 'рџЌІ РљРѕС‚С‘Р»: РѕР»РѕРІСЏРЅРЅС‹Р№ (4 РёРЅРіСЂРµРґРёРµРЅС‚Р°)' },
    { code: 'cauldron_silver', kind: 'image', label: 'рџЌІ РљРѕС‚С‘Р»: СЃРµСЂРµР±СЂСЏРЅС‹Р№ (5 РёРЅРіСЂРµРґРёРµРЅС‚РѕРІ)' },
    { code: 'cauldron_gold', kind: 'image', label: 'рџЌІ РљРѕС‚С‘Р»: Р·РѕР»РѕС‚РѕР№ (6 РёРЅРіСЂРµРґРёРµРЅС‚РѕРІ)' },
    { code: 'potion_brew', kind: 'video', label: 'рџ§Є Р’РёРґРµРѕ РІР°СЂРєРё Р·РµР»СЊСЏ' },
    { code: 'infirmary_book', kind: 'image', label: 'рџ“– РРєРѕРЅРєР° РєРЅРёРіРё Р»РµС‡РµР±РЅРёС†С‹' },
    { code: 'remedy_heal', kind: 'video', label: 'рџ’Љ Р’РёРґРµРѕ Р»РµС‡РµРЅРёСЏ Р¶РёРІРѕС‚РЅРѕРіРѕ' },
  ];

  const [gameMedia, setGameMedia] = useState<GameMedia[]>([]);
  const [mediaTypeSel, setMediaTypeSel] = useState('');

  const [crystalCards, setCrystalCards] = useState<CrystalCard[]>([]);

  // в”Ђв”Ђ Р”РѕСЃС‚РёР¶РµРЅРёСЏ в”Ђв”Ђ
  const [achievements, setAchievements] = useState<Achievement[]>([]);
  const [achKinds, setAchKinds] = useState<AchievementKind[]>([]);
  const [achForm, setAchForm] = useState({ name: '', condition_kind: '', condition_value: '1', production_code: '' });
  const [achEditingId, setAchEditingId] = useState<number | null>(null);
  const [achImage, setAchImage] = useState<File | null>(null);

  // в”Ђв”Ђ Р—Р°РєР°Р·С‡РёРєРё в”Ђв”Ђ
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [customerForm, setCustomerForm] = useState('');
  const [customerEditingId, setCustomerEditingId] = useState<number | null>(null);
  const customerNames = customers.map((c) => c.name);
  const rawCustomerMax = Number(settings['customer_max_orders']);
  const customerMaxOrders = Number.isFinite(rawCustomerMax) ? rawCustomerMax : 3;
  const freeCustomerNames = customers.filter((c) => c.open_orders_count < customerMaxOrders).map((c) => c.name);

  // в”Ђв”Ђ Р¤РѕРЅ в”Ђв”Ђ
  const [bgUrl, setBgUrl] = useState('');
  const [bgInput, setBgInput] = useState('');

  // в”Ђв”Ђ Р—Р°РєР°Р·С‹: СЃРѕР·РґР°РЅРёРµ/СЂРµРґР°РєС‚РёСЂРѕРІР°РЅРёРµ в”Ђв”Ђ
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
    if (!(await confirmDialog(`РЈРґР°Р»РёС‚СЊ Р’Р•РЎР¬ РїСЂРѕРіСЂРµСЃСЃ РёРіСЂРѕРєР° #${selectedPlayer.vk_id} (РіСЂСЏРґРєРё, СЃРєР»Р°Рґ, Р·Р°РєР°Р·С‹, РѕС‚С‡С‘С‚С‹, РґРѕСЃС‚РёР¶РµРЅРёСЏ, РЅРѕСЂРјС‹)?`))) return;
    if (!(await confirmDialog('РўРѕС‡РЅРѕ? Р”РµР№СЃС‚РІРёРµ РЅРµРѕР±СЂР°С‚РёРјРѕ.'))) return;
    setBusy(true); setMsg(null);
    try {
      const updated = await api.adminRestartPlayer(selectedPlayer.vk_id);
      setSelectedPlayer(updated);
      setPlayerReports([]);
      setPlayerDetail(null);
      try { setPlayerDetail(await api.adminPlayerDetail(selectedPlayer.vk_id)); } catch {}
      setMsg('вњ“ РРіСЂРѕРє РїРµСЂРµР·Р°РїСѓС‰РµРЅ: РїСЂРѕРіСЂРµСЃСЃ РѕР±РЅСѓР»С‘РЅ');
    } catch (e: any) {
      setMsg('вњ— ' + (e?.response?.data?.detail || 'РћС€РёР±РєР°'));
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
      setMsg('вњ— ' + (e?.response?.data?.detail || 'РћС€РёР±РєР°'));
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
      setMsg(`вњ“ РРіСЂРѕРє #${added.vk_id} РїРѕР»СѓС‡РёР» РґРѕСЃС‚СѓРї`);
      setAccessLink('');
      setAccessPlayers(await api.adminAccessPlayers());
    } catch (e: any) {
      setMsg('вњ— ' + (e?.response?.data?.detail || 'РћС€РёР±РєР°'));
    } finally {
      setBusy(false);
    }
  }

  async function removeAccessPlayer(vkId: number) {
    if (!(await confirmDialog(`РЈР±СЂР°С‚СЊ РёРіСЂРѕРєР° #${vkId} РёР· СЃРїРёСЃРєР° РґРѕСЃС‚СѓРїР°? РћРЅ СЃСЂР°Р·Сѓ РїРѕС‚РµСЂСЏРµС‚ РІС…РѕРґ.`))) return;
    setBusy(true); setMsg(null);
    try {
      await api.adminDeleteAccessPlayer(vkId);
      setAccessPlayers((prev) => prev.filter((p) => p.vk_id !== vkId));
      setMsg('вњ“ Р”РѕСЃС‚СѓРї СѓР±СЂР°РЅ');
    } catch (e: any) {
      setMsg('вњ— ' + (e?.response?.data?.detail || 'РћС€РёР±РєР°'));
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
      setMsg('вњ“ РЎРѕС…СЂР°РЅРµРЅРѕ');
    } catch (e: any) {
      setMsg('вњ— ' + (e?.response?.data?.detail || 'РћС€РёР±РєР°'));
    } finally {
      setBusy(false);
    }
  }

  async function togglePlayerDlc(vkId: number, code: string, granted: boolean) {
    setBusy(true); setMsg(null);
    try {
      if (granted) {
        await api.adminRevokeDlc(vkId, code);
        setMsg('вњ“ Р”РѕРїРѕР»РЅРµРЅРёРµ Р·Р°Р±СЂР°РЅРѕ');
      } else {
        await api.adminGrantDlc(vkId, code);
        setMsg('вњ“ Р”РѕРїРѕР»РЅРµРЅРёРµ РІС‹РґР°РЅРѕ');
      }
      await reloadPlayerDetail();
    } catch (e: any) {
      setMsg('вњ— ' + (e?.response?.data?.detail || 'РћС€РёР±РєР°'));
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
      setMsg(`вњ“ РЎС‚Р°С‚СѓСЃ: ${PLAYER_STATUS_META[updated.status]?.label ?? updated.status}`);
    } catch (e: any) {
      setMsg('вњ— ' + (e?.response?.data?.detail || 'РћС€РёР±РєР°'));
    } finally {
      setBusy(false);
    }
  }

  async function deletePlayerAccount() {
    if (!selectedPlayer) return;
    if (!(await confirmDialog(`РЈРґР°Р»РёС‚СЊ РёРіСЂРѕРєР° #${selectedPlayer.vk_id} РџРћР›РќРћРЎРўР¬Р® (РїСЂРѕС„РёР»СЊ, РІРµСЃСЊ РїСЂРѕРіСЂРµСЃСЃ, С„РѕС‚Рѕ-РѕС‚С‡С‘С‚С‹, РґРѕСЃС‚СѓРї)?`))) return;
    if (!(await confirmDialog('РўРѕС‡РЅРѕ? Р’РѕСЃСЃС‚Р°РЅРѕРІРёС‚СЊ Р±СѓРґРµС‚ РЅРµРІРѕР·РјРѕР¶РЅРѕ.'))) return;
    setBusy(true); setMsg(null);
    try {
      await api.adminDeletePlayer(selectedPlayer.vk_id);
      setMsg('вњ“ РРіСЂРѕРє СѓРґР°Р»С‘РЅ');
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
      setMsg('вњ— ' + (e?.response?.data?.detail || 'РћС€РёР±РєР°'));
    } finally {
      setBusy(false);
    }
  }

  async function reviewReport(id: number, action: 'accept' | 'reject') {
    setBusy(true);
    setMsg(null);
    try {
      await api.reviewReport(id, action);
      setMsg('вњ“ ' + (action === 'accept' ? 'Р—Р°С‡С‚РµРЅРѕ' : 'РћС‚РєР»РѕРЅРµРЅРѕ'));
      if (selectedPlayer) {
        const reps = await api.adminPlayerReports(selectedPlayer.vk_id);
        setPlayerReports(reps);
      }
      await load();
    } catch (e: any) {
      setMsg('вњ— ' + (e?.response?.data?.detail || 'РћС€РёР±РєР°'));
    } finally {
      setBusy(false);
    }
  }

  async function saveSetting(key: string, value: string) {
    setBusy(true);
    setMsg(null);
    try {
      await api.updateSetting(key, value);
      setMsg('вњ“ РќР°СЃС‚СЂРѕР№РєР° СЃРѕС…СЂР°РЅРµРЅР°');
      await load();
    } catch (e: any) {
      setMsg('вњ— ' + (e?.response?.data?.detail || 'РћС€РёР±РєР°'));
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
      setMsg('вњ“ Р›РѕРєР°С†РёСЏ СЃРѕР·РґР°РЅР°');
      setShowCreate(false); setNewName(''); setNewFieldKind(''); setNewPlantCategory(''); setNewMinLevel('0');
      await load();
    } catch (e: any) {
      setMsg('вњ— ' + (e?.response?.data?.detail || 'РћС€РёР±РєР°'));
    } finally { setBusy(false); }
  }

  async function deleteField(id: number) {
    if (!(await confirmDialog('РЈРґР°Р»РёС‚СЊ Р»РѕРєР°С†РёСЋ СЃРѕ РІСЃРµРјРё РєР»РµС‚РєР°РјРё Рё С€Р°С‚СЂР°РјРё?'))) return;
    setBusy(true); setMsg(null);
    try {
      await api.adminDeleteField(id);
      setMsg('вњ“ Р›РѕРєР°С†РёСЏ СѓРґР°Р»РµРЅР°');
      await load();
    } catch (e: any) {
      setMsg('вњ— ' + (e?.response?.data?.detail || 'РћС€РёР±РєР°'));
    } finally { setBusy(false); }
  }

  async function uploadMap(id: number, file: File) {
    setBusy(true); setMsg(null);
    try {
      await api.adminUploadFieldMap(id, file);
      setMsg('вњ“ РљР°СЂС‚Р° Р·Р°РіСЂСѓР¶РµРЅР°');
      await load();
    } catch (e: any) {
      setMsg('вњ— ' + (e?.response?.data?.detail || 'РћС€РёР±РєР°'));
    } finally { setBusy(false); }
  }

  // в”Ђв”Ђ РљР°С‚Р°Р»РѕРі: CRUD в”Ђв”Ђ
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
      setMsg('вњ“ РЎРѕС…СЂР°РЅРµРЅРѕ');
      await load();
    } catch (e: any) { setMsg('вњ— ' + (e?.response?.data?.detail || 'РћС€РёР±РєР°')); }
    finally { setBusy(false); }
  }

  async function deletePlant(id: number) {
    if (!(await confirmDialog('РЈРґР°Р»РёС‚СЊ СЂР°СЃС‚РµРЅРёРµ?'))) return;
    setBusy(true); setMsg(null);
    try { await api.adminDeletePlant(id); await load(); setMsg('вњ“ РЈРґР°Р»РµРЅРѕ'); }
    catch (e: any) { setMsg('вњ— ' + (e?.response?.data?.detail || 'РћС€РёР±РєР°')); }
    finally { setBusy(false); }
  }

  async function saveAnimal() {
    if (!catForm.name?.trim()) return;
    setBusy(true); setMsg(null);
    try {
      if (editingId) await api.adminUpdateAnimal(editingId, catForm);
      else { const created = await api.adminCreateAnimal(catForm as any); setEditingId(created.id); }
      setMsg('вњ“ РЎРѕС…СЂР°РЅРµРЅРѕ');
      await load();
    } catch (e: any) { setMsg('вњ— ' + (e?.response?.data?.detail || 'РћС€РёР±РєР°')); }
    finally { setBusy(false); }
  }

  async function deleteAnimal(id: number) {
    if (!(await confirmDialog('РЈРґР°Р»РёС‚СЊ Р¶РёРІРѕС‚РЅРѕРµ?'))) return;
    setBusy(true); setMsg(null);
    try { await api.adminDeleteAnimal(id); await load(); setMsg('вњ“ РЈРґР°Р»РµРЅРѕ'); }
    catch (e: any) { setMsg('вњ— ' + (e?.response?.data?.detail || 'РћС€РёР±РєР°')); }
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
      setMsg('вњ“ РЎРѕС…СЂР°РЅРµРЅРѕ');
      await load();
    } catch (e: any) { setMsg('вњ— ' + (e?.response?.data?.detail || 'РћС€РёР±РєР°')); }
    finally { setBusy(false); }
  }

  async function cancelOrder(id: number) {
    if (!(await confirmDialog('РћС‚РјРµРЅРёС‚СЊ Р·Р°РєР°Р·?'))) return;
    setBusy(true); setMsg(null);
    try { await api.adminCancelOrder(id); await load(); setMsg('вњ“ РћС‚РјРµРЅС‘РЅ'); }
    catch (e: any) { setMsg('вњ— ' + (e?.response?.data?.detail || 'РћС€РёР±РєР°')); }
    finally { setBusy(false); }
  }

  async function deleteOrder(id: number) {
    if (!(await confirmDialog('РЈРґР°Р»РёС‚СЊ Р·Р°РєР°Р·?'))) return;
    setBusy(true); setMsg(null);
    try { await api.adminDeleteOrder(id); await load(); setMsg('вњ“ РЈРґР°Р»С‘РЅ'); }
    catch (e: any) { setMsg('вњ— ' + (e?.response?.data?.detail || 'РћС€РёР±РєР°')); }
    finally { setBusy(false); }
  }

  // в”Ђв”Ђ Р—Р°РєР°Р·С‹: СЃРѕР·РґР°РЅРёРµ Рё СЂРµРґР°РєС‚РёСЂРѕРІР°РЅРёРµ в”Ђв”Ђ
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
        setMsg('вњ“ Р—Р°РєР°Р· РѕР±РЅРѕРІР»С‘РЅ');
      } else if (isPotion) {
        const created = await api.adminGenerateOrder(null, undefined, customer ?? null, orderForm.customer_phrase?.trim() || undefined, prid);
        targetId = created.id;
        setMsg('вњ“ Р—Р°РєР°Р· РЅР° Р·РµР»СЊРµ СЃРѕР·РґР°РЅ');
      } else {
        const created = await api.adminGenerateOrder(pid, q, customer ?? null, orderForm.customer_phrase?.trim() || undefined);
        targetId = created.id;
        setMsg('вњ“ Р—Р°РєР°Р· СЃРѕР·РґР°РЅ');
      }
      if (targetId && orderImage) {
        await api.adminUploadOrderImage(targetId, orderImage);
      }
      setOrderFormOpen(false);
      setOrderEditingId(null);
      setOrderImage(null);
      await load();
      api.adminCustomers().then(setCustomers).catch(() => {});
    } catch (e: any) { setMsg('вњ— ' + (e?.response?.data?.detail || 'РћС€РёР±РєР°')); }
    finally { setBusy(false); }
  }

  async function deletePet(id: number) {
    if (!(await confirmDialog('РЈРґР°Р»РёС‚СЊ РїРёС‚РѕРјС†Р°?'))) return;
    setBusy(true); setMsg(null);
    try { await api.adminDeletePet(id); await load(); setMsg('вњ“ РЈРґР°Р»РµРЅРѕ'); }
    catch (e: any) { setMsg('вњ— ' + (e?.response?.data?.detail || 'РћС€РёР±РєР°')); }
    finally { setBusy(false); }
  }

  async function saveProduct() {
    if (!catForm.name?.trim()) return;
    if (!catForm.production_kind) { setMsg('вњ— РЈРєР°Р¶РёС‚Рµ РїСЂРѕРёР·РІРѕРґСЃС‚РІРѕ'); return; }
    if (!catForm.plant_id && !catForm.animal_id && !catForm.pet_id) { setMsg('вњ— РЈРєР°Р¶РёС‚Рµ СЂР°СЃС‚РµРЅРёРµ, Р¶РёРІРѕС‚РЅРѕРµ РёР»Рё РїРёС‚РѕРјС†Р°'); return; }
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
      setMsg('вњ“ РЎРѕС…СЂР°РЅРµРЅРѕ');
      await load();
    } catch (e: any) { setMsg('вњ— ' + (e?.response?.data?.detail || 'РћС€РёР±РєР°')); }
    finally { setBusy(false); }
  }

  async function deleteProduct(id: number) {
    if (!(await confirmDialog('РЈРґР°Р»РёС‚СЊ С‚РѕРІР°СЂ?'))) return;
    setBusy(true); setMsg(null);
    try { await api.adminDeleteProduct(id); await load(); setMsg('вњ“ РЈРґР°Р»РµРЅРѕ'); }
    catch (e: any) { setMsg('вњ— ' + (e?.response?.data?.detail || 'РћС€РёР±РєР°')); }
    finally { setBusy(false); }
  }

  async function saveProduction() {
    if (!catForm.name?.trim()) return;
    setBusy(true); setMsg(null);
    try {
      if (editingId) await api.adminUpdateProductionTemplate(editingId, catForm);
      else { const created = await api.adminCreateProductionTemplate(catForm as any); setEditingId(created.id); }
      setMsg('вњ“ РЎРѕС…СЂР°РЅРµРЅРѕ');
      await load();
    } catch (e: any) { setMsg('вњ— ' + (e?.response?.data?.detail || 'РћС€РёР±РєР°')); }
    finally { setBusy(false); }
  }

  async function deleteProduction(id: number) {
    if (!(await confirmDialog('РЈРґР°Р»РёС‚СЊ РїСЂРѕРёР·РІРѕРґСЃС‚РІРѕ?'))) return;
    setBusy(true); setMsg(null);
    try { await api.adminDeleteProductionTemplate(id); await load(); setMsg('вњ“ РЈРґР°Р»РµРЅРѕ'); }
    catch (e: any) { setMsg('вњ— ' + (e?.response?.data?.detail || 'РћС€РёР±РєР°')); }
    finally { setBusy(false); }
  }

  // в”Ђв”Ђ Р—Р°РєР°Р·С‡РёРєРё в”Ђв”Ђ
  async function loadCustomers() {
    try { setCustomers(await api.adminCustomers()); }
    catch { /* ignore */ }
  }
  async function saveCustomer() {
    const name = customerForm.trim();
    if (!name) { setMsg('вњ— Р’РІРµРґРёС‚Рµ РёРјСЏ Р·Р°РєР°Р·С‡РёРєР°'); return; }
    setBusy(true); setMsg(null);
    try {
      if (customerEditingId) { await api.adminUpdateCustomer(customerEditingId, name); }
      else { await api.adminCreateCustomer(name); }
      await loadCustomers();
      setCustomerForm('');
      setCustomerEditingId(null);
      setMsg('вњ“ РЎРѕС…СЂР°РЅРµРЅРѕ');
    } catch (e: any) { setMsg('вњ— ' + (e?.response?.data?.detail || 'РћС€РёР±РєР°')); }
    finally { setBusy(false); }
  }
  async function deleteCustomer(id: number) {
    if (!(await confirmDialog('РЈРґР°Р»РёС‚СЊ Р·Р°РєР°Р·С‡РёРєР°?'))) return;
    setBusy(true); setMsg(null);
    try { await api.adminDeleteCustomer(id); await loadCustomers(); setMsg('вњ“ РЈРґР°Р»РµРЅРѕ'); }
    catch (e: any) { setMsg('вњ— ' + (e?.response?.data?.detail || 'РћС€РёР±РєР°')); }
    finally { setBusy(false); }
  }
  async function uploadCustomerImage(id: number, file: File) {
    setBusy(true); setMsg(null);
    try {
      await api.adminUploadCustomerImage(id, file);
      await loadCustomers();
      setMsg('вњ“ Р¤РѕС‚Рѕ Р·Р°РіСЂСѓР¶РµРЅРѕ');
    } catch (e: any) { setMsg('вњ— ' + (e?.response?.data?.detail || 'РћС€РёР±РєР°')); }
    finally { setBusy(false); }
  }

  function renderCustomers() {
    return (
      <div>
        <h2>рџ§‘ Р—Р°РєР°Р·С‡РёРєРё</h2>
        <div className="fm-card" style={{ marginBottom: 10, display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
          <input
            className="fm-input"
            placeholder="РРјСЏ Р·Р°РєР°Р·С‡РёРєР°"
            value={customerForm}
            onChange={(e) => setCustomerForm(e.target.value)}
            style={{ maxWidth: 280 }}
          />
          <button type="button" className="fm-btn" disabled={busy} onClick={saveCustomer}>
            {customerEditingId ? 'вњЋ РЎРѕС…СЂР°РЅРёС‚СЊ' : 'вћ• Р”РѕР±Р°РІРёС‚СЊ'}
          </button>
          {customerEditingId && (
            <button type="button" className="fm-btn fm-btn-outline" onClick={() => { setCustomerEditingId(null); setCustomerForm(''); }}>РћС‚РјРµРЅР°</button>
          )}
        </div>
        <table className="fm-table" style={{ width: '100%' }}>
          <thead><tr><th>ID</th><th>РРјСЏ</th><th>РћС‚РєСЂС‹С‚С‹С… Р·Р°РєР°Р·РѕРІ</th><th>Р¤РѕС‚Рѕ</th><th></th></tr></thead>
          <tbody>
            {shownCustomers.map((c) => (
              <tr key={c.id} style={c.open_orders_count >= customerMaxOrders ? { opacity: 0.5 } : undefined}>
                <td>{c.id}</td>
                <td>{c.name}</td>
                <td>{c.open_orders_count}{c.open_orders_count >= customerMaxOrders ? ' (Р»РёРјРёС‚)' : ''}</td>
                <td>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                    {c.image_url && <img src={mediaUrl(c.image_url)} alt="" style={{ width: 36, height: 36, objectFit: 'cover', borderRadius: 4 }} />}
                    <label className="fm-btn fm-btn-sm" style={{ cursor: 'pointer', margin: 0 }}>
                      рџ–ј
                      <input type="file" accept="image/*" hidden onChange={(e) => {
                        const f = e.target.files?.[0];
                        if (f) uploadCustomerImage(c.id, f);
                        e.target.value = '';
                      }} />
                    </label>
                  </div>
                </td>
                <td>
                  <button type="button" className="fm-btn fm-btn-sm" onClick={() => { setCustomerEditingId(c.id); setCustomerForm(c.name); }}>вњЋ</button>
                  <button type="button" className="fm-btn fm-btn-sm" style={{ marginLeft: 4 }} onClick={() => deleteCustomer(c.id)}>рџ—‘</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {qActive && shownCustomers.length === 0 && <div className="fm-card" style={{ color: 'var(--text-muted)', marginTop: 8 }}>{NO_MATCH}</div>}
      </div>
    );
  }

  // в”Ђв”Ђ РЈСЂРѕРІРЅРё в”Ђв”Ђ
  async function loadLevels() {
    try { setLevels(await api.adminLevels()); }
    catch { /* ignore */ }
  }
  async function saveLevel() {
    setBusy(true); setMsg(null);
    try {
      await api.adminSetLevel(levelForm.level, levelForm.coins_required, levelForm.plots_required, levelForm.unlock_type || null);
      await loadLevels();
      setMsg('вњ“ РЎРѕС…СЂР°РЅРµРЅРѕ');
    } catch (e: any) { setMsg('вњ— ' + (e?.response?.data?.detail || 'РћС€РёР±РєР°')); }
    finally { setBusy(false); }
  }
  async function uploadLevelImage() {
    if (!levelImage) { setMsg('вњ— Р’С‹Р±РµСЂРёС‚Рµ С„Р°Р№Р»'); return; }
    setBusy(true); setMsg(null);
    try {
      await api.adminUploadLevelImage(levelImageLevel, levelImage);
      setLevelImage(null);
      await loadLevels();
      setMsg('вњ“ РР·РѕР±СЂР°Р¶РµРЅРёРµ Р·Р°РіСЂСѓР¶РµРЅРѕ');
    } catch (e: any) { setMsg('вњ— ' + (e?.response?.data?.detail || 'РћС€РёР±РєР°')); }
    finally { setBusy(false); }
  }
  async function deleteLevel(level: number) {
    if (!(await confirmDialog(`РЈРґР°Р»РёС‚СЊ СѓСЂРѕРІРµРЅСЊ ${level}?`))) return;
    setBusy(true); setMsg(null);
    try { await api.adminDeleteLevel(level); await loadLevels(); setMsg('вњ“ РЈРґР°Р»РµРЅРѕ'); }
    catch (e: any) { setMsg('вњ— ' + (e?.response?.data?.detail || 'РћС€РёР±РєР°')); }
    finally { setBusy(false); }
  }

  function renderLevels() {
    return (
      <div>
        <h2>рџ“Љ РЈСЂРѕРІРЅРё (РјР°СЂС€СЂСѓС‚РЅС‹Р№ Р»РёСЃС‚)</h2>
        <div className="fm-card" style={{ marginBottom: 10, display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
          <input className="fm-input" type="number" placeholder="РЈСЂРѕРІРµРЅСЊ (0-16)" value={levelForm.level} onChange={(e) => setLevelForm({ ...levelForm, level: Number(e.target.value) })} style={{ width: 80 }} />
          <input className="fm-input" type="number" placeholder="РњРѕРЅРµС‚" value={levelForm.coins_required || ''} onChange={(e) => setLevelForm({ ...levelForm, coins_required: Number(e.target.value) })} style={{ width: 100 }} />
          <input className="fm-input" type="number" placeholder="Р“СЂСЏРґРѕРє" value={levelForm.plots_required || ''} onChange={(e) => setLevelForm({ ...levelForm, plots_required: Number(e.target.value) })} style={{ width: 80 }} />
          <select className="fm-input" value={levelForm.unlock_type} onChange={(e) => setLevelForm({ ...levelForm, unlock_type: e.target.value })} style={{ width: 200 }}>
            <option value="">вЂ” Р§С‚Рѕ СЂР°Р·Р±Р»РѕРєРёСЂСѓРµС‚СЃСЏ вЂ”</option>
            {UNLOCK_OPTIONS.map((opt) => (
              <option key={opt} value={opt}>{opt}</option>
            ))}
          </select>
          <button type="button" className="fm-btn" disabled={busy} onClick={saveLevel}>рџ’ѕ РЎРѕС…СЂР°РЅРёС‚СЊ</button>
        </div>
        <div className="fm-card" style={{ marginBottom: 10, display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
          <input className="fm-input" type="number" placeholder="РЈСЂРѕРІРµРЅСЊ" value={levelImageLevel} onChange={(e) => setLevelImageLevel(Number(e.target.value))} style={{ width: 80 }} />
          <input type="file" accept="image/*" onChange={(e) => setLevelImage(e.target.files?.[0] || null)} style={{ fontSize: 13 }} />
          <button type="button" className="fm-btn fm-btn-sm" disabled={busy || !levelImage} onClick={uploadLevelImage}>рџ–ј Р—Р°РіСЂСѓР·РёС‚СЊ РєР°СЂС‚РёРЅРєСѓ</button>
        </div>
        <table className="fm-table" style={{ width: '100%' }}>
          <thead><tr><th>РЈСЂРѕРІРµРЅСЊ</th><th>РљР°СЂС‚РёРЅРєР°</th><th>РњРѕРЅРµС‚</th><th>Р“СЂСЏРґРѕРє</th><th>Р Р°Р·Р±Р»РѕРєРёСЂРѕРІРєР°</th><th></th></tr></thead>
          <tbody>
            {shownLevels.map((l) => (
              <tr key={l.level}>
                <td>{l.level}</td>
                <td>{l.image_url ? <img src={mediaUrl(l.image_url)} alt="" style={{ maxWidth: 60, maxHeight: 40, borderRadius: 4 }} /> : 'вЂ”'}</td>
                <td>{l.coins_required}</td>
                <td>{l.plots_required}</td>
                <td>{l.unlock_type || 'вЂ”'}</td>
                <td>
                  <button type="button" className="fm-btn fm-btn-sm" onClick={() => { setLevelForm({ level: l.level, coins_required: l.coins_required, plots_required: l.plots_required, unlock_type: l.unlock_type || '' }); }}>вњЋ</button>
                  <button type="button" className="fm-btn fm-btn-sm" style={{ marginLeft: 4 }} onClick={() => deleteLevel(l.level)}>рџ—‘</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {qActive && shownLevels.length === 0 && <div className="fm-card" style={{ color: 'var(--text-muted)', marginTop: 8 }}>{NO_MATCH}</div>}
      </div>
    );
  }

  // в”Ђв”Ђ Р РµС†РµРїС‚С‹ Р·РµР»РёР№ в”Ђв”Ђ
  async function loadPotionRecipes() {
    try { setPotionRecipes(await api.adminPotionRecipes()); }
    catch { /* ignore */ }
  }
  async function savePotionRecipe() {
    if (!potionForm.name) { setMsg('вњ— Р’РІРµРґРёС‚Рµ РЅР°Р·РІР°РЅРёРµ'); return; }
    setBusy(true); setMsg(null);
    try {
      if (potionEditingId) { await api.adminUpdatePotionRecipe(potionEditingId, potionForm); }
      else { await api.adminCreatePotionRecipe(potionForm); }
      await loadPotionRecipes();
      setPotionForm({ name: '', level: 'green', ingredient_slots: [], bonus_code: null, reward_coins: 100, description: '' });
      setPotionEditingId(null);
      setMsg('вњ“ РЎРѕС…СЂР°РЅРµРЅРѕ');
    } catch (e: any) { setMsg('вњ— ' + (e?.response?.data?.detail || 'РћС€РёР±РєР°')); }
    finally { setBusy(false); }
  }
  async function uploadPotionImage(id: number, file: File) {
    setBusy(true); setMsg(null);
    try {
      await api.adminUploadPotionImage(id, file);
      await loadPotionRecipes();
      setMsg('вњ“ РљР°СЂС‚РёРЅРєР° Р·РµР»СЊСЏ Р·Р°РіСЂСѓР¶РµРЅР°');
    } catch (e: any) { setMsg('вњ— ' + (e?.response?.data?.detail || 'РћС€РёР±РєР°')); }
    finally { setBusy(false); }
  }
  async function uploadPotionCardImage(id: number, file: File) {
    setBusy(true); setMsg(null);
    try {
      await api.adminUploadPotionCardImage(id, file);
      await loadPotionRecipes();
      setMsg('вњ“ РљР°СЂС‚РѕС‡РєР° СЂРµС†РµРїС‚Р° Р·Р°РіСЂСѓР¶РµРЅР°');
    } catch (e: any) { setMsg('вњ— ' + (e?.response?.data?.detail || 'РћС€РёР±РєР°')); }
    finally { setBusy(false); }
  }

  async function deletePotionRecipe(id: number) {
    if (!(await confirmDialog('РЈРґР°Р»РёС‚СЊ СЂРµС†РµРїС‚?'))) return;
    setBusy(true); setMsg(null);
    try { await api.adminDeletePotionRecipe(id); await loadPotionRecipes(); setMsg('вњ“ РЈРґР°Р»РµРЅРѕ'); }
    catch (e: any) { setMsg('вњ— ' + (e?.response?.data?.detail || 'РћС€РёР±РєР°')); }
    finally { setBusy(false); }
  }

  // в”Ђв”Ђ РљРѕРєС‚РµР№Р»Рё в”Ђв”Ђ
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
    if (!cocktailForm.name.trim()) { setMsg('вњ— Р’РІРµРґРёС‚Рµ РЅР°Р·РІР°РЅРёРµ'); return; }
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
      setMsg('вњ“ РЎРѕС…СЂР°РЅРµРЅРѕ');
    } catch (e: any) { setMsg('вњ— ' + (e?.response?.data?.detail || 'РћС€РёР±РєР°')); }
    finally { setBusy(false); }
  }
  function addCocktailItem() {
    const itemId = Number(cocktailPickId);
    if (!itemId) { setMsg('вњ— Р’С‹Р±РµСЂРёС‚Рµ РїСЂРµРґРјРµС‚'); return; }
    const qty = Number(cocktailPickQty);
    if (!qty || qty < 1) { setMsg('вњ— РЈРєР°Р¶РёС‚Рµ РєРѕР»РёС‡РµСЃС‚РІРѕ'); return; }
    if (cocktailForm.items.some((i) => i.kind === cocktailPickKind && i.item_id === itemId)) {
      setMsg('вњ— Р­С‚РѕС‚ РїСЂРµРґРјРµС‚ СѓР¶Рµ РґРѕР±Р°РІР»РµРЅ');
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
      setMsg('вњ“ РљР°СЂС‚РёРЅРєР° РєРѕРєС‚РµР№Р»СЏ Р·Р°РіСЂСѓР¶РµРЅР°');
    } catch (e: any) { setMsg('вњ— ' + (e?.response?.data?.detail || 'РћС€РёР±РєР°')); }
    finally { setBusy(false); }
  }
  async function uploadCocktailCardImage(id: number, file: File) {
    setBusy(true); setMsg(null);
    try {
      await api.adminUploadCocktailCardImage(id, file);
      await loadCocktailRecipes();
      setMsg('вњ“ РљР°СЂС‚РѕС‡РєР° РєРѕРєС‚РµР№Р»СЏ Р·Р°РіСЂСѓР¶РµРЅР°');
    } catch (e: any) { setMsg('вњ— ' + (e?.response?.data?.detail || 'РћС€РёР±РєР°')); }
    finally { setBusy(false); }
  }
  async function deleteCocktailRecipe(id: number) {
    if (!(await confirmDialog('РЈРґР°Р»РёС‚СЊ СЂРµС†РµРїС‚ РєРѕРєС‚РµР№Р»СЏ?'))) return;
    setBusy(true); setMsg(null);
    try { await api.adminDeleteCocktailRecipe(id); await loadCocktailRecipes(); setMsg('вњ“ РЈРґР°Р»РµРЅРѕ'); }
    catch (e: any) { setMsg('вњ— ' + (e?.response?.data?.detail || 'РћС€РёР±РєР°')); }
    finally { setBusy(false); }
  }

  function cocktailItemName(kind: string, id: number): string {
    if (kind === 'product') return products.find((p) => p.id === id)?.name ?? `#${id}`;
    if (kind === 'plant') return plants.find((p) => p.id === id)?.name ?? `#${id}`;
    if (kind === 'ingredient') return ingredients.find((i) => i.id === id)?.name ?? `#${id}`;
    if (kind === 'remedy') return remedies.find((r) => r.id === id)?.name ?? `#${id}`;
    return `#${id}`;
  }

  // в”Ђв”Ђ РРЅРіСЂРµРґРёРµРЅС‚С‹ (Р°РїС‚РµРєР°) в”Ђв”Ђ
  async function loadIngredients() {
    try { setIngredients(await api.adminIngredients()); }
    catch { /* ignore */ }
  }
  async function saveIngredient() {
    if (!ingForm.name.trim()) { setMsg('вњ— Р’РІРµРґРёС‚Рµ РЅР°Р·РІР°РЅРёРµ'); return; }
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
      setMsg('вњ“ РЎРѕС…СЂР°РЅРµРЅРѕ');
    } catch (e: any) { setMsg('вњ— ' + (e?.response?.data?.detail || 'РћС€РёР±РєР°')); }
    finally { setBusy(false); }
  }
  async function uploadIngredientImage(id: number, file: File) {
    setBusy(true); setMsg(null);
    try {
      await api.adminUploadIngredientImage(id, file);
      await loadIngredients();
      setMsg('вњ“ РљР°СЂС‚РёРЅРєР° Р·Р°РіСЂСѓР¶РµРЅР°');
    } catch (e: any) { setMsg('вњ— ' + (e?.response?.data?.detail || 'РћС€РёР±РєР°')); }
    finally { setBusy(false); }
  }
  async function deleteIngredient(id: number) {
    if (!(await confirmDialog('РЈРґР°Р»РёС‚СЊ РёРЅРіСЂРµРґРёРµРЅС‚?'))) return;
    setBusy(true); setMsg(null);
    try { await api.adminDeleteIngredient(id); await loadIngredients(); setMsg('вњ“ РЈРґР°Р»РµРЅРѕ'); }
    catch (e: any) { setMsg('вњ— ' + (e?.response?.data?.detail || 'РћС€РёР±РєР°')); }
    finally { setBusy(false); }
  }

  function renderIngredients() {
    return (
      <div>
        <h2>вљ—пёЏ РРЅРіСЂРµРґРёРµРЅС‚С‹</h2>
        <div className="fm-card" style={{ marginBottom: 10 }}>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 8 }}>
            <input className="fm-input" placeholder="РќР°Р·РІР°РЅРёРµ" value={ingForm.name} onChange={(e) => setIngForm({ ...ingForm, name: e.target.value })} />
            <input className="fm-input" type="number" placeholder="РџРѕСЂСЏРґРѕРє" value={ingForm.sort_order} onChange={(e) => setIngForm({ ...ingForm, sort_order: e.target.value })} style={{ width: 80 }} />
          </div>
          <div style={{ marginBottom: 8 }}>
            <label style={{ display: 'block', marginBottom: 4, fontSize: 13 }}>РћРїРёСЃР°РЅРёРµ</label>
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
              рџ–ј РљР°СЂС‚РёРЅРєР°
              <input type="file" accept="image/*" style={{ display: 'none' }}
                onChange={(e) => { const f = e.target.files?.[0]; if (f) uploadIngredientImage(ingEditingId, f); }}
              />
            </label>
          )}
          <button type="button" className="fm-btn" disabled={busy} onClick={saveIngredient}>
            {ingEditingId ? 'вњЋ РЎРѕС…СЂР°РЅРёС‚СЊ' : 'вћ• РЎРѕР·РґР°С‚СЊ'}
          </button>
          {ingEditingId && <button type="button" className="fm-btn" style={{ marginLeft: 6 }} onClick={() => { setIngEditingId(null); setIngForm({ name: '', description: '', sort_order: '0' }); }}>РћС‚РјРµРЅР°</button>}
        </div>
        <table className="fm-table" style={{ width: '100%' }}>
          <thead><tr><th>ID</th><th>РљР°СЂС‚РёРЅРєР°</th><th>РќР°Р·РІР°РЅРёРµ</th><th>РљРѕРґ</th><th>РћРїРёСЃР°РЅРёРµ</th><th>РџРѕСЂСЏРґРѕРє</th><th></th></tr></thead>
          <tbody>
            {shownIngredients.map((ing) => (
              <tr key={ing.id}>
                <td>{ing.id}</td>
                <td>
                  {ing.image_url
                    ? <img src={mediaUrl(ing.image_url)} alt="" style={{ width: 34, height: 34, objectFit: 'cover', borderRadius: 6 }} />
                    : <span style={{ fontSize: 22 }}>вљ—пёЏ</span>}
                </td>
                <td><strong>{ing.name}</strong></td>
                <td style={{ color: 'var(--text-muted)', fontSize: 12 }}>{ing.code}</td>
                <td style={{ color: 'var(--text-muted)', fontSize: 13 }}>{ing.description || 'вЂ”'}</td>
                <td>{ing.sort_order}</td>
                <td style={{ whiteSpace: 'nowrap' }}>
                  <button type="button" className="fm-btn fm-btn-xs" onClick={() => { setIngEditingId(ing.id); setIngForm({ name: ing.name, description: ing.description || '', sort_order: String(ing.sort_order) }); }}>вњЋ</button>{' '}
                  <button type="button" className="fm-btn fm-btn-xs fm-btn-danger" onClick={() => deleteIngredient(ing.id)}>вњ•</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {qActive && shownIngredients.length === 0 && <div className="fm-card" style={{ color: 'var(--text-muted)', marginTop: 8 }}>{NO_MATCH}</div>}
      </div>
    );
  }

  // в”Ђв”Ђ Р›РµС‡РµР±РЅРёС†Р°: РјР°Р·Рё, Р±РѕР»РµР·РЅРё, РїР°С†РёРµРЅС‚С‹ в”Ђв”Ђ
  async function saveDisease() {
    if (!diseaseForm.name.trim()) { setMsg('вњ— Р’РІРµРґРёС‚Рµ РЅР°Р·РІР°РЅРёРµ'); return; }
    setBusy(true); setMsg(null);
    try {
      const data = { name: diseaseForm.name.trim(), description: diseaseForm.description || null, remedy_id: diseaseForm.remedyId ? Number(diseaseForm.remedyId) : null, symptoms: diseaseForm.symptoms };
      if (diseaseEditingId) await api.adminUpdateDisease(diseaseEditingId, data);
      else await api.adminCreateDisease(data);
      await loadInfirmary();
      setDiseaseForm({ name: '', description: '', remedyId: '', symptoms: [] });
      setDiseaseEditingId(null);
      setMsg('вњ“ РЎРѕС…СЂР°РЅРµРЅРѕ');
    } catch (e: any) { setMsg('вњ— ' + (e?.response?.data?.detail || 'РћС€РёР±РєР°')); }
    finally { setBusy(false); }
  }
  function addDiseaseSymptom() {
    if (!diseaseSymPart || !diseaseSymText.trim()) { setMsg('вњ— Р’С‹Р±РµСЂРёС‚Рµ С‡Р°СЃС‚СЊ С‚РµР»Р° Рё РІРїРёС€РёС‚Рµ СЃРёРјРїС‚РѕРј'); return; }
    if (diseaseForm.symptoms.some((s) => s.part_code === diseaseSymPart)) { setMsg('вњ— Р­С‚Р° С‡Р°СЃС‚СЊ С‚РµР»Р° СѓР¶Рµ РґРѕР±Р°РІР»РµРЅР°'); return; }
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
    if (!remedyForm.name.trim()) { setMsg('вњ— Р’РІРµРґРёС‚Рµ РЅР°Р·РІР°РЅРёРµ'); return; }
    if (remedyForm.items.length === 0) { setMsg('вњ— Р”РѕР±Р°РІСЊС‚Рµ С…РѕС‚СЏ Р±С‹ РѕРґРёРЅ РёРЅРіСЂРµРґРёРµРЅС‚'); return; }
    setBusy(true); setMsg(null);
    try {
      const data = { name: remedyForm.name.trim(), description: remedyForm.description || null, recipe_items: remedyForm.items };
      if (remedyEditingId) await api.adminUpdateRemedy(remedyEditingId, data);
      else await api.adminCreateRemedy(data);
      await loadInfirmary();
      setRemedyForm({ name: '', description: '', items: [] });
      setRemedyEditingId(null);
      setMsg('вњ“ РЎРѕС…СЂР°РЅРµРЅРѕ');
    } catch (e: any) { setMsg('вњ— ' + (e?.response?.data?.detail || 'РћС€РёР±РєР°')); }
    finally { setBusy(false); }
  }
  function addRemedyItem() {
    if (remedyPickId === '') { setMsg('вњ— Р’С‹Р±РµСЂРёС‚Рµ РёСЃС‚РѕС‡РЅРёРє'); return; }
    const qty = Number(remedyPickQty);
    if (!qty || qty < 1) { setMsg('вњ— РЈРєР°Р¶РёС‚Рµ РєРѕР»РёС‡РµСЃС‚РІРѕ'); return; }
    const item = remedyPickKind === 'ingredient'
      ? { ingredient_id: Number(remedyPickId), plant_id: null, qty }
      : { ingredient_id: null, plant_id: Number(remedyPickId), qty };
    if (remedyForm.items.some((i) => i.ingredient_id === item.ingredient_id && i.plant_id === item.plant_id)) {
      setMsg('вњ— Р­С‚РѕС‚ РёСЃС‚РѕС‡РЅРёРє СѓР¶Рµ РґРѕР±Р°РІР»РµРЅ');
      return;
    }
    setRemedyForm({ ...remedyForm, items: [...remedyForm.items, item] });
    setRemedyPickId('');
    setRemedyPickQty('1');
  }
  async function deleteRemedy(id: number) {
    if (!(await confirmDialog('РЈРґР°Р»РёС‚СЊ РјР°Р·СЊ?'))) return;
    setBusy(true); setMsg(null);
    try { await api.adminDeleteRemedy(id); await loadInfirmary(); setMsg('вњ“ РЈРґР°Р»РµРЅРѕ'); }
    catch (e: any) { setMsg('вњ— ' + (e?.response?.data?.detail || 'РћС€РёР±РєР°')); }
    finally { setBusy(false); }
  }
  async function uploadDiseaseImage(id: number, file: File) {
    setBusy(true); setMsg(null);
    try {
      await api.adminUploadDiseaseImage(id, file);
      await loadInfirmary();
      setMsg('вњ“ РР·РѕР±СЂР°Р¶РµРЅРёРµ Р±РѕР»РµР·РЅРё Р·Р°РіСЂСѓР¶РµРЅРѕ');
    } catch (e: any) { setMsg('вњ— ' + (e?.response?.data?.detail || 'РћС€РёР±РєР°')); }
    finally { setBusy(false); }
  }
  async function deleteDisease(id: number) {
    if (!(await confirmDialog('РЈРґР°Р»РёС‚СЊ Р±РѕР»РµР·РЅСЊ?'))) return;
    setBusy(true); setMsg(null);
    try { await api.adminDeleteDisease(id); await loadInfirmary(); setMsg('вњ“ РЈРґР°Р»РµРЅРѕ'); }
    catch (e: any) { setMsg('вњ— ' + (e?.response?.data?.detail || 'РћС€РёР±РєР°')); }
    finally { setBusy(false); }
  }
  async function savePatient() {
    if (!patientForm.name.trim()) { setMsg('вњ— Р’РІРµРґРёС‚Рµ РЅР°Р·РІР°РЅРёРµ'); return; }
    setBusy(true); setMsg(null);
    try {
      const data = { name: patientForm.name.trim(), level: Number(patientForm.level) || 1, disease_id: patientForm.diseaseId ? Number(patientForm.diseaseId) : null, animal_type_id: patientForm.animalTypeId ? Number(patientForm.animalTypeId) : null };
      if (patientEditingId) await api.adminUpdatePatient(patientEditingId, data);
      else await api.adminCreatePatient(data);
      await loadInfirmary();
      setPatientForm({ name: '', level: '1', diseaseId: '', animalTypeId: '' });
      setPatientEditingId(null);
      setMsg('вњ“ РЎРѕС…СЂР°РЅРµРЅРѕ (СЃРѕР·РґР°РЅС‹ 3 СЃС†РµРЅС‹: Р±РѕР»СЊРЅРѕРµ / РЅР° Р»РµС‡РµРЅРёРё / Р·РґРѕСЂРѕРІРѕРµ)');
    } catch (e: any) { setMsg('вњ— ' + (e?.response?.data?.detail || 'РћС€РёР±РєР°')); }
    finally { setBusy(false); }
  }
  async function deletePatient(id: number) {
    if (!(await confirmDialog('РЈРґР°Р»РёС‚СЊ РїР°С†РёРµРЅС‚Р° Рё РµРіРѕ СЃС†РµРЅС‹?'))) return;
    setBusy(true); setMsg(null);
    try { await api.adminDeletePatient(id); await loadInfirmary(); setMsg('вњ“ РЈРґР°Р»РµРЅРѕ'); }
    catch (e: any) { setMsg('вњ— ' + (e?.response?.data?.detail || 'РћС€РёР±РєР°')); }
    finally { setBusy(false); }
  }
  async function saveAnimalType() {
    if (!animalTypeForm.name.trim()) { setMsg('вњ— Р’РІРµРґРёС‚Рµ РЅР°Р·РІР°РЅРёРµ'); return; }
    setBusy(true); setMsg(null);
    try {
      const data = { name: animalTypeForm.name.trim(), emoji: animalTypeForm.emoji || null };
      if (animalTypeEditingId) await api.adminUpdateAnimalType(animalTypeEditingId, data);
      else await api.adminCreateAnimalType(data);
      await loadInfirmary();
      setAnimalTypeForm({ name: '', emoji: '' });
      setAnimalTypeEditingId(null);
      setMsg('вњ“ РўРёРї СЃРѕС…СЂР°РЅС‘РЅ');
    } catch (e: any) { setMsg('вњ— ' + (e?.response?.data?.detail || 'РћС€РёР±РєР°')); }
    finally { setBusy(false); }
  }
  async function deleteAnimalType(id: number) {
    if (!(await confirmDialog('РЈРґР°Р»РёС‚СЊ С‚РёРї Р¶РёРІРѕС‚РЅРѕРіРѕ?'))) return;
    setBusy(true); setMsg(null);
    try { await api.adminDeleteAnimalType(id); await loadInfirmary(); setMsg('вњ“ РЈРґР°Р»РµРЅРѕ'); }
    catch (e: any) { setMsg('вњ— ' + (e?.response?.data?.detail || 'РћС€РёР±РєР°')); }
    finally { setBusy(false); }
  }
  async function uploadPatientCardImage(id: number, file: File) {
    setBusy(true); setMsg(null);
    try {
      await api.adminUploadPatientCardImage(id, file);
      await loadInfirmary();
      setMsg('вњ“ РљР°СЂС‚РёРЅРєР° Р·Р°РіСЂСѓР¶РµРЅР°');
    } catch (e: any) { setMsg('вњ— ' + (e?.response?.data?.detail || 'РћС€РёР±РєР°')); }
    finally { setBusy(false); }
  }
  async function uploadPatientAnimalImage(id: number, file: File) {
    setBusy(true); setMsg(null);
    try {
      await api.adminUploadPatientAnimalImage(id, file);
      await loadInfirmary();
      setMsg('вњ“ РР·РѕР±СЂР°Р¶РµРЅРёРµ Р¶РёРІРѕС‚РЅРѕРіРѕ Р·Р°РіСЂСѓР¶РµРЅРѕ');
    } catch (e: any) { setMsg('вњ— ' + (e?.response?.data?.detail || 'РћС€РёР±РєР°')); }
    finally { setBusy(false); }
  }
  async function uploadSceneImage(fieldId: number, file: File) {
    setBusy(true); setMsg(null);
    try {
      await api.adminUploadFieldMap(fieldId, file);
      await loadInfirmary();
      setMsg('вњ“ РљР°СЂС‚РёРЅРєР° СЃС†РµРЅС‹ Р·Р°РіСЂСѓР¶РµРЅР°');
    } catch (e: any) { setMsg('вњ— ' + (e?.response?.data?.detail || 'РћС€РёР±РєР°')); }
    finally { setBusy(false); }
  }
  async function uploadInfirmaryBg(file: File) {
    setBusy(true); setMsg(null);
    try {
      const res = await api.adminUploadInfirmaryBackground(file);
      setInfirmaryBg(res.url);
      setMsg('вњ“ Р¤РѕРЅ Р»РµС‡РµР±РЅРёС†С‹ Р·Р°РіСЂСѓР¶РµРЅ');
    } catch (e: any) { setMsg('вњ— ' + (e?.response?.data?.detail || 'РћС€РёР±РєР°')); }
    finally { setBusy(false); }
  }

  function renderInfirmary() {
    return (
      <div>
        <h2>рџЊІ Р›РµС‡РµР±РЅРёС†Р°</h2>
        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginBottom: 12 }}>
          <TabBtn active={infirmaryTab === 'remedies'} onClick={() => setInfirmaryTab('remedies')}>рџ§ґ РњР°Р·Рё</TabBtn>
          <TabBtn active={infirmaryTab === 'diseases'} onClick={() => setInfirmaryTab('diseases')}>рџ¦  Р‘РѕР»РµР·РЅРё</TabBtn>
          <TabBtn active={infirmaryTab === 'types'} onClick={() => setInfirmaryTab('types')}>рџђѕ РўРёРїС‹ Р¶РёРІРѕС‚РЅС‹С…</TabBtn>
          <TabBtn active={infirmaryTab === 'locations'} onClick={() => setInfirmaryTab('locations')}>рџЊІ Р›РѕРєР°С†РёРё Р›РµС‡РµР±РЅРёС†С‹</TabBtn>
        </div>

        {infirmaryTab === 'remedies' && (<>
        <div className="fm-card" style={{ marginBottom: 10 }}>
          <h3 style={{ marginTop: 0 }}>РњР°Р·Рё (СЃРѕСЃС‚Р°РІ)</h3>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 8 }}>
            <input className="fm-input" placeholder="РќР°Р·РІР°РЅРёРµ" value={remedyForm.name} onChange={(e) => setRemedyForm({ ...remedyForm, name: e.target.value })} />
          </div>
          <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', alignItems: 'center', marginBottom: 8 }}>
            <select className="fm-input" value={remedyPickKind} onChange={(e) => { setRemedyPickKind(e.target.value as 'ingredient' | 'plant'); setRemedyPickId(''); }} style={{ width: 150 }}>
              <option value="ingredient">вљ—пёЏ РђРїС‚РµРєР°СЂСЃРєРёР№</option>
              <option value="plant">рџЊ± Р Р°СЃС‚РµРЅРёРµ</option>
            </select>
            <select className="fm-input" value={remedyPickId} onChange={(e) => setRemedyPickId(e.target.value ? Number(e.target.value) : '')} style={{ minWidth: 160 }}>
              <option value="">вЂ” РІС‹Р±РµСЂРёС‚Рµ вЂ”</option>
              {remedyPickKind === 'ingredient'
                ? ingredients.map((i) => <option key={i.id} value={i.id}>{i.name}</option>)
                : plants.map((p) => <option key={p.id} value={p.id}>{p.emoji || 'рџЊ±'} {p.name}</option>)}
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
                    {label} Г—{it.qty} вњ•
                  </span>
                );
              })}
            </div>
          )}
          <button type="button" className="fm-btn" disabled={busy} onClick={saveRemedy}>{remedyEditingId ? 'вњЋ РЎРѕС…СЂР°РЅРёС‚СЊ' : 'вћ• РЎРѕР·РґР°С‚СЊ'}</button>
          {remedyEditingId && <button type="button" className="fm-btn" style={{ marginLeft: 6 }} onClick={() => { setRemedyEditingId(null); setRemedyForm({ name: '', description: '', items: [] }); }}>РћС‚РјРµРЅР°</button>}
        </div>
        <table className="fm-table" style={{ width: '100%', marginBottom: 16 }}>
          <thead><tr><th>ID</th><th>РќР°Р·РІР°РЅРёРµ</th><th>РЎРѕСЃС‚Р°РІ</th><th></th></tr></thead>
          <tbody>
            {remedies.map((r) => (
              <tr key={r.id}>
                <td>{r.id}</td>
                <td><strong>{r.name}</strong></td>
                <td style={{ fontSize: 12, color: 'var(--text-muted)' }}>{r.recipe_items.map((i) => `${i.ingredient_name || i.plant_name || i.ingredient_id} Г—${i.qty}`).join(', ') || 'вЂ”'}</td>
                <td style={{ whiteSpace: 'nowrap' }}>
                  <button type="button" className="fm-btn fm-btn-xs" onClick={() => { setRemedyEditingId(r.id); setRemedyForm({ name: r.name, description: r.description || '', items: r.recipe_items.map((i) => ({ ingredient_id: i.ingredient_id, plant_id: i.plant_id, qty: i.qty })) }); }}>вњЋ</button>{' '}
                  <button type="button" className="fm-btn fm-btn-xs fm-btn-danger" onClick={() => deleteRemedy(r.id)}>вњ•</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        </>)}

        {infirmaryTab === 'diseases' && (<>
        <div className="fm-card" style={{ marginBottom: 10 }}>
          <h3 style={{ marginTop: 0 }}>Р‘РѕР»РµР·РЅРё (СЃРёРјРїС‚РѕРјС‹)</h3>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 8 }}>
            <input className="fm-input" placeholder="РќР°Р·РІР°РЅРёРµ" value={diseaseForm.name} onChange={(e) => setDiseaseForm({ ...diseaseForm, name: e.target.value })} />
            <select className="fm-input" value={diseaseForm.remedyId} onChange={(e) => setDiseaseForm({ ...diseaseForm, remedyId: e.target.value })}>
              <option value="">вЂ” РјР°Р·СЊ вЂ”</option>
              {remedies.map((r) => <option key={r.id} value={r.id}>{r.name}</option>)}
            </select>
          </div>
          <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', alignItems: 'center', marginBottom: 8 }}>
            <select className="fm-input" value={diseaseSymPart} onChange={(e) => setDiseaseSymPart(e.target.value)} style={{ width: 140 }}>
              <option value="">вЂ” С‡Р°СЃС‚СЊ С‚РµР»Р° вЂ”</option>
              {BODY_PARTS.map((p) => <option key={p.code} value={p.code}>{p.label}</option>)}
            </select>
            <input className="fm-input" placeholder="РЎРёРјРїС‚РѕРј (РЅР°РїСЂРёРјРµСЂ: РіРѕСЂСЏС‡РёР№ РЅРѕСЃ)" value={diseaseSymText} onChange={(e) => setDiseaseSymText(e.target.value)} style={{ flex: 1, minWidth: 160 }} />
            <button type="button" className="fm-btn fm-btn-sm" onClick={addDiseaseSymptom}>+</button>
          </div>
          {diseaseForm.symptoms.length > 0 && (
            <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap', marginBottom: 8 }}>
              {diseaseForm.symptoms.map((s, idx) => (
                <span key={idx} className="fm-card" style={{ padding: '2px 8px', fontSize: 13, cursor: 'pointer' }} onClick={() => setDiseaseForm({ ...diseaseForm, symptoms: diseaseForm.symptoms.filter((_, j) => j !== idx) })}>
                  {BODY_PART_LABELS[s.part_code] || s.part_code}: {s.text} вњ•
                </span>
              ))}
            </div>
          )}
          <button type="button" className="fm-btn" disabled={busy} onClick={saveDisease}>{diseaseEditingId ? 'вњЋ РЎРѕС…СЂР°РЅРёС‚СЊ' : 'вћ• РЎРѕР·РґР°С‚СЊ'}</button>
          {diseaseEditingId && <button type="button" className="fm-btn" style={{ marginLeft: 6 }} onClick={() => { setDiseaseEditingId(null); setDiseaseForm({ name: '', description: '', remedyId: '', symptoms: [] }); }}>РћС‚РјРµРЅР°</button>}
        </div>
        <table className="fm-table" style={{ width: '100%', marginBottom: 16 }}>
          <thead><tr><th>ID</th><th>РќР°Р·РІР°РЅРёРµ</th><th>РњР°Р·СЊ</th><th>РЎРёРјРїС‚РѕРјС‹</th><th>РР·РѕР±СЂР°Р¶РµРЅРёРµ</th><th></th></tr></thead>
          <tbody>
            {diseases.map((d) => (
              <tr key={d.id}>
                <td>{d.id}</td>
                <td><strong>{d.name}</strong></td>
                <td style={{ fontSize: 12 }}>{d.remedy_name || 'вЂ”'}</td>
                <td style={{ fontSize: 12, color: 'var(--text-muted)' }}>{d.symptoms.map((s) => `${BODY_PART_LABELS[s.part_code] || s.part_code}: ${s.text}`).join('; ') || 'вЂ”'}</td>
                <td style={{ whiteSpace: 'nowrap' }}>
                  <span title="РР·РѕР±СЂР°Р¶РµРЅРёРµ Р±РѕР»РµР·РЅРё">{d.image_url ? 'рџ–јпёЏвњ“' : 'рџ–јпёЏвњ—'}</span>{' '}
                  <label className="fm-btn fm-btn-xs fm-btn-outline" title="Р—Р°РіСЂСѓР·РёС‚СЊ РёР·РѕР±СЂР°Р¶РµРЅРёРµ Р±РѕР»РµР·РЅРё" style={{ cursor: 'pointer' }}>в¬†<input type="file" accept="image/*" style={{ display: 'none' }} onChange={(e) => { const f = e.target.files?.[0]; if (f) uploadDiseaseImage(d.id, f); }} /></label>
                </td>
                <td style={{ whiteSpace: 'nowrap' }}>
                  <button type="button" className="fm-btn fm-btn-xs" onClick={() => { setDiseaseEditingId(d.id); setDiseaseForm({ name: d.name, description: d.description || '', remedyId: d.remedy_id ? String(d.remedy_id) : '', symptoms: d.symptoms.map((s) => ({ part_code: s.part_code, text: s.text })) }); }}>вњЋ</button>{' '}
                  <button type="button" className="fm-btn fm-btn-xs fm-btn-danger" onClick={() => deleteDisease(d.id)}>вњ•</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        </>)}

        {infirmaryTab === 'types' && (<>
        <div className="fm-card" style={{ marginBottom: 10 }}>
          <h3 style={{ marginTop: 0 }}>рџђѕ РўРёРїС‹ Р¶РёРІРѕС‚РЅС‹С… Р»РµС‡РµР±РЅРёС†С‹</h3>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 8 }}>
            <input className="fm-input" placeholder="РќР°Р·РІР°РЅРёРµ (РЅР°РїСЂРёРјРµСЂ, Р›РёСЃ)" value={animalTypeForm.name} onChange={(e) => setAnimalTypeForm({ ...animalTypeForm, name: e.target.value })} />
            <input className="fm-input" placeholder="Р­РјРѕРґР·Рё" value={animalTypeForm.emoji} onChange={(e) => setAnimalTypeForm({ ...animalTypeForm, emoji: e.target.value })} style={{ width: 80 }} />
          </div>
          <button type="button" className="fm-btn" disabled={busy} onClick={saveAnimalType}>{animalTypeEditingId ? 'вњЋ РЎРѕС…СЂР°РЅРёС‚СЊ' : 'вћ• РЎРѕР·РґР°С‚СЊ'}</button>
          {animalTypeEditingId && <button type="button" className="fm-btn" style={{ marginLeft: 6 }} onClick={() => { setAnimalTypeEditingId(null); setAnimalTypeForm({ name: '', emoji: '' }); }}>РћС‚РјРµРЅР°</button>}
          <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginTop: 10 }}>
            {animalTypes.map((t) => (
              <span key={t.id} className="fm-card" style={{ padding: '4px 10px', fontSize: 13 }}>
                {t.emoji || 'рџђѕ'} {t.name}{' '}
                <button type="button" className="fm-btn fm-btn-xs" style={{ marginLeft: 6 }} onClick={() => { setAnimalTypeEditingId(t.id); setAnimalTypeForm({ name: t.name, emoji: t.emoji || '' }); }}>вњЋ</button>
                <button type="button" className="fm-btn fm-btn-xs fm-btn-danger" onClick={() => deleteAnimalType(t.id)}>вњ•</button>
              </span>
            ))}
            {animalTypes.length === 0 && <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>РўРёРїРѕРІ РїРѕРєР° РЅРµС‚.</span>}
          </div>
        </div>
        </>)}

        {infirmaryTab === 'locations' && (<>
        <div className="fm-card" style={{ marginBottom: 10 }}>
          <h3 style={{ marginTop: 0 }}>рџ–јпёЏ Р¤РѕРЅ Р»РµС‡РµР±РЅРёС†С‹</h3>
          <p style={{ fontSize: 12, color: 'var(--text-muted)', margin: '0 0 8px' }}>
            РР·РѕР±СЂР°Р¶РµРЅРёРµ Р±СѓРґРµС‚ Р·Р°РґРЅРёРј С„РѕРЅРѕРј РґР»СЏ Р»РµС‡РµР±РЅРёС†С‹ Рё РµС‘ РїРѕРґСЃС‚СЂР°РЅРёС†: СЃС†РµРЅ, Р»Р°Р±РѕСЂР°С‚РѕСЂРёРё СЃРЅР°РґРѕР±РёР№, РїРѕР»СЏРЅС‹ Рё Р»Р°РІРєРё.
          </p>
          {infirmaryBg && (
            <img src={infirmaryBg} alt="Р¤РѕРЅ Р»РµС‡РµР±РЅРёС†С‹" style={{ maxWidth: 200, maxHeight: 120, objectFit: 'cover', borderRadius: 8, marginBottom: 8, display: 'block' }} />
          )}
          <label className="fm-btn" style={{ cursor: 'pointer', display: 'inline-block' }}>в¬† Р—Р°РіСЂСѓР·РёС‚СЊ С„РѕРЅ<input type="file" accept="image/*" style={{ display: 'none' }} onChange={(e) => { const f = e.target.files?.[0]; if (f) uploadInfirmaryBg(f); }} /></label>
        </div>

        <div className="fm-card" style={{ marginBottom: 10 }}>
          <h3 style={{ marginTop: 0 }}>рџЊІ Р›РѕРєР°С†РёРё Р›РµС‡РµР±РЅРёС†С‹</h3>
          <p style={{ fontSize: 12, color: 'var(--text-muted)', margin: '0 0 8px' }}>
            РџСЂРё СЃРѕР·РґР°РЅРёРё Р¶РёРІРѕС‚РЅРѕРіРѕ Р°РІС‚РѕРјР°С‚РёС‡РµСЃРєРё РїРѕСЏРІСЏС‚СЃСЏ С‚СЂРё Р»РѕРєР°С†РёРё-СЃС†РµРЅС‹: Р±РѕР»СЊРЅРѕРµ, РЅР° Р»РµС‡РµРЅРёРё, Р·РґРѕСЂРѕРІРѕРµ. Р”Р»СЏ РєР°Р¶РґРѕР№ СЃС†РµРЅС‹ Р·Р°РіСЂСѓР·РёС‚Рµ РєР°СЂС‚РёРЅРєСѓ Рё РѕС‚РєСЂРѕР№С‚Рµ СЂРµРґР°РєС‚РѕСЂ, С‡С‚РѕР±С‹ СЂР°Р·РјРµСЃС‚РёС‚СЊ С‡Р°СЃС‚Рё С‚РµР»Р° Рё РєРЅРёРіСѓ.
          </p>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 8 }}>
            <input className="fm-input" placeholder="РќР°Р·РІР°РЅРёРµ" value={patientForm.name} onChange={(e) => setPatientForm({ ...patientForm, name: e.target.value })} />
            <select className="fm-input" value={patientForm.animalTypeId} onChange={(e) => setPatientForm({ ...patientForm, animalTypeId: e.target.value })}>
              <option value="">вЂ” С‚РёРї Р¶РёРІРѕС‚РЅРѕРіРѕ вЂ”</option>
              {animalTypes.map((t) => <option key={t.id} value={t.id}>{t.emoji || 'рџђѕ'} {t.name}</option>)}
            </select>
            <select className="fm-input" value={patientForm.level} onChange={(e) => setPatientForm({ ...patientForm, level: e.target.value })}>
              <option value="1">РЈСЂРѕРІРµРЅСЊ 1</option>
              <option value="2">РЈСЂРѕРІРµРЅСЊ 2</option>
              <option value="3">РЈСЂРѕРІРµРЅСЊ 3</option>
            </select>
            <select className="fm-input" value={patientForm.diseaseId} onChange={(e) => setPatientForm({ ...patientForm, diseaseId: e.target.value })}>
              <option value="">вЂ” Р±РѕР»РµР·РЅСЊ вЂ”</option>
              {diseases.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
            </select>
          </div>
          <button type="button" className="fm-btn" disabled={busy} onClick={savePatient}>{patientEditingId ? 'вњЋ РЎРѕС…СЂР°РЅРёС‚СЊ' : 'вћ• РЎРѕР·РґР°С‚СЊ Р¶РёРІРѕС‚РЅРѕРµ'}</button>
          {patientEditingId && <button type="button" className="fm-btn" style={{ marginLeft: 6 }} onClick={() => { setPatientEditingId(null); setPatientForm({ name: '', level: '1', diseaseId: '', animalTypeId: '' }); }}>РћС‚РјРµРЅР°</button>}
        </div>
        <table className="fm-table" style={{ width: '100%' }}>
          <thead><tr><th>ID</th><th>РќР°Р·РІР°РЅРёРµ</th><th>РўРёРї</th><th>РЈСЂ.</th><th>Р‘РѕР»РµР·РЅСЊ</th><th>РЎС†РµРЅС‹</th><th>РР·РѕР±СЂР°Р¶РµРЅРёСЏ</th><th></th></tr></thead>
          <tbody>
            {patients.map((p) => (
              <tr key={p.id}>
                <td>{p.id}</td>
                <td><strong>{p.name}</strong></td>
                <td style={{ fontSize: 12 }}>{p.animal_type_emoji || ''} {p.animal_type_name || 'вЂ”'}</td>
                <td>{p.level}</td>
                <td style={{ fontSize: 12 }}>{p.disease_name || 'вЂ”'}</td>
                <td>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                    {p.scenes.map((sc) => (
                      <div key={sc.field_id} style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: 12 }}>
                        <span>{sc.stage === 'sick' ? 'рџ¤’' : sc.stage === 'treating' ? 'рџЏҐ' : 'вњ…'}</span>
                        <span style={{ minWidth: 90 }}>{sc.stage === 'sick' ? 'Р‘РѕР»СЊРЅРѕРµ' : sc.stage === 'treating' ? 'РќР° Р»РµС‡РµРЅРёРё' : 'Р—РґРѕСЂРѕРІРѕРµ'}</span>
                        <span style={{ fontSize: 12 }} title="РР·РѕР±СЂР°Р¶РµРЅРёРµ СЃС†РµРЅС‹">{sc.map_url ? 'рџ–јпёЏвњ“' : 'рџ–јпёЏвњ—'}</span>
                        <label className="fm-btn fm-btn-xs fm-btn-outline" title="РљР°СЂС‚РёРЅРєР° СЃС†РµРЅС‹" style={{ cursor: 'pointer', marginRight: 2 }}>в¬†<input type="file" accept="image/*" style={{ display: 'none' }} onChange={(e) => { const f = e.target.files?.[0]; if (f) uploadSceneImage(sc.field_id, f); }} /></label>
                        <button type="button" className="fm-btn fm-btn-xs" onClick={() => { setEditorFieldId(sc.field_id); }}>вњЋ Р Р°Р·РјРµС‚РёС‚СЊ</button>
                      </div>
                    ))}
                  </div>
                </td>
                <td style={{ whiteSpace: 'nowrap' }}>
                  <span title="РР·РѕР±СЂР°Р¶РµРЅРёРµ Р¶РёРІРѕС‚РЅРѕРіРѕ">{p.animal_image_url ? 'рџђѕвњ“' : 'рџђѕвњ—'}</span>{' '}
                  <label className="fm-btn fm-btn-xs fm-btn-outline" title="РР·РѕР±СЂР°Р¶РµРЅРёРµ Р¶РёРІРѕС‚РЅРѕРіРѕ" style={{ cursor: 'pointer', marginRight: 2 }}>в¬†<input type="file" accept="image/*" style={{ display: 'none' }} onChange={(e) => { const f = e.target.files?.[0]; if (f) uploadPatientAnimalImage(p.id, f); }} /></label>
                  <label className="fm-btn fm-btn-xs fm-btn-outline" title="РљР°СЂС‚РѕС‡РєР° РєРѕР»Р»РµРєС†РёРё" style={{ cursor: 'pointer' }}>рџѓЏ<input type="file" accept="image/*" style={{ display: 'none' }} onChange={(e) => { const f = e.target.files?.[0]; if (f) uploadPatientCardImage(p.id, f); }} /></label>
                </td>
                <td style={{ whiteSpace: 'nowrap' }}>
                  <button type="button" className="fm-btn fm-btn-xs" onClick={() => { setPatientEditingId(p.id); setPatientForm({ name: p.name, level: String(p.level), diseaseId: p.disease_id ? String(p.disease_id) : '', animalTypeId: p.animal_type_id ? String(p.animal_type_id) : '' }); }}>вњЋ</button>{' '}
                  <button type="button" className="fm-btn fm-btn-xs fm-btn-danger" onClick={() => deletePatient(p.id)}>вњ•</button>
                </td>
              </tr>
            ))}
            {patients.length === 0 && (
              <tr><td colSpan={8} style={{ color: 'var(--text-muted)' }}>Р–РёРІРѕС‚РЅС‹С… Р»РµС‡РµР±РЅРёС†С‹ РїРѕРєР° РЅРµС‚.</td></tr>
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
        <h2>рџ§Є Р РµС†РµРїС‚С‹ Р·РµР»РёР№</h2>
        <div className="fm-card" style={{ marginBottom: 10 }}>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 8 }}>
            <input className="fm-input" placeholder="РќР°Р·РІР°РЅРёРµ" value={potionForm.name} onChange={(e) => setPotionForm({ ...potionForm, name: e.target.value })} />
            <select className="fm-input" value={potionForm.level} onChange={(e) => setPotionForm({ ...potionForm, level: e.target.value })}>
              <option value="green">рџџў РџСЂРѕСЃС‚РѕРµ</option>
              <option value="blue">рџ”µ РЎСЂРµРґРЅРµРµ</option>
              <option value="violet">рџџЈ РЎР»РѕР¶РЅРѕРµ</option>
            </select>
            <input className="fm-input" type="number" placeholder="РњРѕРЅРµС‚" value={potionForm.reward_coins || ''} onChange={(e) => setPotionForm({ ...potionForm, reward_coins: Number(e.target.value) })} style={{ width: 80 }} />
            <select className="fm-input" value={potionForm.bonus_code || ''} onChange={(e) => setPotionForm({ ...potionForm, bonus_code: e.target.value || null })}>
              <option value="">Р‘РµР· Р±РѕРЅСѓСЃР°</option>
              <option value="double_garden_harvest">рџџў Г—2 РіСЂСЏРґРєР°</option>
              <option value="double_orchard_harvest">рџџў Г—2 СЃР°Рґ</option>
              <option value="double_animal_product">рџџў Г—2 Р¶РёРІРѕС‚РЅРѕРµ</option>
              <option value="skip_plant_stitch">рџџў Р‘РµР· РѕС‚С€РёРІР°</option>
              <option value="early_level_up">рџџў +1 СѓСЂРѕРІРµРЅСЊ</option>
              <option value="double_order_reward">рџџў Г—2 Р·Р°РєР°Р·</option>
              <option value="free_pet">рџ”µ РџРёС‚РѕРјРµС†</option>
              <option value="extra_barnyard_slot">рџ”µ +1 Р·Р°РіРѕРЅ</option>
              <option value="bonus_sewing_product">рџ”µ +1 РїРѕСЂС‚РЅРёС…Р°</option>
              <option value="bonus_workshop_product">рџ”µ +1 РјР°СЃС‚РµСЂСЃРєР°СЏ</option>
              <option value="bonus_alchemy_product">рџ”µ +1 Р·РµР»СЊРµРІР°СЂРµРЅРёРµ</option>
              <option value="skip_animal_stitch">рџџЈ Р‘РµР· РѕС‚С€РёРІР° Р¶РёРІ.</option>
              <option value="unlock_garden_l3">рџџЈ Р“СЂСЏРґРєР° 3 СѓСЂ.</option>
              <option value="unlock_orchard_l3">рџџЈ РЎР°Рґ 3 СѓСЂ.</option>
              <option value="partial_order">рџџЈ РќРµРїРѕР»РЅС‹Р№ Р·Р°РєР°Р·</option>
            </select>
          </div>
          <div style={{ marginBottom: 8, display: 'flex', gap: 6, alignItems: 'center' }}>
            <span style={{ fontSize: 13 }}>РРЅРіСЂРµРґРёРµРЅС‚С‹:</span>
            <select className="fm-input" value={potionSlotInput} onChange={(e) => setPotionSlotInput(e.target.value)}>
              <option value="">вЂ” С‚РёРї РёРЅРіСЂРµРґРёРµРЅС‚Р° вЂ”</option>
              <option value="plant_garden">рџЊ± Р Р°СЃС‚РµРЅРёРµ (РіСЂСЏРґРєР°)</option>
              <option value="plant_orchard">рџЌЋ Р Р°СЃС‚РµРЅРёРµ (СЃР°Рґ)</option>
              <option value="animal_product">рџђ„ РџСЂРѕРґСѓРєС†РёСЏ Р¶РёРІРѕС‚РЅРѕРіРѕ</option>
              <option value="workshop">рџ”Ё РўРѕРІР°СЂ РјР°СЃС‚РµСЂСЃРєРѕР№</option>
              <option value="sewing">рџ§µ РўРѕРІР°СЂ РїРѕСЂС‚РЅРёС…Рё</option>
              <option value="alchemy">рџ”® РўРѕРІР°СЂ Р·РµР»СЊРµРІР°СЂРµРЅРёСЏ</option>
              <option value="barnyard">рџЏљпёЏ РўРѕРІР°СЂ СЃРєРѕС‚РЅРѕРіРѕ РґРІРѕСЂР°</option>
            </select>
            <button type="button" className="fm-btn fm-btn-sm" onClick={() => { if (potionSlotInput.trim()) { setPotionForm({ ...potionForm, ingredient_slots: [...potionForm.ingredient_slots, potionSlotInput.trim()] }); setPotionSlotInput(''); } }}>+</button>
          </div>
          <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap', marginBottom: 8 }}>
            {potionForm.ingredient_slots.map((s, i) => (
              <span key={i} className="fm-card" style={{ padding: '2px 8px', fontSize: 13, cursor: 'pointer' }} onClick={() => setPotionForm({ ...potionForm, ingredient_slots: potionForm.ingredient_slots.filter((_, j) => j !== i) })}>
                {potionIngredientLabel(s)} вњ•
              </span>
            ))}
          </div>
          <div style={{ marginBottom: 8 }}>
            <label style={{ display: 'block', marginBottom: 4, fontSize: 13 }}>РћРїРёСЃР°РЅРёРµ РґРµР№СЃС‚РІРёСЏ Р·РµР»СЊСЏ</label>
            <textarea
              className="fm-input"
              value={potionForm.description || ''}
              onChange={(e) => setPotionForm({ ...potionForm, description: e.target.value })}
              placeholder="РќР°РїСЂРёРјРµСЂ: СѓРґРІР°РёРІР°РµС‚ СѓСЂРѕР¶Р°Р№ СЃ РѕРґРЅРѕР№ РіСЂСЏРґРєРё"
              rows={2}
              style={{ width: '100%' }}
            />
          </div>
          {potionEditingId && (
            <>
              <label className="fm-btn fm-btn-sm fm-btn-outline" style={{ cursor: 'pointer', marginBottom: 8, display: 'inline-flex', alignItems: 'center', gap: 6 }}>
                рџ–ј РљР°СЂС‚РёРЅРєР° Р·РµР»СЊСЏ
                <input type="file" accept="image/*" style={{ display: 'none' }}
                  onChange={(e) => { const f = e.target.files?.[0]; if (f) uploadPotionImage(potionEditingId, f); }}
                />
              </label>
              <label className="fm-btn fm-btn-sm fm-btn-outline" style={{ cursor: 'pointer', marginBottom: 8, marginLeft: 6, display: 'inline-flex', alignItems: 'center', gap: 6 }}>
                рџѓЏ РљР°СЂС‚РѕС‡РєР° СЂРµС†РµРїС‚Р°
                <input type="file" accept="image/*" style={{ display: 'none' }}
                  onChange={(e) => { const f = e.target.files?.[0]; if (f) uploadPotionCardImage(potionEditingId, f); }}
                />
              </label>
            </>
          )}
          <button type="button" className="fm-btn" disabled={busy} onClick={savePotionRecipe}>
            {potionEditingId ? 'вњЋ РЎРѕС…СЂР°РЅРёС‚СЊ' : 'вћ• РЎРѕР·РґР°С‚СЊ'}
          </button>
          {potionEditingId && <button type="button" className="fm-btn" style={{ marginLeft: 6 }} onClick={() => { setPotionEditingId(null); setPotionForm({ name: '', level: 'green', ingredient_slots: [], bonus_code: null, reward_coins: 100, description: '' }); }}>РћС‚РјРµРЅР°</button>}
        </div>
        <table className="fm-table" style={{ width: '100%' }}>
          <thead><tr><th>ID</th><th>РќР°Р·РІР°РЅРёРµ</th><th>РЈСЂРѕРІРµРЅСЊ</th><th>РЎР»РѕС‚РѕРІ</th><th>Р‘РѕРЅСѓСЃ</th><th>РћРїРёСЃР°РЅРёРµ</th><th></th></tr></thead>
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
                <td>{potionBonusLabel(r.bonus_code) || 'вЂ”'}</td>
                <td style={{ maxWidth: 220 }}>{r.description || 'вЂ”'}</td>
                <td>
                  <button type="button" className="fm-btn fm-btn-sm" onClick={() => { setPotionEditingId(r.id); setPotionForm({ name: r.name, level: r.level, ingredient_slots: r.ingredient_slots, bonus_code: r.bonus_code, reward_coins: r.reward_coins, description: r.description || '' }); }}>вњЋ</button>
                  <button type="button" className="fm-btn fm-btn-sm" style={{ marginLeft: 4 }} onClick={() => deletePotionRecipe(r.id)}>рџ—‘</button>
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
        <h2>рџЌё Р РµС†РµРїС‚С‹ РєРѕРєС‚РµР№Р»РµР№</h2>
        <div className="fm-card" style={{ marginBottom: 10 }}>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 8 }}>
            <input className="fm-input" placeholder="РќР°Р·РІР°РЅРёРµ" value={cocktailForm.name} onChange={(e) => setCocktailForm({ ...cocktailForm, name: e.target.value })} />
            <select className="fm-input" value={cocktailForm.patient_id} onChange={(e) => setCocktailForm({ ...cocktailForm, patient_id: e.target.value })}>
              <option value="">РћС‚РєСЂС‹С‚ СЃСЂР°Р·Сѓ (Р±РµР· Р¶РёРІРѕС‚РЅРѕРіРѕ)</option>
              {patients.map((p) => (
                <option key={p.id} value={p.id}>рџ”“ Р–РёРІРѕС‚РЅРѕРµ: {p.name}</option>
              ))}
            </select>
          </div>
          <div style={{ marginBottom: 8 }}>
            <label style={{ display: 'block', marginBottom: 4, fontSize: 13 }}>РРЅРіСЂРµРґРёРµРЅС‚С‹ РєРѕРєС‚РµР№Р»СЏ (С‚РѕС‡РЅС‹Рµ РїСЂРµРґРјРµС‚С‹)</label>
            <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginBottom: 6 }}>
              <select className="fm-input" value={cocktailPickKind} onChange={(e) => { setCocktailPickKind(e.target.value as any); setCocktailPickId(''); }}>
                <option value="product">рџ“¦ РўРѕРІР°СЂ</option>
                <option value="plant">рџЊ± Р Р°СЃС‚РµРЅРёРµ</option>
                <option value="ingredient">рџЊѕ РРЅРіСЂРµРґРёРµРЅС‚</option>
                <option value="remedy">вљ—пёЏ Р›РµРєР°СЂСЃС‚РІРѕ</option>
              </select>
              <select className="fm-input" value={cocktailPickId} onChange={(e) => setCocktailPickId(e.target.value)}>
                <option value="">вЂ” РїСЂРµРґРјРµС‚ вЂ”</option>
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
                  {cocktailItemName(it.kind, it.item_id)} Г—{it.qty} вњ•
                </span>
              ))}
            </div>
          </div>
          <div style={{ marginBottom: 8 }}>
            <label style={{ display: 'block', marginBottom: 4, fontSize: 13 }}>РћРїРёСЃР°РЅРёРµ РєРѕРєС‚РµР№Р»СЏ</label>
            <textarea
              className="fm-input"
              value={cocktailForm.description}
              onChange={(e) => setCocktailForm({ ...cocktailForm, description: e.target.value })}
              placeholder="РќР°РїСЂРёРјРµСЂ: РѕСЃРІРµР¶Р°СЋС‰РёР№ Р»РµСЃРЅРѕР№ РєРѕРєС‚РµР№Р»СЊ"
              rows={2}
              style={{ width: '100%' }}
            />
          </div>
          {cocktailEditingId && (
            <>
              <label className="fm-btn fm-btn-sm fm-btn-outline" style={{ cursor: 'pointer', marginBottom: 8, display: 'inline-flex', alignItems: 'center', gap: 6 }}>
                рџ–ј РљР°СЂС‚РёРЅРєР° РєРѕРєС‚РµР№Р»СЏ
                <input type="file" accept="image/*" style={{ display: 'none' }}
                  onChange={(e) => { const f = e.target.files?.[0]; if (f) uploadCocktailImage(cocktailEditingId, f); }}
                />
              </label>
              <label className="fm-btn fm-btn-sm fm-btn-outline" style={{ cursor: 'pointer', marginBottom: 8, marginLeft: 6, display: 'inline-flex', alignItems: 'center', gap: 6 }}>
                рџѓЏ РљР°СЂС‚РѕС‡РєР° СЂРµС†РµРїС‚Р°
                <input type="file" accept="image/*" style={{ display: 'none' }}
                  onChange={(e) => { const f = e.target.files?.[0]; if (f) uploadCocktailCardImage(cocktailEditingId, f); }}
                />
              </label>
            </>
          )}
          <button type="button" className="fm-btn" disabled={busy} onClick={saveCocktailRecipe}>
            {cocktailEditingId ? 'вњЋ РЎРѕС…СЂР°РЅРёС‚СЊ' : 'вћ• РЎРѕР·РґР°С‚СЊ'}
          </button>
          {cocktailEditingId && <button type="button" className="fm-btn" style={{ marginLeft: 6 }} onClick={() => { setCocktailEditingId(null); setCocktailForm({ name: '', description: '', patient_id: '', items: [] }); }}>РћС‚РјРµРЅР°</button>}
        </div>
        <table className="fm-table" style={{ width: '100%' }}>
          <thead><tr><th>ID</th><th>РќР°Р·РІР°РЅРёРµ</th><th>Р–РёРІРѕС‚РЅРѕРµ</th><th>РЎРѕСЃС‚Р°РІ</th><th></th></tr></thead>
          <tbody>
            {shownCocktailRecipes.map((r) => (
              <tr key={r.id}>
                <td>{r.id}</td>
                <td>
                  {r.image_url && <img src={mediaUrl(r.image_url)} alt="" style={{ width: 28, height: 28, objectFit: 'cover', borderRadius: 4, marginRight: 4, verticalAlign: 'middle' }} />}
                  {r.card_image_url && <img src={mediaUrl(r.card_image_url)} alt="" style={{ width: 28, height: 28, objectFit: 'cover', borderRadius: 4, marginRight: 4, verticalAlign: 'middle', border: '1px solid var(--border)' }} />}
                  {r.name}
                </td>
                <td>{r.patient_name || 'вЂ”'}</td>
                <td style={{ maxWidth: 260 }}>{r.items.map((i) => `${i.name || i.kind} Г—${i.qty}`).join(', ')}</td>
                <td>
                  <button type="button" className="fm-btn fm-btn-sm" onClick={() => { setCocktailEditingId(r.id); setCocktailForm({ name: r.name, description: r.description || '', patient_id: r.patient_id != null ? String(r.patient_id) : '', items: r.items.map((i) => ({ kind: i.kind, item_id: i.item_id, qty: i.qty })) }); }}>вњЋ</button>
                  <button type="button" className="fm-btn fm-btn-sm" style={{ marginLeft: 4 }} onClick={() => deleteCocktailRecipe(r.id)}>рџ—‘</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {qActive && shownCocktailRecipes.length === 0 && <div className="fm-card" style={{ color: 'var(--text-muted)', marginTop: 8 }}>{NO_MATCH}</div>}
      </div>
    );
  }

  // в”Ђв”Ђ Р РµС†РµРїС‚С‹ Р±РёР±Р»РёРѕС‚РµРєРё в”Ђв”Ђ
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
    if (!productId) { setMsg('вњ— Р’С‹Р±РµСЂРёС‚Рµ С‚РѕРІР°СЂ'); return; }
    const plantId = recipeForm.source_kind === 'plant' ? Number(recipeForm.plant_id) || null : null;
    const sourceProductId = recipeForm.source_kind === 'animal_product' ? Number(recipeForm.source_product_id) || null : null;
    if (!plantId && !sourceProductId) {
      setMsg(recipeForm.source_kind === 'plant' ? 'вњ— Р’С‹Р±РµСЂРёС‚Рµ СЂР°СЃС‚РµРЅРёРµ' : 'вњ— Р’С‹Р±РµСЂРёС‚Рµ РїСЂРѕРґСѓРєС†РёСЋ Р¶РёРІРѕС‚РЅРѕРіРѕ');
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
      setMsg('вњ“ РЎРѕС…СЂР°РЅРµРЅРѕ');
    } catch (e: any) { setMsg('вњ— ' + (e?.response?.data?.detail || 'РћС€РёР±РєР°')); }
    finally { setBusy(false); }
  }
  async function deleteRecipe(id: number) {
    if (!(await confirmDialog('РЈРґР°Р»РёС‚СЊ СЂРµС†РµРїС‚?'))) return;
    setBusy(true); setMsg(null);
    try { await api.adminDeleteRecipe(id); await loadRecipes(); setMsg('вњ“ РЈРґР°Р»РµРЅРѕ'); }
    catch (e: any) { setMsg('вњ— ' + (e?.response?.data?.detail || 'РћС€РёР±РєР°')); }
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
        <h2>рџ“љ Р РµС†РµРїС‚С‹ Р±РёР±Р»РёРѕС‚РµРєРё</h2>
        <div className="fm-card" style={{ marginBottom: 10 }}>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 8 }}>
            <select className="fm-input" value={recipeForm.source_kind} onChange={(e) => setRecipeForm({ ...recipeForm, source_kind: e.target.value })}>
              <option value="plant">рџЊ± РР· СЂР°СЃС‚РµРЅРёСЏ</option>
              <option value="animal_product">рџҐљ РР· РїСЂРѕРґСѓРєС†РёРё Р¶РёРІРѕС‚РЅРѕРіРѕ</option>
            </select>
            {recipeForm.source_kind === 'plant' ? (
              <select className="fm-input" value={recipeForm.plant_id} onChange={(e) => setRecipeForm({ ...recipeForm, plant_id: e.target.value })}>
                <option value="">вЂ” СЂР°СЃС‚РµРЅРёРµ вЂ”</option>
                {(recipeEditingId ? plants : recipePlants).map((p) => (
                  <option key={p.id} value={String(p.id)}>{p.emoji || 'рџЊ±'} {p.name}</option>
                ))}
              </select>
            ) : (
              <select className="fm-input" value={recipeForm.source_product_id} onChange={(e) => setRecipeForm({ ...recipeForm, source_product_id: e.target.value })}>
                <option value="">вЂ” РїСЂРѕРґСѓРєС†РёСЏ Р¶РёРІРѕС‚РЅРѕРіРѕ вЂ”</option>
                {animalProducts.map((p) => (
                  <option key={p.id} value={String(p.id)}>{p.emoji || 'рџҐљ'} {p.name}</option>
                ))}
              </select>
            )}
            <select className="fm-input" value={recipeForm.product_id} onChange={(e) => setRecipeForm({ ...recipeForm, product_id: e.target.value })}>
              <option value="">вЂ” С‚РѕРІР°СЂ вЂ”</option>
              {catalogProducts.map((p) => (
                <option key={p.id} value={String(p.id)}>{p.emoji || 'рџ“¦'} {p.name}</option>
              ))}
            </select>
            <select className="fm-input" value={recipeForm.level} onChange={(e) => setRecipeForm({ ...recipeForm, level: e.target.value })}>
              <option value="1">1 СѓСЂРѕРІРµРЅСЊ</option>
              <option value="2">2 СѓСЂРѕРІРµРЅСЊ</option>
              <option value="3">3 СѓСЂРѕРІРµРЅСЊ</option>
            </select>
          </div>
          <button type="button" className="fm-btn" disabled={busy} onClick={saveRecipe}>
            {recipeEditingId ? 'вњЋ РЎРѕС…СЂР°РЅРёС‚СЊ' : 'вћ• РЎРѕР·РґР°С‚СЊ'}
          </button>
          {recipeEditingId && <button type="button" className="fm-btn" style={{ marginLeft: 6 }} onClick={() => { setRecipeEditingId(null); setRecipeForm({ source_kind: 'plant', plant_id: '', source_product_id: '', product_id: '', level: '1' }); }}>РћС‚РјРµРЅР°</button>}
        </div>
        <table className="fm-table" style={{ width: '100%' }}>
          <thead><tr><th>ID</th><th>РСЃС‚РѕС‡РЅРёРє</th><th>РўРѕРІР°СЂ</th><th>РЈСЂРѕРІРµРЅСЊ</th><th></th></tr></thead>
          <tbody>
            {shownRecipes.map((r) => (
              <tr key={r.id}>
                <td>{r.id}</td>
                <td>{r.source_product_id != null
                  ? <>{r.source_product_emoji || 'рџҐљ'} {r.source_product_name}</>
                  : <>{r.plant_emoji || 'рџЊ±'} {r.plant_name}</>}</td>
                <td>{r.product_emoji || 'рџ“¦'} {r.product_name}</td>
                <td>{r.level}</td>
                <td>
                  <button type="button" className="fm-btn fm-btn-sm" onClick={() => { setRecipeEditingId(r.id); setRecipeForm({
                    source_kind: r.source_product_id != null ? 'animal_product' : 'plant',
                    plant_id: r.plant_id != null ? String(r.plant_id) : '',
                    source_product_id: r.source_product_id != null ? String(r.source_product_id) : '',
                    product_id: String(r.product_id),
                    level: String(r.level),
                  }); }}>вњЋ</button>
                  <button type="button" className="fm-btn fm-btn-sm" style={{ marginLeft: 4 }} onClick={() => deleteRecipe(r.id)}>рџ—‘</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {qActive && shownRecipes.length === 0 && <div className="fm-card" style={{ color: 'var(--text-muted)', marginTop: 8 }}>{NO_MATCH}</div>}
      </div>
    );
  }

  // в”Ђв”Ђ Р¤РѕРЅ в”Ђв”Ђ
  async function loadBg() {
    try { const data = await api.getBackground(); setBgUrl(data.url); setBgInput(data.url); }
    catch { /* ignore */ }
  }
  async function saveBg() {
    setBusy(true); setMsg(null);
    try { const data = await api.setBackground(bgInput); setBgUrl(data.url); setMsg('вњ“ Р¤РѕРЅ РѕР±РЅРѕРІР»С‘РЅ'); }
    catch (e: any) { setMsg('вњ— ' + (e?.response?.data?.detail || 'РћС€РёР±РєР°')); }
    finally { setBusy(false); }
  }

  async function uploadPlantImage(id: number, file: File) {
    setBusy(true); setMsg(null);
    try { await api.adminUploadPlantImage(id, file); await load(); setMsg('вњ“ РР·РѕР±СЂР°Р¶РµРЅРёРµ Р·Р°РіСЂСѓР¶РµРЅРѕ'); }
    catch (e: any) { setMsg('вњ— ' + (e?.response?.data?.detail || 'РћС€РёР±РєР°')); }
    finally { setBusy(false); }
  }
  async function uploadPlantImageYoung(id: number, file: File) {
    setBusy(true); setMsg(null);
    try { await api.adminUploadPlantImageYoung(id, file); await load(); setMsg('вњ“ РњРѕР»РѕРґРѕРµ СЂР°СЃС‚РµРЅРёРµ Р·Р°РіСЂСѓР¶РµРЅРѕ'); }
    catch (e: any) { setMsg('вњ— ' + (e?.response?.data?.detail || 'РћС€РёР±РєР°')); }
    finally { setBusy(false); }
  }
  async function uploadPlantImageGrown(id: number, file: File) {
    setBusy(true); setMsg(null);
    try { await api.adminUploadPlantImageGrown(id, file); await load(); setMsg('вњ“ РЎРѕР·СЂРµРІС€РµРµ СЂР°СЃС‚РµРЅРёРµ Р·Р°РіСЂСѓР¶РµРЅРѕ'); }
    catch (e: any) { setMsg('вњ— ' + (e?.response?.data?.detail || 'РћС€РёР±РєР°')); }
    finally { setBusy(false); }
  }
  async function uploadPlantImageHarvested(id: number, file: File) {
    setBusy(true); setMsg(null);
    try { await api.adminUploadPlantImageHarvested(id, file); await load(); setMsg('вњ“ Р’С‹СЂР°С‰РµРЅРЅРѕРµ СЂР°СЃС‚РµРЅРёРµ Р·Р°РіСЂСѓР¶РµРЅРѕ'); }
    catch (e: any) { setMsg('вњ— ' + (e?.response?.data?.detail || 'РћС€РёР±РєР°')); }
    finally { setBusy(false); }
  }
  async function uploadAnimalImage(id: number, file: File) {
    setBusy(true); setMsg(null);
    try { await api.adminUploadAnimalImage(id, file); await load(); setMsg('вњ“ РР·РѕР±СЂР°Р¶РµРЅРёРµ Р·Р°РіСЂСѓР¶РµРЅРѕ'); }
    catch (e: any) { setMsg('вњ— ' + (e?.response?.data?.detail || 'РћС€РёР±РєР°')); }
    finally { setBusy(false); }
  }
  async function uploadAnimalEmptyPenImage(id: number, file: File) {
    setBusy(true); setMsg(null);
    try { await api.adminUploadAnimalEmptyPenImage(id, file); await load(); setMsg('вњ“ Р—Р°РіРѕРЅ Р·Р°РіСЂСѓР¶РµРЅ'); }
    catch (e: any) { setMsg('вњ— ' + (e?.response?.data?.detail || 'РћС€РёР±РєР°')); }
    finally { setBusy(false); }
  }
  async function uploadAnimalPenImage(id: number, file: File) {
    setBusy(true); setMsg(null);
    try { await api.adminUploadAnimalPenImage(id, file); await load(); setMsg('вњ“ Р’С‹СЂР°С‰РµРЅРЅРѕРµ (Р·Р°РіРѕРЅ СЃ Р¶РёРІРѕС‚РЅС‹Рј) Р·Р°РіСЂСѓР¶РµРЅРѕ'); }
    catch (e: any) { setMsg('вњ— ' + (e?.response?.data?.detail || 'РћС€РёР±РєР°')); }
    finally { setBusy(false); }
  }
  async function uploadPetImage(id: number, file: File) {
    setBusy(true); setMsg(null);
    try { await api.adminUploadPetImage(id, file); await load(); setMsg('вњ“ РР·РѕР±СЂР°Р¶РµРЅРёРµ Р·Р°РіСЂСѓР¶РµРЅРѕ'); }
    catch (e: any) { setMsg('вњ— ' + (e?.response?.data?.detail || 'РћС€РёР±РєР°')); }
    finally { setBusy(false); }
  }

  async function uploadProductionImage(id: number, file: File) {
    setBusy(true); setMsg(null);
    try { await api.adminUploadProductionTemplateImage(id, file); await load(); setMsg('вњ“ РР·РѕР±СЂР°Р¶РµРЅРёРµ Р·Р°РіСЂСѓР¶РµРЅРѕ'); }
    catch (e: any) { setMsg('вњ— ' + (e?.response?.data?.detail || 'РћС€РёР±РєР°')); }
    finally { setBusy(false); }
  }

  async function uploadProductImage(id: number, file: File) {
    setBusy(true); setMsg(null);
    try { await api.adminUploadProductImage(id, file); await load(); setMsg('вњ“ РР·РѕР±СЂР°Р¶РµРЅРёРµ Р·Р°РіСЂСѓР¶РµРЅРѕ'); }
    catch (e: any) { setMsg('вњ— ' + (e?.response?.data?.detail || 'РћС€РёР±РєР°')); }
    finally { setBusy(false); }
  }

  async function saveGameMedia() {
    const mt = MEDIA_TYPES.find(m => m.code === mediaTypeSel);
    if (!mt) { setMsg('вњ— Р’С‹Р±РµСЂРёС‚Рµ С‚РёРї'); return; }
    setBusy(true); setMsg(null);
    try {
      await api.adminCreateGameMedia({ code: mt.code, kind: mt.kind });
      setMediaTypeSel('');
      const list = await api.adminGameMedia();
      setGameMedia(list);
      setMsg('вњ“ РЎРѕР·РґР°РЅРѕ');
    } catch (e: any) { setMsg('вњ— ' + (e?.response?.data?.detail || 'РћС€РёР±РєР°')); }
    finally { setBusy(false); }
  }

  async function deleteGameMedia(id: number) {
    if (!(await confirmDialog('РЈРґР°Р»РёС‚СЊ РјРµРґРёР°?'))) return;
    setBusy(true); setMsg(null);
    try { await api.adminDeleteGameMedia(id); setGameMedia(await api.adminGameMedia()); setMsg('вњ“ РЈРґР°Р»РµРЅРѕ'); }
    catch (e: any) { setMsg('вњ— ' + (e?.response?.data?.detail || 'РћС€РёР±РєР°')); }
    finally { setBusy(false); }
  }

  async function uploadGameMediaFile(id: number, file: File) {
    setBusy(true); setMsg(null);
    try { await api.adminUploadGameMedia(id, file); setGameMedia(await api.adminGameMedia()); setMsg('вњ“ Р¤Р°Р№Р» Р·Р°РіСЂСѓР¶РµРЅ'); }
    catch (e: any) { setMsg('вњ— ' + (e?.response?.data?.detail || 'РћС€РёР±РєР°')); }
    finally { setBusy(false); }
  }

  // в”Ђв”Ђ РџСЂРµРґС‹СЃС‚РѕСЂРёСЏ в”Ђв”Ђ
  async function saveStorySlide() {
    if (!storyForm.text.trim()) { setMsg('вњ— Р’РІРµРґРёС‚Рµ С‚РµРєСЃС‚'); return; }
    setBusy(true); setMsg(null);
    try {
      const data = { text: storyForm.text.trim(), sort_order: Number(storyForm.sort_order) || 0, location_code: storyForm.location_code || null };
      if (storyEditingId) await api.adminUpdateStorySlide(storyEditingId, data);
      else await api.adminCreateStorySlide(data);
      setMsg('вњ“ РЎР»Р°Р№Рґ СЃРѕС…СЂР°РЅС‘РЅ');
      setStoryForm({ text: '', sort_order: '0', location_code: '' });
      setStoryEditingId(null);
      setStorySlides(await api.adminStorySlides());
    } catch (e: any) { setMsg('вњ— ' + (e?.response?.data?.detail || 'РћС€РёР±РєР°')); }
    finally { setBusy(false); }
  }

  async function uploadStoryImage(id: number, file: File) {
    setBusy(true); setMsg(null);
    try { await api.adminUploadStorySlideImage(id, file); setStorySlides(await api.adminStorySlides()); setMsg('вњ“ РљР°СЂС‚РёРЅРєР° Р·Р°РіСЂСѓР¶РµРЅР°'); }
    catch (e: any) { setMsg('вњ— ' + (e?.response?.data?.detail || 'РћС€РёР±РєР°')); }
    finally { setBusy(false); }
  }

  async function deleteStorySlide(id: number) {
    if (!(await confirmDialog('РЈРґР°Р»РёС‚СЊ СЃР»Р°Р№Рґ РїСЂРµРґС‹СЃС‚РѕСЂРёРё?'))) return;
    setBusy(true); setMsg(null);
    try { await api.adminDeleteStorySlide(id); setStorySlides(await api.adminStorySlides()); setMsg('вњ“ РЈРґР°Р»РµРЅРѕ'); }
    catch (e: any) { setMsg('вњ— ' + (e?.response?.data?.detail || 'РћС€РёР±РєР°')); }
    finally { setBusy(false); }
  }

  // в”Ђв”Ђ Р’РёРґРµРѕ-СѓСЂРѕРєРё в”Ђв”Ђ
  async function saveLesson() {
    if (!lessonForm.title.trim()) { setMsg('вњ— Р’РІРµРґРёС‚Рµ РЅР°Р·РІР°РЅРёРµ'); return; }
    setBusy(true); setMsg(null);
    try {
      const data = { title: lessonForm.title.trim(), description: lessonForm.description.trim() || null, sort_order: Number(lessonForm.sort_order) || 0 };
      if (lessonEditingId) await api.adminUpdateLesson(lessonEditingId, data);
      else await api.adminCreateLesson(data);
      setMsg('вњ“ РЈСЂРѕРє СЃРѕС…СЂР°РЅС‘РЅ');
      setLessonForm({ title: '', description: '', sort_order: '0' });
      setLessonEditingId(null);
      setLessons(await api.adminLessons());
    } catch (e: any) { setMsg('вњ— ' + (e?.response?.data?.detail || 'РћС€РёР±РєР°')); }
    finally { setBusy(false); }
  }

  async function uploadLessonVideo(id: number, file: File) {
    setBusy(true); setMsg(null);
    try { await api.adminUploadLessonVideo(id, file); setLessons(await api.adminLessons()); setMsg('вњ“ Р’РёРґРµРѕ Р·Р°РіСЂСѓР¶РµРЅРѕ'); }
    catch (e: any) { setMsg('вњ— ' + (e?.response?.data?.detail || 'РћС€РёР±РєР°')); }
    finally { setBusy(false); }
  }

  async function deleteLesson(id: number) {
    if (!(await confirmDialog('РЈРґР°Р»РёС‚СЊ СѓСЂРѕРє?'))) return;
    setBusy(true); setMsg(null);
    try { await api.adminDeleteLesson(id); setLessons(await api.adminLessons()); setMsg('вњ“ РЈРґР°Р»РµРЅРѕ'); }
    catch (e: any) { setMsg('вњ— ' + (e?.response?.data?.detail || 'РћС€РёР±РєР°')); }
    finally { setBusy(false); }
  }

  async function uploadCrystalCardImage(id: number, file: File) {
    setBusy(true); setMsg(null);
    try { await api.adminUploadCrystalCardImage(id, file); setCrystalCards(await api.adminCrystalCards()); setMsg('вњ“ РљР°СЂС‚РёРЅРєР° Р·Р°РіСЂСѓР¶РµРЅР°'); }
    catch (e: any) { setMsg('вњ— ' + (e?.response?.data?.detail || 'РћС€РёР±РєР°')); }
    finally { setBusy(false); }
  }

  // в”Ђв”Ђ Р”РѕСЃС‚РёР¶РµРЅРёСЏ в”Ђв”Ђ
  async function loadAchievements() {
    try {
      const [list, kinds] = await Promise.all([api.adminAchievements(), api.adminAchievementKinds()]);
      setAchievements(list);
      setAchKinds(kinds);
    } catch { /* ignore */ }
  }
  async function saveAchievement() {
    if (!achForm.name.trim() || !achForm.condition_kind.trim()) { setMsg('вњ— Р—Р°РїРѕР»РЅРёС‚Рµ РЅР°Р·РІР°РЅРёРµ Рё СѓСЃР»РѕРІРёРµ'); return; }
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
      setMsg('вњ“ РЎРѕС…СЂР°РЅРµРЅРѕ');
    } catch (e: any) { setMsg('вњ— ' + (e?.response?.data?.detail || 'РћС€РёР±РєР°')); }
    finally { setBusy(false); }
  }
  async function deleteAchievement(id: number) {
    if (!(await confirmDialog('РЈРґР°Р»РёС‚СЊ РґРѕСЃС‚РёР¶РµРЅРёРµ?'))) return;
    setBusy(true); setMsg(null);
    try { await api.adminDeleteAchievement(id); await loadAchievements(); setMsg('вњ“ РЈРґР°Р»РµРЅРѕ'); }
    catch (e: any) { setMsg('вњ— ' + (e?.response?.data?.detail || 'РћС€РёР±РєР°')); }
    finally { setBusy(false); }
  }
  async function uploadAchImage(id: number, file: File) {
    setBusy(true); setMsg(null);
    try { await api.adminUploadAchievementImage(id, file); await loadAchievements(); setMsg('вњ“ РљР°СЂС‚РёРЅРєР° Р·Р°РіСЂСѓР¶РµРЅР°'); }
    catch (e: any) { setMsg('вњ— ' + (e?.response?.data?.detail || 'РћС€РёР±РєР°')); }
    finally { setBusy(false); }
  }

  const [tabQuery, setTabQuery] = useState<Record<string, string>>({});
  const query = tabQuery[tab] || '';
  const setQuery = (v: string) => setTabQuery((m) => ({ ...m, [tab]: v }));
  const qActive = query.trim().length > 0;
  const fl = <T,>(items: T[]): T[] => (qActive ? items.filter((it) => matchesAny(it, query)) : items);

  const shownOrders = fl(adminOrders);
  const shownFields = fl(fields);
  const shownPlants = fl(plants);
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

  const NO_MATCH = 'РќРёС‡РµРіРѕ РЅРµ РЅР°Р№РґРµРЅРѕ.';

  return (
    <div style={{ maxWidth: 'var(--shell-max-width)', margin: '0 auto', padding: 'var(--shell-pad)' }}>
      <div style={{ display: 'flex', gap: 6, marginBottom: 14, flexWrap: 'wrap' }}>
        <TabBtn active={tab === 'players'} onClick={() => setTab('players')}>рџ‘Ґ РРіСЂРѕРєРё</TabBtn>
        <TabBtn active={tab === 'settings'} onClick={() => setTab('settings')}>рџ”§ РќР°СЃС‚СЂРѕР№РєРё</TabBtn>
        <TabBtn active={tab === 'fields'} onClick={() => setTab('fields')}>рџ—єпёЏ Р›РѕРєР°С†РёРё</TabBtn>
        <TabBtn active={tab === 'orders'} onClick={() => setTab('orders')}>рџ§є Р—Р°РєР°Р·С‹</TabBtn>
        <TabBtn active={tab === 'plants'} onClick={() => setTab('plants')}>рџЊ± Р Р°СЃС‚РµРЅРёСЏ</TabBtn>
        <TabBtn active={tab === 'animals'} onClick={() => setTab('animals')}>рџђ„ Р–РёРІРѕС‚РЅС‹Рµ</TabBtn>
        <TabBtn active={tab === 'pets'} onClick={() => setTab('pets')}>рџђѕ РџРёС‚РѕРјС†С‹</TabBtn>
        <TabBtn active={tab === 'products'} onClick={() => setTab('products')}>рџ“¦ РўРѕРІР°СЂС‹</TabBtn>
        <TabBtn active={tab === 'productions'} onClick={() => setTab('productions')}>рџЏ­ РџСЂРѕРёР·РІРѕРґСЃС‚РІР°</TabBtn>
        <TabBtn active={tab === 'recipes'} onClick={() => { setTab('recipes'); loadRecipes(); }}>рџ“љ Р РµС†РµРїС‚С‹</TabBtn>
        <TabBtn active={tab === 'customers'} onClick={() => { setTab('customers'); loadCustomers(); }}>рџ§‘ Р—Р°РєР°Р·С‡РёРєРё</TabBtn>
        <TabBtn active={tab === 'levels'} onClick={() => { setTab('levels'); loadLevels(); }}>рџ“Љ РЈСЂРѕРІРЅРё</TabBtn>
        <TabBtn active={tab === 'potion-recipes'} onClick={() => { setTab('potion-recipes'); loadPotionRecipes(); }}>рџ§Є Р РµС†РµРїС‚С‹ Р·РµР»РёР№</TabBtn>
        <TabBtn active={tab === 'cocktail-recipes'} onClick={() => { setTab('cocktail-recipes'); loadCocktailRecipes(); }}>рџЌё РљРѕРєС‚РµР№Р»Рё</TabBtn>
        <TabBtn active={tab === 'ingredients'} onClick={() => { setTab('ingredients'); loadIngredients(); }}>вљ—пёЏ РРЅРіСЂРµРґРёРµРЅС‚С‹</TabBtn>
        <TabBtn active={tab === 'infirmary'} onClick={() => { setTab('infirmary'); loadInfirmary(); }}>рџЊІ Р›РµС‡РµР±РЅРёС†Р°</TabBtn>
        <TabBtn active={tab === 'media'} onClick={() => setTab('media')}>рџЋ¬ РњРµРґРёР°</TabBtn>
        <TabBtn active={tab === 'story'} onClick={() => setTab('story')}>рџ“њ РџСЂРµРґС‹СЃС‚РѕСЂРёСЏ</TabBtn>
        <TabBtn active={tab === 'lessons'} onClick={() => setTab('lessons')}>рџЋ¬ РЈСЂРѕРєРё</TabBtn>
        <TabBtn active={tab === 'crystal-cards'} onClick={() => setTab('crystal-cards')}>рџѓЏ РљР°СЂС‚С‹</TabBtn>
        <TabBtn active={tab === 'achievements'} onClick={() => { setTab('achievements'); loadAchievements(); }}>рџЏ† Р”РѕСЃС‚РёР¶РµРЅРёСЏ</TabBtn>
        <TabBtn active={tab === 'logs'} onClick={() => setTab('logs')}>рџ“њ Р›РѕРіРё</TabBtn>
      </div>

      {tab !== 'players' && tab !== 'logs' && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
          <input
            className="fm-input"
            placeholder="рџ”Ќ РџРѕРёСЃРє РїРѕ РІСЃРµРј РїРѕР»СЏРјвЂ¦"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
          {qActive && (
            <>
              <span style={{ fontSize: 12, color: 'var(--text-muted)', whiteSpace: 'nowrap' }}>
                {totals[tab]?.shown ?? 0} РёР· {totals[tab]?.total ?? 0}
              </span>
              <button type="button" className="fm-btn fm-btn-sm fm-btn-outline" onClick={() => setQuery('')}>вњ•</button>
            </>
          )}
        </div>
      )}

      {msg && <Toast text={msg} onClose={() => setMsg(null)} />}

      {loading ? (
        <div className="fm-card">Р—Р°РіСЂСѓР·РєР°вЂ¦</div>
      ) : (
        <>
          {tab === 'players' && (
            <>
              {selectedPlayer ? (
                <div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 14 }}>
                    <button type="button" className="fm-btn fm-btn-sm fm-btn-outline" onClick={() => { setSelectedPlayer(null); setPlayerDetail(null); setPlayerReports([]); }}>в†ђ РќР°Р·Р°Рґ</button>
                    <h2 style={{ margin: 0, fontSize: 18 }}>
                      {selectedPlayer.first_name || selectedPlayer.last_name ? `${selectedPlayer.first_name} ${selectedPlayer.last_name}`.trim() : `#${selectedPlayer.vk_id}`}
                    </h2>
                    <button type="button" className="fm-btn fm-btn-sm fm-btn-danger" style={{ marginLeft: 'auto' }} disabled={busy} onClick={restartPlayer}>
                      рџ”Ѓ Р Р•РЎРўРђР Рў
                    </button>
                    {selectedPlayer.role !== 'admin' && (
                      <button type="button" className="fm-btn fm-btn-sm fm-btn-danger" disabled={busy} onClick={deletePlayerAccount}>
                        рџ—‘ РЈРґР°Р»РёС‚СЊ
                      </button>
                    )}
                  </div>
                  <div className="fm-card" style={{ marginBottom: 14, fontSize: 13 }}>
                    <div>ID: {selectedPlayer.vk_id} В· Р РѕР»СЊ: {selectedPlayer.role} В· РЎС‚Р°С‚СѓСЃ: {PLAYER_STATUS_META[selectedPlayer.status ?? 'active']?.emoji} {PLAYER_STATUS_META[selectedPlayer.status ?? 'active']?.label ?? selectedPlayer.status}</div>
                    <div>РљСЂРµСЃС‚РёРєРё: {selectedPlayer.crosses_balance} (РІСЃРµРіРѕ {selectedPlayer.crosses_total}) В· РњРѕРЅРµС‚С‹: {selectedPlayer.coins} В· Р Р°СѓРЅРґ: {selectedPlayer.round}</div>
                    {selectedPlayer.role !== 'admin' && (
                      <div style={{ marginTop: 8, display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                        {selectedPlayer.status !== 'blocked' && (
                          <button type="button" className="fm-btn fm-btn-sm fm-btn-danger" disabled={busy} onClick={() => setPlayerStatus(selectedPlayer.vk_id, 'blocked')}>
                            рџљ« Р—Р°Р±Р»РѕРєРёСЂРѕРІР°С‚СЊ
                          </button>
                        )}
                        {selectedPlayer.status !== 'readonly' && (
                          <button type="button" className="fm-btn fm-btn-sm fm-btn-outline" disabled={busy} onClick={() => setPlayerStatus(selectedPlayer.vk_id, 'readonly')}>
                            рџ‘Ѓ РўРѕР»СЊРєРѕ РїСЂРѕСЃРјРѕС‚СЂ
                          </button>
                        )}
                        {selectedPlayer.status !== 'active' && (
                          <button type="button" className="fm-btn fm-btn-sm" disabled={busy} onClick={() => setPlayerStatus(selectedPlayer.vk_id, 'active')}>
                            вњ… Р Р°Р·Р±Р»РѕРєРёСЂРѕРІР°С‚СЊ
                          </button>
                        )}
                      </div>
                    )}
                    <div style={{ marginTop: 8, display: 'flex', gap: 6, flexWrap: 'wrap', alignItems: 'center' }}>
                      <span>Р”РѕРїРѕР»РЅРµРЅРёСЏ:</span>
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
                            {granted ? 'вњ“ ' : ''}{title}
                          </button>
                        );
                      })}
                    </div>
                  </div>

                  <div style={{ display: 'flex', gap: 6, marginBottom: 14 }}>
                    <TabBtn active={playerTab === 'overview'} onClick={() => setPlayerTab('overview')}>рџЏЎ РҐРѕР·СЏР№СЃС‚РІРѕ</TabBtn>
                    <TabBtn active={playerTab === 'reports'} onClick={() => setPlayerTab('reports')}>рџ“· РћС‚С‡С‘С‚С‹ ({selectedPlayer.reports_total})</TabBtn>
                  </div>

                  {playerTab === 'overview' && playerDetail && (
                    <div>
                      <h3 style={{ marginTop: 0 }}>рџ—єпёЏ Р›РѕРєР°С†РёРё</h3>
                      {playerFields.length === 0 ? (
                        <div className="fm-card" style={{ color: 'var(--text-muted)', fontSize: 13 }}>РќРµС‚ РїРѕР»РµР№.</div>
                      ) : (
                        <div className="fm-grid">
                          {playerFields.map((f) => (
                            <button key={f.id} className="fm-card fm-rise" style={{ fontSize: 13, textAlign: 'left', cursor: 'pointer' }} onClick={() => openPlayerField(f.id)}>
                              <strong>рџ—єпёЏ {f.name}</strong>
                              <div style={{ color: 'var(--text-muted)', marginTop: 2 }}>{f.cols}Г—{f.rows} РєР»РµС‚РѕРє</div>
                            </button>
                          ))}
                        </div>
                      )}

                      <h3 style={{ marginTop: 16 }}>рџЊ± Р“СЂСЏРґРєРё ({playerDetail.plots.length})</h3>
                      {playerDetail.plots.length === 0 ? (
                        <div className="fm-card" style={{ color: 'var(--text-muted)', fontSize: 13 }}>РќРµС‚ РіСЂСЏРґРѕРє.</div>
                      ) : (
                        <div className="fm-grid">
                          {playerDetail.plots.map((plot) => (
                            <div key={plot.id} className="fm-card fm-rise" style={{ fontSize: 13 }}>
                              <strong>{plot.plant_emoji} {plot.plant_name} Г—{plot.qty}</strong>
                              <div style={{ color: 'var(--text-muted)', marginTop: 2 }}>
                                {plot.status === 'grown' ? 'вњ… Р’С‹СЂР°С‰РµРЅР°' : 'рџЊ± Р’ РїСЂРѕС†РµСЃСЃРµ'}
                              </div>
                              <div style={{ fontSize: 12, marginTop: 2 }}>
                                {plot.accumulated}/{plot.required} вќЋ{plot.norm_per_unit != null ? <> В· {plot.norm_per_unit}/С€С‚</> : null}
                                {plot.crystal_color && <> В· {plot.crystal_color} Г—{plot.crystal_count}</>}
                              </div>
                            </div>
                          ))}
                        </div>
                      )}

                      <h3 style={{ marginTop: 16 }}>вќ† Р¦РµРЅС‹ 1 СЂР°СЃС‚РµРЅРёСЏ ({playerDetail.plant_norms?.length ?? 0})</h3>
                      {(playerDetail.plant_norms ?? []).length === 0 ? (
                        <div className="fm-card" style={{ color: 'var(--text-muted)', fontSize: 13 }}>РРіСЂРѕРє РµС‰С‘ РЅРёС‡РµРіРѕ РЅРµ СЃР°Р¶Р°Р».</div>
                      ) : (
                        <div className="fm-grid">
                          {(playerDetail.plant_norms ?? []).map((n) => (
                            <div key={n.plant_id} className="fm-card fm-rise" style={{ fontSize: 13 }}>
                              <strong>{n.plant_emoji} {n.plant_name}</strong>
                              <div style={{ color: 'var(--text-muted)', marginTop: 2, fontSize: 12 }}>РўРµРєСѓС‰Р°СЏ С†РµРЅР°: {n.norm_per_unit} вќЋ/С€С‚</div>
                              <div style={{ marginTop: 6 }}>
                                <PlantNormEditor vkId={selectedPlayer.vk_id} plantId={n.plant_id} initial={n.norm_per_unit} onSaved={() => reloadPlayerDetail()} />
                              </div>
                            </div>
                          ))}
                        </div>
                      )}

                      <h3 style={{ marginTop: 16 }}>рџЏ­ РџСЂРѕРёР·РІРѕРґСЃС‚РІР° ({playerDetail.productions.length})</h3>
                      {playerDetail.productions.length === 0 ? (
                        <div className="fm-card" style={{ color: 'var(--text-muted)', fontSize: 13 }}>РќРµС‚ РїСЂРѕРёР·РІРѕРґСЃС‚РІ.</div>
                      ) : (
                        <div className="fm-grid">
                          {playerDetail.productions.map((pr) => (
                            <div key={pr.id} className="fm-card fm-rise" style={{ fontSize: 13 }}>
                              <strong>{pr.name}</strong>
                              <div style={{ color: 'var(--text-muted)', marginTop: 2 }}>{pr.kind}</div>
                              <div style={{ fontSize: 12, marginTop: 2 }}>
                                {pr.accumulated}/{pr.required} вќЋ
                              </div>
                            </div>
                          ))}
                        </div>
                      )}

                      <h3 style={{ marginTop: 16 }}>рџ“¦ РЎРєР»Р°Рґ ({playerDetail.inventory.length})</h3>
                      {playerDetail.inventory.length === 0 ? (
                        <div className="fm-card" style={{ color: 'var(--text-muted)', fontSize: 13 }}>РџСѓСЃС‚Рѕ.</div>
                      ) : (
                        <div className="fm-grid">
                          {playerDetail.inventory.map((inv) => (
                            <div key={inv.item_id} className="fm-card fm-rise" style={{ fontSize: 13 }}>
                              <strong>{inv.item_emoji} {inv.item_name}</strong>
                              <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 2 }}>
                                Г—{inv.qty} В· {inv.item_code}
                              </div>
                            </div>
                          ))}
                        </div>
                      )}

                      <h3 style={{ marginTop: 16 }}>рџЏљпёЏ Р—Р°РіРѕРЅС‹ ({playerDetail.barnyard?.length ?? 0})</h3>
                      {(playerDetail.barnyard ?? []).length === 0 ? (
                        <div className="fm-card" style={{ color: 'var(--text-muted)', fontSize: 13 }}>Р—Р°РіРѕРЅРѕРІ РЅРµС‚.</div>
                      ) : (
                        <div className="fm-grid">
                          {(playerDetail.barnyard ?? []).map((b) => (
                            <div key={b.id} className="fm-card fm-rise" style={{ fontSize: 13, borderColor: b.is_ghost ? '#e05555' : undefined }}>
                              <strong>{b.animal_emoji || 'рџђѕ'} {b.animal_name ?? 'вЂ” РїСѓСЃС‚Рѕ вЂ”'}</strong>
                              <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 2 }}>
                                {b.is_ghost
                                  ? <span style={{ color: '#e05555' }}>вљ пёЏ РїСЂРёР·СЂР°Рє: РЅРµ РѕС‚РѕР±СЂР°Р¶Р°РµС‚СЃСЏ РІ РёРіСЂРµ</span>
                                  : <>РєР»РµС‚РєР° ({b.cell_col}, {b.cell_row})</>}
                              </div>
                              <div style={{ fontSize: 12, marginTop: 2 }}>
                                {b.status} В· {b.accumulated}/{b.required} вќЋ
                              </div>
                              <button type="button" className="fm-btn fm-btn-xs fm-btn-danger" style={{ marginTop: 6 }} disabled={busy}
                                onClick={async () => {
                                  if (!selectedPlayer) return;
                                  if (!(await confirmDialog('РЈРґР°Р»РёС‚СЊ Р·Р°РіРѕРЅ РёРіСЂРѕРєР°? Р–РёРІРѕС‚РЅРѕРµ Рё РїСЂРѕРіСЂРµСЃСЃ Р±СѓРґСѓС‚ РїРѕС‚РµСЂСЏРЅС‹.'))) return;
                                  setBusy(true);
                                  try {
                                    await api.adminDeletePlayerBarnyard(selectedPlayer.vk_id, b.id);
                                    setMsg('вњ“ Р—Р°РіРѕРЅ СѓРґР°Р»С‘РЅ');
                                    await reloadPlayerDetail();
                                  } catch (e: any) {
                                    setMsg('вњ— ' + (e?.response?.data?.detail || 'РћС€РёР±РєР°'));
                                  } finally { setBusy(false); }
                                }}>
                                рџ—‘ РЈРґР°Р»РёС‚СЊ
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
                        <div className="fm-card" style={{ color: 'var(--text-muted)' }}>РћС‚С‡С‘С‚РѕРІ РЅРµС‚.</div>
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
                                  <strong>вќЋ {r.amount}</strong>
                                  {r.note && <div style={{ fontSize: 13 }}>{r.note}</div>}
                                  <span className="fm-chip" style={{ marginTop: 4, fontSize: 11 }}>
                                    {r.status === 'accepted' ? 'вњ“ Р·Р°С‡С‚РµРЅРѕ' : r.status === 'pending' ? 'вЏі Р¶РґС‘С‚' : 'вњ– РѕС‚РєР»РѕРЅРµРЅРѕ'}
                                  </span>
                                </div>
                              </div>
                              {r.status === 'pending' && (
                                <div style={{ display: 'flex', gap: 6, marginTop: 8 }}>
                                  <button type="button" className="fm-btn fm-btn-sm" style={{ flex: 1 }} disabled={busy} onClick={() => reviewReport(r.id, 'accept')}>Р—Р°С‡РµСЃС‚СЊ</button>
                                  <button type="button" className="fm-btn fm-btn-sm fm-btn-danger" disabled={busy} onClick={() => reviewReport(r.id, 'reject')}>РћС‚РєР»РѕРЅРёС‚СЊ</button>
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
                  <h2 style={{ marginTop: 0 }}>рџ‘Ґ РРіСЂРѕРєРё</h2>
                  <div className="fm-card" style={{ marginBottom: 12 }}>
                    <h3 style={{ margin: '0 0 8px' }}>рџ”‘ Р”РѕСЃС‚СѓРї Рє РёРіСЂРµ</h3>
                    <div style={{ display: 'flex', gap: 8 }}>
                      <input
                        className="fm-input"
                        style={{ flex: 1 }}
                        placeholder="РЎСЃС‹Р»РєР° Р’Рљ: https://vk.ru/id123 РёР»Рё vk.ru/РёРјСЏ"
                        value={accessLink}
                        onChange={(e) => setAccessLink(e.target.value)}
                      />
                      <button type="button" className="fm-btn" disabled={busy || !accessLink.trim()} onClick={addAccessPlayer}>вћ• Р”РѕР±Р°РІРёС‚СЊ</button>
                    </div>
                    {accessPlayers.length === 0 ? (
                      <div style={{ color: 'var(--text-muted)', fontSize: 13, marginTop: 8 }}>
                        РџРѕРєР° РґРѕСЃС‚СѓРї РµСЃС‚СЊ С‚РѕР»СЊРєРѕ Сѓ Р°РґРјРёРЅРёСЃС‚СЂР°С‚РѕСЂРѕРІ. Р”РѕР±Р°РІСЊС‚Рµ РёРіСЂРѕРєР° РїРѕ СЃСЃС‹Р»РєРµ Р’Рљ.
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
                                #{p.vk_id}{p.screen_name ? ` В· ${p.screen_name}` : ''}
                              </div>
                            </div>
                            <button type="button" className="fm-btn fm-btn-sm fm-btn-danger" disabled={busy} onClick={() => removeAccessPlayer(p.vk_id)}>вњ•</button>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                  <div style={{ marginBottom: 12 }}>
                    <input
                      className="fm-input"
                      type="text"
                      placeholder="РџРѕРёСЃРє РїРѕ РІСЃРµРј РїРѕР»СЏРј (ID, РёРјСЏ, СЂРѕР»СЊ, РјРѕРЅРµС‚С‹вЂ¦)"
                      value={playerSearch}
                      onChange={(e) => { setPlayerSearch(e.target.value); doSearch(e.target.value); }}
                    />
                  </div>
                  {players.length === 0 ? (
                    <div className="fm-card" style={{ color: 'var(--text-muted)' }}>РРіСЂРѕРєРѕРІ РЅРµС‚.</div>
                  ) : (
                    <>
                      <div className="fm-card" style={{ overflowX: 'auto', padding: 0 }}>
                        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
                          <thead>
                            <tr style={{ borderBottom: '1px solid var(--border)' }}>
                              <th style={{ padding: '8px 12px', textAlign: 'left' }}>РРіСЂРѕРє</th>
                              <th style={{ padding: '8px 12px', textAlign: 'right' }}>вќЋ</th>
                              <th style={{ padding: '8px 12px', textAlign: 'right' }}>рџЄ™</th>
                              <th style={{ padding: '8px 12px', textAlign: 'right' }}>рџ“·</th>
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
                          <button type="button" className="fm-btn fm-btn-sm fm-btn-outline" disabled={playerPage === 0} onClick={() => setPlayerPage((p) => p - 1)}>в†ђ РќР°Р·Р°Рґ</button>
                          <span style={{ color: 'var(--text-muted)' }}>{playerPage + 1} / {Math.ceil(players.length / PER_PAGE)}</span>
                          <button type="button" className="fm-btn fm-btn-sm fm-btn-outline" disabled={playerPage >= Math.ceil(players.length / PER_PAGE) - 1} onClick={() => setPlayerPage((p) => p + 1)}>Р’РїРµСЂС‘Рґ в†’</button>
                        </div>
                      )}
                    </>
                  )}
                </div>
              )}
            </>
          )}

          {/* РџРѕР»РЅРѕСЌРєСЂР°РЅРЅС‹Р№ РїСЂРѕСЃРјРѕС‚СЂ РїРѕР»СЏ РёРіСЂРѕРєР° (Р°РґРјРёРЅ) */}
          {viewField && (
            <div style={{ position: 'fixed', inset: 0, zIndex: 100, background: '#1a1a2e', display: 'flex', flexDirection: 'column' }}>
              <div style={{ padding: '10px var(--shell-pad)', display: 'flex', alignItems: 'center', gap: 10, background: 'rgba(0,0,0,0.4)', flexShrink: 0 }}>
                <button type="button" className="fm-btn fm-btn-sm fm-btn-outline" onClick={() => setViewField(null)} style={{ color: '#fff', borderColor: '#fff' }}>в†ђ РќР°Р·Р°Рґ</button>
                <span style={{ color: '#ccc', fontSize: 14 }}>{viewField.name} В· {viewField.cols}Г—{viewField.rows}</span>
              </div>
              <div style={{ flex: 1, position: 'relative', overflow: 'auto' }}>
                <FieldGridView field={viewField} playerVkId={selectedPlayer?.vk_id}
                  onResetNorm={async (plotId) => {
                    if (!selectedPlayer) return;
                    if (!(await confirmDialog('РЎР±СЂРѕСЃРёС‚СЊ РЅРѕСЂРјСѓ? РРіСЂРѕРєСѓ РІС‹РїР°РґСѓС‚ РЅРѕРІС‹Рµ СЃР»СѓС‡Р°Р№РЅС‹Рµ РєР°СЂС‚С‹.'))) return;
                    setBusy(true);
                    try {
                      await api.adminResetPlotNorm(selectedPlayer.vk_id, plotId);
                      setMsg('вњ“ РќРѕСЂРјР° СЃР±СЂРѕС€РµРЅР°');
                      const fd = await api.adminPlayerField(selectedPlayer.vk_id, viewField!.id);
                      setViewField(fd);
                    } catch (e: any) {
                      setMsg('вњ— ' + (e?.response?.data?.detail || 'РћС€РёР±РєР°'));
                    } finally { setBusy(false); }
                  }}
                  onDeletePlot={async (plotId) => {
                    if (!selectedPlayer) return;
                    if (!(await confirmDialog('РЈРґР°Р»РёС‚СЊ РіСЂСЏРґРєСѓ РёРіСЂРѕРєР°? Р Р°СЃС‚РµРЅРёРµ Рё РїСЂРѕРіСЂРµСЃСЃ Р±СѓРґСѓС‚ РїРѕС‚РµСЂСЏРЅС‹.'))) return;
                    setBusy(true);
                    try {
                      await api.adminDeletePlayerPlot(selectedPlayer.vk_id, plotId);
                      setMsg('вњ“ Р“СЂСЏРґРєР° СѓРґР°Р»РµРЅР°');
                      const fd = await api.adminPlayerField(selectedPlayer.vk_id, viewField!.id);
                      setViewField(fd);
                    } catch (e: any) {
                      setMsg('вњ— ' + (e?.response?.data?.detail || 'РћС€РёР±РєР°'));
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
                <h3>рџ”’ Р—Р°РєСЂС‹С‚С‹Рµ Р»РѕРєР°С†РёРё</h3>
                <div style={{ color: 'var(--text-muted)', fontSize: 13, marginBottom: 10 }}>
                  Р—Р°РєСЂС‹С‚С‹Рµ Р»РѕРєР°С†РёРё РІРёРґРЅС‹ РёРіСЂРѕРєР°Рј СЃ Р·Р°РјРєРѕРј рџ”’ Рё РЅРµРґРѕСЃС‚СѓРїРЅС‹ Р±РµР· РґРѕРїРѕР»РЅРµРЅРёСЏ. РђРґРјРёРЅР°Рј РІСЃС‘ РґРѕСЃС‚СѓРїРЅРѕ РІСЃРµРіРґР°. Р”РѕРїРѕР»РЅРµРЅРёСЏ РІС‹РґР°СЋС‚СЃСЏ РІ РєР°СЂС‚РѕС‡РєРµ РёРіСЂРѕРєР°.
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                  {Object.entries(LOCATION_TITLES).map(([code, title]) => (
                    <label key={code} style={{ display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer' }}>
                      <input type="checkbox" checked={lockedLocations.includes(code)} disabled={busy} onChange={() => toggleLockedLocation(code)} />
                      <span>{title}</span>
                      <span style={{ color: 'var(--text-muted)', fontSize: 12 }}>
                        {lockedLocations.includes(code) ? 'Р·Р°РєСЂС‹С‚Р° рџ”’' : 'РѕС‚РєСЂС‹С‚Р°'}
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
                <h3>рџ–јпёЏ РќРµР№С‚СЂР°Р»СЊРЅС‹Р№ С„РѕРЅ</h3>
                <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                  <input className="fm-input" style={{ flex: 1 }} placeholder="URL С„РѕРЅР°" value={bgInput} onChange={(e) => setBgInput(e.target.value)} />
                  <button type="button" className="fm-btn" disabled={busy} onClick={saveBg}>рџ’ѕ</button>
                </div>
                {bgUrl && <img src={bgUrl} alt="Р¤РѕРЅ" style={{ maxWidth: 200, marginTop: 8, borderRadius: 8 }} />}
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
                    вћ• РЎРѕР·РґР°С‚СЊ Р»РѕРєР°С†РёСЋ
                  </button>
                  {shownFields.length === 0 ? (
                    <div className="fm-card" style={{ color: 'var(--text-muted)' }}>{qActive ? NO_MATCH : 'Р›РѕРєР°С†РёР№ РїРѕРєР° РЅРµС‚.'}</div>
                  ) : (
                    <div className="fm-grid">
                      {shownFields.map((f) => (
                        <div key={f.id} className="fm-card fm-rise">
                          <strong style={{ fontSize: 16 }}>рџ—єпёЏ {f.name}</strong>
                          <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 4 }}>{f.cols}Г—{f.rows} РєР»РµС‚РѕРє</div>
                          {f.map_url && <img src={mediaUrl(f.map_url)} alt="" style={{ width: '100%', marginTop: 8, borderRadius: 'var(--radius-sm)' }} />}
                          <div style={{ display: 'flex', flexDirection: 'column', gap: 6, marginTop: 8 }}>
                            <button type="button" className="fm-btn fm-btn-sm" disabled={busy} onClick={() => setEditorFieldId(f.id)}>вњЋ Р РµРґР°РєС‚РёСЂРѕРІР°С‚СЊ</button>
                            <label className="fm-btn fm-btn-sm fm-btn-outline" style={{ cursor: 'pointer' }}>
                              {f.map_url ? 'рџ–јпёЏ РЎРјРµРЅРёС‚СЊ РєР°СЂС‚РёРЅРєСѓ' : 'рџ–јпёЏ Р—Р°РіСЂСѓР·РёС‚СЊ РєР°СЂС‚Сѓ'}
                              <input type="file" accept="image/*" style={{ display: 'none' }} onChange={(e) => { const file = e.target.files?.[0]; if (file) uploadMap(f.id, file); }} />
                            </label>
                            <button type="button" className="fm-btn fm-btn-sm fm-btn-danger" disabled={busy} onClick={() => deleteField(f.id)}>РЈРґР°Р»РёС‚СЊ</button>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                  {showCreate && (
                    <div style={{ position: 'fixed', inset: 0, zIndex: 60, background: 'rgba(0,0,0,0.6)', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 16 }}>
                      <div className="fm-card fm-rise" onClick={(e) => e.stopPropagation()} style={{ width: '100%', maxWidth: 'calc(var(--shell-max-width) * 0.633)' }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
                          <h3 style={{ margin: 0 }}>вћ• РќРѕРІР°СЏ Р»РѕРєР°С†РёСЏ</h3>
                          <button type="button" className="fm-btn fm-btn-xs fm-btn-outline" onClick={() => setShowCreate(false)}>вњ•</button>
                        </div>
                        <label style={{ display: 'block', margin: '8px 0 6px', fontSize: 14 }}>РќР°Р·РІР°РЅРёРµ</label>
                        <input className="fm-input" value={newName} onChange={(e) => setNewName(e.target.value)} placeholder="РћРіРѕСЂРѕРґ" />
                        <div style={{ display: 'flex', gap: 8, marginTop: 10 }}>
                          <div style={{ flex: 1 }}>
                            <label style={{ display: 'block', marginBottom: 6, fontSize: 14 }}>РљРѕР»РѕРЅРєРё</label>
                            <input className="fm-input" type="number" min={1} max={30} value={newCols} onChange={(e) => { setNewCols(e.target.value); if (lockRatio) { const c = Number(e.target.value); if (c > 0) setNewRows(String(Math.round(c * 3 / 4) || 1)); } }} />
                          </div>
                          <div style={{ flex: 1 }}>
                            <label style={{ display: 'block', marginBottom: 6, fontSize: 14 }}>РЎС‚СЂРѕРєРё</label>
                            <input className="fm-input" type="number" min={1} max={30} value={newRows} onChange={(e) => { setNewRows(e.target.value); if (lockRatio) { const r = Number(e.target.value); if (r > 0) setNewCols(String(Math.round(r * 4 / 3) || 1)); } }} />
                          </div>
                        </div>
                        <label style={{ display: 'flex', alignItems: 'center', gap: 6, marginTop: 8, fontSize: 13, cursor: 'pointer' }}>
                          <input type="checkbox" checked={lockRatio} onChange={(e) => setLockRatio(e.target.checked)} />
                          РЎРѕС…СЂР°РЅРёС‚СЊ РїСЂРѕРїРѕСЂС†РёРё 4:3
                        </label>
                        <div style={{ marginTop: 8 }}>
                          <label style={{ display: 'block', marginBottom: 4, fontSize: 14 }}>РўРёРї Р»РѕРєР°С†РёРё</label>
                          <select className="fm-input" value={newFieldKind} onChange={(e) => setNewFieldKind(e.target.value)}>
                            <option value="">вЂ” Р±РµР· С‚РёРїР° вЂ”</option>
                            <option value="garden_beds">рџЊ± Р“СЂСЏРґРєРё</option>
                            <option value="orchard">рџЌЋ РЎР°Рґ</option>
                            <option value="lawn">рџЊї Р›СѓР¶Р°Р№РєР°</option>
                            <option value="house">рџЏ  Р”РѕРј</option>
                            <option value="barnyard">рџђ„ РЎРєРѕС‚РЅС‹Р№ РґРІРѕСЂ</option>
                            <option value="library">рџ“– Р‘РёР±Р»РёРѕС‚РµРєР°</option>
                            <option value="brewery">рџ§Є Р—РµР»СЊРµРІР°СЂРЅСЏ</option>
                            <option value="meadow">рџЊї Р›РµСЃРЅР°СЏ РїРѕР»СЏРЅР°</option>
                            <option value="shop">рџ›’ Р“РѕСЂРѕРґСЃРєР°СЏ Р»Р°РІРєР°</option>
                            <option value="infirmary">рџЊІ Р›РµСЃРЅР°СЏ Р»РµС‡РµР±РЅРёС†Р°</option>
                            <option value="remedy_lab">вљ—пёЏ Р›Р°Р±РѕСЂР°С‚РѕСЂРёСЏ СЃРЅР°РґРѕР±РёР№</option>
                            <option value="forest_bar">рџЌ№ Р›РµСЃРЅРѕР№ Р±Р°СЂ</option>
                          </select>
                        </div>
                        <div style={{ marginTop: 8 }}>
                          <label style={{ display: 'block', marginBottom: 4, fontSize: 14 }}>РљР°С‚РµРіРѕСЂРёСЏ СЂР°СЃС‚РµРЅРёР№</label>
                          <select className="fm-input" value={newPlantCategory} onChange={(e) => setNewPlantCategory(e.target.value)}>
                            <option value="">вЂ” Р»СЋР±Р°СЏ вЂ”</option>
                            <option value="garden">рџЊ± Р“СЂСЏРґРєР°</option>
                            <option value="orchard">рџЌЋ РЎР°Рґ</option>
                          </select>
                        </div>
                        <div style={{ marginTop: 8 }}>
                          <label style={{ display: 'block', marginBottom: 4, fontSize: 14 }}>РњРёРЅ. СѓСЂРѕРІРµРЅСЊ РґР»СЏ РѕС‚РєСЂС‹С‚РёСЏ</label>
                          <input className="fm-input" type="number" min={0} max={16} value={newMinLevel} onChange={(e) => setNewMinLevel(e.target.value)} />
                        </div>
                        <button type="button" className="fm-btn" style={{ width: '100%', marginTop: 14 }} disabled={busy || !newName.trim()} onClick={createField}>РЎРѕР·РґР°С‚СЊ</button>
                      </div>
                    </div>
                  )}
                </>
              )}
            </>
          )}

          {tab === 'plants' && (
            <CatalogTab title="рџЊ± Р Р°СЃС‚РµРЅРёСЏ" items={shownPlants} busy={busy} form={catForm} formOpen={formOpen} editingId={editingId} onFormChange={setCatForm} onCreate={startCreate} onEdit={startEdit} onCancel={cancelForm} onSave={savePlant} onDelete={deletePlant} onUploadImage={uploadPlantImage} onUploadImageYoung={uploadPlantImageYoung} onUploadImageGrown={uploadPlantImageGrown} onUploadImageHarvested={uploadPlantImageHarvested} hideMainImage emptyText={qActive ? NO_MATCH : undefined}
              fields={[{ key: 'name', label: 'РќР°Р·РІР°РЅРёРµ', ph: 'Р”Р¶РµРєРѕР±РѕР±' }, { key: 'emoji', label: 'Р­РјРѕРґР·Рё', ph: 'рџЊ±' }, { key: 'level', label: 'РЈСЂРѕРІРµРЅСЊ', ph: '1', type: 'number' }, { key: 'category', label: 'РљР°С‚РµРіРѕСЂРёСЏ', options: [{ value: 'garden', label: 'рџЊ± Р“СЂСЏРґРєР°' }, { value: 'orchard', label: 'рџЌЋ РЎР°Рґ' }] }, { key: 'description', label: 'РћРїРёСЃР°РЅРёРµ', ph: 'Р“СЂРёР±С‹' }, { key: 'stitch_condition', label: 'РЈСЃР»РѕРІРёРµ РѕС‚С€РёРІР°', ph: 'Р’С‹С€РёС‚СЊ РЅР° Р±РµР»РѕР№ РєР°РЅРІРµ' }]}
            />
          )}

          {tab === 'animals' && (
            <CatalogTab title="рџђ„ Р–РёРІРѕС‚РЅС‹Рµ" items={shownAnimals} busy={busy} form={catForm} formOpen={formOpen} editingId={editingId} onFormChange={setCatForm} onCreate={startCreate} onEdit={startEdit} onCancel={cancelForm} onSave={saveAnimal} onDelete={deleteAnimal} onUploadImage={uploadAnimalImage} onUploadImageEmptyPen={uploadAnimalEmptyPenImage} onUploadImagePen={uploadAnimalPenImage} hideMainImage emptyText={qActive ? NO_MATCH : undefined}
              fields={[{ key: 'name', label: 'РќР°Р·РІР°РЅРёРµ', ph: 'Р•РґРёРЅРѕСЂРѕРі' }, { key: 'product_name', label: 'РџСЂРѕРґСѓРєС†РёСЏ', ph: 'Р РѕРі РµРґРёРЅРѕСЂРѕРіР°' }]}
            />
          )}

          {tab === 'pets' && (
            <CatalogTab title="рџђѕ РџРёС‚РѕРјС†С‹" items={shownPets} busy={busy} form={catForm} formOpen={formOpen} editingId={editingId} onFormChange={setCatForm} onCreate={startCreate} onEdit={startEdit} onCancel={cancelForm} onSave={savePet} onDelete={deletePet} onUploadImage={uploadPetImage} emptyText={qActive ? NO_MATCH : undefined}
              fields={[{ key: 'name', label: 'РќР°Р·РІР°РЅРёРµ', ph: 'Р›РёСЃ РЎРёР»СЊРІР°СЂРёСЃ' }, { key: 'bonus_kind', label: 'Р‘РѕРЅСѓСЃ', options: BONUS_KIND_OPTIONS }]}
              imageLabel="РїРёС‚РѕРјС†Р°"
            />
          )}

          {tab === 'products' && (
            <CatalogTab title="рџ“¦ РўРѕРІР°СЂС‹" items={shownProducts} busy={busy} form={catForm} formOpen={formOpen} editingId={editingId} onFormChange={setCatForm} onCreate={startCreate} onEdit={startEdit} onCancel={cancelForm} onSave={saveProduct} onDelete={deleteProduct} onUploadImage={uploadProductImage} emptyText={qActive ? NO_MATCH : undefined}
              fields={[
                { key: 'name', label: 'РќР°Р·РІР°РЅРёРµ', ph: 'РЇРґ' },
                { key: 'stars', label: 'Р—РІС‘Р·РґС‹', ph: '1', type: 'number' },
                { key: 'production_kind', label: 'РџСЂРѕРёР·РІРѕРґСЃС‚РІРѕ', ph: '', options: prodTemplates.map((pt) => ({ value: pt.code, label: `${pt.emoji || ''} ${pt.name}` })) },
                { key: 'plant_id', label: 'Р Р°СЃС‚РµРЅРёРµ-РёСЃС‚РѕС‡РЅРёРє', options: plants.filter((p) => !catalogProducts.some((x) => x.plant_id === p.id && x.id !== editingId)).map((p) => ({ value: String(p.id), label: `${p.emoji || ''} ${p.name}` })) },
                { key: 'animal_id', label: 'Р–РёРІРѕС‚РЅРѕРµ-РёСЃС‚РѕС‡РЅРёРє', options: animals.filter((a) => !catalogProducts.some((x) => x.animal_id === a.id && x.id !== editingId)).map((a) => ({ value: String(a.id), label: `${a.emoji || ''} ${a.name}` })) },
                { key: 'pet_id', label: 'РџРёС‚РѕРјРµС†-РёСЃС‚РѕС‡РЅРёРє', options: pets.filter((pt) => !catalogProducts.some((x) => x.pet_id === pt.id && x.id !== editingId)).map((pt) => ({ value: String(pt.id), label: `${pt.emoji || ''} ${pt.name}` })) },
              ]}
            />
          )}

          {tab === 'productions' && (
            <CatalogTab title="рџЏ­ РџСЂРѕРёР·РІРѕРґСЃС‚РІР°" items={shownProductions} busy={busy} form={catForm} formOpen={formOpen} editingId={editingId} onFormChange={setCatForm} onCreate={startCreate} onEdit={startEdit} onCancel={cancelForm} onSave={saveProduction} onDelete={deleteProduction} onUploadImage={uploadProductionImage} emptyText={qActive ? NO_MATCH : undefined}
              fields={[
                { key: 'name', label: 'РќР°Р·РІР°РЅРёРµ', ph: 'РЎС‚РѕР» Р·РµР»СЊРµРІР°СЂРµРЅРёСЏ' },
                { key: 'cards_to_draw', label: 'РљР°СЂС‚ РґР»СЏ РЅРѕСЂРјС‹', options: CARDS_DRAW_OPTIONS },
                { key: 'surcharge', label: 'Р”РѕР±Р°РІРѕС‡РЅР°СЏ СЃС‚РѕРёРјРѕСЃС‚СЊ', options: SURCHARGE_OPTIONS },
                { key: 'processing_crystal', label: 'рџ’Ћ РљСЂРёСЃС‚Р°Р»Р» РїРµСЂРµСЂР°Р±РѕС‚РєРё', ph: '0', type: 'number' },
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
                <h2 style={{ margin: 0 }}>рџ§є Р’СЃРµ Р·Р°РєР°Р·С‹</h2>
                <button type="button" className="fm-btn fm-btn-sm" disabled={busy} onClick={startCreateOrder}>
                  вћ• РЎРѕР·РґР°С‚СЊ Р·Р°РєР°Р·
                </button>
              </div>

              {orderFormOpen && (
                <div className="fm-card" style={{ marginBottom: 10 }}>
                  <h3 style={{ marginTop: 0 }}>{orderEditingId ? 'вњЋ Р РµРґР°РєС‚РёСЂРѕРІР°С‚СЊ Р·Р°РєР°Р·' : 'вћ• РЎРѕР·РґР°С‚СЊ Р·Р°РєР°Р·'}</h3>
                  {orderEditingId === null && (
                    <div style={{ marginBottom: 8 }}>
                      <label style={{ display: 'block', marginBottom: 4, fontSize: 13 }}>РўРёРї Р·Р°РєР°Р·Р°</label>
                      <select className="fm-input" value={orderForm.kind || 'product'} onChange={(e) => setOrderForm({ ...orderForm, kind: e.target.value })}>
                        <option value="product">рџ“¦ РўРѕРІР°СЂ</option>
                        <option value="potion">рџ§Є Р—РµР»СЊРµ</option>
                      </select>
                    </div>
                  )}
                  {orderForm.kind === 'potion' ? (
                    <div style={{ marginBottom: 8 }}>
                      <label style={{ display: 'block', marginBottom: 4, fontSize: 13 }}>Р—РµР»СЊРµ</label>
                      <select className="fm-input" value={orderForm.potion_recipe_id || ''} onChange={(e) => setOrderForm({ ...orderForm, potion_recipe_id: e.target.value })}>
                        <option value="">вЂ” РІС‹Р±РµСЂРёС‚Рµ вЂ”</option>
                        {potionRecipes.map((r) => (
                          <option key={r.id} value={String(r.id)}>{r.name} ({r.level})</option>
                        ))}
                      </select>
                      <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 4 }}>
                        Р—Р°РєР°Р· РІСЃРµРіРґР° РЅР° 1 Р·РµР»СЊРµ. РќР°РіСЂР°РґР° Р±РµСЂС‘С‚СЃСЏ РёР· СЂРµС†РµРїС‚Р°.
                      </div>
                    </div>
                  ) : (
                    <>
                      <div style={{ marginBottom: 8 }}>
                        <label style={{ display: 'block', marginBottom: 4, fontSize: 13 }}>РўРѕРІР°СЂ</label>
                        <select className="fm-input" value={orderForm.product_id || ''} onChange={(e) => setOrderForm({ ...orderForm, product_id: e.target.value })}>
                          <option value="">вЂ” РІС‹Р±РµСЂРёС‚Рµ вЂ”</option>
                          {products.map((p) => (
                            <option key={p.id} value={String(p.id)}>{p.emoji} {p.name} ({p.code})</option>
                          ))}
                        </select>
                      </div>
                      <div style={{ marginBottom: 8 }}>
                        <label style={{ display: 'block', marginBottom: 4, fontSize: 13 }}>РљРѕР»РёС‡РµСЃС‚РІРѕ (1вЂ“20)</label>
                        <input className="fm-input" type="number" min={1} max={20} value={orderForm.qty || ''} onChange={(e) => setOrderForm({ ...orderForm, qty: e.target.value })} placeholder="РѕСЃС‚Р°РІСЊС‚Рµ РїСѓСЃС‚С‹Рј РґР»СЏ РґРµС„РѕР»С‚Р°" />
                      </div>
                    </>
                  )}
                  <div style={{ marginBottom: 8 }}>
                    <label style={{ display: 'block', marginBottom: 4, fontSize: 13 }}>Р—Р°РєР°Р·С‡РёРє</label>
                    <select className="fm-input" value={orderForm.customer || ''} onChange={(e) => setOrderForm({ ...orderForm, customer: e.target.value })}>
                      <option value="">вЂ” РЅРµ СѓРєР°Р·Р°РЅ вЂ”</option>
                      {orderCustomerOptions.map((n) => (
                        <option key={n} value={n}>{n}</option>
                      ))}
                    </select>
                    {customers.some((c) => c.open_orders_count >= customerMaxOrders) && orderEditingId === null && (
                      <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 4 }}>
                        Р—Р°РєР°Р·С‡РёРєРё СЃ {customerMaxOrders} РѕС‚РєСЂС‹С‚С‹РјРё Р·Р°РєР°Р·Р°РјРё СЃРєСЂС‹С‚С‹
                      </div>
                    )}
                  </div>
                  <div style={{ marginBottom: 8 }}>
                    <label style={{ display: 'block', marginBottom: 4, fontSize: 13 }}>Р РµРїР»РёРєР° Р·Р°РєР°Р·С‡РёРєР°</label>
                    <textarea
                      className="fm-input"
                      rows={3}
                      value={orderForm.customer_phrase || ''}
                      onChange={(e) => setOrderForm({ ...orderForm, customer_phrase: e.target.value })}
                      placeholder="В«РњРЅРµ СЃСЂРѕС‡РЅРѕ РЅСѓР¶РЅС‹ С‚СЂРё СЃРєР»СЏРЅРєРё СЏРґР° РґРѕ Р·Р°РєР°С‚Р°!В»"
                    />
                  </div>
                  {orderEditingId !== null && (
                    <>
                      <div style={{ marginBottom: 8 }}>
                        <label style={{ display: 'block', marginBottom: 4, fontSize: 13 }}>РќР°РіСЂР°РґР° (РјРѕРЅРµС‚)</label>
                        <input className="fm-input" type="number" value={orderForm.reward_coins || ''} onChange={(e) => setOrderForm({ ...orderForm, reward_coins: e.target.value })} />
                      </div>
                      <div style={{ marginBottom: 8 }}>
                        <label style={{ display: 'block', marginBottom: 4, fontSize: 13 }}>РќР°Р·РІР°РЅРёРµ (РЅР° РєР°СЂС‚РѕС‡РєРµ)</label>
                        <input className="fm-input" value={orderForm.name || ''} onChange={(e) => setOrderForm({ ...orderForm, name: e.target.value })} />
                      </div>
                    </>
                  )}
                  <div style={{ marginBottom: 8 }}>
                    <label style={{ display: 'block', marginBottom: 4, fontSize: 13 }}>РР·РѕР±СЂР°Р¶РµРЅРёРµ</label>
                    <input type="file" accept="image/*" onChange={(e) => setOrderImage(e.target.files?.[0] ?? null)} style={{ fontSize: 13 }} />
                    {orderImage && <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 4 }}>{orderImage.name}</div>}
                  </div>
                  <div style={{ display: 'flex', gap: 8 }}>
                    <button type="button" className="fm-btn" disabled={busy} onClick={saveOrder}>рџ’ѕ РЎРѕС…СЂР°РЅРёС‚СЊ</button>
                    <button type="button" className="fm-btn fm-btn-outline" disabled={busy} onClick={() => { setOrderFormOpen(false); setOrderEditingId(null); setOrderImage(null); }}>РћС‚РјРµРЅР°</button>
                  </div>
                </div>
              )}

              {shownOrders.length === 0 ? (
                <div className="fm-card" style={{ color: 'var(--text-muted)' }}>{qActive ? NO_MATCH : 'Р—Р°РєР°Р·РѕРІ РЅРµС‚.'}</div>
              ) : (
                <div className="fm-grid">
                  {shownOrders.map((o) => {
                    return (
                      <div key={o.id} className="fm-card fm-rise" style={{ textAlign: 'center' }}>
                        <SpritePedestal url={o.image_url || o.product_image_url || o.potion_image_url ? mediaUrl(o.image_url || o.product_image_url || o.potion_image_url) : null} emoji={o.product_emoji} height={100} />
                        <strong style={{ display: 'block', marginBottom: 6 }}>{o.product_name} Г—{o.qty}</strong>
                        {o.name && <div style={{ fontSize: 13, color: 'var(--text-secondary)', marginBottom: 6 }}>{o.name}</div>}
                        <div style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 4, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 5 }}>
                          {o.customer_image_url
                            ? <img src={mediaUrl(o.customer_image_url)} alt="" style={{ width: 20, height: 20, borderRadius: '50%', objectFit: 'cover' }} />
                            : o.customer ? <span>рџ§‘</span> : null}
                          <span>{o.customer || 'вЂ”'}</span>
                        </div>
                        {o.customer_phrase && (
                          <div style={{ fontSize: 12, fontStyle: 'italic', color: 'var(--text-secondary)', marginBottom: 8 }}>
                            В«{(o.customer_phrase.length > 60 ? o.customer_phrase.slice(0, 60) + 'вЂ¦' : o.customer_phrase)}В»
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
                          <span style={{ color: 'var(--accent-warm)', fontWeight: 600, whiteSpace: 'nowrap' }}>рџЄ™ {o.reward_coins}</span>
                        </div>
                        <div style={{ display: 'flex', gap: 6 }}>
                          <button type="button" className="fm-btn fm-btn-xs" style={{ flex: 1 }} disabled={busy} onClick={() => startEditOrder(o)}>вњЋ</button>
                          {o.status === 'open' && (
                            <button type="button" className="fm-btn fm-btn-xs fm-btn-danger" style={{ flex: 1 }} disabled={busy} onClick={() => cancelOrder(o.id)}>
                              вњ–пёЏ
                            </button>
                          )}
                          <button type="button" className="fm-btn fm-btn-xs fm-btn-danger" style={{ flex: 1 }} disabled={busy} onClick={() => deleteOrder(o.id)}>
                            рџ—‘
                          </button>
                          <label className="fm-btn fm-btn-xs fm-btn-outline" style={{ cursor: 'pointer', flex: 1 }}>
                            рџ–јпёЏ
                            <input type="file" accept="image/*" style={{ display: 'none' }}
                              onChange={async (e) => {
                                const file = e.target.files?.[0];
                                if (file) {
                                  setBusy(true); setMsg(null);
                                  try { await api.adminUploadOrderImage(o.id, file); await load(); setMsg('вњ“ РљР°СЂС‚РёРЅРєР° Р·Р°РіСЂСѓР¶РµРЅР°'); }
                                  catch (e2: any) { setMsg('вњ— ' + (e2?.response?.data?.detail || 'РћС€РёР±РєР°')); }
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
              <h2 style={{ marginTop: 0 }}>рџЋ¬ РњРµРґРёР° (РІРёРґРµРѕ, РєР°СЂС‚РёРЅРєРё)</h2>
              <div className="fm-card" style={{ marginBottom: 10, display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'flex-end' }}>
                <div>
                  <label style={{ display: 'block', fontSize: 13, marginBottom: 2 }}>РўРёРї РјРµРґРёР°</label>
                  <select className="fm-input" value={mediaTypeSel} onChange={(e) => setMediaTypeSel(e.target.value)} style={{ width: 240 }}>
                    <option value="">вЂ” РІС‹Р±РµСЂРёС‚Рµ вЂ”</option>
                    {MEDIA_TYPES.filter(mt => !gameMedia.some(gm => gm.code === mt.code)).map(mt => (
                      <option key={mt.code} value={mt.code}>{mt.label}</option>
                    ))}
                  </select>
                </div>
                <button type="button" className="fm-btn fm-btn-sm" disabled={busy || !mediaTypeSel} onClick={saveGameMedia}>вћ• РЎРѕР·РґР°С‚СЊ</button>
              </div>
              <div className="fm-grid">
                {shownMedia.map((gm) => {
                  const label = MEDIA_TYPES.find(m => m.code === gm.code)?.label || gm.code;
                  return (
                    <div key={gm.id} className="fm-card fm-rise" style={{ fontSize: 13 }}>
                      <strong>{label}</strong>
                      <div style={{ color: 'var(--text-muted)', marginTop: 2 }}>{gm.kind}</div>
                      {gm.url ? (
                        <div style={{ marginTop: 4, fontSize: 12, color: '#5f8' }}>вњ“ Р—Р°РіСЂСѓР¶РµРЅРѕ</div>
                      ) : (
                        <div style={{ marginTop: 4, fontSize: 12, color: '#f88' }}>Р¤Р°Р№Р»Р° РЅРµС‚</div>
                      )}
                      <div style={{ display: 'flex', gap: 4, marginTop: 6, flexWrap: 'wrap' }}>
                        <label className="fm-btn fm-btn-xs fm-btn-outline" style={{ cursor: 'pointer' }}>
                          рџ“Ѓ
                          <input type="file" accept="image/*,video/*" style={{ display: 'none' }}
                            onChange={async (e) => { const f = e.target.files?.[0]; if (f) await uploadGameMediaFile(gm.id, f); }} />
                        </label>
                        <button type="button" className="fm-btn fm-btn-xs fm-btn-danger" disabled={busy} onClick={() => deleteGameMedia(gm.id)}>рџ—‘</button>
                      </div>
                    </div>
                  );
                })}
              </div>
              {gameMedia.length === 0 && <div className="fm-card" style={{ color: 'var(--text-muted)', fontSize: 13 }}>РњРµРґРёР° РїРѕРєР° РЅРµС‚. Р’С‹Р±РµСЂРёС‚Рµ С‚РёРї РёР· СЃРїРёСЃРєР° Рё СЃРѕР·РґР°Р№С‚Рµ Р·Р°РїРёСЃСЊ РґР»СЏ Р·Р°РіСЂСѓР·РєРё С„Р°Р№Р»Р°.</div>}
              {qActive && shownMedia.length === 0 && <div className="fm-card" style={{ color: 'var(--text-muted)', fontSize: 13 }}>{NO_MATCH}</div>}
            </div>
          )}

          {tab === 'story' && (
            <div>
              <h2 style={{ marginTop: 0 }}>рџ“њ РџСЂРµРґС‹СЃС‚РѕСЂРёСЏ</h2>
              <div className="fm-card" style={{ marginBottom: 10 }}>
                <label style={{ display: 'block', marginBottom: 4, fontSize: 13 }}>РўРµРєСЃС‚ СЃР»Р°Р№РґР°</label>
                <textarea className="fm-input" rows={4} value={storyForm.text} onChange={(e) => setStoryForm({ ...storyForm, text: e.target.value })} placeholder="РўРµРєСЃС‚ СЃР»Р°Р№РґР° РїСЂРµРґС‹СЃС‚РѕСЂРёРёвЂ¦" />
                <div style={{ display: 'flex', gap: 8, marginTop: 8, alignItems: 'flex-end', flexWrap: 'wrap' }}>
                  <div>
                    <label style={{ display: 'block', fontSize: 13, marginBottom: 2 }}>Р›РѕРєР°С†РёСЏ (DLC)</label>
                    <select className="fm-input" value={storyForm.location_code} onChange={(e) => setStoryForm({ ...storyForm, location_code: e.target.value })} style={{ width: 200 }}>
                      <option value="">вЂ” РѕР±С‰Р°СЏ РїСЂРµРґС‹СЃС‚РѕСЂРёСЏ вЂ”</option>
                      {dlcLocations.map((l) => <option key={l.code} value={l.code}>{l.name} ({l.code})</option>)}
                    </select>
                  </div>
                  <div>
                    <label style={{ display: 'block', fontSize: 13, marginBottom: 2 }}>РџРѕСЂСЏРґРѕРє</label>
                    <input className="fm-input" type="number" min={0} value={storyForm.sort_order} onChange={(e) => setStoryForm({ ...storyForm, sort_order: e.target.value })} style={{ width: 90 }} />
                  </div>
                  <button type="button" className="fm-btn" disabled={busy} onClick={saveStorySlide}>
                    {storyEditingId ? 'вњЋ РЎРѕС…СЂР°РЅРёС‚СЊ' : 'вћ• Р”РѕР±Р°РІРёС‚СЊ СЃР»Р°Р№Рґ'}
                  </button>
                  {storyEditingId && (
                    <button type="button" className="fm-btn" onClick={() => { setStoryEditingId(null); setStoryForm({ text: '', sort_order: '0', location_code: '' }); }}>РћС‚РјРµРЅР°</button>
                  )}
                </div>
                <p style={{ fontSize: 12, color: 'var(--text-muted)', margin: '8px 0 0' }}>
                  В«РћР±С‰Р°СЏ РїСЂРµРґС‹СЃС‚РѕСЂРёСЏВ» РїРѕРєР°Р·С‹РІР°РµС‚СЃСЏ РёРіСЂРѕРєСѓ РѕРґРёРЅ СЂР°Р· РїСЂРё РІС…РѕРґРµ, РґРѕ РЅР°СЃС‚СЂРѕР№РєРё РЅРѕСЂРј. РЎР»Р°Р№РґС‹ DLC-Р»РѕРєР°С†РёРё РїРѕРєР°Р·С‹РІР°СЋС‚СЃСЏ РїСЂРё РїРµСЂРІРѕРј РѕС‚РєСЂС‹С‚РёРё РґРѕРїРѕР»РЅРµРЅРёСЏ.
                </p>
              </div>
              <div className="fm-grid">
                {shownStorySlides.map((s) => (
                  <div key={s.id} className="fm-card fm-rise" style={{ fontSize: 13 }}>
                    {s.image_url && <img src={mediaUrl(s.image_url)} alt="" style={{ width: '100%', maxHeight: 120, objectFit: 'contain', borderRadius: 'var(--radius-sm)', marginBottom: 6 }} />}
                    <strong style={{ display: 'block', marginBottom: 4 }}>#{s.sort_order} {s.location_code ? `В· ${s.location_code}` : ''}</strong>
                    <div style={{ whiteSpace: 'pre-wrap', color: 'var(--text-secondary)', marginBottom: 6 }}>{s.text || 'вЂ”'}</div>
                    <div style={{ display: 'flex', gap: 4 }}>
                      <button type="button" className="fm-btn fm-btn-xs" disabled={busy} onClick={() => { setStoryEditingId(s.id); setStoryForm({ text: s.text || '', sort_order: String(s.sort_order), location_code: s.location_code || '' }); }}>вњЋ</button>
                      <label className="fm-btn fm-btn-xs fm-btn-outline" style={{ cursor: 'pointer' }}>
                        рџ–јпёЏ
                        <input type="file" accept="image/*" hidden onChange={(e) => { const f = e.target.files?.[0]; if (f) uploadStoryImage(s.id, f); e.target.value = ''; }} />
                      </label>
                      <button type="button" className="fm-btn fm-btn-xs fm-btn-danger" disabled={busy} onClick={() => deleteStorySlide(s.id)}>рџ—‘</button>
                    </div>
                  </div>
                ))}
              </div>
              {storySlides.length === 0 && <div className="fm-card" style={{ color: 'var(--text-muted)', fontSize: 13 }}>РЎР»Р°Р№РґРѕРІ РїРѕРєР° РЅРµС‚ вЂ” РґРѕР±Р°РІСЊС‚Рµ РїСЂРµРґС‹СЃС‚РѕСЂРёСЋ.</div>}
              {qActive && shownStorySlides.length === 0 && <div className="fm-card" style={{ color: 'var(--text-muted)', fontSize: 13 }}>{NO_MATCH}</div>}
            </div>
          )}

          {tab === 'lessons' && (
            <div>
              <h2 style={{ marginTop: 0 }}>рџЋ¬ Р’РёРґРµРѕ-СѓСЂРѕРєРё</h2>
              <div className="fm-card" style={{ marginBottom: 10 }}>
                <label style={{ display: 'block', marginBottom: 4, fontSize: 13 }}>РќР°Р·РІР°РЅРёРµ</label>
                <input className="fm-input" value={lessonForm.title} onChange={(e) => setLessonForm({ ...lessonForm, title: e.target.value })} placeholder="РќР°РїСЂРёРјРµСЂ: РєР°Рє СЃР°Р¶Р°С‚СЊ СЂР°СЃС‚РµРЅРёСЏ" />
                <label style={{ display: 'block', margin: '8px 0 4px', fontSize: 13 }}>РћРїРёСЃР°РЅРёРµ</label>
                <textarea className="fm-input" rows={3} value={lessonForm.description} onChange={(e) => setLessonForm({ ...lessonForm, description: e.target.value })} placeholder="РљРѕСЂРѕС‚РєРѕРµ РѕРїРёСЃР°РЅРёРµ СѓСЂРѕРєР°вЂ¦" />
                <div style={{ display: 'flex', gap: 8, marginTop: 8, alignItems: 'center', flexWrap: 'wrap' }}>
                  <div>
                    <label style={{ display: 'block', fontSize: 13, marginBottom: 2 }}>РџРѕСЂСЏРґРѕРє</label>
                    <input className="fm-input" type="number" min={0} value={lessonForm.sort_order} onChange={(e) => setLessonForm({ ...lessonForm, sort_order: e.target.value })} style={{ width: 90 }} />
                  </div>
                  <button type="button" className="fm-btn" disabled={busy} onClick={saveLesson} style={{ marginTop: 18 }}>
                    {lessonEditingId ? 'вњЋ РЎРѕС…СЂР°РЅРёС‚СЊ' : 'вћ• Р”РѕР±Р°РІРёС‚СЊ СѓСЂРѕРє'}
                  </button>
                  {lessonEditingId && (
                    <button type="button" className="fm-btn" style={{ marginTop: 18 }} onClick={() => { setLessonEditingId(null); setLessonForm({ title: '', description: '', sort_order: '0' }); }}>РћС‚РјРµРЅР°</button>
                  )}
                </div>
              </div>
              <div className="fm-grid">
                {shownLessons.map((l) => (
                  <div key={l.id} className="fm-card fm-rise" style={{ fontSize: 13 }}>
                    <strong>{l.title}</strong>
                    {l.video_url && (
                      <video src={mediaUrl(l.video_url)} controls playsInline style={{ width: '100%', maxHeight: 160, borderRadius: 8, marginTop: 6, marginBottom: 6 }} />
                    )}
                    <div style={{ color: 'var(--text-secondary)', marginTop: 4, whiteSpace: 'pre-wrap' }}>{l.description || 'вЂ”'}</div>
                    <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 4 }}>#{l.sort_order}</div>
                    <div style={{ display: 'flex', gap: 4, marginTop: 6 }}>
                      <button type="button" className="fm-btn fm-btn-xs" disabled={busy} onClick={() => { setLessonEditingId(l.id); setLessonForm({ title: l.title, description: l.description || '', sort_order: String(l.sort_order) }); }}>вњЋ</button>
                      <label className="fm-btn fm-btn-xs fm-btn-outline" style={{ cursor: 'pointer' }}>
                        рџЋ¬
                        <input type="file" accept="video/*" hidden onChange={(e) => { const f = e.target.files?.[0]; if (f) uploadLessonVideo(l.id, f); e.target.value = ''; }} />
                      </label>
                      <button type="button" className="fm-btn fm-btn-xs fm-btn-danger" disabled={busy} onClick={() => deleteLesson(l.id)}>рџ—‘</button>
                    </div>
                  </div>
                ))}
              </div>
              {lessons.length === 0 && <div className="fm-card" style={{ color: 'var(--text-muted)', fontSize: 13 }}>РЈСЂРѕРєРѕРІ РїРѕРєР° РЅРµС‚.</div>}
              {qActive && shownLessons.length === 0 && <div className="fm-card" style={{ color: 'var(--text-muted)', fontSize: 13 }}>{NO_MATCH}</div>}
            </div>
          )}

          {tab === 'achievements' && (
            <div>
              <h2 style={{ marginTop: 0 }}>рџЏ† Р”РѕСЃС‚РёР¶РµРЅРёСЏ</h2>
              <div className="fm-card" style={{ marginBottom: 10 }}>
                <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 8, alignItems: 'center' }}>
                  <input className="fm-input" placeholder="РќР°Р·РІР°РЅРёРµ" value={achForm.name} onChange={(e) => setAchForm({ ...achForm, name: e.target.value })} style={{ width: 160 }} />
                  <select className="fm-input" value={achForm.condition_kind} onChange={(e) => setAchForm({ ...achForm, condition_kind: e.target.value })} style={{ width: 180 }}>
                    <option value="">вЂ” С‚РёРї СѓСЃР»РѕРІРёСЏ вЂ”</option>
                    {achKinds.map((k) => <option key={k.kind} value={k.kind}>{k.label}</option>)}
                  </select>
                  {achForm.condition_kind === 'tents_count' && (
                    <select className="fm-input" value={achForm.production_code || ''} onChange={(e) => setAchForm({ ...achForm, production_code: e.target.value })} style={{ width: 180 }}>
                      <option value="">вЂ” Р»СЋР±РѕР№ С€Р°С‚С‘СЂ вЂ”</option>
                      {prodTemplates.map((pt) => <option key={pt.code} value={pt.code}>{pt.emoji || ''} {pt.name}</option>)}
                    </select>
                  )}
                  <input className="fm-input" type="number" placeholder="Р—РЅР°С‡РµРЅРёРµ" value={achForm.condition_value} onChange={(e) => setAchForm({ ...achForm, condition_value: e.target.value })} style={{ width: 80 }} />
                </div>
                {(() => { const k = achKinds.find((x) => x.kind === achForm.condition_kind); return k?.hint ? <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 8 }}>{k.hint}</div> : null; })()}
                {achEditingId && (() => { const cur = achievements.find((x) => x.id === achEditingId); return cur?.image_url ? <img src={mediaUrl(cur.image_url)} alt="" style={{ width: 56, height: 56, objectFit: 'cover', borderRadius: 'var(--radius-sm)', marginBottom: 8 }} /> : null; })()}
                <div style={{ marginBottom: 8 }}>
                  <input type="file" accept="image/*" onChange={(e) => setAchImage(e.target.files?.[0] ?? null)} style={{ fontSize: 13 }} />
                  {achImage && <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 4 }}>{achImage.name}</div>}
                </div>
                <button type="button" className="fm-btn" disabled={busy} onClick={saveAchievement}>
                  {achEditingId ? 'вњЋ РЎРѕС…СЂР°РЅРёС‚СЊ' : 'вћ• РЎРѕР·РґР°С‚СЊ'}
                </button>
                {achEditingId && <button type="button" className="fm-btn" style={{ marginLeft: 6 }} onClick={() => { setAchEditingId(null); setAchForm({ name: '', condition_kind: '', condition_value: '1', production_code: '' }); setAchImage(null); }}>РћС‚РјРµРЅР°</button>}
              </div>
              <div className="fm-grid">
                {shownAchievements.map((a) => (
                  <div key={a.id} className="fm-card fm-rise" style={{ fontSize: 13 }}>
                    {a.image_url && <img src={mediaUrl(a.image_url)} alt="" style={{ width: 56, height: 56, objectFit: 'cover', borderRadius: 'var(--radius-sm)', marginBottom: 6 }} />}
                    <strong>{a.name}</strong>
                    <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>{achKinds.find((x) => x.kind === a.condition_kind)?.label ?? a.condition_kind}: {a.condition_value}</div>
                    <div style={{ display: 'flex', gap: 4, marginTop: 6 }}>
                      <button type="button" className="fm-btn fm-btn-xs" disabled={busy} onClick={() => { setAchEditingId(a.id); setAchForm({ name: a.name, condition_kind: a.condition_kind, condition_value: String(a.condition_value), production_code: a.production_code || '' }); setAchImage(null); }}>вњЋ</button>
                      <label className="fm-btn fm-btn-xs fm-btn-outline" style={{ cursor: 'pointer' }}>
                        рџ–јпёЏ
                        <input type="file" accept="image/*" hidden onChange={(e) => { const f = e.target.files?.[0]; if (f) uploadAchImage(a.id, f); e.target.value = ''; }} />
                      </label>
                      <button type="button" className="fm-btn fm-btn-xs fm-btn-danger" disabled={busy} onClick={() => deleteAchievement(a.id)}>рџ—‘</button>
                    </div>
                  </div>
                ))}
              </div>
              {achievements.length === 0 && <div className="fm-card" style={{ color: 'var(--text-muted)', fontSize: 13 }}>Р”РѕСЃС‚РёР¶РµРЅРёР№ РїРѕРєР° РЅРµС‚.</div>}
              {qActive && shownAchievements.length === 0 && <div className="fm-card" style={{ color: 'var(--text-muted)', fontSize: 13 }}>{NO_MATCH}</div>}
            </div>
          )}

          {tab === 'crystal-cards' && (
            <div>
              <h2 style={{ marginTop: 0 }}>рџѓЏ РљР°СЂС‚С‹ РєСЂРёСЃС‚Р°Р»Р»РѕРІ ({shownCards.length}{qActive ? ` РёР· ${crystalCards.length}` : ''})</h2>
              <div className="fm-grid">
                {shownCards.map((card) => (
                  <div key={card.id} className="fm-card fm-rise" style={{ fontSize: 13, textAlign: 'center' }}>
                    {card.image_url ? (
                      <img src={mediaUrl(card.image_url)} alt="" style={{ width: 80, height: 80, objectFit: 'contain', marginBottom: 4 }} />
                    ) : (
                      <div style={{ width: 80, height: 80, background: 'var(--bg-card)', borderRadius: 'var(--radius-sm)', margin: '0 auto 4px', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 24 }}>
                        {card.is_treasure ? 'рџ’Ћ' : card.color === 'green' ? 'рџџў' : card.color === 'blue' ? 'рџ”µ' : 'рџџЈ'}
                      </div>
                    )}
                    <div>
                      {card.is_treasure ? 'РЎРѕРєСЂРѕРІРёС‰Рµ' : `${card.color} Г—${card.value}`}
                    </div>
                    <label className="fm-btn fm-btn-xs fm-btn-outline" style={{ cursor: 'pointer', marginTop: 4 }}>
                      рџ–јпёЏ
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
              <h2 style={{ marginTop: 0 }}>рџ“њ Р›РѕРіРё С„РµСЂРјС‹</h2>
              <div className="fm-card" style={{ marginBottom: 10, display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
                <select className="fm-input" value={logFilter.source} onChange={(e) => setLogFilter({ ...logFilter, source: e.target.value })} style={{ width: 130 }}>
                  <option value="">РСЃС‚РѕС‡РЅРёРє: РІСЃРµ</option>
                  <option value="server">рџ–Ґ РЎРµСЂРІРµСЂ</option>
                  <option value="vk">рџџў Р’Рљ</option>
                </select>
                <select className="fm-input" value={logFilter.level} onChange={(e) => setLogFilter({ ...logFilter, level: e.target.value })} style={{ width: 140 }}>
                  <option value="">РЈСЂРѕРІРµРЅСЊ: РІСЃРµ</option>
                  <option value="error">РћС€РёР±РєР°</option>
                  <option value="warn">РџСЂРµРґСѓРїСЂРµР¶РґРµРЅРёРµ</option>
                </select>
                <input className="fm-input" placeholder="user_id" value={logFilter.user_id} onChange={(e) => setLogFilter({ ...logFilter, user_id: e.target.value })} style={{ width: 90 }} />
                <input className="fm-input" placeholder="РџРѕРёСЃРє (РїСѓС‚СЊ / СЃРѕР±С‹С‚РёРµ / С‚РµРєСЃС‚)" value={logFilter.q} onChange={(e) => setLogFilter({ ...logFilter, q: e.target.value })} style={{ flex: 1, minWidth: 180 }} />
                <button type="button" className="fm-btn" disabled={busy} onClick={() => { setLogOffset(0); loadLogs(false); }}>рџ”„ РћР±РЅРѕРІРёС‚СЊ</button>
                <button type="button" className="fm-btn fm-btn-danger" disabled={busy} onClick={clearLogs}>рџ—‘ РћС‡РёСЃС‚РёС‚СЊ</button>
              </div>

              {logs.length === 0 && <div className="fm-card" style={{ color: 'var(--text-muted)', fontSize: 13 }}>Р›РѕРіРѕРІ РїРѕРєР° РЅРµС‚.</div>}

              <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                {logs.filter((l) => l.level !== 'info').map((l) => {
                  const lvlColor = l.level === 'error' ? '#e55' : l.level === 'warn' ? '#e90' : 'var(--text-muted)';
                  const srcColor = l.source === 'vk' ? '#3a7a4f' : '#3a5a7a';
                  return (
                    <div key={l.id} className="fm-card" style={{ padding: 10, fontSize: 13, cursor: l.details ? 'pointer' : 'default' }} onClick={() => l.details && setExpandedLog(expandedLog === l.id ? null : l.id)}>
                      <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
                        <span style={{ fontSize: 11, color: 'var(--text-muted)', fontFamily: 'monospace' }}>{fmtMsk(l.created_at)}</span>
                        <span style={{ background: srcColor, color: '#fff', borderRadius: 4, padding: '1px 6px', fontSize: 11 }}>{l.source === 'vk' ? 'VK' : 'РЎР•Р Р’'}</span>
                        <span style={{ color: lvlColor, fontWeight: 600, fontSize: 11 }}>{l.level.toUpperCase()}</span>
                        {l.status_code != null && <span style={{ fontSize: 11, fontFamily: 'monospace' }}>{l.status_code}</span>}
                        <span style={{ fontFamily: 'monospace', fontSize: 12 }}>{l.method} {l.path}</span>
                        {l.event && <span style={{ fontSize: 11, color: 'var(--text-secondary)' }}>В· {l.event}</span>}
                        {l.user_id != null && <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>В· u{l.user_id}</span>}
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
                  <button type="button" className="fm-btn fm-btn-outline" disabled={busy} onClick={() => loadLogs(true)}>РџРѕРєР°Р·Р°С‚СЊ РµС‰С‘</button>
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
        <button type="button" className="fm-btn fm-btn-sm" disabled={disabled || v === value} onClick={() => onSave(v)}>
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
    <div style={{ display: 'flex', gap: 4, alignItems: 'center' }}>
      <input
        className="fm-input"
        type="number"
        min={0}
        value={val}
        onChange={(e) => setVal(e.target.value)}
        style={{ width: 80 }}
        aria-label="Р¦РµРЅР° 1 СЂР°СЃС‚РµРЅРёСЏ"
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
        рџ’ѕ
      </button>
    </div>
  );
}

function TabBtn({ active, onClick, children }: { active: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <button type="button" className={active ? 'fm-btn' : 'fm-btn fm-btn-outline'} onClick={onClick} style={{ fontSize: 13, padding: '6px 10px' }}>
      {children}
    </button>
  );
}

interface CatField { key: string; label: string; ph?: string; type?: string; options?: { value: string; label: string }[] }

function CatalogTab({
  title, items, busy, form, formOpen, editingId, onFormChange, onCreate, onEdit, onCancel, onSave, onDelete, onUploadImage, onUploadImageYoung, onUploadImageGrown, onUploadImageEmptyPen, onUploadImagePen, onUploadImageHarvested, fields, imageLabel = 'РР·РѕР±СЂР°Р¶РµРЅРёРµ', hideMainImage = false, emptyText,
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
      if (!form.name?.trim()) onFormChange({ ...form, name: 'РќРѕРІРѕРµ' });
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
          вћ• Р”РѕР±Р°РІРёС‚СЊ
        </button>
      </div>

      {formOpen && (
        <div className="fm-card" style={{ marginBottom: 10 }}>
          <h3 style={{ marginTop: 0 }}>{editingId ? 'вњЋ Р РµРґР°РєС‚РёСЂРѕРІР°С‚СЊ' : 'вћ• РЎРѕР·РґР°С‚СЊ'}</h3>
          {fields.map((f) => (
            <div key={f.key} style={{ marginBottom: 8 }}>
              <label style={{ display: 'block', marginBottom: 4, fontSize: 13 }}>{f.label}</label>
              {f.options ? (
                <select className="fm-input" value={form[f.key] || ''} onChange={(e) => onFormChange({ ...form, [f.key]: e.target.value })}>
                  <option value="">вЂ”</option>
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
            <button type="button" className="fm-btn" disabled={busy} onClick={onSave}>рџ’ѕ РЎРѕС…СЂР°РЅРёС‚СЊ</button>
            <button type="button" className="fm-btn fm-btn-outline" disabled={busy} onClick={onCancel}>РћС‚РјРµРЅР°</button>
          </div>
          <div style={{ marginTop: 10, display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            {!hideMainImage && (
              <label className="fm-btn fm-btn-sm fm-btn-outline" style={{ cursor: 'pointer' }}>
                рџ–јпёЏ {imageLabel}
                <input type="file" accept="image/*" hidden onChange={(e) => handleFile(e.target.files?.[0], onUploadImage)} />
              </label>
            )}
            {onUploadImageYoung && (
              <label className="fm-btn fm-btn-sm fm-btn-outline" style={{ cursor: 'pointer' }}>
                рџЊ± РњРѕР»РѕРґРѕРµ
                <input type="file" accept="image/*" hidden onChange={(e) => handleFile(e.target.files?.[0], onUploadImageYoung!)} />
              </label>
            )}
            {onUploadImageGrown && (
              <label className="fm-btn fm-btn-sm fm-btn-outline" style={{ cursor: 'pointer' }}>
                рџЊі РЎРѕР·СЂРµРІС€РµРµ
                <input type="file" accept="image/*" hidden onChange={(e) => handleFile(e.target.files?.[0], onUploadImageGrown!)} />
              </label>
            )}
            {onUploadImageHarvested && (
              <label className="fm-btn fm-btn-sm fm-btn-outline" style={{ cursor: 'pointer' }}>
                рџ§є Р’С‹СЂР°С‰РµРЅРЅРѕРµ
                <input type="file" accept="image/*" hidden onChange={(e) => handleFile(e.target.files?.[0], onUploadImageHarvested!)} />
              </label>
            )}
            {onUploadImageEmptyPen && (
              <label className="fm-btn fm-btn-sm fm-btn-outline" style={{ cursor: 'pointer' }}>
                рџЏљпёЏ Р—Р°РіРѕРЅ
                <input type="file" accept="image/*" hidden onChange={(e) => handleFile(e.target.files?.[0], onUploadImageEmptyPen!)} />
              </label>
            )}
            {onUploadImagePen && (
              <label className="fm-btn fm-btn-sm fm-btn-outline" style={{ cursor: 'pointer' }}>
                рџђ„ Р’С‹СЂР°С‰РµРЅРЅРѕРµ
                <input type="file" accept="image/*" hidden onChange={(e) => handleFile(e.target.files?.[0], onUploadImagePen!)} />
              </label>
            )}
          </div>
        </div>
      )}

      {items.length === 0 ? (
        <div className="fm-card" style={{ color: 'var(--text-muted)' }}>{emptyText ?? 'РџСѓСЃС‚Рѕ. РќР°Р¶РјРёС‚Рµ В«Р”РѕР±Р°РІРёС‚СЊВ».'}</div>
      ) : (
        <div className="fm-grid">
          {items.map((item) => {
            return (
              <div key={item.id} className="fm-card fm-rise">
                <div style={{ marginBottom: 4 }}>
                  <strong style={{ wordBreak: 'break-word' }}>{item.emoji || 'вќ”'} {item.name}</strong>
                  <div style={{ fontSize: 12, color: 'var(--text-muted)', wordBreak: 'break-all' }}>{item.code}</div>
                </div>
                {!hideMainImage && item.image_url && (
                  <img src={mediaUrl(item.image_url)} alt="" style={{ width: 56, height: 56, objectFit: 'cover', borderRadius: 'var(--radius-sm)', marginBottom: 6 }} />
                )}
                {(item.image_young_url || item.image_grown_url || item.image_harvested_url) && (
                  <div style={{ display: 'flex', gap: 8, marginBottom: 6, flexWrap: 'wrap' }}>
                    <div style={{ textAlign: 'center' }}>
                      {item.image_young_url && (
                        <img src={mediaUrl(item.image_young_url)} alt="РјРѕР»РѕРґРѕРµ" style={{ width: 56, height: 56, objectFit: 'cover', borderRadius: 'var(--radius-sm)', display: 'block' }} />
                      )}
                      <div style={{ fontSize: 10, color: 'var(--text-muted)', marginTop: 2 }}>РјРѕР»РѕРґРѕРµ</div>
                    </div>
                    <div style={{ textAlign: 'center' }}>
                      {item.image_grown_url && (
                        <img src={mediaUrl(item.image_grown_url)} alt="СЃРѕР·СЂРµРІС€РµРµ" style={{ width: 56, height: 56, objectFit: 'cover', borderRadius: 'var(--radius-sm)', display: 'block' }} />
                      )}
                      <div style={{ fontSize: 10, color: 'var(--text-muted)', marginTop: 2 }}>СЃРѕР·СЂРµРІС€РµРµ</div>
                    </div>
                    <div style={{ textAlign: 'center' }}>
                      {item.image_harvested_url && (
                        <img src={mediaUrl(item.image_harvested_url)} alt="РІС‹СЂР°С‰РµРЅРЅРѕРµ" style={{ width: 56, height: 56, objectFit: 'cover', borderRadius: 'var(--radius-sm)', display: 'block' }} />
                      )}
                      <div style={{ fontSize: 10, color: 'var(--text-muted)', marginTop: 2 }}>РІС‹СЂР°С‰РµРЅРЅРѕРµ</div>
                    </div>
                  </div>
                )}
                {(item.image_empty_pen_url || item.image_pen_url) && (
                  <div style={{ display: 'flex', gap: 8, marginBottom: 6, flexWrap: 'wrap' }}>
                    {item.image_empty_pen_url && (
                      <div style={{ textAlign: 'center' }}>
                        <img src={mediaUrl(item.image_empty_pen_url)} alt="РїСѓСЃС‚РѕР№ Р·Р°РіРѕРЅ" style={{ width: 48, height: 48, objectFit: 'cover', borderRadius: 'var(--radius-sm)' }} />
                        <div style={{ fontSize: 9, color: 'var(--text-muted)' }}>Р·Р°РіРѕРЅ</div>
                      </div>
                    )}
                    {item.image_pen_url && (
                      <div style={{ textAlign: 'center' }}>
                        <img src={mediaUrl(item.image_pen_url)} alt="Р·Р°РіРѕРЅ СЃ Р¶РёРІРѕС‚РЅС‹Рј" style={{ width: 48, height: 48, objectFit: 'cover', borderRadius: 'var(--radius-sm)' }} />
                        <div style={{ fontSize: 9, color: 'var(--text-muted)' }}>СЃ Р¶РёРІРѕС‚РЅС‹Рј</div>
                      </div>
                    )}
                    {item.image_harvested_url && (
                      <div style={{ textAlign: 'center' }}>
                        <img src={mediaUrl(item.image_harvested_url)} alt="РІС‹СЂР°С‰РµРЅРЅРѕРµ" style={{ width: 48, height: 48, objectFit: 'cover', borderRadius: 'var(--radius-sm)' }} />
                        <div style={{ fontSize: 9, color: 'var(--text-muted)' }}>РІС‹СЂР°С‰РµРЅРЅРѕРµ</div>
                      </div>
                    )}
                  </div>
                )}
                {onUploadImageYoung ? (
                  <div style={{ display: 'flex', gap: 4, marginTop: 8, flexWrap: 'wrap' }}>
                    <button type="button" className="fm-btn fm-btn-xs" disabled={busy} onClick={() => onEdit(item)}>вњЋ</button>
                    <label className="fm-btn fm-btn-xs fm-btn-outline" title="Р—Р°РіСЂСѓР·РёС‚СЊ РјРѕР»РѕРґРѕРµ СЂР°СЃС‚РµРЅРёРµ" style={{ cursor: 'pointer' }}>
                      рџЊ±
                      <input type="file" accept="image/*" style={{ display: 'none' }}
                        onChange={async (e) => { const f = e.target.files?.[0]; if (f && onUploadImageYoung) await onUploadImageYoung(item.id, f); }}
                      />
                    </label>
                    <label className="fm-btn fm-btn-xs fm-btn-outline" title="Р—Р°РіСЂСѓР·РёС‚СЊ СЃРѕР·СЂРµРІС€РµРµ СЂР°СЃС‚РµРЅРёРµ" style={{ cursor: 'pointer' }}>
                      рџЊѕ
                      <input type="file" accept="image/*" style={{ display: 'none' }}
                        onChange={async (e) => { const f = e.target.files?.[0]; if (f && onUploadImageGrown) await onUploadImageGrown(item.id, f); }}
                      />
                    </label>
                    {onUploadImageHarvested && (
                      <label className="fm-btn fm-btn-xs fm-btn-outline" title="Р—Р°РіСЂСѓР·РёС‚СЊ РІС‹СЂР°С‰РµРЅРЅРѕРµ СЂР°СЃС‚РµРЅРёРµ" style={{ cursor: 'pointer' }}>
                        рџ§є
                        <input type="file" accept="image/*" style={{ display: 'none' }}
                          onChange={async (e) => { const f = e.target.files?.[0]; if (f && onUploadImageHarvested) await onUploadImageHarvested(item.id, f); }}
                        />
                      </label>
                    )}
                    <button type="button" className="fm-btn fm-btn-xs fm-btn-danger" disabled={busy} onClick={() => onDelete(item.id)}>вњ•</button>
                  </div>
                ) : (
                  <div style={{ display: 'flex', gap: 4, marginTop: 8, flexWrap: 'wrap' }}>
                    <button type="button" className="fm-btn fm-btn-xs" disabled={busy} onClick={() => onEdit(item)}>вњЋ</button>
                    {!hideMainImage && (
                      <label className="fm-btn fm-btn-xs fm-btn-outline" title="Р—Р°РіСЂСѓР·РёС‚СЊ РёР·РѕР±СЂР°Р¶РµРЅРёРµ" style={{ cursor: 'pointer' }}>
                        рџ–јпёЏ
                        <input type="file" accept="image/*" style={{ display: 'none' }}
                          onChange={async (e) => {
                            const file = e.target.files?.[0];
                            if (file) { await onUploadImage(item.id, file); }
                          }}
                        />
                      </label>
                    )}
                    <button type="button" className="fm-btn fm-btn-xs fm-btn-danger" disabled={busy} onClick={() => onDelete(item.id)}>вњ•</button>
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

