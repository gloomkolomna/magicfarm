import client from './client';
import { compressImage } from './media';

export interface Plant {
  id: number;
  code: string;
  name: string;
  emoji: string | null;
  category: string;
  level: number;
  norm_per_crystal: number;
  description: string | null;
  stitch_condition: string | null;
  image_url: string | null;
  image_young_url: string | null;
  image_grown_url: string | null;
  image_harvested_url: string | null;
}

export interface Customer {
  id: number;
  name: string;
  image_url: string | null;
  open_orders_count: number;
}

export interface LevelGate {
  level: number;
  coins_required: number;
  plots_required: number;
  unlock_type: string | null;
  image_url: string | null;
}

export const UNLOCK_OPTIONS = [
  'Животноводство +1',
  'Животноводство +2',
  'Питомец-помощник +1',
  'Сад 1 уровня',
  'Сад 2 уровня',
  'Сад 3 уровня',
  'Грядка 2 уровня',
  'Грядка 3 уровня',
] as const;

export interface PotionRecipe {
  id: number;
  code: string;
  name: string;
  level: string;
  ingredient_slots: string[];
  bonus_code: string | null;
  reward_coins: number;
  description: string | null;
  image_url: string | null;
  card_image_url?: string | null;
}

export const POTION_BONUS_LABELS: Record<string, string> = {
  double_garden_harvest: '×2 урожай с грядки',
  double_orchard_harvest: '×2 урожай из сада',
  double_animal_product: '×2 продукция животного',
  skip_plant_stitch: 'Растение без отшива нормы',
  early_level_up: '+1 уровень маршрутного листа',
  double_order_reward: '×2 награда за заказ',
  free_pet: 'Бесплатный питомец',
  extra_barnyard_slot: '+1 загон зверо-двора',
  bonus_sewing_product: '+1 товар портнихи',
  bonus_workshop_product: '+1 товар мастерской',
  bonus_alchemy_product: '+1 товар зельеварения',
  skip_animal_stitch: 'Животное без отшива нормы',
  unlock_garden_l3: 'Грядки 3 уровня',
  unlock_orchard_l3: 'Сады 3 уровня',
  partial_order: 'Неполное выполнение заказа',
};

export function potionBonusLabel(code: string | null | undefined): string | null {
  if (!code) return null;
  return POTION_BONUS_LABELS[code] || code;
}

export const POTION_INGREDIENT_ICONS: Record<string, string> = {
  plant: '🌿',
  product: '📦',
  plant_garden: '🍃',
  plant_orchard: '🍎',
  animal_product: '🥚',
  workshop: '🔨',
  sewing: '🧵',
  alchemy: '🔮',
  barnyard: '🏚️',
};

export const POTION_INGREDIENT_LABELS: Record<string, string> = {
  plant: 'Растение',
  product: 'Товар',
  plant_garden: 'Растение (грядка)',
  plant_orchard: 'Растение (сад)',
  animal_product: 'Продукция животного',
  workshop: 'Товар мастерской',
  sewing: 'Товар портнихи',
  alchemy: 'Товар зельеварения',
  barnyard: 'Товар скотного двора',
};

export function potionIngredientLabel(code: string): string {
  return POTION_INGREDIENT_LABELS[code] || code;
}

export function cauldronMaterialFor(slots: string[]): 'tin' | 'silver' | 'gold' {
  const n = slots.length;
  if (n >= 6) return 'gold';
  if (n === 5) return 'silver';
  return 'tin';
}

export const CAULDRON_MATERIAL_LABELS: Record<string, string> = {
  tin: 'Оловянный котёл',
  silver: 'Серебряный котёл',
  gold: 'Золотой котёл',
};

export interface PotionRecipeCreate {
  name: string;
  level: string;
  ingredient_slots: string[];
  bonus_code?: string | null;
  reward_coins?: number;
  description?: string | null;
}

export interface CauldronSlot {
  slot_index: number;
  item_type: string;
  item_id: number;
}

export interface Cauldron {
  id: number;
  recipe_id: number;
  recipe_name: string;
  material: string;
  capacity: number;
  status: string;
  slots: CauldronSlot[];
}

export interface SlotWarehouseItem {
  item_kind: string;
  item_id: number;
  item_name: string;
  item_emoji: string | null;
  item_image: string | null;
  qty: number;
}

export interface UserPotion {
  id: number;
  potion_recipe_id: number;
  potion_name: string;
  bonus_code: string | null;
  bonus_description: string | null;
  when_fires: string | null;
  description: string | null;
  image_url: string | null;
  activated: boolean;
  used: boolean;
}

export interface BonusCatalogItem {
  code: string;
  label: string;
  kind: 'instant' | 'conditional';
  owned: boolean;
  activated: boolean;
  used: boolean;
  potion_id: number | null;
  when_fires: string | null;
}

export type CrystalColor = 'green' | 'blue' | 'violet';

export interface ColorNorms {
  norm: number;
  treasure: number;
}

export type CrystalNorms = Record<CrystalColor, ColorNorms>;

export interface LevelNorms {
  level1: number | null;
  level2: number | null;
  level3: number | null;
}

export interface CrystalNormsMine {
  onboarding_done: boolean;
  norms: CrystalNorms;
  dice_norm: number;
  study_norms: LevelNorms;
  production_norms: LevelNorms;
}

export interface Animal {
  id: number;
  code: string;
  name: string;
  emoji: string | null;
  product_name: string | null;
  sort_order: number;
  image_url: string | null;
  image_empty_pen_url: string | null;
  image_pen_url: string | null;
  image_harvested_url: string | null;
}

export interface Pet {
  id: number;
  code: string;
  name: string;
  emoji: string | null;
  bonus_kind: string | null;
  bonus_description: string | null;
  image_url: string | null;
}

export interface Plot {
  id: number;
  plant_id: number;
  plant_name: string;
  plant_emoji: string | null;
  qty: number;
  status: string;
  accumulated: number;
  required: number;
  crystal_color: string | null;
  crystal_count: number | null;
  drawn_cards_json: string | null;
  norm_revealed: boolean;
  created_at: string | null;
  completed_at: string | null;
}

export interface Production {
  id: number;
  kind: string;
  name: string;
  status: string;
  accumulated: number;
  required: number;
  created_at: string | null;
}

export interface LibraryRecipe {
  id: number;
  source_kind: string;
  plant_id: number | null;
  plant_name: string | null;
  plant_emoji: string | null;
  plant_image?: string | null;
  source_product_id: number | null;
  source_product_name: string | null;
  source_product_emoji: string | null;
  source_product_image?: string | null;
  product_id: number;
  product_name: string;
  product_emoji: string | null;
  product_image?: string | null;
  level: number;
  status: string;
}

export interface InventoryItem {
  item_kind: string;
  item_id: number;
  item_code: string;
  item_name: string;
  item_emoji: string | null;
  item_image: string | null;
  qty: number;
  ingredient_type: string | null;
  ingredient_icon: string | null;
}

export interface CraftInfo {
  source_kind: string;
  plant_id: number | null;
  plant_name: string | null;
  plant_emoji: string | null;
  source_product_id: number | null;
  source_product_name: string | null;
  source_product_emoji: string | null;
  stock_qty: number;
  norm_per_unit: number;
}

export interface CraftStart {
  craft_session_id: number;
  required: number;
  plant_name?: string;
  source_product_name?: string;
  product_name: string;
  qty: number;
}

export interface CraftSessionInfo {
  id: number;
  product_id: number;
  product_name: string;
  product_emoji: string | null;
  plant_name: string | null;
  source_product_name: string | null;
  qty: number;
  required: number;
  production_kind: string | null;
  status: string;
  created_at: string | null;
}

export interface ProductionTemplate {
  id: number;
  code: string;
  name: string;
  emoji: string | null;
  required: number;
  cards_to_draw: number;
  surcharge: number;
  processing_crystal: number;
  image_url: string | null;
}

export interface Product {
  id: number;
  code: string;
  name: string;
  emoji: string | null;
  plant_id: number | null;
  animal_id: number | null;
  pet_id: number | null;
  stars: number;
  production_kind: string | null;
  image_url: string | null;
}

export interface AdminRecipe {
  id: number;
  plant_id: number | null;
  plant_name: string | null;
  plant_emoji: string | null;
  source_product_id: number | null;
  source_product_name: string | null;
  source_product_emoji: string | null;
  product_id: number;
  product_name: string;
  product_emoji: string | null;
  level: number;
}

export interface AdminRecipeCreate {
  plant_id: number | null;
  source_product_id: number | null;
  product_id: number;
  level: number;
}

export interface PlayerDetail extends Player {
  plots: Plot[];
  productions: Production[];
  inventory: InventoryItem[];
}

export interface Player {
  vk_id: number;
  first_name: string;
  last_name: string;
  role: string;
  crosses_balance: number;
  crosses_total: number;
  coins: number;
  round: number;
  reports_total: number;
  created_at: string | null;
}

export interface StitchReport {
  id: number;
  user_id: number;
  amount: number;
  photo_before_url: string | null;
  photo_after_url: string;
  note: string | null;
  context_type: string | null;
  context_id: number | null;
  status: string;
  reviewer_id: number | null;
  reviewed_at: string | null;
  created_at: string | null;
}

export interface Order {
  id: number;
  product_id: number;
  product_code: string;
  product_name: string;
  product_emoji: string | null;
  product_image_url: string | null;
  qty: number;
  reward_coins: number;
  customer: string | null;
  customer_phrase: string | null;
  customer_image_url: string | null;
  status: string;
  name: string | null;
  image_url: string | null;
  created_at: string | null;
  fulfilled_at: string | null;
  available?: boolean;
  lock_reason?: string | null;
}

export interface AdminOrder extends Order {
  user_id: number | null;
}

export interface Setting {
  key: string;
  value: string;
}

// ── Карты-локации ──
export interface FieldInfo {
  id: number;
  code: string;
  name: string;
  map_url: string | null;
  cols: number;
  rows: number;
  grid_color: string;
  plant_category: string | null;
  min_level: number;
  field_kind: string | null;
  created_at: string | null;
}

export interface FieldCell {
  id: number;
  col: number;
  row: number;
  kind: string;
  plant_id: number | null;
  occupant_user_id: number | null;
  tent_id: number | null;
}

export interface BarnyardCell {
  slot_id: number;
  animal_id: number | null;
  animal_name: string | null;
  animal_emoji: string | null;
  status: string;
  accumulated: number;
  required: number;
  last_die: number | null;
  image_empty_pen_url: string | null;
  image_pen_url: string | null;
  image_harvested_url: string | null;
}

export interface PetCell {
  pet_id: number;
  pet_name: string;
  pet_emoji: string | null;
  bonus_description: string | null;
}

export interface FieldCellDetail extends FieldCell {
  plant_name: string | null;
  plant_emoji: string | null;
  plant_image_young: string | null;
  plant_image_grown: string | null;
  plant_image_harvested: string | null;
  plot: Plot | null;
  tent_name: string | null;
  tent_image: string | null;
  occupant_name: string | null;
  barnyard: BarnyardCell | null;
  pet: PetCell | null;
}

export interface Tent {
  id: number;
  name: string;
  image_url: string | null;
  kind: string;
  col1: number;
  row1: number;
  col2: number;
  row2: number;
  builder_user_id: number | null;
  build_status: string;
  accumulated: number;
  required: number;
  crystal_color: string | null;
  crystal_count: number | null;
  drawn_cards_json: string | null;
  norm_revealed: boolean;
}

export interface HouseState {
  id: number | null;
  tent_id: number;
  phase: 'materials' | 'built';
  current_material: string | null;
  current_die: number | null;
  current_required: number | null;
  collected: string[];
  cards_json: string | null;
  required: number;
}

export interface PlantBed {
  id: number;
  field_id: number;
  col1: number;
  row1: number;
  col2: number;
  row2: number;
  plant_category: string | null;
  plant_id: number | null;
  occupant_user_id: number | null;
  plant_name?: string | null;
  plant_emoji?: string | null;
  plant_image_young?: string | null;
  plant_image_grown?: string | null;
  plant_image_harvested?: string | null;
  plot?: Plot | null;
}

export interface PetZone {
  id: number;
  field_id: number;
  col1: number;
  row1: number;
  col2: number;
  row2: number;
}

export interface BreweryZone {
  id: number;
  field_id: number;
  zone_kind: 'cauldron' | 'jar' | 'ingredient' | 'recipe_card';
  col1: number;
  row1: number;
  col2: number;
  row2: number;
  image_url: string | null;
  recipe_id: number | null;
}

export interface BreweryZoneView extends BreweryZone {
  recipe_name?: string | null;
  recipe_image?: string | null;
  recipe_card_image?: string | null;
}

export interface FieldDetail extends FieldInfo {
  cells: FieldCellDetail[];
  plants: Plant[];
  tents?: Tent[];
  plant_beds?: PlantBed[];
  pet_zones?: PetZone[];
  animal_ids?: number[];
  pet_ids?: number[];
  brewery_zones?: BreweryZoneView[];
  potion_recipes?: PotionRecipe[];
  active_cauldron?: Cauldron | null;
}

export interface NormImage {
  color: string;
  count: number;
  image_url: string | null;
}

export interface BarnyardPen {
  id: number;
  animal_id: number | null;
  animal_name: string | null;
  animal_emoji: string | null;
  status: 'empty' | 'building' | 'ready';
  accumulated: number;
  required: number;
  last_die: number | null;
  drawn_cards_json: string | null;
  opening_order: number;
  cell_id: number | null;
  image_empty_pen_url: string | null;
  image_pen_url: string | null;
  image_harvested_url: string | null;
}

export interface BarnyardProduceResult {
  slot_id: number;
  die: number;
  required: number;
  animal_name: string;
  product_coins: number;
}

export interface GameMedia {
  id: number;
  code: string;
  kind: string;
  url: string | null;
}

export interface CrystalCard {
  id: number;
  color: string;
  value: number;
  is_treasure: boolean;
  image_url: string | null;
}

export interface Achievement {
  id: number;
  code: string;
  name: string;
  condition_kind: string;
  condition_value: number;
  production_code: string | null;
  image_url: string | null;
  earned: boolean;
}

export interface AchievementKind {
  kind: string;
  label: string;
  hint?: string;
}

export interface LogEntry {
  id: number;
  source: string;
  level: string;
  event: string | null;
  method: string | null;
  path: string | null;
  status_code: number | null;
  message: string | null;
  details: string | null;
  user_id: number | null;
  client_ip: string | null;
  created_at: string;
}

export interface LogsQuery {
  source?: string;
  level?: string;
  q?: string;
  user_id?: number;
  limit?: number;
  offset?: number;
}

export const api = {
  // ── Производства / склад ──
  investPlot: (plot_id: number, amount: number) =>
    client.post<Plot>(`/farm/plots/${plot_id}/invest`, { amount }).then((r) => r.data),
  revealNorm: (plot_id: number) =>
    client.post<Plot>(`/farm/plots/${plot_id}/reveal-norm`).then((r) => r.data),
  craftProduct: (production_id: number, product_id: number, qty = 1) =>
    client
      .post<CraftStart>(`/farm/productions/${production_id}/craft`, { product_id, qty })
      .then((r) => r.data),
  productCraftInfo: (product_id: number, production_kind?: string) =>
    client.get<CraftInfo>('/farm/products/' + product_id + '/craft-info', {
      params: production_kind ? { production_kind } : undefined,
    }).then((r) => r.data),
  craftSessions: () =>
    client.get<CraftSessionInfo[]>('/farm/craft-sessions', { params: { status: 'pending' } }).then((r) => r.data),
  cancelCraftSession: (id: number) =>
    client.delete(`/farm/craft-sessions/${id}`).then((r) => r.data),
  productions: () => client.get<Production[]>('/farm/productions').then((r) => r.data),
  inventory: (itemKind?: string) =>
    client.get<InventoryItem[]>('/farm/inventory', { params: itemKind ? { item_kind: itemKind } : {} }).then((r) => r.data),
  products: () => client.get<Product[]>('/farm/products').then((r) => r.data),

  // ── Каталог растений ──
  plants: (category?: string) =>
    client
      .get<Plant[]>('/plants', { params: category ? { category } : {} })
      .then((r) => r.data),

  // ── Фото-отчёты по вышивке ──
  createStitchReport: async (amount: number, photoBefore: File, photoAfter: File, note?: string, contextType?: string, contextId?: number, cellId?: number) => {
    const [cb, ca] = await Promise.all([
      compressImage(photoBefore, 1280, 0.85).catch(() => photoBefore),
      compressImage(photoAfter, 1280, 0.85).catch(() => photoAfter),
    ]);
    const form = new FormData();
    form.append('amount', String(amount));
    if (note) form.append('note', note);
    form.append('photo_before', cb);
    form.append('photo_after', ca);
    if (contextType) form.append('context_type', contextType);
    if (contextId != null) form.append('context_id', String(contextId));
    if (cellId != null) form.append('cell_id', String(cellId));
    const r = await client.post<StitchReport>('/stitches/reports', form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return r.data;
  },
  stitchReports: (status?: string, mine = true) =>
    client
      .get<StitchReport[]>('/stitches/reports', { params: { status, mine } })
      .then((r) => r.data),
  reviewReport: (id: number, action: 'accept' | 'reject') =>
    client.post<StitchReport>(`/stitches/reports/${id}/${action}`).then((r) => r.data),
  deleteReport: (id: number) =>
    client.delete(`/stitches/reports/${id}`).then((r) => r.data),

  // ── Заказы ──
  orders: (status_filter?: string) =>
    client
      .get<Order[]>('/orders', { params: status_filter ? { status_filter } : {} })
      .then((r) => r.data),
  generateOrder: (product_id: number, qty?: number, customer?: string | null) =>
    client.post<Order>('/orders/generate', { product_id, qty, customer }).then((r) => r.data),
  availableOrders: () =>
    client.get<Order[]>('/orders/available').then((r) => r.data),
  takeOrder: (id: number) =>
    client.post<Order>(`/orders/${id}/take`).then((r) => r.data),
  customerNames: () =>
    client.get<string[]>('/orders/customers').then((r) => r.data),
  fulfillOrder: (id: number) => client.post<Order>(`/orders/${id}/fulfill`).then((r) => r.data),
  cancelOrder: (id: number) => client.post<Order>(`/orders/${id}/cancel`).then((r) => r.data),
  uploadOrderImage: async (orderId: number, file: File) => {
    const compressed = await compressImage(file, 1280, 0.85).catch(() => file);
    const form = new FormData();
    form.append('image', compressed);
    return client.post<Order>(`/orders/${orderId}/image`, form, { headers: { 'Content-Type': 'multipart/form-data' } }).then((r) => r.data);
  },

  // ── Библиотека рецептов ──
  library: () =>
    client.get<LibraryRecipe[]>('/library').then((r) => r.data),
  studyRecipe: (id: number) =>
    client.post<LibraryRecipe>(`/library/${id}/study`).then((r) => r.data),

  // ── Настройки ──
  getSetting: (key: string) =>
    client.get<Setting>(`/settings/${key}`).then((r) => r.data),
  updateSetting: (key: string, value: string) =>
    client.put<Setting>(`/admin/settings/${key}`, { value }).then((r) => r.data),

  // ── Нормы кристаллов ──
  crystalStandard: () =>
    client.get<{ norms: CrystalNorms }>('/crystal-norms/standard').then((r) => r.data.norms),
  setCrystalStandard: (norms: CrystalNorms) =>
    client.put<{ norms: CrystalNorms }>('/crystal-norms/admin/standard', { norms }).then((r) => r.data.norms),
  normImages: () =>
    client.get<NormImage[]>('/crystal-norms/admin/images').then((r) => r.data),
  uploadNormImage: (color: string, count: number, file: File) => {
    const form = new FormData();
    form.append('image', file);
    return client.put<NormImage>(`/crystal-norms/admin/images/${color}/${count}`, form, { headers: { 'Content-Type': 'multipart/form-data' } }).then((r) => r.data);
  },
  myCrystalNorms: () =>
    client.get<CrystalNormsMine>('/crystal-norms/mine').then((r) => r.data),
  setMyCrystalNorms: (
    norms: CrystalNorms,
    diceNorm: number,
    studyNorms?: { level1: number | null; level2: number | null; level3: number | null },
    productionNorms?: { level1: number | null; level2: number | null; level3: number | null },
  ) =>
    client.put<CrystalNormsMine>('/crystal-norms/mine', {
      norms,
      dice_norm: diceNorm,
      study_norms: studyNorms,
      production_norms: productionNorms,
    }).then((r) => r.data),

  // ── Питомцы ──
  userPets: () => client.get<any[]>('/pets').then(r => r.data),
  settlePet: (petId: number) => client.post('/pets/settle', {pet_id: petId}).then(r => r.data),
  settlePetOnCell: (cellId: number, petId: number) =>
    client.post(`/pets/cells/${cellId}/settle`, { pet_id: petId }).then(r => r.data),
  petsCatalog: () => client.get<Pet[]>('/pets/catalog').then((r) => r.data),

  // ── Карты-локации: админка ──
  adminFields: () => client.get<FieldInfo[]>('/admin/fields').then((r) => r.data),
  adminCreateField: (name: string, cols = 6, rows = 4, plant_category?: string | null, min_level?: number, field_kind?: string | null) =>
    client.post<FieldInfo>('/admin/fields', { name, cols, rows, plant_category, min_level, field_kind }).then((r) => r.data),
  adminGetField: (id: number) =>
    client.get<FieldDetail>(`/admin/fields/${id}`).then((r) => r.data),
  adminUpdateField: (id: number, data: { name?: string; cols?: number; rows?: number; grid_color?: string; min_level?: number }) =>
    client.put<FieldDetail>(`/admin/fields/${id}`, data).then((r) => r.data),
  adminUploadFieldMap: (id: number, mapImage: File) => {
    const form = new FormData();
    form.append('map_image', mapImage);
    return client
      .put<FieldInfo>(`/admin/fields/${id}/map`, form, { headers: { 'Content-Type': 'multipart/form-data' } })
      .then((r) => r.data);
  },
  adminDeleteField: (id: number) =>
    client.delete(`/admin/fields/${id}`).then((r) => r.data),
  adminSetBlocked: (id: number, cells: { col: number; row: number }[], kind: string = 'bed') =>
    client.put<FieldDetail>(`/admin/fields/${id}/cells/blocked`, { cells, kind }).then((r) => r.data),
  adminSetCellKind: (fieldId: number, col: number, row: number, kind: string) =>
    client.put<FieldCell>(`/admin/fields/${fieldId}/cell/${col}/${row}`, { kind }).then((r) => r.data),
  adminSetFieldPlants: (id: number, plantIds: number[]) =>
    client.put<Plant[]>(`/admin/fields/${id}/plants`, { plant_ids: plantIds }).then((r) => r.data),
  adminSetFieldAnimals: (id: number, animalIds: number[]) =>
    client.put<number[]>(`/admin/fields/${id}/animals`, { animal_ids: animalIds }).then((r) => r.data),
  adminSetFieldPets: (id: number, petIds: number[]) =>
    client.put<number[]>(`/admin/fields/${id}/pets`, { pet_ids: petIds }).then((r) => r.data),
  adminCreateTent: (
    id: number,
    data: { name: string; kind: string; col1: number; row1: number; col2: number; row2: number },
    image?: File,
  ) => {
    const form = new FormData();
    form.append('name', data.name);
    form.append('kind', data.kind);
    form.append('col1', String(data.col1));
    form.append('row1', String(data.row1));
    form.append('col2', String(data.col2));
    form.append('row2', String(data.row2));
    if (image) form.append('image', image);
    return client
      .post<Tent>(`/admin/fields/${id}/tents`, form, { headers: { 'Content-Type': 'multipart/form-data' } })
      .then((r) => r.data);
  },
  adminDeleteTent: (fieldId: number, tentId: number) =>
    client.delete(`/admin/fields/${fieldId}/tents/${tentId}`).then((r) => r.data),

  adminCreatePlantBed: (fieldId: number, col1: number, row1: number, col2: number, row2: number) => {
    const form = new FormData();
    form.append('col1', String(col1));
    form.append('row1', String(row1));
    form.append('col2', String(col2));
    form.append('row2', String(row2));
    return client
      .post<PlantBed>(`/admin/fields/${fieldId}/plant-beds`, form, { headers: { 'Content-Type': 'multipart/form-data' } })
      .then((r) => r.data);
  },
  adminDeletePlantBed: (fieldId: number, bedId: number) =>
    client.delete(`/admin/fields/${fieldId}/plant-beds/${bedId}`).then((r) => r.data),

  adminCreateBreweryZone: (
    fieldId: number,
    zoneKind: 'cauldron' | 'jar' | 'ingredient' | 'recipe_card',
    rect: { col1: number; row1: number; col2: number; row2: number },
    opts?: { image?: File; recipeId?: number },
  ) => {
    const form = new FormData();
    form.append('zone_kind', zoneKind);
    form.append('col1', String(rect.col1));
    form.append('row1', String(rect.row1));
    form.append('col2', String(rect.col2));
    form.append('row2', String(rect.row2));
    if (opts?.image) form.append('image', opts.image);
    if (opts?.recipeId != null) form.append('recipe_id', String(opts.recipeId));
    return client
      .post<BreweryZone>(`/admin/fields/${fieldId}/brewery-zones`, form, { headers: { 'Content-Type': 'multipart/form-data' } })
      .then((r) => r.data);
  },
  adminUploadBreweryZoneImage: (fieldId: number, zoneId: number, image: File) => {
    const form = new FormData();
    form.append('image', image);
    return client
      .put<BreweryZone>(`/admin/fields/${fieldId}/brewery-zones/${zoneId}/image`, form, { headers: { 'Content-Type': 'multipart/form-data' } })
      .then((r) => r.data);
  },
  adminDeleteBreweryZone: (fieldId: number, zoneId: number) =>
    client.delete(`/admin/fields/${fieldId}/brewery-zones/${zoneId}`).then((r) => r.data),
  adminSetFieldPotionRecipes: (fieldId: number, recipeIds: number[]) =>
    client.put<number[]>(`/admin/fields/${fieldId}/potion-recipes`, { recipe_ids: recipeIds }).then((r) => r.data),

  adminCreatePetZone: (fieldId: number, col1: number, row1: number, col2: number, row2: number) => {
    const form = new FormData();
    form.append('col1', String(col1));
    form.append('row1', String(row1));
    form.append('col2', String(col2));
    form.append('row2', String(row2));
    return client
      .post<PetZone>(`/admin/fields/${fieldId}/pet-zones`, form, { headers: { 'Content-Type': 'multipart/form-data' } })
      .then((r) => r.data);
  },
  adminDeletePetZone: (fieldId: number, zoneId: number) =>
    client.delete(`/admin/fields/${fieldId}/pet-zones/${zoneId}`).then((r) => r.data),

  // ── Каталог: растения, животные, питомцы ──
  adminPlants: () => client.get<Plant[]>('/admin/catalog/plants').then((r) => r.data),
  adminCreatePlant: (data: Partial<Plant> & { code: string; name: string }) =>
    client.post<Plant>('/admin/catalog/plants', data).then((r) => r.data),
  adminUpdatePlant: (id: number, data: Partial<Plant>) =>
    client.put<Plant>(`/admin/catalog/plants/${id}`, data).then((r) => r.data),
  adminDeletePlant: (id: number) =>
    client.delete(`/admin/catalog/plants/${id}`).then((r) => r.data),

  adminAnimals: () => client.get<Animal[]>('/admin/catalog/animals').then((r) => r.data),
  adminCreateAnimal: (data: Partial<Animal> & { code: string; name: string }) =>
    client.post<Animal>('/admin/catalog/animals', data).then((r) => r.data),
  adminUpdateAnimal: (id: number, data: Partial<Animal>) =>
    client.put<Animal>(`/admin/catalog/animals/${id}`, data).then((r) => r.data),
  adminDeleteAnimal: (id: number) =>
    client.delete(`/admin/catalog/animals/${id}`).then((r) => r.data),

  adminPets: () => client.get<Pet[]>('/admin/catalog/pets').then((r) => r.data),
  adminCreatePet: (data: Partial<Pet> & { code: string; name: string }) =>
    client.post<Pet>('/admin/catalog/pets', data).then((r) => r.data),
  adminUpdatePet: (id: number, data: Partial<Pet>) =>
    client.put<Pet>(`/admin/catalog/pets/${id}`, data).then((r) => r.data),
  adminDeletePet: (id: number) =>
    client.delete(`/admin/catalog/pets/${id}`).then((r) => r.data),

  adminProducts: () => client.get<Product[]>('/admin/catalog/products').then((r) => r.data),
  adminCreateProduct: (data: Partial<Product> & { code: string; name: string }) =>
    client.post<Product>('/admin/catalog/products', data).then((r) => r.data),
  adminUpdateProduct: (id: number, data: Partial<Product>) =>
    client.put<Product>(`/admin/catalog/products/${id}`, data).then((r) => r.data),
  adminDeleteProduct: (id: number) =>
    client.delete(`/admin/catalog/products/${id}`).then((r) => r.data),

  adminProductionTemplates: () =>
    client.get<ProductionTemplate[]>('/admin/catalog/production-templates').then((r) => r.data),
  adminCreateProductionTemplate: (data: Partial<ProductionTemplate> & { name: string }) =>
    client.post<ProductionTemplate>('/admin/catalog/production-templates', data).then((r) => r.data),
  adminUpdateProductionTemplate: (id: number, data: Partial<ProductionTemplate>) =>
    client.put<ProductionTemplate>(`/admin/catalog/production-templates/${id}`, data).then((r) => r.data),
  adminDeleteProductionTemplate: (id: number) =>
    client.delete(`/admin/catalog/production-templates/${id}`).then((r) => r.data),

  adminRecipes: () => client.get<AdminRecipe[]>('/admin/catalog/recipes').then((r) => r.data),
  adminCreateRecipe: (data: AdminRecipeCreate) =>
    client.post<AdminRecipe>('/admin/catalog/recipes', data).then((r) => r.data),
  adminUpdateRecipe: (id: number, data: Partial<AdminRecipeCreate>) =>
    client.put<AdminRecipe>(`/admin/catalog/recipes/${id}`, data).then((r) => r.data),
  adminDeleteRecipe: (id: number) =>
    client.delete(`/admin/catalog/recipes/${id}`).then((r) => r.data),

  adminUploadPlantImage: (id: number, file: File) => {
    const form = new FormData();
    form.append('image', file);
    return client.put<Plant>(`/admin/catalog/plants/${id}/image`, form, { headers: { 'Content-Type': 'multipart/form-data' } }).then((r) => r.data);
  },
  adminUploadPlantImageYoung: (id: number, file: File) => {
    const form = new FormData();
    form.append('image', file);
    return client.put<Plant>(`/admin/catalog/plants/${id}/image-young`, form, { headers: { 'Content-Type': 'multipart/form-data' } }).then((r) => r.data);
  },
  adminUploadPlantImageGrown: (id: number, file: File) => {
    const form = new FormData();
    form.append('image', file);
    return client.put<Plant>(`/admin/catalog/plants/${id}/image-grown`, form, { headers: { 'Content-Type': 'multipart/form-data' } }).then((r) => r.data);
  },
  adminUploadPlantImageHarvested: (id: number, file: File) => {
    const form = new FormData();
    form.append('image', file);
    return client.put<Plant>(`/admin/catalog/plants/${id}/image-harvested`, form, { headers: { 'Content-Type': 'multipart/form-data' } }).then((r) => r.data);
  },
  adminUploadAnimalImage: (id: number, file: File) => {
    const form = new FormData();
    form.append('image', file);
    return client.put<Animal>(`/admin/catalog/animals/${id}/image`, form, { headers: { 'Content-Type': 'multipart/form-data' } }).then((r) => r.data);
  },
  adminUploadAnimalEmptyPenImage: (id: number, file: File) => {
    const form = new FormData();
    form.append('image', file);
    return client.put<Animal>(`/admin/catalog/animals/${id}/image-empty-pen`, form, { headers: { 'Content-Type': 'multipart/form-data' } }).then((r) => r.data);
  },
  adminUploadAnimalPenImage: (id: number, file: File) => {
    const form = new FormData();
    form.append('image', file);
    return client.put<Animal>(`/admin/catalog/animals/${id}/image-pen`, form, { headers: { 'Content-Type': 'multipart/form-data' } }).then((r) => r.data);
  },
  adminUploadAnimalImageHarvested: (id: number, file: File) => {
    const form = new FormData();
    form.append('image', file);
    return client.put<Animal>(`/admin/catalog/animals/${id}/image-harvested`, form, { headers: { 'Content-Type': 'multipart/form-data' } }).then((r) => r.data);
  },
  adminUploadPetImage: (id: number, file: File) => {
    const form = new FormData();
    form.append('image', file);
    return client.put<Pet>(`/admin/catalog/pets/${id}/image`, form, { headers: { 'Content-Type': 'multipart/form-data' } }).then((r) => r.data);
  },
  adminUploadProductionTemplateImage: (id: number, file: File) => {
    const form = new FormData();
    form.append('image', file);
    return client.put<ProductionTemplate>(`/admin/catalog/production-templates/${id}/image`, form, { headers: { 'Content-Type': 'multipart/form-data' } }).then((r) => r.data);
  },
  adminUploadProductImage: (id: number, file: File) => {
    const form = new FormData();
    form.append('image', file);
    return client.put<Product>(`/admin/catalog/products/${id}/image`, form, { headers: { 'Content-Type': 'multipart/form-data' } }).then((r) => r.data);
  },

  // ── Админ: игроки ──
  adminPlayers: () =>
    client.get<Player[]>('/admin/players').then((r) => r.data),
  adminPlayerDetail: (vkId: number) =>
    client.get<PlayerDetail>(`/admin/players/${vkId}`).then((r) => r.data),
  adminPlayerReports: (vkId: number) =>
    client.get<StitchReport[]>(`/admin/players/${vkId}/reports`).then((r) => r.data),
  adminPlayerField: (vkId: number, fieldId: number) =>
    client.get<FieldDetail>(`/admin/players/${vkId}/fields/${fieldId}`).then((r) => r.data),
  adminResetPlotNorm: (vkId: number, plotId: number) =>
    client.post<any>(`/admin/players/${vkId}/plots/${plotId}/reset-norm`).then((r) => r.data),
  adminRestartPlayer: (vkId: number) =>
    client.post<Player>(`/admin/players/${vkId}/restart`).then((r) => r.data),
  adminDeletePlayerPlot: (vkId: number, plotId: number) =>
    client.delete(`/admin/players/${vkId}/plots/${plotId}`).then((r) => r.data),

  // ── Админ: заказы ──
  adminOrders: (userId?: number) =>
    client.get<AdminOrder[]>('/admin/orders', { params: userId !== undefined ? { user_id: userId } : {} }).then((r) => r.data),
  adminGenerateOrder: (productId: number, qty?: number, customer?: string | null, customerPhrase?: string | null) =>
    client.post<AdminOrder>('/admin/orders/generate', { product_id: productId, qty, customer, customer_phrase: customerPhrase }).then((r) => r.data),
  adminUpdateOrder: (orderId: number, data: Partial<Pick<AdminOrder, 'product_id' | 'qty' | 'reward_coins' | 'customer' | 'customer_phrase' | 'status' | 'name'>>) =>
    client.put<AdminOrder>(`/admin/orders/${orderId}`, data).then((r) => r.data),
  adminCancelOrder: (orderId: number) =>
    client.post<AdminOrder>(`/admin/orders/${orderId}/cancel`).then((r) => r.data),
  adminDeleteOrder: (orderId: number) =>
    client.delete(`/admin/orders/${orderId}`).then((r) => r.data),
  adminUploadOrderImage: async (orderId: number, file: File) => {
    const compressed = await compressImage(file, 1280, 0.85).catch(() => file);
    const form = new FormData();
    form.append('image', compressed);
    return client.put<AdminOrder>(`/admin/orders/${orderId}/image`, form, { headers: { 'Content-Type': 'multipart/form-data' } }).then((r) => r.data);
  },

  // ── Админ: заказчики ──
  adminCustomers: () =>
    client.get<Customer[]>('/admin/customers').then((r) => r.data),
  adminCreateCustomer: (name: string) =>
    client.post<Customer>('/admin/customers', { name }).then((r) => r.data),
  adminUpdateCustomer: (id: number, name: string) =>
    client.put<Customer>(`/admin/customers/${id}`, { name }).then((r) => r.data),
  adminDeleteCustomer: (id: number) =>
    client.delete(`/admin/customers/${id}`).then((r) => r.data),
  adminUploadCustomerImage: async (id: number, image: File) => {
    const compressed = await compressImage(image, 400, 0.85).catch(() => image);
    const form = new FormData();
    form.append('image', compressed);
    return client.put<Customer>(`/admin/customers/${id}/image`, form, { headers: { 'Content-Type': 'multipart/form-data' } }).then((r) => r.data);
  },

  // ── Админ: уровни ──
  adminLevels: () =>
    client.get<LevelGate[]>('/admin/levels').then((r) => r.data),
  adminSetLevel: (level: number, coins_required: number, plots_required: number, unlock_type?: string | null) =>
    client.put<LevelGate>('/admin/levels', null, { params: { level, coins_required, plots_required, unlock_type } }).then((r) => r.data),
  adminUploadLevelImage: (level: number, file: File) => {
    const fd = new FormData();
    fd.append('image', file);
    return client.post<LevelGate>(`/admin/levels/${level}/image`, fd, { headers: { 'Content-Type': 'multipart/form-data' } }).then((r) => r.data);
  },
  adminDeleteLevel: (level: number) =>
    client.delete(`/admin/levels/${level}`).then((r) => r.data),

  // ── Админ: рецепты зелий ──
  adminPotionRecipes: () =>
    client.get<PotionRecipe[]>('/admin/potion-recipes').then((r) => r.data),
  adminCreatePotionRecipe: (data: PotionRecipeCreate) =>
    client.post<PotionRecipe>('/admin/potion-recipes', data).then((r) => r.data),
  adminUploadPotionImage: (id: number, file: File) => {
    const form = new FormData();
    form.append('image', file);
    return client.put<PotionRecipe>(`/admin/potion-recipes/${id}/image`, form, { headers: { 'Content-Type': 'multipart/form-data' } }).then((r) => r.data);
  },
  adminUploadPotionCardImage: (id: number, file: File) => {
    const form = new FormData();
    form.append('image', file);
    return client.put<PotionRecipe>(`/admin/potion-recipes/${id}/card-image`, form, { headers: { 'Content-Type': 'multipart/form-data' } }).then((r) => r.data);
  },
  adminUpdatePotionRecipe: (id: number, data: PotionRecipeCreate) =>
    client.put<PotionRecipe>(`/admin/potion-recipes/${id}`, data).then((r) => r.data),
  adminDeletePotionRecipe: (id: number) =>
    client.delete(`/admin/potion-recipes/${id}`).then((r) => r.data),

  // ── Зелья: игрок ──
  potionRecipes: (level?: string) =>
    client.get<PotionRecipe[]>('/potions/recipes', { params: { level } }).then((r) => r.data),
  createCauldron: (recipeId: number) =>
    client.post<Cauldron>('/potions/cauldrons', { recipe_id: recipeId }).then((r) => r.data),
  getCauldron: (id: number) =>
    client.get<Cauldron>(`/potions/cauldrons/${id}`).then((r) => r.data),
  activeCauldron: () =>
    client.get<Cauldron | null>('/potions/cauldrons/active').then((r) => r.data),
  cauldronSlotWarehouse: (cauldronId: number, slotIndex: number) =>
    client.get<SlotWarehouseItem[]>(`/potions/cauldrons/${cauldronId}/slot/${slotIndex}/warehouse`).then((r) => r.data),
  fillCauldronSlot: (cauldronId: number, slotIndex: number, itemKind: string, itemId: number) =>
    client.post<Cauldron>(`/potions/cauldrons/${cauldronId}/slot/${slotIndex}`, { item_kind: itemKind, item_id: itemId }).then((r) => r.data),
  clearCauldronSlot: (cauldronId: number, slotIndex: number) =>
    client.delete(`/potions/cauldrons/${cauldronId}/slot/${slotIndex}`).then((r) => r.data),
  brewCauldron: (cauldronId: number) =>
    client.post<Cauldron>(`/potions/cauldrons/${cauldronId}/brew`).then((r) => r.data),
  userPotions: () =>
    client.get<UserPotion[]>('/potions').then((r) => r.data),
  potionBonuses: () =>
    client.get<BonusCatalogItem[]>('/potions/bonuses').then((r) => r.data),
  activatePotion: (id: number) =>
    client.post<UserPotion>(`/potions/${id}/activate`).then((r) => r.data),

  // ── Маршруты / уровни ──
  levels: () =>
    client.get<LevelGate[]>('/levels').then((r) => r.data),

  // ── Настройки: фон ──
  getBackground: () => client.get<{ url: string }>('/settings/background').then((r) => r.data),
  setBackground: (url: string) => client.put<{ url: string }>('/settings/background', { url }).then((r) => r.data),

  // ── Скотный двор ──
  animalsAvailable: () => client.get<Animal[]>('/animals').then((r) => r.data),
  barnyardPens: () => client.get<BarnyardPen[]>('/animals/pens').then((r) => r.data),
  barnyardInstall: (slotId: number, animalId: number) =>
    client.post<BarnyardPen>(`/animals/pens/${slotId}/install`, { animal_id: animalId }).then((r) => r.data),
  barnyardInstallOnCell: (cellId: number, animalId: number) =>
    client.post<BarnyardPen>(`/animals/cells/${cellId}/install`, { animal_id: animalId }).then((r) => r.data),
  barnyardInvest: (slotId: number, amount: number) =>
    client.post(`/animals/pens/${slotId}/invest`, { amount }).then((r) => r.data),
  barnyardProduce: (slotId: number) =>
    client.post<BarnyardProduceResult>(`/animals/pens/${slotId}/produce`).then((r) => r.data),

  // ── Карты-локации: игрок ──
  fields: () => client.get<FieldInfo[]>('/fields').then((r) => r.data),
  fieldDetail: (id: number) => client.get<FieldDetail>(`/fields/${id}`).then((r) => r.data),
  plantOnCell: (fieldId: number, col: number, row: number, plantId: number, qty?: number) =>
    client.post<FieldCellDetail>(`/fields/${fieldId}/cells/${col}/${row}/plant`, { plant_id: plantId, qty: qty ?? 1 }).then((r) => r.data),
  harvestCell: (fieldId: number, col: number, row: number) =>
    client.post<FieldCellDetail>(`/fields/${fieldId}/cells/${col}/${row}/harvest`).then((r) => r.data),
  replantCell: (fieldId: number, col: number, row: number, qty: number) =>
    client.post<FieldCellDetail>(`/fields/${fieldId}/cells/${col}/${row}/replant`, { qty }).then((r) => r.data),
  plantOnBed: (fieldId: number, bedId: number, plantId: number, qty?: number) =>
    client.post<PlantBed>(`/fields/${fieldId}/plant-beds/${bedId}/plant`, { plant_id: plantId, qty: qty ?? 1 }).then((r) => r.data),
  harvestBed: (fieldId: number, bedId: number) =>
    client.post<PlantBed>(`/fields/${fieldId}/plant-beds/${bedId}/harvest`).then((r) => r.data),
  replantBed: (fieldId: number, bedId: number, qty: number) =>
    client.post<PlantBed>(`/fields/${fieldId}/plant-beds/${bedId}/replant`, { qty }).then((r) => r.data),
  startTentBuild: (fieldId: number, tentId: number) =>
    client.post<Tent>(`/fields/${fieldId}/tents/${tentId}/start-build`).then((r) => r.data),
  investTentBuild: (fieldId: number, tentId: number, amount: number) =>
    client.post<Tent>(`/fields/${fieldId}/tents/${tentId}/build-invest`, { amount }).then((r) => r.data),
  revealTentNorm: (fieldId: number, tentId: number) =>
    client.post<Tent>(`/fields/${fieldId}/tents/${tentId}/reveal-norm`).then((r) => r.data),

  houseState: (fieldId: number, tentId: number) =>
    client.get<HouseState>(`/fields/${fieldId}/house/${tentId}`).then((r) => r.data),
  houseRequestMaterial: (fieldId: number, tentId: number) =>
    client.post<HouseState>(`/fields/${fieldId}/house/${tentId}/request-material`).then((r) => r.data),
  houseBuild: (fieldId: number, tentId: number) =>
    client.post<HouseState>(`/fields/${fieldId}/house/${tentId}/build`).then((r) => r.data),

  sellSurplus: (itemKind: string, itemId: number, qty: number) =>
    client.post<{ coins_earned: number }>('/farm/sell-surplus', { item_kind: itemKind, item_id: itemId, qty }).then((r) => r.data),

  // ── GameMedia ──
  adminGameMedia: () =>
    client.get<GameMedia[]>('/admin/game-media').then((r) => r.data),
  adminCreateGameMedia: (data: { code: string; kind: string }) =>
    client.post<GameMedia>('/admin/game-media', data).then((r) => r.data),
  adminUpdateGameMedia: (id: number, data: { code?: string; kind?: string }) =>
    client.put<GameMedia>(`/admin/game-media/${id}`, data).then((r) => r.data),
  adminDeleteGameMedia: (id: number) =>
    client.delete(`/admin/game-media/${id}`).then((r) => r.data),
  adminUploadGameMedia: (id: number, file: File) => {
    const form = new FormData();
    form.append('file', file);
    return client.put<GameMedia>(`/admin/game-media/${id}/upload`, form, { headers: { 'Content-Type': 'multipart/form-data' } }).then((r) => r.data);
  },
  gameMedia: () =>
    client.get<GameMedia[]>('/game-media').then((r) => r.data),
  gameMediaByCode: (code: string) =>
    client.get<GameMedia>(`/game-media/${code}`).then((r) => r.data),

  // ── CrystalCard ──
  adminCrystalCards: () =>
    client.get<CrystalCard[]>('/admin/catalog/crystal-cards').then((r) => r.data),
  adminUploadCrystalCardImage: (id: number, file: File) => {
    const form = new FormData();
    form.append('image', file);
    return client.put<CrystalCard>(`/admin/catalog/crystal-cards/${id}/image`, form, { headers: { 'Content-Type': 'multipart/form-data' } }).then((r) => r.data);
  },
  crystalCards: () =>
    client.get<CrystalCard[]>('/crystal-cards').then((r) => r.data),

  // ── Достижения ──
  achievements: () =>
    client.get<Achievement[]>('/achievements').then((r) => r.data),
  adminAchievements: () =>
    client.get<Achievement[]>('/admin/achievements').then((r) => r.data),
  adminAchievementKinds: () =>
    client.get<AchievementKind[]>('/admin/achievements/kinds').then((r) => r.data),
  adminCreateAchievement: (data: { name: string; condition_kind: string; condition_value?: number; production_code?: string | null; image_url?: string | null }) =>
    client.post<Achievement>('/admin/achievements', data).then((r) => r.data),
  adminUpdateAchievement: (id: number, data: { name: string; condition_kind: string; condition_value?: number; production_code?: string | null; image_url?: string | null }) =>
    client.put<Achievement>(`/admin/achievements/${id}`, data).then((r) => r.data),
  adminDeleteAchievement: (id: number) =>
    client.delete(`/admin/achievements/${id}`).then((r) => r.data),
  adminUploadAchievementImage: (id: number, file: File) => {
    const form = new FormData();
    form.append('image', file);
    return client.put<Achievement>(`/admin/achievements/${id}/image`, form, { headers: { 'Content-Type': 'multipart/form-data' } }).then((r) => r.data);
  },

  // ── Логи ──
  adminLogs: (params: LogsQuery = {}) =>
    client.get<LogEntry[]>('/admin/logs', { params }).then((r) => r.data),
  adminClearLogs: () => client.delete('/admin/logs').then((r) => r.data),
  vkLogReport: (payload: { level?: string; event?: string; message?: string; details?: unknown }) =>
    client.post('/logs/vk', payload).then((r) => r.data),
};
