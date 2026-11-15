/* tslint:disable */
/* eslint-disable */
/**
/* This file was automatically generated from pydantic models by running pydantic2ts.
/* Do not modify it by hand - just update the pydantic models and then re-run the script
*/

export type AiProposalKind = "RECIPE_VARIANT" | "SHOPPING_LIST" | "MENU" | "SUBSTITUTION" | "RECIPE_DRAFT";
export type AiProposalStatus = "PENDING" | "ACCEPTED" | "REJECTED";
export type RestrictionScope = "INDIVIDUAL" | "ENTIRE_MEAL" | "ENTIRE_PREPARATION";
export type RestrictionSeverity = "PREFERENCE" | "MODERATE" | "STRICT";
export type RestrictionKind = "MEDICAL" | "ALLERGY" | "INTOLERANCE" | "ETHICAL" | "PREFERENCE";
export type VerificationStatus = "VERIFIED" | "UNVERIFIED" | "INCOMPATIBLE";
export type FindingCode =
  | "RULE_MATCH"
  | "LABEL_CHECK"
  | "FREE_CLAIM"
  | "NO_DATA"
  | "FREE_TEXT"
  | "STORED"
  | "TOOL_CHECK"
  | "NO_INGREDIENTS"
  | "NO_VARIANT"
  | "MANUAL_ASSIGNMENT"
  | "MISSING_SERVINGS"
  | "RECIPE_NOT_FOUND";
export type VerificationSource = "MANUAL" | "RULE" | "AI_SUGGESTION" | "PRODUCT_LABEL";
export type InspirationKind = "LINK" | "PHOTO" | "NOTE" | "VIDEO" | "IDEA";
export type InspirationStatus = "INSPIRATION" | "DRAFT" | "VALIDATED";
export type MealCourse = "APERITIF" | "STARTER" | "MAIN" | "SIDE" | "DESSERT" | "OTHER";
export type Appetite = "SMALL" | "NORMAL" | "LARGE";
export type MealEventStatus = "DRAFT" | "PLANNED" | "DONE";
export type FoodPreferenceKind = "LIKE" | "DISLIKE";
export type RetailStore = "coop" | "migros" | "aldi" | "lidl";
export type ShoppingPlanSource = "EVENT" | "MEALPLAN" | "RECIPES";
export type ShoppingPlanStatus = "OPEN" | "DONE";
export type ShoppingPlanLineState = "ACTIVE" | "DISMISSED" | "OBSOLETE";

export interface AiProposalOut {
  id: string;
  kind: AiProposalKind;
  status: AiProposalStatus;
  title: string;
  payload: {
    [k: string]: unknown;
  } | null;
  eventId: string | null;
  createdAt: string | null;
  decidedAt: string | null;
  result: {
    [k: string]: unknown;
  } | null;
}
export interface AiProposalSave {
  groupId: string;
  householdId: string;
  kind: AiProposalKind;
  status?: AiProposalStatus;
  title: string;
  payload?: {
    [k: string]: unknown;
  } | null;
  eventId?: string | null;
  createdBy?: string | null;
  decidedAt?: string | null;
  result?: {
    [k: string]: unknown;
  } | null;
}
export interface AppliedConstraintOut {
  restrictionKey: string;
  restrictionName: string;
  scope: RestrictionScope;
  severity: RestrictionSeverity;
  personIds: string[];
  personNames: string[];
  origins: string[];
}
export interface AssistantChatRequest {
  message: string;
  history?: AssistantMessage[];
  eventId?: string | null;
}
export interface AssistantMessage {
  role: string;
  content: string;
}
export interface AssistantChatResponse {
  available: boolean;
  reply: string;
  toolCalls: AssistantToolCall[];
  proposals: AiProposalOut[];
  error: string | null;
}
export interface AssistantToolCall {
  name: string;
  arguments: {
    [k: string]: unknown;
  };
}
export interface AssistantStatus {
  enabled: boolean;
  providerName: string | null;
  model: string | null;
}
export interface ChecklistItemOut {
  code: string;
  restrictionKey: string;
  subject: string;
  detail: string | null;
}
export interface ConstraintSetOut {
  shared: AppliedConstraintOut[];
  individual: PersonConstraintsOut[];
}
export interface PersonConstraintsOut {
  personId: string;
  personName: string;
  constraints: AppliedConstraintOut[];
}
export interface DietaryRestrictionCreate {
  key: string;
  name: string;
  kind?: RestrictionKind;
  description?: string | null;
}
export interface DietaryRestrictionOut {
  id: string;
  groupId: string;
  key: string;
  name: string;
  kind: RestrictionKind;
  description: string | null;
  isSystem: boolean;
}
export interface DietaryRestrictionSave {
  key: string;
  name: string;
  kind?: RestrictionKind;
  description?: string | null;
  groupId: string;
  isSystem?: boolean;
}
export interface FindingOut {
  restrictionKey: string;
  status: VerificationStatus;
  code: FindingCode;
  subject: string;
  kind: string;
  term: string | null;
  detail: string | null;
  foodId: string | null;
  toolId: string | null;
  recipeId: string | null;
  recipeName: string | null;
  personId: string | null;
  personName: string | null;
}
export interface FoodBulkVerify {
  foodIds: string[];
  restrictionId: string;
  status: VerificationStatus;
  reason?: string | null;
}
export interface FoodComplianceOut {
  foodId: string;
  foodName: string;
  statuses: FoodRestrictionEffective[];
}
export interface FoodRestrictionEffective {
  restrictionId: string;
  restrictionKey: string;
  restrictionName: string;
  status: VerificationStatus;
  code: FindingCode | null;
  term: string | null;
  reason: string | null;
  source: VerificationSource | null;
  stored: boolean;
}
export interface FoodPackagingCreate {
  foodId: string;
  unitId?: string | null;
  quantity: number;
  label?: string | null;
  store?: string | null;
  isDefault?: boolean;
  productId?: string | null;
}
export interface FoodPackagingOut {
  id: string;
  foodId: string;
  food: PersonalFoodSummary;
  unitId: string | null;
  unit: PersonalUnitSummary | null;
  quantity: number;
  label: string | null;
  store: string | null;
  isDefault: boolean;
  productId: string | null;
}
export interface PersonalFoodSummary {
  id: string;
  name: string;
  pluralName: string | null;
  labelId: string | null;
}
export interface PersonalUnitSummary {
  id: string;
  name: string;
  pluralName: string | null;
  abbreviation: string | null;
  useAbbreviation: boolean | null;
  standardQuantity: number | null;
  standardUnit: string | null;
}
export interface FoodPackagingSave {
  foodId: string;
  unitId?: string | null;
  quantity: number;
  label?: string | null;
  store?: string | null;
  isDefault?: boolean;
  productId?: string | null;
  groupId: string;
  householdId: string;
}
export interface FoodRestrictionStatusOut {
  id: string;
  foodId: string;
  restrictionId: string;
  restriction: DietaryRestrictionOut;
  status: VerificationStatus;
  source: VerificationSource;
  reason: string | null;
  verifiedBy: string | null;
  verifiedAt: string | null;
}
export interface FoodRestrictionStatusSave {
  groupId: string;
  foodId: string;
  restrictionId: string;
  status: VerificationStatus;
  source: VerificationSource;
  reason?: string | null;
  verifiedBy?: string | null;
  verifiedAt?: string | null;
}
export interface FoodRestrictionStatusUpdate {
  status: VerificationStatus;
  reason?: string | null;
}
export interface InspirationCreate {
  title: string;
  kind?: InspirationKind;
  url?: string | null;
  text?: string | null;
  tags?: string[];
}
export interface InspirationDraft {
  name?: string;
  description?: string | null;
  recipeServings?: number;
  ingredients?: string[];
  instructions?: string[];
  notes?: string | null;
}
export interface InspirationOut {
  id: string;
  groupId: string;
  householdId: string;
  title: string;
  kind: InspirationKind;
  url: string | null;
  text: string | null;
  image: string | null;
  tags: string[];
  status: InspirationStatus;
  draft: InspirationDraft | null;
  recipeId: string | null;
  recipeSlug: string | null;
  createdAt: string | null;
}
export interface InspirationSave {
  title: string;
  kind?: InspirationKind;
  url?: string | null;
  text?: string | null;
  tags?: string[];
  groupId: string;
  householdId: string;
  status?: InspirationStatus;
  draft?: {
    [k: string]: unknown;
  } | null;
  image?: string | null;
  recipeId?: string | null;
}
export interface InspirationUpdate {
  title: string;
  kind?: InspirationKind;
  url?: string | null;
  text?: string | null;
  tags?: string[];
  draft?: InspirationDraft | null;
}
export interface MealEventAnalysisOut {
  eventId: string;
  totalPersons: number;
  totalPortions: number;
  constraints: ConstraintSetOut;
  menu: MenuItemAnalysisOut[];
  status: VerificationStatus;
  blocking: FindingOut[];
  toVerify: FindingOut[];
  checklist: ChecklistItemOut[];
  canPlan: boolean;
}
export interface MenuItemAnalysisOut {
  menuItemId: string;
  course: MealCourse;
  title: string | null;
  constraints: ConstraintSetOut;
  variants: VariantAnalysisOut[];
  unassignedPersonIds: string[];
  unassignedPersonNames: string[];
}
export interface VariantAnalysisOut {
  variantId: string;
  recipeId: string;
  recipeName: string;
  recipeSlug: string;
  recipeServings: number;
  label: string | null;
  status: VerificationStatus;
  statuses: {
    [k: string]: VerificationStatus;
  };
  findings: FindingOut[];
  portions: number;
  scale: number | null;
  personIds: string[];
  personNames: string[];
  error: string | null;
}
export interface MealEventAssignmentOut {
  id: string;
  menuItemId: string;
  personId: string;
  variantId: string;
}
export interface MealEventAssignmentSet {
  menuItemId: string;
  personId: string;
  variantId?: string | null;
}
export interface MealEventCreate {
  name: string;
  startsAt?: string | null;
  location?: string | null;
  cookPersonId?: string | null;
  leftoverPortions?: number;
  notes?: string | null;
}
export interface MealEventGuestCreate {
  personId: string;
  attending?: boolean;
  appetiteOverride?: Appetite | null;
}
export interface MealEventGuestOut {
  id: string;
  personId: string;
  person: PersonSummary;
  attending: boolean;
  appetiteOverride: Appetite | null;
}
export interface PersonSummary {
  id: string;
  displayName: string;
  appetite: Appetite;
  linkedUserId: string | null;
}
export interface MealEventHistoryOut {
  id: string;
  createdAt: string | null;
  userId: string | null;
  action: string;
  detail: string | null;
}
export interface MealEventMenuItemCreate {
  id?: string | null;
  course?: MealCourse;
  title?: string | null;
  variants?: MealEventVariantCreate[];
}
export interface MealEventVariantCreate {
  id?: string | null;
  recipeId: string;
  label?: string | null;
  portionsOverride?: number | null;
}
export interface MealEventMenuItemOut {
  id: string;
  course: MealCourse;
  title: string | null;
  position: number;
  variants: MealEventVariantOut[];
}
export interface MealEventVariantOut {
  id: string;
  menuItemId: string;
  recipeId: string;
  label: string | null;
  position: number;
  portionsOverride: number | null;
}
export interface MealEventOut {
  id: string;
  groupId: string;
  householdId: string;
  name: string;
  startsAt: string | null;
  location: string | null;
  cookPersonId: string | null;
  status: MealEventStatus;
  leftoverPortions: number;
  notes: string | null;
  guests: MealEventGuestOut[];
  menuItems: MealEventMenuItemOut[];
  assignments: MealEventAssignmentOut[];
  overrides: MealEventOverrideOut[];
  history: MealEventHistoryOut[];
}
export interface MealEventOverrideOut {
  id: string;
  personId: string;
  restrictionId: string;
  restriction: DietaryRestrictionOut;
  scope: RestrictionScope;
  reason: string;
  menuItemId: string | null;
  createdBy: string | null;
  createdAt: string | null;
}
export interface MealEventOverrideCreate {
  personId: string;
  restrictionId: string;
  scope: RestrictionScope;
  reason: string;
  menuItemId?: string | null;
}
export interface MealEventSave {
  name: string;
  startsAt?: string | null;
  location?: string | null;
  cookPersonId?: string | null;
  leftoverPortions?: number;
  notes?: string | null;
  groupId: string;
  householdId: string;
  status?: MealEventStatus;
}
export interface MealEventStatusUpdate {
  status: MealEventStatus;
  acknowledgeUnverified?: boolean;
}
export interface MealEventSummary {
  id: string;
  groupId: string;
  householdId: string;
  name: string;
  startsAt: string | null;
  location: string | null;
  cookPersonId: string | null;
  status: MealEventStatus;
  leftoverPortions: number;
  notes: string | null;
  guests: MealEventGuestOut[];
}
export interface PantryAdjust {
  delta: number;
}
export interface PantryItemCreate {
  foodId: string;
  quantity?: number;
  unitId?: string | null;
  confirmedUsable?: boolean;
  expiresOn?: string | null;
  location?: string | null;
  note?: string | null;
  productId?: string | null;
}
export interface PantryItemOut {
  id: string;
  groupId: string;
  householdId: string;
  foodId: string;
  food: PersonalFoodSummary;
  unitId: string | null;
  unit: PersonalUnitSummary | null;
  quantity: number;
  confirmedUsable: boolean;
  confirmedAt: string | null;
  expiresOn: string | null;
  location: string | null;
  note: string | null;
  productId: string | null;
}
export interface PantryItemSave {
  foodId: string;
  quantity?: number;
  unitId?: string | null;
  confirmedUsable?: boolean;
  expiresOn?: string | null;
  location?: string | null;
  note?: string | null;
  productId?: string | null;
  groupId: string;
  householdId: string;
  confirmedAt?: string | null;
}
export interface PantryReceive {
  shoppingListId: string;
  confirmUsable?: boolean;
}
export interface PantryReceiveOut {
  received: number;
  skipped: number;
  items: PantryItemOut[];
}
export interface PersonCreate {
  displayName: string;
  appetite?: Appetite;
  notes?: string | null;
  isMe?: boolean;
  consentGiven?: boolean;
  consentNote?: string | null;
  restrictions?: PersonRestrictionCreate[];
  foodPreferences?: PersonFoodPreferenceCreate[];
}
export interface PersonRestrictionCreate {
  restrictionId: string;
  severity?: RestrictionSeverity;
  defaultScope?: RestrictionScope;
  appliesWhenCooking?: boolean;
  notes?: string | null;
}
export interface PersonFoodPreferenceCreate {
  foodId: string;
  kind: FoodPreferenceKind;
  note?: string | null;
}
export interface PersonFoodPreferenceOut {
  id: string;
  personId: string;
  foodId: string;
  food: PersonalFoodSummary;
  kind: FoodPreferenceKind;
  note: string | null;
}
export interface PersonFoodPreferenceSave {
  foodId: string;
  kind: FoodPreferenceKind;
  note?: string | null;
  groupId: string;
  householdId: string;
  personId: string;
}
export interface PersonOut {
  id: string;
  displayName: string;
  appetite: Appetite;
  linkedUserId: string | null;
  groupId: string;
  householdId: string;
  notes: string | null;
  consentGivenAt: string | null;
  consentNote: string | null;
  restrictions: PersonRestrictionOut[];
  foodPreferences: PersonFoodPreferenceOut[];
  createdAt: string | null;
}
export interface PersonRestrictionOut {
  id: string;
  personId: string;
  restrictionId: string;
  restriction: DietaryRestrictionOut;
  severity: RestrictionSeverity;
  defaultScope: RestrictionScope;
  appliesWhenCooking: boolean;
  notes: string | null;
}
export interface PersonRestrictionSave {
  restrictionId: string;
  severity?: RestrictionSeverity;
  defaultScope?: RestrictionScope;
  appliesWhenCooking?: boolean;
  notes?: string | null;
  groupId: string;
  householdId: string;
  personId: string;
}
export interface PersonSave {
  groupId: string;
  householdId: string;
  displayName: string;
  appetite?: Appetite;
  notes?: string | null;
  linkedUserId?: string | null;
  consentGivenAt?: string | null;
  consentNote?: string | null;
}
export interface PersonalRecipeSummary {
  id: string;
  name: string;
  slug: string;
  recipeServings: number;
  image: string | null;
}
export interface ProductBase {
  barcode: string;
  name: string;
  brand?: string | null;
  stores?: string[];
  quantity?: number | null;
  quantityUnit?: string | null;
  quantityText?: string | null;
  labels?: string[];
  allergens?: string[];
  traces?: string[];
  imageUrl?: string | null;
  source?: string;
  sourceUrl?: string | null;
}
export interface ProductImport {
  barcode: string;
  foodId?: string | null;
  createPackaging?: boolean;
}
export interface ProductImportOut {
  product: ProductOut;
  packaging: FoodPackagingOut | null;
  hints: string[];
}
export interface ProductOut {
  barcode: string;
  name: string;
  brand: string | null;
  stores: string[];
  quantity: number | null;
  quantityUnit: string | null;
  quantityText: string | null;
  labels: string[];
  allergens: string[];
  traces: string[];
  imageUrl: string | null;
  source: string;
  sourceUrl: string | null;
  id: string;
  groupId: string;
  foodId: string | null;
  fetchedAt: string | null;
}
export interface ProductSave {
  barcode: string;
  name: string;
  brand?: string | null;
  stores?: string[];
  quantity?: number | null;
  quantityUnit?: string | null;
  quantityText?: string | null;
  labels?: string[];
  allergens?: string[];
  traces?: string[];
  imageUrl?: string | null;
  source?: string;
  sourceUrl?: string | null;
  groupId: string;
  foodId?: string | null;
  fetchedAt?: string | null;
}
export interface ProductSearchOut {
  query: string;
  store: RetailStore | null;
  available: boolean;
  products: ProductBase[];
}
export interface RecipeComplianceOut {
  recipeId: string;
  recipeName: string;
  recipeSlug: string;
  restrictionKeys: string[];
  status: VerificationStatus;
  statuses: {
    [k: string]: VerificationStatus;
  };
  findings: FindingOut[];
}
export interface ShoppingPlanApply {
  shoppingListId?: string | null;
  restoreDismissed?: boolean;
}
export interface ShoppingPlanApplyOut {
  plan: ShoppingPlanOut;
  shoppingListId: string;
  created: number;
  updated: number;
  deleted: number;
  lines: ShoppingPlanPreviewLine[];
  issues: ShoppingPlanIssue[];
}
export interface ShoppingPlanOut {
  id: string;
  groupId: string;
  householdId: string;
  name: string;
  sourceType: ShoppingPlanSource;
  eventId: string | null;
  dateFrom: string | null;
  dateTo: string | null;
  recipes: ShoppingPlanRecipeEntry[];
  shoppingListId: string | null;
  status: ShoppingPlanStatus;
  useStock: boolean;
  usePackaging: boolean;
  computedAt: string | null;
  createdAt: string | null;
}
export interface ShoppingPlanRecipeEntry {
  recipeId: string;
  scale?: number;
}
export interface ShoppingPlanPreviewLine {
  key: string;
  display: string;
  foodId: string | null;
  foodName: string | null;
  unitId: string | null;
  unitName: string;
  note: string | null;
  quantityNeeded: number;
  quantityFromStock: number;
  quantityToBuy: number;
  packs: number | null;
  packLabel: string | null;
  stockWarnings: string[];
  sources: ShoppingPlanSourceOut[];
  checks: ShoppingPlanCheckOut[];
  action: string;
  itemQuantity: number;
  purchasedQuantity: number;
  state: ShoppingPlanLineState;
}
export interface ShoppingPlanSourceOut {
  recipeId: string | null;
  recipeName: string | null;
  label: string | null;
  scale: number;
  baseQuantity: number;
  unitName: string;
  note: string | null;
}
export interface ShoppingPlanCheckOut {
  restrictionKey: string;
  status: string;
  code: string;
  term: string | null;
  detail: string | null;
}
export interface ShoppingPlanIssue {
  code: string;
  recipeId: string | null;
  recipeName: string | null;
  detail: string | null;
}
export interface ShoppingPlanConsumeOut {
  plan: ShoppingPlanOut;
  consumed: number;
}
export interface ShoppingPlanCreate {
  name: string;
  sourceType: ShoppingPlanSource;
  eventId?: string | null;
  dateFrom?: string | null;
  dateTo?: string | null;
  recipes?: ShoppingPlanRecipeEntry[];
  shoppingListId?: string | null;
  useStock?: boolean;
  usePackaging?: boolean;
}
export interface ShoppingPlanLineOut {
  id: string;
  key: string;
  foodId: string | null;
  unitId: string | null;
  note: string | null;
  display: string;
  quantityNeeded: number;
  quantityFromStock: number;
  quantityToBuy: number;
  packs: number | null;
  packLabel: string | null;
  projectedQuantity: number;
  purchasedQuantity: number;
  shoppingListItemId: string | null;
  state: ShoppingPlanLineState;
  sources: ShoppingPlanSourceOut[];
  checks: ShoppingPlanCheckOut[];
}
export interface ShoppingPlanPreviewOut {
  plan: ShoppingPlanOut;
  lines: ShoppingPlanPreviewLine[];
  issues: ShoppingPlanIssue[];
}
export interface ShoppingPlanSave {
  groupId: string;
  householdId: string;
  name: string;
  sourceType: ShoppingPlanSource;
  eventId?: string | null;
  dateFrom?: string | null;
  dateTo?: string | null;
  recipes?:
    | {
        [k: string]: unknown;
      }[]
    | null;
  shoppingListId?: string | null;
  status?: ShoppingPlanStatus;
  useStock?: boolean;
  usePackaging?: boolean;
  computedAt?: string | null;
}
export interface ToolRestrictionStatusCreate {
  toolId: string;
  restrictionId: string;
  reason?: string | null;
}
export interface ToolRestrictionStatusOut {
  id: string;
  toolId: string;
  restrictionId: string;
  restriction: DietaryRestrictionOut;
  requiresCheck: boolean;
  reason: string | null;
}
export interface ToolRestrictionStatusSave {
  toolId: string;
  restrictionId: string;
  reason?: string | null;
  groupId: string;
  requiresCheck?: boolean;
}
export interface MealieOutModel {}
