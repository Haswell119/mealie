"""
Read the prices of Swiss shops from an optional price service.

The application does not hold the code that reads the shops. A separate service does (see
`deploy/nas/price-bridge`), and the application calls it over HTTP when `PE_PRICE_SOURCE_URL` names it.
Without that service, prices typed by hand still give a budget.

A request carries the search text and the names of the shops. It never carries anything about a person.
"""

import os
from datetime import date, datetime
from typing import Any

import httpx

from mealie.core.root_logger import get_logger
from mealie.schema.personal.enums import PriceSizeUnit, RetailStore
from mealie.schema.personal.price import PriceOffer

logger = get_logger()

ENV_URL = "PE_PRICE_SOURCE_URL"
SOURCE_NAME = "swissgroceries"
TIMEOUT_SECONDS = 25
SEARCH_LIMIT = 8
_SIZE_UNITS = {unit.value for unit in PriceSizeUnit}


class PriceSourceUnavailable(Exception):
    """No price service is configured, or it did not answer."""


def _number(value: Any) -> float | None:
    try:
        number = float(value)
    except TypeError, ValueError:
        return None
    return number if number > 0 else None


def _day(value: Any) -> date | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).date()
    except ValueError:
        return None


def _mapping(value: Any) -> dict[str, Any]:
    """The value when it is an object, or else an empty object: a field of the service may be absent or null."""
    return value if isinstance(value, dict) else {}


def parse_offer(product: Any) -> PriceOffer | None:
    """Read one product of the price service. Return None when it has no name or no price."""
    if not isinstance(product, dict):
        return None
    price = _mapping(product.get("price"))
    current = _number(price.get("current"))
    name = str(product.get("name") or product.get("productName") or "").strip()
    external_id = str(product.get("id") or product.get("productId") or "").strip()
    store = str(product.get("chain") or "").strip().lower()
    if current is None or not name or not external_id or not store:
        return None

    size = _mapping(product.get("size"))
    size_unit = str(size.get("unit") or "").lower()
    size_value = _number(size.get("value")) if size_unit in _SIZE_UNITS else None

    unit_price = _mapping(product.get("unitPrice"))
    promotion = _mapping(product.get("promotion"))
    regular = _number(price.get("regular"))

    return PriceOffer(
        store=store,
        external_id=external_id,
        name=name,
        brand=str(product.get("brand") or "").strip() or None,
        price=current,
        regular_price=regular if regular and regular > current else None,
        size=size_value,
        size_unit=PriceSizeUnit(size_unit) if size_value is not None else None,
        unit_price=_number(unit_price.get("value")),
        unit_price_per=str(unit_price.get("per") or "") or None,
        tags=[str(tag) for tag in product.get("tags") or [] if isinstance(tag, str)],
        image_url=_http_url(product.get("imageUrl")),
        product_url=_http_url(product.get("productUrl")),
        promotion=str(promotion.get("description") or product.get("description") or "").strip() or None,
        promotion_ends_on=_day(promotion.get("endsAt") or product.get("validUntil")),
    )


def _http_url(value: Any) -> str | None:
    url = str(value or "").strip()
    return url if url.lower().startswith(("http://", "https://")) else None


class PriceSource:
    """The client of the price service."""

    name = SOURCE_NAME

    def __init__(self, base_url: str | None = None) -> None:
        self.base_url = (base_url if base_url is not None else os.environ.get(ENV_URL, "")).strip().rstrip("/")

    @property
    def enabled(self) -> bool:
        return self.base_url.lower().startswith(("http://", "https://"))

    def _call(self, tool: str, arguments: dict[str, Any]) -> Any:
        if not self.enabled:
            raise PriceSourceUnavailable()
        try:
            # The address comes from the configuration of the server, never from a request: it may be private.
            with httpx.Client(timeout=TIMEOUT_SECONDS) as client:
                response = client.post(f"{self.base_url}/tools/{tool}", json=arguments)
            response.raise_for_status()
            data = response.json()
        except Exception as e:
            logger.warning(f"Price source request failed: {e.__class__.__name__}")
            raise PriceSourceUnavailable() from e

        if not isinstance(data, dict):
            raise PriceSourceUnavailable()
        if data.get("ok"):
            return data.get("result")
        if data.get("error") == "not_found":
            return None
        raise PriceSourceUnavailable()

    def search(
        self, query: str, stores: list[RetailStore], limit: int = SEARCH_LIMIT
    ) -> tuple[list[PriceOffer], list[str]]:
        """The offers that match a text in the given shops, and the shops that did not answer."""
        wanted = [store.value for store in stores]
        result = self._call("search_products", {"query": query, "chains": wanted, "limit": limit})
        if not isinstance(result, dict):
            raise PriceSourceUnavailable()

        by_chain = _mapping(result.get("byChain"))
        offers: list[PriceOffer] = []
        for chain in wanted:
            for product in by_chain.get(chain) or []:
                offer = parse_offer(product)
                if offer is not None and offer.store == chain:
                    offers.append(offer)

        failed = [
            str(error.get("chain"))
            for error in result.get("errors") or []
            if isinstance(error, dict) and error.get("chain") in wanted
        ]
        return offers, failed

    def product(self, store: str, external_id: str) -> PriceOffer | None:
        """One product by its id in a shop, with its price of today. None when the shop no longer lists it."""
        result = self._call("get_product", {"chain": store, "id": external_id})
        if not isinstance(result, dict):
            return None
        return parse_offer(result.get("product"))
