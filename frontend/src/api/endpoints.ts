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
  unlocked: boolean;
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
  item_id: number | null;
  item_name: string | null;
  item_emoji: string | null;
  item_image: string | null;
}

export interface Cauldron {
  id: number;
  recipe_id: number;
  recipe_name: string;
  field_id?: number | null;
  field_name?: string | null;
  material: string;
  capacity: number;
  status: string;
  slots: CauldronSlot[];
  image_url: string | null;
  created_at?: string | null;
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
  animal_product_norm: number;
  study_norms: LevelNorms;
  production_norms: LevelNorms;
}

export interface StorySlide {
  id: number;
  image_url: string | null;
  text: string | null;
  sort_order: number;
  location_code?: string | null;
}

export interface DlcStory {
  slides: StorySlide[];
  seen: boolean;
}

export interface DlcLocation {
  code: string;
  name: string;
}

export interface Lesson {
  id: number;
  title: string;
  description: string | null;
  video_url: string | null;
  image_url: string | null;
  sort_order: number;
  category: string;
}

export const LESSON_CATEGORIES: { code: string; label: string }[] = [
  { code: 'farm', label: '🌾 Ферма' },
  { code: 'brewery', label: '🧪 Зельеварение' },
  { code: 'infirmary', label: '🌲 Лесная лечебница' },
];

export function lessonCategoryLabel(code: string): string {
  return LESSON_CATEGORIES.find((c) => c.code === code)?.label ?? code;
}

export interface PlayerSearchItem {
  vk_id: number;
  display_name: string;
  level: number;
  coins: number;
  crosses_total: number;
}

export interface FarmPlot {
  plant_name: string | null;
  plant_emoji: string | null;
  status: string;
  accumulated: number;
  required: number;
}

export interface FarmProduction {
  kind: string;
  name: string;
  status: string;
  accumulated: number;
  required: number;
}

export interface FarmItem {
  item_id: number;
  name: string;
  emoji: string | null;
  qty: number;
}

export interface FarmPet {
  name: string;
  emoji: string | null;
}

export interface FarmField {
  id: number;
  code: string;
  name: string;
  cols: number;
  rows: number;
  map_url: string | null;
}

export interface PlayerFarm {
  vk_id: number;
  display_name: string;
  level: number;
  coins: number;
  crosses_total: number;
  round: number;
  achievements_total: number;
  fields: FarmField[];
  plots: FarmPlot[];
  productions: FarmProduction[];
  plants: FarmItem[];
  products: FarmItem[];
  ingredients: FarmItem[];
  pets: FarmPet[];
}

export interface TradeItemIn {
  kind: 'plant' | 'product' | 'ingredient';
  item_id: number;
  qty: number;
  direction: 'give' | 'want';
}

export interface TradeOfferItem {
  id: number;
  kind: string;
  item_id: number;
  item_name: string;
  item_emoji: string | null;
  qty: number;
  direction: string;
  reserved?: boolean;
}

export interface TradeOffer {
  id: number;
  from_user_id: number;
  from_name: string;
  to_user_id: number;
  to_name: string;
  status: string;
  message: string | null;
  created_at: string | null;
  accepted_at: string | null;
  items: TradeOfferItem[];
}

export interface ChatMessage {
  id: number;
  from_user_id: number;
  to_user_id: number;
  text: string;
  created_at: string;
  read: boolean;
  kind?: string;
  gift_id?: number | null;
  gift_claimed?: boolean;
  gift_item_emoji?: string | null;
  gift_item_image_url?: string | null;
}

export interface Conversation {
  vk_id: number;
  display_name: string;
  last_message: string;
  last_message_at: string | null;
  unread_count: number;
}

export interface Notification {
  id: number;
  text: string;
  peer_vk_id?: number | null;
  created_at: string;
  read: boolean;
}

export interface Gift {
  id: number;
  from_user_id: number;
  from_name: string;
  to_user_id: number;
  kind: string;
  item_id: number;
  item_name: string;
  item_emoji: string | null;
  item_image_url: string | null;
  qty: number;
  created_at: string | null;
  claimed: boolean;
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
  norm_per_unit: number | null;
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
  sell_price: number | null;
}

export interface Ingredient {
  id: number;
  code: string;
  name: string;
  description: string | null;
  image_url: string | null;
  sort_order: number;
}

export interface ApothecaryItem {
  ingredient_id: number;
  code: string;
  name: string;
  description: string | null;
  image_url: string | null;
  qty: number;
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
  available?: boolean;
  craftable?: boolean;
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

export interface PlayerPlantNorm {
  plant_id: number;
  plant_name: string;
  plant_emoji: string | null;
  norm_per_unit: number;
}

export interface PlayerBarnyardSlot {
  id: number;
  animal_id: number | null;
  animal_name: string | null;
  animal_emoji: string | null;
  status: string;
  accumulated: number;
  required: number;
  cell_id: number | null;
  cell_col: number | null;
  cell_row: number | null;
  is_ghost: boolean;
}

export interface PlayerDetail extends Player {
  plots: Plot[];
  productions: Production[];
  inventory: InventoryItem[];
  plant_norms?: PlayerPlantNorm[];
  dlc_locations?: string[];
  barnyard?: PlayerBarnyardSlot[];
}

export interface AllowedPlayer {
  vk_id: number;
  screen_name: string | null;
  first_name: string;
  last_name: string;
  created_at: string | null;
}

export const LOCATION_TITLES: Record<string, string> = {
  infirmary: '🌲 Лечебница',
  brewery: '🧪 Зельеварение',
};

export interface Player {
  vk_id: number;
  first_name: string;
  last_name: string;
  role: string;
  status: string;
  hidden?: boolean;
  crosses_balance: number;
  crosses_total: number;
  coins: number;
  round: number;
  reports_total: number;
  created_at: string | null;
  trial_until: string | null;
  subscription_until: string | null;
  subscription_dlc_codes: string[];
  is_donor?: boolean;
  donor_exempt?: boolean;
}

export interface StitchReport {
  id: number;
  user_id: number;
  amount: number;
  photo_before_url: string | null;
  photo_after_url: string | null;
  photo_before_thumb_url?: string | null;
  photo_after_thumb_url?: string | null;
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
  product_id: number | null;
  product_code: string;
  product_name: string;
  product_emoji: string | null;
  product_image_url: string | null;
  potion_recipe_id: number | null;
  potion_name: string | null;
  potion_image_url: string | null;
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

export interface AdminOrder extends Order {}

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
  locked_reason?: string | null;
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
  opening_order: number | null;
  image_empty_pen_url: string | null;
  image_pen_url: string | null;
}

export interface PetCell {
  pet_id: number;
  pet_name: string;
  pet_emoji: string | null;
  pet_image_url: string | null;
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
  pet_id?: number | null;
  pet_name?: string | null;
  pet_emoji?: string | null;
  pet_image_url?: string | null;
  bonus_description?: string | null;
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

export interface CocktailItem {
  kind: 'product' | 'plant' | 'ingredient' | 'remedy';
  item_id: number;
  name: string | null;
  emoji: string | null;
  image_url: string | null;
  qty: number;
  have: number;
  enough: boolean;
}

export interface CocktailRecipe {
  id: number;
  code: string;
  name: string;
  description: string | null;
  image_url: string | null;
  card_image_url: string | null;
  patient_id: number | null;
  patient_name: string | null;
  reward_coins: number;
  unlocked: boolean;
  items: CocktailItem[];
}

export interface Shaker {
  id: number;
  cocktail_recipe_id: number | null;
  recipe_name: string | null;
  status: string;
  items: CocktailItem[];
}

export interface BarZone {
  id: number;
  field_id: number;
  zone_kind: 'shaker' | 'book' | 'cocktail_card';
  col1: number;
  row1: number;
  col2: number;
  row2: number;
  image_url: string | null;
  cocktail_recipe_id: number | null;
  cocktail_recipe_name?: string | null;
  recipe_image?: string | null;
  recipe_card_image?: string | null;
}

export interface CocktailItemIn {
  kind: string;
  item_id: number;
  qty: number;
}

export interface CocktailRecipeAdmin {
  id: number;
  code: string;
  name: string;
  description: string | null;
  image_url: string | null;
  card_image_url: string | null;
  patient_id: number | null;
  patient_name: string | null;
  items: { kind: string; item_id: number; name: string | null; emoji: string | null; image_url: string | null; qty: number }[];
}

export interface GatherCell {
  id: number;
  field_id: number;
  col: number;
  row: number;
  window: string;
  ingredient_ids: number[];
  ingredient_names: string[];
}

export interface TradeCell {
  id: number;
  field_id: number;
  col: number;
  row: number;
  ingredient_ids: number[];
  ingredient_names: string[];
}

export interface MeadowCell {
  id: number;
  col: number;
  row: number;
  window: string;
  available: boolean;
  collected_today: boolean;
  next_open_at: string | null;
  countdown_to: string | null;
  ingredients: Ingredient[];
}

export interface Meadow {
  field_id: number;
  name: string;
  map_url: string | null;
  cols: number;
  rows: number;
  now_msk: string;
  cells: MeadowCell[];
}

export interface ShopCell {
  id: number;
  col: number;
  row: number;
  ingredients: Ingredient[];
}

export interface Shop {
  field_id: number;
  name: string;
  map_url: string | null;
  cols: number;
  rows: number;
  cells: ShopCell[];
  apothecary: ApothecaryItem[];
  inventory: InventoryItem[];
}

export interface GatherResult {
  cell_id: number;
  ingredient: Ingredient;
  apothecary_qty: number;
}

export interface BarterGive {
  kind: string;
  id: number;
  name: string;
  emoji: string | null;
}

export interface BarterResult {
  cell_id: number;
  want: Ingredient;
  give: BarterGive;
  qty: number;
  apothecary: ApothecaryItem[];
  inventory: InventoryItem[];
}

// ── Лесная лечебница ──
export interface RemedyRecipeItem {
  ingredient_id: number | null;
  ingredient_name: string | null;
  plant_id: number | null;
  plant_name: string | null;
  qty: number;
}

export interface RemedyRecipeItemHave extends RemedyRecipeItem {
  have: number;
}

export interface Remedy {
  id: number;
  code: string;
  name: string;
  description: string | null;
  image_url: string | null;
  recipe_items: RemedyRecipeItem[];
}

export interface Symptom {
  part_code: string;
  text: string;
}

export const BODY_PARTS: { code: string; label: string }[] = [
  { code: 'nose', label: 'Нос' },
  { code: 'ear', label: 'Ухо' },
  { code: 'eye', label: 'Глаз' },
  { code: 'tail', label: 'Хвост' },
  { code: 'paw', label: 'Лапа' },
  { code: 'belly', label: 'Живот' },
  { code: 'back', label: 'Спина' },
  { code: 'wing', label: 'Крыло' },
  { code: 'head', label: 'Голова' },
  { code: 'throat', label: 'Горло' },
];

export const BODY_PART_LABELS: Record<string, string> = Object.fromEntries(BODY_PARTS.map((p) => [p.code, p.label]));

export interface Disease {
  id: number;
  code: string;
  name: string;
  description: string | null;
  image_url: string | null;
  remedy_id: number | null;
  remedy_name: string | null;
  symptoms: Symptom[];
}

export interface ClinicAnimalType {
  id: number;
  code: string;
  name: string;
  emoji: string | null;
  sort_order: number;
}

export interface PatientScene {
  field_id: number;
  stage: string;
  name: string;
  map_url: string | null;
}

export interface Patient {
  id: number;
  code: string;
  name: string;
  level: number;
  card_image_url: string | null;
  animal_image_url: string | null;
  animal_type_id: number | null;
  animal_type_name: string | null;
  animal_type_emoji: string | null;
  disease_id: number | null;
  disease_name: string | null;
  scenes: PatientScene[];
}

export interface ClinicPartCell {
  id: number;
  field_id: number;
  col: number;
  row: number;
  part_code: string;
}

export interface InfirmaryPatient {
  id: number;
  name: string;
  level: number;
  animal_type_name: string | null;
  animal_type_emoji: string | null;
  animal_image_url: string | null;
  healed: boolean;
  card_earned: boolean;
}

export interface InfirmaryLevel {
  level: number;
  unlocked: boolean;
  patients: InfirmaryPatient[];
}

export interface InfirmaryScene {
  stage: string;
  field_id: number;
  name: string;
  map_url: string | null;
  cols: number;
  rows: number;
}

export interface InfirmaryCurrent {
  id: number;
  name: string;
  level: number;
  animal_type_name: string | null;
  animal_type_emoji: string | null;
  animal_image_url: string | null;
  disease_name: string | null;
  status: string;
  current_field_id: number | null;
  remedy_lab_field_id: number | null;
  card_image_url: string | null;
  scenes: InfirmaryScene[];
}

export interface InfirmaryLocation {
  field_id: number;
  name: string;
  field_kind: string;
  map_url: string | null;
}

export interface Infirmary {
  levels: InfirmaryLevel[];
  current: InfirmaryCurrent | null;
  locations: InfirmaryLocation[];
  memories?: InfirmaryMemory[];
}

export interface InfirmaryMemory {
  patient_id: number;
  name: string;
  level: number;
  healthy_image_url: string | null;
  healed: boolean;
}

export interface InfirmaryPartCell {
  id: number;
  col: number;
  row: number;
  part_code: string;
}

export interface InfirmaryZone {
  id: number;
  zone_kind: 'book';
  col1: number;
  row1: number;
  col2: number;
  row2: number;
}

export interface InfirmaryDetail {
  field_id: number;
  name: string;
  map_url: string | null;
  cols: number;
  rows: number;
  stage: string | null;
  patient_id: number | null;
  patient_name: string | null;
  patient_level: number | null;
  patient_type_name: string | null;
  patient_type_emoji: string | null;
  patient_animal_image_url: string | null;
  status: 'sick' | 'diagnosed' | 'treated' | 'released' | null;
  disease_name: string | null;
  remedy_name: string | null;
  healed: boolean;
  card_earned: boolean;
  penalty_due?: number;
  examined_parts?: string[];
  part_cells: InfirmaryPartCell[];
  infirmary_zones: InfirmaryZone[];
  patient_scenes: InfirmaryScene[];
  remedy_lab_field_id: number | null;
}

export interface HandbookDisease {
  id: number;
  code: string;
  name: string;
  description: string | null;
  image_url: string | null;
  remedy_id: number | null;
  remedy_name: string | null;
  remedy_image_url: string | null;
  symptoms: Symptom[];
}

export interface ExamineResult {
  part_code: string;
  symptoms: string[];
  first_time?: boolean;
  penalty_due?: number;
}

export interface DiagnoseResult {
  correct: boolean;
  crosses_balance: number;
  penalty_due?: number;
  remedy_card_id: number | null;
  remedy_id: number | null;
  remedy_name: string | null;
  remedy_description: string | null;
  remedy_image_url: string | null;
  recipe_items: RemedyRecipeItem[];
}

export interface RemedyCard {
  id: number;
  patient_id: number;
  patient_name: string;
  patient_level: number;
  remedy_id: number;
  remedy_name: string;
  remedy_image_url: string | null;
  recipe_items: RemedyRecipeItemHave[];
}

export interface DeviceRemedy {
  remedy_id: number;
  remedy_name: string;
  remedy_image_url: string | null;
}

export interface DeviceState {
  id: number;
  build_status: string;
  accumulated: number;
  required: number;
  drawn_cards_json: string | null;
  brew_card_id: number | null;
  brew_patient_name: string | null;
  brew_remedy_name: string | null;
  brew_required: number | null;
  brew_accumulated: number;
  brew_dice: number[];
}

export interface DeviceCell {
  id: number;
  col1: number;
  row1: number;
  col2: number;
  row2: number;
  install_cards: number;
  image_url: string | null;
  name: string | null;
  remedies: DeviceRemedy[];
  device: DeviceState | null;
}

export interface RemedyStockItem {
  remedy_id: number;
  remedy_name: string;
  remedy_image_url: string | null;
  qty: number;
}

export interface RemedyLab {
  field_id: number;
  name: string;
  map_url: string | null;
  cols: number;
  rows: number;
  remedy_cards: RemedyCard[];
  apothecary: ApothecaryItem[];
  device_cells?: DeviceCell[];
  remedies_stock?: RemedyStockItem[];
  infirmary_zones?: InfirmaryZone[];
}

export interface InstallDeviceResult {
  device: DeviceState;
  cards: { color: string; value: number; is_treasure: boolean }[];
  required: number;
}

export interface BrewDeviceResult {
  device: DeviceState;
  dice: number[];
  required: number;
  remedy_name: string;
  patient_name: string;
}

export interface GiveRemedyResult {
  patient_id: number;
  patient_name: string;
  status: string;
  remedy_name: string | null;
  otter_granted: boolean;
}

export interface ReleaseResult {
  patient_id: number;
  patient_name: string;
  card_earned: boolean;
}

export interface CollectionCard {
  patient_id: number;
  patient_name: string;
  level: number;
  card_image_url: string | null;
  earned: boolean;
}

export interface CollectionLevel {
  level: number;
  earned_count: number;
  total_count: number;
  cards: CollectionCard[];
}

export interface Collection {
  levels: CollectionLevel[];
}

export interface AdminDeviceCell {
  id: number;
  col1: number;
  row1: number;
  col2: number;
  row2: number;
  install_cards: number;
  image_url: string | null;
  name: string | null;
  remedies: { remedy_id: number; remedy_name: string; remedy_image_url: string | null }[];
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
  gather_cells?: GatherCell[];
  trade_cells?: TradeCell[];
  part_cells?: ClinicPartCell[];
  infirmary_zones?: InfirmaryZone[];
  device_cells?: AdminDeviceCell[];
  potion_recipes?: PotionRecipe[];
  active_cauldron?: Cauldron | null;
  bar_zones?: BarZone[];
  cocktail_recipes?: CocktailRecipe[];
  active_shaker?: Shaker | null;
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
  status: 'empty' | 'placed' | 'building' | 'ready';
  accumulated: number;
  required: number;
  drawn_cards_json: string | null;
  opening_order: number;
  cell_id: number | null;
  image_empty_pen_url: string | null;
  image_pen_url: string | null;
}

export interface BarnyardCollectResult {
  slot_id: number;
  die: number;
  qty_added: number;
  product_id: number;
  product_name: string;
  storage_qty: number;
}

export interface BarnyardStorageItem {
  product_id: number;
  product_name: string;
  product_emoji: string | null;
  product_image_url: string | null;
  qty: number;
  price_per_unit: number | null;
}

export interface BarnyardWithdrawal {
  id: number;
  product_id: number;
  product_name: string;
  product_emoji: string | null;
  qty: number;
  required: number;
  status: string;
  created_at: string | null;
}

export interface BarnyardTentStorage {
  items: BarnyardStorageItem[];
  pending: BarnyardWithdrawal[];
  norm_per_unit: number;
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

export interface ForestActions {
  free_used_today: boolean;
  paid_used_today: boolean;
  sleeping: boolean;
  wake_at: string | null;
  paid_pending: boolean;
  paid_required: number;
  paid_accumulated: number;
  paid_task_id: number | null;
  ingredient_id: number | null;
  ingredient_name: string | null;
  pool: { id: number; name: string }[];
}

export interface UserPetInfo {
  id: number;
  pet_id: number;
  pet_name: string;
  pet_emoji: string | null;
  bonus_description: string | null;
  acquired_at: string | null;
  cell_id: number | null;
  code?: string | null;
  forest?: ForestActions | null;
}

export interface ForestResult {
  pet_id: number;
  ingredient_id: number | null;
  ingredient_name: string | null;
  apothecary_qty: number | null;
  paid: boolean;
  sleeping: boolean;
  wake_at: string | null;
  task_id?: number | null;
  required?: number | null;
  paid_pending?: boolean;
}


export interface PaymentPrice {
  period_days: number;
  base_rub: number;
  dlc: { code: string; name: string; price_rub: number; topup_rub: number | null }[];
  topup_days_left: number | null;
}

export interface SubscriptionOrder {
  order_id: number;
  transaction_id: string;
  payment_url: string;
  amount_kop: number;
  amount_rub: number;
  period_days: number;
  kind: string;
  dlc_codes: string[];
}

export interface PaymentOrderStatus {
  id: number;
  status: string;
  amount_kop: number;
  period_days: number;
  kind: string;
  dlc_codes: string[];
  created_at: string;
}

export interface AdminPaymentOrder {
  id: number;
  vk_id: number;
  amount_kop: number;
  amount_rub: number;
  period_days: number;
  kind: string;
  dlc_codes: string[];
  status: string;
  gateway_txn_id: string | null;
  created_at: string;
  completed_at: string | null;
}

export interface AdminPaymentLog {
  id: number;
  vk_id: number | null;
  order_id: number | null;
  txn_id: string | null;
  action: string;
  detail: string | null;
  created_at: string;
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
  availableOrders: () =>
    client.get<Order[]>('/orders/available').then((r) => r.data),
  takeOrder: (id: number) =>
    client.post<Order>(`/orders/${id}/take`).then((r) => r.data),
  customerNames: () =>
    client.get<string[]>('/orders/customers').then((r) => r.data),
  fulfillOrder: (id: number) => client.post<Order>(`/orders/${id}/fulfill`).then((r) => r.data),
  cancelOrder: (id: number) => client.post<Order>(`/orders/${id}/cancel`).then((r) => r.data),

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

  // ── Доны ──
  adminDonorSync: () =>
    client.post<{ synced: number }>('/admin/players/donor-sync').then((r) => r.data),
  adminSetDonorExempt: (vkId: number, enabled: boolean) =>
    client.post<Player>(`/admin/players/${vkId}/donor-exempt`, { enabled }).then((r) => r.data),

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
    animalProductNorm?: number,
    studyNorms?: { level1: number | null; level2: number | null; level3: number | null },
    productionNorms?: { level1: number | null; level2: number | null; level3: number | null },
  ) =>
    client.put<CrystalNormsMine>('/crystal-norms/mine', {
      norms,
      dice_norm: diceNorm,
      animal_product_norm: animalProductNorm,
      study_norms: studyNorms,
      production_norms: productionNorms,
    }).then((r) => r.data),

  // ── Питомцы ──
  userPets: () => client.get<UserPetInfo[]>('/pets').then(r => r.data),
  petForest: (petId: number, paid: boolean, ingredientId?: number) =>
    client.post<ForestResult>(`/pets/${petId}/forest`, { paid, ingredient_id: ingredientId ?? null }).then(r => r.data),
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
  adminCleanupField: (id: number) =>
    client.post<FieldDetail>(`/admin/fields/${id}/cleanup`).then((r) => r.data),
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
  adminUpdateTent: (fieldId: number, tentId: number, data: { name?: string; kind?: string }) =>
    client.put<Tent>(`/admin/fields/${fieldId}/tents/${tentId}`, data).then((r) => r.data),

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

  adminCreateBarZone: (
    fieldId: number,
    zoneKind: 'shaker' | 'book' | 'cocktail_card',
    rect: { col1: number; row1: number; col2: number; row2: number },
    opts?: { image?: File; cocktailRecipeId?: number },
  ) => {
    const form = new FormData();
    form.append('zone_kind', zoneKind);
    form.append('col1', String(rect.col1));
    form.append('row1', String(rect.row1));
    form.append('col2', String(rect.col2));
    form.append('row2', String(rect.row2));
    if (opts?.image) form.append('image', opts.image);
    if (opts?.cocktailRecipeId != null) form.append('cocktail_recipe_id', String(opts.cocktailRecipeId));
    return client
      .post<BarZone>(`/admin/fields/${fieldId}/bar-zones`, form, { headers: { 'Content-Type': 'multipart/form-data' } })
      .then((r) => r.data);
  },
  adminUploadBarZoneImage: (fieldId: number, zoneId: number, image: File) => {
    const form = new FormData();
    form.append('image', image);
    return client
      .put<BarZone>(`/admin/fields/${fieldId}/bar-zones/${zoneId}/image`, form, { headers: { 'Content-Type': 'multipart/form-data' } })
      .then((r) => r.data);
  },
  adminDeleteBarZone: (fieldId: number, zoneId: number) =>
    client.delete(`/admin/fields/${fieldId}/bar-zones/${zoneId}`).then((r) => r.data),
  adminSetFieldCocktailRecipes: (fieldId: number, recipeIds: number[]) =>
    client.put<number[]>(`/admin/fields/${fieldId}/cocktail-recipes`, { recipe_ids: recipeIds }).then((r) => r.data),

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
  adminSetPlantNorm: (vkId: number, plantId: number, normPerUnit: number) =>
    client.put<any>(`/admin/players/${vkId}/plant-norms/${plantId}`, { norm_per_unit: normPerUnit }).then((r) => r.data),
  adminRestartPlayer: (vkId: number) =>
    client.post<Player>(`/admin/players/${vkId}/restart`).then((r) => r.data),
  adminDeletePlayerPlot: (vkId: number, plotId: number) =>
    client.delete(`/admin/players/${vkId}/plots/${plotId}`).then((r) => r.data),
  adminDeletePlayerBarnyard: (vkId: number, slotId: number) =>
    client.delete(`/admin/players/${vkId}/barnyard/${slotId}`).then((r) => r.data),
  adminGrantDlc: (vkId: number, locationCode: string) =>
    client.post(`/admin/players/${vkId}/dlc`, { location_code: locationCode }).then((r) => r.data),
  adminRevokeDlc: (vkId: number, locationCode: string) =>
    client.delete(`/admin/players/${vkId}/dlc/${locationCode}`).then((r) => r.data),
  adminSetPlayerStatus: (vkId: number, status: string) =>
    client.post<Player>(`/admin/players/${vkId}/status`, { status }).then((r) => r.data),
  adminSetPlayerHidden: (vkId: number, hidden: boolean) =>
    client.post<Player>(`/admin/players/${vkId}/hidden`, { hidden }).then((r) => r.data),
  adminDeletePlayer: (vkId: number) =>
    client.delete(`/admin/players/${vkId}`).then((r) => r.data),

  adminAccessPlayers: () =>
    client.get<AllowedPlayer[]>('/admin/access/players').then((r) => r.data),
  adminAddAccessPlayer: (link: string) =>
    client.post<AllowedPlayer>('/admin/access/players', { link }).then((r) => r.data),
  adminDeleteAccessPlayer: (vkId: number) =>
    client.delete(`/admin/access/players/${vkId}`).then((r) => r.data),

  getLockedLocations: () =>
    client.get<{ codes: string[] }>('/settings/locked-locations').then((r) => r.data),
  setLockedLocations: (codes: string[]) =>
    client.put<{ codes: string[] }>('/admin/settings/locked-locations', { codes }).then((r) => r.data),

  // ── Админ: заказы ──
  adminOrders: () =>
    client.get<AdminOrder[]>('/admin/orders').then((r) => r.data),
  adminGenerateOrder: (productId: number | null, qty?: number, customer?: string | null, customerPhrase?: string | null, potionRecipeId?: number | null) =>
    client.post<AdminOrder>('/admin/orders/generate', {
      product_id: productId,
      potion_recipe_id: potionRecipeId ?? null,
      qty, customer, customer_phrase: customerPhrase,
    }).then((r) => r.data),
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

  // ── Админ: рецепты коктейлей ──
  adminCocktailRecipes: () =>
    client.get<CocktailRecipeAdmin[]>('/admin/cocktail-recipes').then((r) => r.data),
  adminCreateCocktailRecipe: (data: { name: string; description?: string | null; patient_id?: number | null; items: CocktailItemIn[] }) =>
    client.post<CocktailRecipeAdmin>('/admin/cocktail-recipes', data).then((r) => r.data),
  adminUpdateCocktailRecipe: (id: number, data: { name?: string; description?: string | null; patient_id?: number | null; items?: CocktailItemIn[] }) =>
    client.put<CocktailRecipeAdmin>(`/admin/cocktail-recipes/${id}`, data).then((r) => r.data),
  adminDeleteCocktailRecipe: (id: number) =>
    client.delete(`/admin/cocktail-recipes/${id}`).then((r) => r.data),
  adminUploadCocktailImage: (id: number, file: File) => {
    const form = new FormData();
    form.append('image', file);
    return client.put<CocktailRecipeAdmin>(`/admin/cocktail-recipes/${id}/image`, form, { headers: { 'Content-Type': 'multipart/form-data' } }).then((r) => r.data);
  },
  adminUploadCocktailCardImage: (id: number, file: File) => {
    const form = new FormData();
    form.append('image', file);
    return client.put<CocktailRecipeAdmin>(`/admin/cocktail-recipes/${id}/card-image`, form, { headers: { 'Content-Type': 'multipart/form-data' } }).then((r) => r.data);
  },

  // ── Зелья: игрок ──
  potionRecipes: (level?: string) =>
    client.get<PotionRecipe[]>('/potions/recipes', { params: { level } }).then((r) => r.data),
  createCauldron: (recipeId: number, fieldId?: number) =>
    client.post<Cauldron>('/potions/cauldrons', { recipe_id: recipeId, field_id: fieldId ?? null }).then((r) => r.data),
  getCauldron: (id: number) =>
    client.get<Cauldron>(`/potions/cauldrons/${id}`).then((r) => r.data),
  activeCauldrons: () =>
    client.get<Cauldron[]>('/potions/cauldrons/active').then((r) => r.data),
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

  // ── Коктейли: игрок ──
  cocktailRecipes: () =>
    client.get<CocktailRecipe[]>('/cocktails/recipes').then((r) => r.data),
  shaker: () =>
    client.get<Shaker | null>('/cocktails/shaker').then((r) => r.data),
  installShaker: (recipeId: number) =>
    client.post<Shaker>('/cocktails/shaker', { recipe_id: recipeId }).then((r) => r.data),
  mixCocktail: () =>
    client.post<{ id: number; recipe_name: string | null; coins_earned: number; coins_balance: number }>('/cocktails/shaker/mix').then((r) => r.data),

  // ── Маршруты / уровни ──
  levels: () =>
    client.get<LevelGate[]>('/levels').then((r) => r.data),

  // ── Настройки: фон ──
  getBackground: () => client.get<{ url: string }>('/settings/background').then((r) => r.data),
  setBackground: (url: string) => client.put<{ url: string }>('/settings/background', { url }).then((r) => r.data),
  getInfirmaryBackground: () => client.get<{ url: string }>('/settings/infirmary-background').then((r) => r.data),
  adminUploadInfirmaryBackground: (file: File) => {
    const form = new FormData();
    form.append('image', file);
    return client.put<{ url: string }>('/admin/infirmary-background', form, { headers: { 'Content-Type': 'multipart/form-data' } }).then((r) => r.data);
  },

  // ── Скотный двор ──
  animalsAvailable: () => client.get<Animal[]>('/animals').then((r) => r.data),
  barnyardInstallOnCell: (cellId: number, animalId: number) =>
    client.post<BarnyardPen>(`/animals/cells/${cellId}/install`, { animal_id: animalId }).then((r) => r.data),
  barnyardPreparePen: (slotId: number) =>
    client.post<BarnyardPen>(`/animals/pens/${slotId}/prepare`).then((r) => r.data),
  barnyardCollectProduct: (slotId: number) =>
    client.post<BarnyardCollectResult>(`/animals/pens/${slotId}/produce`).then((r) => r.data),
  barnyardReleasePen: (slotId: number) =>
    client.delete(`/animals/pens/${slotId}`).then((r) => r.data),
  barnyardTentStorage: () =>
    client.get<BarnyardTentStorage>('/animals/tents/storage').then((r) => r.data),
  barnyardWithdraw: (productId: number, qty: number) =>
    client.post<BarnyardWithdrawal>('/animals/tents/withdraw', { product_id: productId, qty }).then((r) => r.data),

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
    return client.put<GameMedia>(`/admin/game-media/${id}/upload`, form, { headers: { 'Content-Type': 'multipart/form-data' }, timeout: 0 }).then((r) => r.data);
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
    client.get<LogEntry[]>('/admin/logs', { params: { ...params, _t: Date.now() } }).then((r) => r.data),
  adminClearLogs: () => client.delete('/admin/logs').then((r) => r.data),
  vkLogReport: (payload: { level?: string; event?: string; message?: string; details?: unknown }) =>
    client.post('/logs/vk', payload).then((r) => r.data),

  // ── Аптека: ингредиенты и склад ──
  ingredients: () =>
    client.get<Ingredient[]>('/ingredients').then((r) => r.data),
  apothecary: () =>
    client.get<ApothecaryItem[]>('/apothecary').then((r) => r.data),
  adminIngredients: () =>
    client.get<Ingredient[]>('/admin/ingredients').then((r) => r.data),
  adminCreateIngredient: (data: { name: string; description?: string | null; sort_order?: number }) =>
    client.post<Ingredient>('/admin/ingredients', data).then((r) => r.data),
  adminUpdateIngredient: (id: number, data: { name?: string; description?: string | null; sort_order?: number }) =>
    client.put<Ingredient>(`/admin/ingredients/${id}`, data).then((r) => r.data),
  adminDeleteIngredient: (id: number) =>
    client.delete(`/admin/ingredients/${id}`).then((r) => r.data),
  adminUploadIngredientImage: (id: number, file: File) => {
    const form = new FormData();
    form.append('image', file);
    return client.put<Ingredient>(`/admin/ingredients/${id}/image`, form, { headers: { 'Content-Type': 'multipart/form-data' } }).then((r) => r.data);
  },

  // ── Лесная поляна / городская лавка: игрок ──
  meadow: (fieldId: number) =>
    client.get<Meadow>(`/meadow/${fieldId}`).then((r) => r.data),
  gatherCell: (cellId: number) =>
    client.post<GatherResult>(`/meadow/cells/${cellId}/gather`).then((r) => r.data),
  shop: (fieldId: number) =>
    client.get<Shop>(`/shop/${fieldId}`).then((r) => r.data),
  barterCell: (cellId: number, wantIngredientId: number, giveKind: string, giveItemId: number, qty: number) =>
    client.post<BarterResult>(`/shop/cells/${cellId}/barter`, {
      want_ingredient_id: wantIngredientId,
      give_kind: giveKind,
      give_item_id: giveItemId,
      qty,
    }).then((r) => r.data),

  // ── Админ: клетки поляны и лавки ──
  adminCreateGatherCell: (fieldId: number, data: { col: number; row: number; window: string; ingredient_ids: number[] }) =>
    client.post<GatherCell>(`/admin/fields/${fieldId}/gather-cells`, data).then((r) => r.data),
  adminCreateRemedyDeviceCell: (fieldId: number, data: { col1: number; row1: number; col2: number; row2: number; install_cards: number; remedy_ids: number[]; name?: string | null }) =>
    client.post<AdminDeviceCell>(`/admin/fields/${fieldId}/remedy-device-cells`, data).then((r) => r.data),
  adminUpdateRemedyDeviceCell: (fieldId: number, id: number, data: { install_cards?: number; remedy_ids?: number[]; name?: string | null }) =>
    client.put<AdminDeviceCell>(`/admin/fields/${fieldId}/remedy-device-cells/${id}`, data).then((r) => r.data),
  adminUploadRemedyDeviceImage: (fieldId: number, id: number, image: File) => {
    const form = new FormData();
    form.append('image', image);
    return client.put<AdminDeviceCell>(`/admin/fields/${fieldId}/remedy-device-cells/${id}/image`, form, { headers: { 'Content-Type': 'multipart/form-data' } })
      .then((r) => r.data);
  },
  adminDeleteRemedyDeviceCell: (fieldId: number, id: number) =>
    client.delete(`/admin/fields/${fieldId}/remedy-device-cells/${id}`).then((r) => r.data),
  adminUpdateGatherCell: (fieldId: number, id: number, data: { window?: string; ingredient_ids?: number[] }) =>
    client.put<GatherCell>(`/admin/fields/${fieldId}/gather-cells/${id}`, data).then((r) => r.data),
  adminDeleteGatherCell: (fieldId: number, id: number) =>
    client.delete(`/admin/fields/${fieldId}/gather-cells/${id}`).then((r) => r.data),
  adminCreateTradeCell: (fieldId: number, data: { col: number; row: number; ingredient_ids: number[] }) =>
    client.post<TradeCell>(`/admin/fields/${fieldId}/trade-cells`, data).then((r) => r.data),
  adminUpdateTradeCell: (fieldId: number, id: number, data: { ingredient_ids?: number[] }) =>
    client.put<TradeCell>(`/admin/fields/${fieldId}/trade-cells/${id}`, data).then((r) => r.data),
  adminDeleteTradeCell: (fieldId: number, id: number) =>
    client.delete(`/admin/fields/${fieldId}/trade-cells/${id}`).then((r) => r.data),

  // ── Лесная лечебница: игрок ──
  infirmary: () =>
    client.get<Infirmary>('/infirmary').then((r) => r.data),
  infirmaryDetail: (fieldId: number) =>
    client.get<InfirmaryDetail>(`/infirmary/${fieldId}`).then((r) => r.data),
  handbook: () =>
    client.get<{ diseases: HandbookDisease[] }>('/infirmary/handbook').then((r) => r.data),
  examinePatient: (patientId: number, partCode: string) =>
    client.post<ExamineResult>(`/infirmary/patients/${patientId}/examine`, { part_code: partCode }).then((r) => r.data),
  diagnosePatient: (patientId: number, diseaseId: number) =>
    client.post<DiagnoseResult>(`/infirmary/patients/${patientId}/diagnose`, { disease_id: diseaseId }).then((r) => r.data),
  releasePatient: (patientId: number) =>
    client.post<ReleaseResult>(`/infirmary/patients/${patientId}/release`).then((r) => r.data),
  giveRemedy: (patientId: number) =>
    client.post<GiveRemedyResult>(`/infirmary/patients/${patientId}/give-remedy`).then((r) => r.data),
  remedyLab: (fieldId: number) =>
    client.get<RemedyLab>(`/remedy-lab/${fieldId}`).then((r) => r.data),
  installRemedyDevice: (cellId: number) =>
    client.post<InstallDeviceResult>(`/remedy-lab/cells/${cellId}/install`).then((r) => r.data),
  brewRemedy: (cardId: number, cellId: number) =>
    client.post<BrewDeviceResult>(`/remedy-cards/${cardId}/brew`, { cell_id: cellId }).then((r) => r.data),
  collection: () =>
    client.get<Collection>('/collection').then((r) => r.data),

  // ── Админ: лечебница ──
  adminRemedies: () => client.get<Remedy[]>('/admin/remedies').then((r) => r.data),
  adminCreateRemedy: (data: { name: string; description?: string | null; recipe_items: { ingredient_id: number | null; plant_id: number | null; qty: number }[] }) =>
    client.post<Remedy>('/admin/remedies', data).then((r) => r.data),
  adminUpdateRemedy: (id: number, data: { name?: string; description?: string | null; recipe_items?: { ingredient_id: number | null; plant_id: number | null; qty: number }[] }) =>
    client.put<Remedy>(`/admin/remedies/${id}`, data).then((r) => r.data),
  adminDeleteRemedy: (id: number) =>
    client.delete(`/admin/remedies/${id}`).then((r) => r.data),
  adminUploadRemedyImage: (id: number, file: File) => {
    const form = new FormData();
    form.append('image', file);
    return client.put<Remedy>(`/admin/remedies/${id}/image`, form, { headers: { 'Content-Type': 'multipart/form-data' } }).then((r) => r.data);
  },
  adminDiseases: () => client.get<Disease[]>('/admin/diseases').then((r) => r.data),
  adminCreateDisease: (data: { name: string; description?: string | null; remedy_id?: number | null; symptoms: Symptom[] }) =>
    client.post<Disease>('/admin/diseases', data).then((r) => r.data),
  adminUpdateDisease: (id: number, data: { name?: string; description?: string | null; remedy_id?: number | null; symptoms?: Symptom[] }) =>
    client.put<Disease>(`/admin/diseases/${id}`, data).then((r) => r.data),
  adminDeleteDisease: (id: number) =>
    client.delete(`/admin/diseases/${id}`).then((r) => r.data),
  adminUploadDiseaseImage: (id: number, file: File) => {
    const form = new FormData();
    form.append('image', file);
    return client.put<Disease>(`/admin/diseases/${id}/image`, form, { headers: { 'Content-Type': 'multipart/form-data' } }).then((r) => r.data);
  },
  adminPatients: () => client.get<Patient[]>('/admin/patients').then((r) => r.data),
  adminCreatePatient: (data: { name: string; level: number; disease_id?: number | null; animal_type_id?: number | null }) =>
    client.post<Patient>('/admin/patients', data).then((r) => r.data),
  adminUpdatePatient: (id: number, data: { name?: string; level?: number; disease_id?: number | null; animal_type_id?: number | null }) =>
    client.put<Patient>(`/admin/patients/${id}`, data).then((r) => r.data),
  adminDeletePatient: (id: number) =>
    client.delete(`/admin/patients/${id}`).then((r) => r.data),
  adminUploadPatientCardImage: (id: number, file: File) => {
    const form = new FormData();
    form.append('image', file);
    return client.put<Patient>(`/admin/patients/${id}/card-image`, form, { headers: { 'Content-Type': 'multipart/form-data' } }).then((r) => r.data);
  },
  adminUploadPatientAnimalImage: (id: number, file: File) => {
    const form = new FormData();
    form.append('image', file);
    return client.put<Patient>(`/admin/patients/${id}/animal-image`, form, { headers: { 'Content-Type': 'multipart/form-data' } }).then((r) => r.data);
  },
  adminAnimalTypes: () => client.get<ClinicAnimalType[]>('/admin/clinic-animal-types').then((r) => r.data),
  adminCreateAnimalType: (data: { name: string; emoji?: string | null }) =>
    client.post<ClinicAnimalType>('/admin/clinic-animal-types', data).then((r) => r.data),
  adminUpdateAnimalType: (id: number, data: { name?: string; emoji?: string | null }) =>
    client.put<ClinicAnimalType>(`/admin/clinic-animal-types/${id}`, data).then((r) => r.data),
  adminDeleteAnimalType: (id: number) =>
    client.delete(`/admin/clinic-animal-types/${id}`).then((r) => r.data),
  adminCreatePartCell: (fieldId: number, data: { col: number; row: number; part_code: string }) =>
    client.post<ClinicPartCell>(`/admin/fields/${fieldId}/part-cells`, data).then((r) => r.data),
  adminUpdatePartCell: (fieldId: number, id: number, data: { part_code?: string }) =>
    client.put<ClinicPartCell>(`/admin/fields/${fieldId}/part-cells/${id}`, data).then((r) => r.data),
  adminDeletePartCell: (fieldId: number, id: number) =>
    client.delete(`/admin/fields/${fieldId}/part-cells/${id}`).then((r) => r.data),
  adminCreateInfirmaryZone: (fieldId: number, data: { zone_kind: 'book'; col1: number; row1: number; col2: number; row2: number }) =>
    client.post<InfirmaryZone>(`/admin/fields/${fieldId}/infirmary-zones`, data).then((r) => r.data),
  adminDeleteInfirmaryZone: (fieldId: number, id: number) =>
    client.delete(`/admin/fields/${fieldId}/infirmary-zones/${id}`).then((r) => r.data),

  // ── Предыстория ──
  storySlides: () => client.get<StorySlide[]>('/story/slides').then((r) => r.data),
  markStorySeen: () => client.post<{ ok: boolean }>('/story/seen').then((r) => r.data),
  storyDlc: (code: string) => client.get<DlcStory>(`/story/dlc/${code}`).then((r) => r.data),
  markStoryDlcSeen: (code: string) => client.post<{ ok: boolean }>(`/story/dlc/${code}/seen`).then((r) => r.data),
  adminStorySlides: () => client.get<StorySlide[]>('/admin/story/slides').then((r) => r.data),
  adminDlcLocations: () => client.get<DlcLocation[]>('/admin/story/dlc-locations').then((r) => r.data),
  adminCreateStorySlide: (data: { text?: string | null; sort_order: number; location_code?: string | null }) =>
    client.post<StorySlide>('/admin/story/slides', data).then((r) => r.data),
  adminUpdateStorySlide: (id: number, data: { text?: string | null; sort_order?: number; location_code?: string | null }) =>
    client.put<StorySlide>(`/admin/story/slides/${id}`, data).then((r) => r.data),
  adminUploadStorySlideImage: (id: number, file: File) => {
    const form = new FormData();
    form.append('file', file);
    return client.put<StorySlide>(`/admin/story/slides/${id}/image`, form, { headers: { 'Content-Type': 'multipart/form-data' } }).then((r) => r.data);
  },
  adminDeleteStorySlide: (id: number) =>
    client.delete(`/admin/story/slides/${id}`).then((r) => r.data),

  // ── Видео-уроки ──
  lessons: () => client.get<Lesson[]>('/lessons').then((r) => r.data),
  adminLessons: () => client.get<Lesson[]>('/admin/lessons').then((r) => r.data),
  adminCreateLesson: (data: { title: string; description?: string | null; sort_order: number; category?: string }) =>
    client.post<Lesson>('/admin/lessons', data).then((r) => r.data),
  adminUpdateLesson: (id: number, data: { title?: string; description?: string | null; sort_order?: number; category?: string }) =>
    client.put<Lesson>(`/admin/lessons/${id}`, data).then((r) => r.data),
  adminUploadLessonVideo: (id: number, file: File) => {
    const form = new FormData();
    form.append('file', file);
    return client.put<Lesson>(`/admin/lessons/${id}/video`, form, { headers: { 'Content-Type': 'multipart/form-data' }, timeout: 0 }).then((r) => r.data);
  },
  adminUploadLessonImage: (id: number, file: File) => {
    const form = new FormData();
    form.append('file', file);
    return client.put<Lesson>(`/admin/lessons/${id}/image`, form, { headers: { 'Content-Type': 'multipart/form-data' } }).then((r) => r.data);
  },
  adminDeleteLesson: (id: number) =>
    client.delete(`/admin/lessons/${id}`).then((r) => r.data),

  // ── Чужие фермы (только просмотр) ──
  playerSearch: (q: string, limit?: number) =>
    client.get<PlayerSearchItem[]>('/players/search', { params: { q, limit } }).then((r) => r.data),
  playerFarm: (vkId: number) =>
    client.get<PlayerFarm>(`/players/${vkId}/farm`).then((r) => r.data),
  playerField: (vkId: number, fieldId: number) =>
    client.get<FieldDetail>(`/players/${vkId}/fields/${fieldId}`).then((r) => r.data),

  // ── Бартер ──
  tradeIncoming: () => client.get<TradeOffer[]>('/trades/incoming').then((r) => r.data),
  tradeOutgoing: () => client.get<TradeOffer[]>('/trades/outgoing').then((r) => r.data),
  tradeHistory: () => client.get<TradeOffer[]>('/trades/history').then((r) => r.data),
  createTrade: (data: { to_user_id: number; message?: string | null; items: TradeItemIn[] }) =>
    client.post<TradeOffer>('/trades', data).then((r) => r.data),
  acceptTrade: (id: number) => client.post<TradeOffer>(`/trades/${id}/accept`).then((r) => r.data),
  cancelTrade: (id: number) => client.post<TradeOffer>(`/trades/${id}/cancel`).then((r) => r.data),
  rejectTrade: (id: number) => client.post<TradeOffer>(`/trades/${id}/reject`).then((r) => r.data),

  // ── Чат ──
  chatConversations: () => client.get<Conversation[]>('/chat/conversations').then((r) => r.data),
  chatThread: (vkId: number) => client.get<ChatMessage[]>(`/chat/with/${vkId}`).then((r) => r.data),
  sendChatMessage: (vkId: number, text: string) =>
    client.post<ChatMessage>(`/chat/with/${vkId}`, { text }).then((r) => r.data),

  // ── Уведомления ──
  notifications: () => client.get<Notification[]>('/notifications').then((r) => r.data),
  notificationUnreadCount: () => client.get<{ count: number }>('/notifications/unread-count').then((r) => r.data),
  markNotificationsRead: () => client.post<{ ok: boolean }>('/notifications/read').then((r) => r.data),
  markNotificationRead: (id: number) => client.post<{ ok: boolean }>(`/notifications/${id}/read`).then((r) => r.data),

  // ── Подарки ──
  sendGift: (data: { to_user_id: number; kind: string; item_id: number; qty: number }) =>
    client.post<Gift>('/gifts', data).then((r) => r.data),
  receivedGifts: () => client.get<Gift[]>('/gifts/received').then((r) => r.data),
  giftDetail: (id: number) => client.get<Gift>(`/gifts/${id}`).then((r) => r.data),
  claimGift: (id: number) => client.post<Gift>(`/gifts/${id}/claim`).then((r) => r.data),

  // ── Подписка / оплата ──
  paymentPrice: () => client.get<PaymentPrice>('/payment/price').then((r) => r.data),
  createSubscriptionOrder: (data: { dlc_codes: string[]; receipt_email: string }) =>
    client.post<SubscriptionOrder>('/payment/create-order', data).then((r) => r.data),
  paymentOrderStatus: (orderId: number) =>
    client.get<PaymentOrderStatus>(`/payment/orders/${orderId}`).then((r) => r.data),

  adminPaymentOrders: (statusFilter = '') =>
    client.get<AdminPaymentOrder[]>(`/admin/payment-orders${statusFilter ? `?status_filter=${statusFilter}` : ''}`).then((r) => r.data),
  adminCancelPaymentOrder: (id: number) =>
    client.post<AdminPaymentOrder>(`/admin/payment-orders/${id}/cancel`).then((r) => r.data),
  adminPaymentLogs: () => client.get<AdminPaymentLog[]>('/admin/payment-logs').then((r) => r.data),
  adminExtendTrial: (vkId: number, days: number) =>
    client.post(`/admin/players/${vkId}/trial`, { days }).then((r) => r.data),
  adminSetTrialUntil: (vkId: number, until: string | null) =>
    client.post(`/admin/players/${vkId}/trial-until`, { until }).then((r) => r.data),
  adminSetSubscriptionUntil: (vkId: number, until: string | null) =>
    client.post(`/admin/players/${vkId}/subscription-until`, { until }).then((r) => r.data),
};
