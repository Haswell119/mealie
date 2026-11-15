from datetime import UTC, datetime

from pydantic import UUID4

from mealie.repos.repository_factory import AllRepositories
from mealie.schema.personal.enums import RetailStore, VerificationSource, VerificationStatus
from mealie.schema.personal.pantry import (
    FoodPackagingCreate,
    FoodPackagingOut,
    ProductBase,
    ProductImport,
    ProductImportOut,
    ProductOut,
    ProductSave,
    ProductSearchOut,
)

from .dietary_service import DietaryService
from .errors import PersonalError, PersonalNotFound
from .pantry_service import PantryService
from .product_catalog import OpenFoodFactsClient, ProductCatalogUnavailable

# What an allergen or a label of a product says about a restriction.
ALLERGEN_KEYS: dict[str, list[str]] = {
    "gluten": ["gluten"],
    "milk": ["dairy", "lactose"],
    "eggs": ["egg"],
    "peanuts": ["peanut"],
    "nuts": ["tree_nut"],
    "soybeans": ["soy"],
    "fish": ["fish"],
    "crustaceans": ["shellfish"],
    "molluscs": ["shellfish"],
}
FREE_LABEL_KEYS: dict[str, list[str]] = {
    "no-gluten": ["gluten"],
    "gluten-free": ["gluten"],
    "no-lactose": ["lactose"],
    "lactose-free": ["lactose"],
    "vegetarian": ["meat", "fish", "shellfish"],
    "vegan": ["meat", "fish", "shellfish", "dairy", "lactose", "egg"],
}
STANDARD_UNITS = {"g": "gram", "ml": "milliliter"}


class ProductService:
    """Retail products: search them in the open product database, keep them, link them to a food."""

    def __init__(self, repos: AllRepositories, client: OpenFoodFactsClient | None = None) -> None:
        self.repos = repos
        self.products = repos.pe_products
        self.client = client or OpenFoodFactsClient()
        self.dietary = DietaryService(repos)
        self.pantry = PantryService(repos)

    def search(self, query: str, store: RetailStore | None = None) -> ProductSearchOut:
        query = query.strip()
        if len(query) < 2:
            raise PersonalError("QUERY_TOO_SHORT", "Type at least two characters.")
        # Without a shop, search each of the four shops: an open search also returns products of other chains.
        stores = [store] if store is not None else list(RetailStore)
        products: dict[str, ProductBase] = {}
        answered = False
        for wanted in stores:
            try:
                found = self.client.search(query, wanted)
            except ProductCatalogUnavailable:
                continue
            answered = True
            for product in found:
                products.setdefault(product.barcode, product)

        if not answered:
            return ProductSearchOut(query=query, store=store, available=False)
        return ProductSearchOut(query=query, store=store, products=list(products.values()))

    def get_one(self, product_id: UUID4) -> ProductOut:
        product = self.products.get_one(product_id)
        if product is None:
            raise PersonalNotFound("Product not found.")
        return product

    def delete(self, product_id: UUID4) -> ProductOut:
        product = self.get_one(product_id)
        for repo in (self.repos.pe_food_packagings, self.repos.pe_pantry_items):
            for row in repo.multi_query({"product_id": product_id}):
                repo.update(row.id, {"product_id": None})
        self.products.delete(product_id)
        return product

    def import_product(self, data: ProductImport) -> ProductImportOut:
        """
        Keep a product of the open database and link it to a food.

        The label of the product becomes a hint on the food. A hint never marks a food as verified.
        """
        if data.food_id is not None and self.repos.ingredient_foods.get_one(data.food_id) is None:
            raise PersonalNotFound("Food not found.")

        try:
            found = self.client.lookup(data.barcode.strip())
        except ProductCatalogUnavailable as e:
            raise PersonalError("CATALOG_UNAVAILABLE", "The product database does not answer. Try again later.") from e
        if found is None:
            raise PersonalNotFound("No product with this barcode.")

        product = self._store(found, data.food_id)
        out = ProductImportOut(product=product)

        if data.food_id is not None:
            out.hints = self._record_hints(found, data.food_id)
            if data.create_packaging:
                out.packaging = self._create_packaging(product, data.food_id)
                if out.packaging is None:
                    out.hints.append("NO_PACK_SIZE")
        return out

    def _store(self, found: ProductBase, food_id: UUID4 | None) -> ProductOut:
        save = found.cast(ProductSave, group_id=self.repos.group_id, food_id=food_id, fetched_at=datetime.now(UTC))
        existing = self.products.get_one(found.barcode, "barcode")
        if existing is None:
            return self.products.create(save)
        if food_id is None:
            save.food_id = existing.food_id
        return self.products.update(existing.id, save)

    def _record_hints(self, product: ProductBase, food_id: UUID4) -> list[str]:
        by_key = self.dietary.restrictions_by_key()
        hints: list[str] = []

        def suggest(key: str, status: VerificationStatus, reason: str, hint: str) -> None:
            restriction = by_key.get(key)
            if restriction is None:
                return
            stored = self.dietary.suggest_food_status(
                food_id, restriction.id, status, VerificationSource.PRODUCT_LABEL, reason
            )
            if stored is not None and hint not in hints:
                hints.append(hint)

        label = f"{product.name} ({product.barcode})"
        for allergen in product.allergens:
            for key in ALLERGEN_KEYS.get(allergen, []):
                suggest(key, VerificationStatus.INCOMPATIBLE, f"Allergène déclaré sur {label}", f"CONTAINS:{key}")
        for trace in product.traces:
            for key in ALLERGEN_KEYS.get(trace, []):
                suggest(key, VerificationStatus.UNVERIFIED, f"Traces déclarées sur {label}", f"TRACES:{key}")
        for product_label in product.labels:
            for key in FREE_LABEL_KEYS.get(product_label, []):
                suggest(
                    key,
                    VerificationStatus.UNVERIFIED,
                    f"Étiquette « {product_label} » déclarée sur {label}. À vérifier sur l'emballage.",
                    f"LABEL_CLAIM:{key}",
                )
        return hints

    def _create_packaging(self, product: ProductOut, food_id: UUID4) -> FoodPackagingOut | None:
        if not product.quantity or product.quantity_unit not in STANDARD_UNITS:
            return None

        standard_unit = STANDARD_UNITS[product.quantity_unit]
        unit = next(
            (
                unit
                for unit in self.repos.ingredient_units.get_all()
                if unit.standard_unit == standard_unit and unit.standard_quantity == 1
            ),
            None,
        )
        if unit is None:
            return None

        store = next((s for s in product.stores if s in {store.value for store in RetailStore}), None)
        return self.pantry.create_packaging(
            FoodPackagingCreate(
                food_id=food_id,
                unit_id=unit.id,
                quantity=product.quantity,
                label=" ".join(part for part in [product.brand, product.name, product.quantity_text] if part),
                store=store,
                is_default=True,
                product_id=product.id,
            )
        )
