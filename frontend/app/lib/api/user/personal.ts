import { BaseAPI, BaseCRUDAPI } from "../base/base-clients";
import type { ApiRequestInstance, PaginationData } from "~/lib/api/types/non-generated";
import type {
  AiProposalOut,
  AssistantChatRequest,
  AssistantChatResponse,
  AssistantStatus,
  DietaryRestrictionCreate,
  DietaryRestrictionOut,
  FoodBulkVerify,
  FoodComplianceOut,
  FoodPackagingCreate,
  FoodPackagingOut,
  FoodRestrictionStatusOut,
  FoodRestrictionStatusUpdate,
  InspirationCreate,
  InspirationOut,
  InspirationUpdate,
  MealEventAnalysisOut,
  MealEventAssignmentSet,
  MealEventCreate,
  MealEventGuestCreate,
  MealEventMenuItemCreate,
  MealEventOut,
  MealEventOverrideCreate,
  MealEventStatusUpdate,
  MealEventSummary,
  PantryItemCreate,
  PantryItemOut,
  PantryReceiveOut,
  PersonCreate,
  PersonOut,
  ProductImport,
  ProductImportOut,
  ProductOut,
  ProductSearchOut,
  RecipeComplianceOut,
  RetailStore,
  ShoppingPlanApply,
  ShoppingPlanApplyOut,
  ShoppingPlanConsumeOut,
  ShoppingPlanCreate,
  ShoppingPlanLineOut,
  ShoppingPlanOut,
  ShoppingPlanPreviewOut,
  ToolRestrictionStatusCreate,
  ToolRestrictionStatusOut,
} from "~/lib/api/types/personal";
import { route } from "~/lib/api/base/route";

const prefix = "/api/households";

export class PersonsApi extends BaseCRUDAPI<PersonCreate, PersonOut> {
  constructor(requests: ApiRequestInstance) {
    super(requests, `${prefix}/persons`, id => `${prefix}/persons/${id}`);
  }
}

export class DietaryApi extends BaseAPI {
  async getRestrictions() {
    return await this.requests.get<DietaryRestrictionOut[]>(`${prefix}/dietary/restrictions`);
  }

  async createRestriction(payload: DietaryRestrictionCreate) {
    return await this.requests.post<DietaryRestrictionOut>(`${prefix}/dietary/restrictions`, payload);
  }

  async updateRestriction(id: string, payload: DietaryRestrictionCreate) {
    return await this.requests.put<DietaryRestrictionOut, DietaryRestrictionCreate>(`${prefix}/dietary/restrictions/${id}`, payload);
  }

  async deleteRestriction(id: string) {
    return await this.requests.delete<DietaryRestrictionOut>(`${prefix}/dietary/restrictions/${id}`);
  }

  async getFood(foodId: string) {
    return await this.requests.get<FoodComplianceOut>(`${prefix}/dietary/foods/${foodId}`);
  }

  async setFoodStatus(foodId: string, restrictionId: string, payload: FoodRestrictionStatusUpdate) {
    return await this.requests.put<FoodRestrictionStatusOut, FoodRestrictionStatusUpdate>(
      `${prefix}/dietary/foods/${foodId}/restrictions/${restrictionId}`,
      payload,
    );
  }

  async clearFoodStatus(foodId: string, restrictionId: string) {
    return await this.requests.delete<null>(`${prefix}/dietary/foods/${foodId}/restrictions/${restrictionId}`);
  }

  async setFoodStatusBulk(payload: FoodBulkVerify) {
    return await this.requests.post<FoodRestrictionStatusOut[]>(`${prefix}/dietary/foods/bulk`, payload);
  }

  async getRecipe(recipeId: string, restrictions: string[] = []) {
    const url = `${prefix}/dietary/recipes/${recipeId}`;
    return await this.requests.get<RecipeComplianceOut>(restrictions.length ? route(url, { restriction: restrictions }) : url);
  }

  async getToolFlags() {
    return await this.requests.get<ToolRestrictionStatusOut[]>(`${prefix}/dietary/tools`);
  }

  async flagTool(payload: ToolRestrictionStatusCreate) {
    return await this.requests.post<ToolRestrictionStatusOut>(`${prefix}/dietary/tools`, payload);
  }

  async unflagTool(id: string) {
    return await this.requests.delete<ToolRestrictionStatusOut>(`${prefix}/dietary/tools/${id}`);
  }
}

export class MealEventsApi extends BaseCRUDAPI<MealEventCreate, MealEventOut, MealEventCreate, MealEventSummary> {
  constructor(requests: ApiRequestInstance) {
    super(requests, `${prefix}/meal-events`, id => `${prefix}/meal-events/${id}`);
  }

  async setGuests(id: string, guests: MealEventGuestCreate[]) {
    return await this.requests.put<MealEventOut, MealEventGuestCreate[]>(`${this.itemRoute(id)}/guests`, guests);
  }

  async setMenu(id: string, menu: MealEventMenuItemCreate[]) {
    return await this.requests.put<MealEventOut, MealEventMenuItemCreate[]>(`${this.itemRoute(id)}/menu`, menu);
  }

  async setAssignment(id: string, payload: MealEventAssignmentSet) {
    return await this.requests.put<MealEventOut, MealEventAssignmentSet>(`${this.itemRoute(id)}/assignments`, payload);
  }

  async addOverride(id: string, payload: MealEventOverrideCreate) {
    return await this.requests.post<MealEventOut>(`${this.itemRoute(id)}/overrides`, payload);
  }

  async deleteOverride(id: string, overrideId: string) {
    return await this.requests.delete<MealEventOut>(`${this.itemRoute(id)}/overrides/${overrideId}`);
  }

  async setStatus(id: string, payload: MealEventStatusUpdate) {
    return await this.requests.put<MealEventOut, MealEventStatusUpdate>(`${this.itemRoute(id)}/status`, payload);
  }

  async getAnalysis(id: string) {
    return await this.requests.get<MealEventAnalysisOut>(`${this.itemRoute(id)}/analysis`);
  }
}

export class ShoppingPlansApi extends BaseCRUDAPI<ShoppingPlanCreate, ShoppingPlanOut> {
  constructor(requests: ApiRequestInstance) {
    super(requests, `${prefix}/shopping-plans`, id => `${prefix}/shopping-plans/${id}`);
  }

  async getLines(id: string) {
    return await this.requests.get<ShoppingPlanLineOut[]>(`${this.itemRoute(id)}/lines`);
  }

  async getPreview(id: string, restoreDismissed = false) {
    return await this.requests.get<ShoppingPlanPreviewOut>(route(`${this.itemRoute(id)}/preview`, { restoreDismissed }));
  }

  async apply(id: string, payload: ShoppingPlanApply = {}) {
    return await this.requests.post<ShoppingPlanApplyOut>(`${this.itemRoute(id)}/apply`, payload);
  }

  async consume(id: string) {
    return await this.requests.post<ShoppingPlanConsumeOut>(`${this.itemRoute(id)}/consume`, {});
  }
}

export class PantryApi extends BaseCRUDAPI<PantryItemCreate, PantryItemOut> {
  constructor(requests: ApiRequestInstance) {
    super(requests, `${prefix}/pantry`, id => `${prefix}/pantry/${id}`);
  }

  async adjust(id: string, delta: number) {
    return await this.requests.post<PantryItemOut>(`${this.itemRoute(id)}/adjust`, { delta });
  }

  async confirm(id: string, usable: boolean) {
    return await this.requests.post<PantryItemOut>(route(`${this.itemRoute(id)}/confirm`, { usable }), {});
  }

  async receive(shoppingListId: string, confirmUsable = true) {
    return await this.requests.post<PantryReceiveOut>(`${prefix}/pantry/receive`, { shoppingListId, confirmUsable });
  }
}

export class PackagingsApi extends BaseCRUDAPI<FoodPackagingCreate, FoodPackagingOut> {
  constructor(requests: ApiRequestInstance) {
    super(requests, `${prefix}/packagings`, id => `${prefix}/packagings/${id}`);
  }
}

export class ProductsApi extends BaseAPI {
  async getAll() {
    return await this.requests.get<PaginationData<ProductOut>>(route(`${prefix}/products`, { page: 1, perPage: -1 }));
  }

  async search(query: string, store?: RetailStore | null) {
    return await this.requests.get<ProductSearchOut>(route(`${prefix}/products/search`, store ? { query, store } : { query }));
  }

  async importProduct(payload: ProductImport) {
    return await this.requests.post<ProductImportOut>(`${prefix}/products/import`, payload);
  }

  async deleteOne(id: string) {
    return await this.requests.delete<ProductOut>(`${prefix}/products/${id}`);
  }
}

export class InspirationsApi extends BaseCRUDAPI<InspirationCreate, InspirationOut, InspirationUpdate> {
  constructor(requests: ApiRequestInstance) {
    super(requests, `${prefix}/inspirations`, id => `${prefix}/inspirations/${id}`);
  }

  async startDraft(id: string) {
    return await this.requests.post<InspirationOut>(`${this.itemRoute(id)}/draft`, {});
  }

  async validate(id: string) {
    return await this.requests.post<InspirationOut>(`${this.itemRoute(id)}/validate`, {});
  }

  async structure(id: string) {
    return await this.requests.post<AiProposalOut>(`${this.itemRoute(id)}/structure`, {});
  }

  async setImage(id: string, file: File) {
    const formData = new FormData();
    formData.append("image", file);
    return await this.requests.put<InspirationOut, FormData>(`${this.itemRoute(id)}/image`, formData);
  }

  async getImage(id: string) {
    return await this.requests.get<Blob>(`${this.itemRoute(id)}/image`, undefined, { responseType: "blob" });
  }
}

export class AssistantApi extends BaseAPI {
  async getStatus() {
    return await this.requests.get<AssistantStatus>(`${prefix}/assistant/status`);
  }

  async chat(payload: AssistantChatRequest) {
    return await this.requests.post<AssistantChatResponse>(`${prefix}/assistant/chat`, payload);
  }

  async getProposals() {
    return await this.requests.get<PaginationData<AiProposalOut>>(
      route(`${prefix}/assistant/proposals`, { page: 1, perPage: 50, orderBy: "created_at", orderDirection: "desc" }),
    );
  }

  async acceptProposal(id: string) {
    return await this.requests.post<AiProposalOut>(`${prefix}/assistant/proposals/${id}/accept`, {});
  }

  async rejectProposal(id: string) {
    return await this.requests.post<AiProposalOut>(`${prefix}/assistant/proposals/${id}/reject`, {});
  }

  async deleteProposal(id: string) {
    return await this.requests.delete<AiProposalOut>(`${prefix}/assistant/proposals/${id}`);
  }
}

/** Every API of the personal edition. */
export class PersonalApi {
  public persons: PersonsApi;
  public dietary: DietaryApi;
  public mealEvents: MealEventsApi;
  public shoppingPlans: ShoppingPlansApi;
  public pantry: PantryApi;
  public packagings: PackagingsApi;
  public products: ProductsApi;
  public inspirations: InspirationsApi;
  public assistant: AssistantApi;

  constructor(requests: ApiRequestInstance) {
    this.persons = new PersonsApi(requests);
    this.dietary = new DietaryApi(requests);
    this.mealEvents = new MealEventsApi(requests);
    this.shoppingPlans = new ShoppingPlansApi(requests);
    this.pantry = new PantryApi(requests);
    this.packagings = new PackagingsApi(requests);
    this.products = new ProductsApi(requests);
    this.inspirations = new InspirationsApi(requests);
    this.assistant = new AssistantApi(requests);
  }
}
