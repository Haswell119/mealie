"""
Read retail products from Open Food Facts, an open product database.

The request carries only the search text or the barcode. It never carries anything about a person.
"""

import re
from typing import Any

import httpx

from mealie.core.root_logger import get_logger
from mealie.pkgs import safehttp
from mealie.schema.personal.enums import RetailStore
from mealie.schema.personal.pantry import ProductBase

logger = get_logger()

BASE_URL = "https://world.openfoodfacts.org"
# The text search of the main site times out. The search engine of the same project answers at once.
SEARCH_URL = "https://search.openfoodfacts.org"
USER_AGENT = "recipe-manager/1.0"
TIMEOUT_SECONDS = 12
PAGE_SIZE = 24
COUNTRY = "switzerland"
FIELDS = ",".join(
    [
        "code",
        "product_name",
        "product_name_fr",
        "generic_name_fr",
        "brands",
        "quantity",
        "product_quantity",
        "product_quantity_unit",
        "stores",
        "stores_tags",
        "labels_tags",
        "allergens_tags",
        "traces_tags",
        "image_front_small_url",
    ]
)

_QUANTITY_PATTERN = re.compile(r"(\d+(?:[.,]\d+)?)\s*(kg|g|ml|cl|dl|l)\b", re.IGNORECASE)
_UNIT_TO_BASE: dict[str, tuple[str, float]] = {
    "g": ("g", 1),
    "kg": ("g", 1000),
    "ml": ("ml", 1),
    "cl": ("ml", 10),
    "dl": ("ml", 100),
    "l": ("ml", 1000),
}


def _search_text(query: str) -> str:
    """The words of a search without the characters that the query language of the search engine reads."""
    text = re.sub(r"[^\w\s'’.,%-]+", " ", query)
    text = re.sub(r"\b(AND|OR|NOT|TO)\b", lambda match: match.group().lower(), text)
    return " ".join(text.split())


class ProductCatalogUnavailable(Exception):
    """The product database did not answer, or its answer could not be read."""


def _strip_tags(tags: Any) -> list[str]:
    if not isinstance(tags, list):
        return []
    return [str(tag).split(":", 1)[-1] for tag in tags if tag]


def _text_list(value: Any) -> list[str]:
    """A field that one endpoint gives as a list and the other as text with commas."""
    parts = value if isinstance(value, list) else str(value or "").split(",")
    return [str(part).strip() for part in parts if str(part).strip()]


def _stores(product: dict[str, Any]) -> list[str]:
    """The shops of a product, as lower case keys without a duplicate."""
    names = _strip_tags(product.get("stores_tags")) or _text_list(product.get("stores"))
    keys: list[str] = []
    for name in names:
        key = re.sub(r"\s+", "-", name.strip().lower())
        if key and key not in keys:
            keys.append(key)
    return keys


def parse_quantity(product: dict[str, Any]) -> tuple[float | None, str | None]:
    """The size of the pack in grams or milliliters, or nothing when the product does not state it."""
    unit = str(product.get("product_quantity_unit") or "").lower()
    raw = product.get("product_quantity")
    try:
        value = float(raw) if raw not in (None, "") else None
    except TypeError, ValueError:
        value = None

    if value and value > 0 and unit in _UNIT_TO_BASE:
        base_unit, factor = _UNIT_TO_BASE[unit]
        return value * factor, base_unit

    match = _QUANTITY_PATTERN.search(str(product.get("quantity") or ""))
    if match:
        base_unit, factor = _UNIT_TO_BASE[match.group(2).lower()]
        return float(match.group(1).replace(",", ".")) * factor, base_unit

    return None, None


def parse_product(product: dict[str, Any]) -> ProductBase | None:
    barcode = str(product.get("code") or "").strip()
    name = (
        product.get("product_name_fr") or product.get("product_name") or product.get("generic_name_fr") or ""
    ).strip()
    if not barcode or not name:
        return None

    quantity, quantity_unit = parse_quantity(product)
    brands = _text_list(product.get("brands"))
    return ProductBase(
        barcode=barcode,
        name=name,
        brand=brands[0] if brands else None,
        stores=_stores(product),
        quantity=quantity,
        quantity_unit=quantity_unit,
        quantity_text=str(product.get("quantity") or "") or None,
        labels=_strip_tags(product.get("labels_tags")),
        allergens=_strip_tags(product.get("allergens_tags")),
        traces=_strip_tags(product.get("traces_tags")),
        image_url=product.get("image_front_small_url") or None,
        source="openfoodfacts",
        source_url=f"{BASE_URL}/product/{barcode}",
    )


class OpenFoodFactsClient:
    def _get(self, path: str, params: dict[str, Any], base_url: str = BASE_URL) -> dict[str, Any]:
        try:
            transport = safehttp.SafeTransport(timeout=TIMEOUT_SECONDS)
            with httpx.Client(transport=transport, follow_redirects=True) as client:
                response = client.get(
                    f"{base_url}{path}",
                    params=params,
                    timeout=TIMEOUT_SECONDS,
                    headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
                )
            response.raise_for_status()
            data = response.json()
        except Exception as e:
            logger.warning(f"Open Food Facts request failed: {e.__class__.__name__}")
            raise ProductCatalogUnavailable() from e

        if not isinstance(data, dict):
            raise ProductCatalogUnavailable()
        return data

    def search(self, query: str, store: RetailStore | None = None) -> list[ProductBase]:
        """
        Products sold in Switzerland that match a text, in one shop or in any of the shops of the application.

        One request serves every shop: an open search also returns the products of other chains.
        """
        wanted = [store] if store is not None else list(RetailStore)
        shops = " OR ".join(f'"{shop.value}"' for shop in wanted)
        params: dict[str, Any] = {
            "q": f'{_search_text(query)} countries_tags:"en:{COUNTRY}" stores:({shops})',
            "page_size": PAGE_SIZE,
            "langs": "fr,de,it,en",
            "fields": FIELDS,
        }
        data = self._get("/search", params, SEARCH_URL)
        products = [parse_product(product) for product in data.get("hits") or [] if isinstance(product, dict)]
        return [product for product in products if product is not None]

    def lookup(self, barcode: str) -> ProductBase | None:
        if not re.fullmatch(r"\d{6,14}", barcode):
            return None
        data = self._get(f"/api/v2/product/{barcode}.json", {"fields": FIELDS})
        product = data.get("product")
        return parse_product(product) if isinstance(product, dict) else None
