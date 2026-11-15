import pytest
from fastapi.testclient import TestClient

from mealie.services.personal import product_catalog
from mealie.services.personal.product_catalog import (
    OpenFoodFactsClient,
    ProductCatalogUnavailable,
    parse_product,
    parse_quantity,
)
from tests.utils.fixture_schemas import TestUser

from .helpers import BASE, create_food, create_unit, restriction_ids

PRODUCTS = f"{BASE}/products"
INSPIRATIONS = f"{BASE}/inspirations"

GF_BUN = {
    "code": "7610200000017",
    "product_name_fr": "Pains burger sans gluten",
    "brands": "aha!, Migros",
    "quantity": "4 x 75 g",
    "product_quantity": "300",
    "product_quantity_unit": "g",
    "stores_tags": ["migros"],
    "labels_tags": ["en:no-gluten", "en:vegetarian"],
    "allergens_tags": ["en:eggs"],
    "traces_tags": ["en:nuts"],
    "image_front_small_url": "https://images.openfoodfacts.org/x.jpg",
}


@pytest.fixture()
def catalog(monkeypatch: pytest.MonkeyPatch):
    """Replaces the network call of the product database and records what the application asks for."""
    calls: list[tuple[str, dict]] = []
    state = {"fail": False}

    def fake_get(self, path: str, params: dict) -> dict:
        calls.append((path, params))
        if state["fail"]:
            raise ProductCatalogUnavailable()
        if path.startswith("/api/v2/product/"):
            barcode = path.split("/")[-1].removesuffix(".json")
            return {"product": GF_BUN} if barcode == GF_BUN["code"] else {"status": 0}
        return {"products": [GF_BUN, {"code": "", "product_name": "sans code"}, {"code": "123", "product_name": ""}]}

    monkeypatch.setattr(OpenFoodFactsClient, "_get", fake_get)
    return calls, state


def test_product_quantity_parsing():
    assert parse_quantity({"product_quantity": "300", "product_quantity_unit": "g"}) == (300, "g")
    assert parse_quantity({"product_quantity": 1.5, "product_quantity_unit": "kg"}) == (1500, "g")
    assert parse_quantity({"quantity": "75 cl"}) == (750, "ml")
    assert parse_quantity({"quantity": "1,5 l"}) == (1500, "ml")
    assert parse_quantity({"quantity": "6 pièces"}) == (None, None)
    assert parse_product({"code": "1", "product_name": ""}) is None


def test_product_search_is_limited_to_switzerland_and_a_shop(api_client: TestClient, unique_user: TestUser, catalog):
    calls, _ = catalog
    response = api_client.get(
        f"{PRODUCTS}/search", params={"query": "pain burger", "store": "migros"}, headers=unique_user.token
    )
    assert response.status_code == 200, response.text
    body = response.json()

    assert body["available"] is True
    assert [product["barcode"] for product in body["products"]] == [GF_BUN["code"]]
    product = body["products"][0]
    assert (product["quantity"], product["quantityUnit"]) == (300, "g")
    assert product["brand"] == "aha!"
    assert product["labels"] == ["no-gluten", "vegetarian"]
    assert product["stores"] == ["migros"]

    path, params = calls[0]
    assert path == "/cgi/search.pl"
    assert params["tag_0"] == "switzerland"
    assert params["tag_1"] == "migros"
    # the request carries the search text and nothing about the user
    assert params["search_terms"] == "pain burger"
    assert unique_user.email not in str(params) and unique_user.username not in str(params)

    for store in ("coop", "aldi", "lidl"):
        ok = api_client.get(f"{PRODUCTS}/search", params={"query": "pain", "store": store}, headers=unique_user.token)
        assert ok.status_code == 200
    bad = api_client.get(f"{PRODUCTS}/search", params={"query": "pain", "store": "walmart"}, headers=unique_user.token)
    assert bad.status_code == 422


def test_product_search_reports_an_unavailable_database(api_client: TestClient, unique_user: TestUser, catalog):
    _, state = catalog
    state["fail"] = True
    response = api_client.get(f"{PRODUCTS}/search", params={"query": "farine"}, headers=unique_user.token)
    assert response.status_code == 200
    assert response.json() == {"query": "farine", "store": None, "available": False, "products": []}


def test_importing_a_product_creates_a_pack_size_and_hints(api_client: TestClient, unique_user: TestUser, catalog):
    ids = restriction_ids(api_client, unique_user)
    gram = create_unit(unique_user, standard_quantity=1, standard_unit="gram")
    food = create_food(unique_user)

    payload = {"barcode": GF_BUN["code"], "foodId": str(food.id)}
    response = api_client.post(f"{PRODUCTS}/import", json=payload, headers=unique_user.token)
    assert response.status_code == 201, response.text
    body = response.json()

    assert body["product"]["foodId"] == str(food.id)
    assert body["packaging"]["quantity"] == 300
    assert body["packaging"]["unitId"] == str(gram.id)
    assert body["packaging"]["store"] == "migros"
    assert {"LABEL_CLAIM:gluten", "CONTAINS:egg", "TRACES:tree_nut"} <= set(body["hints"])

    statuses = api_client.get(f"{BASE}/dietary/foods/{food.id}", headers=unique_user.token).json()["statuses"]
    by_key = {status["restrictionKey"]: status for status in statuses}

    # a "gluten free" label is a hint to check: the food is not verified
    assert by_key["gluten"]["status"] == "UNVERIFIED"
    assert by_key["gluten"]["source"] == "PRODUCT_LABEL"
    assert by_key["egg"]["status"] == "INCOMPATIBLE"
    assert by_key["tree_nut"]["status"] == "UNVERIFIED"
    assert all(status["status"] != "VERIFIED" for status in statuses)

    # the person decides: a manual verification replaces the hint, and a new import does not undo it
    verified = api_client.put(
        f"{BASE}/dietary/foods/{food.id}/restrictions/{ids['gluten']}",
        json={"status": "VERIFIED", "reason": "étiquette lue le 15.11"},
        headers=unique_user.token,
    )
    assert verified.status_code == 200
    again = api_client.post(f"{PRODUCTS}/import", json=payload, headers=unique_user.token)
    assert again.status_code == 201
    assert again.json()["product"]["id"] == body["product"]["id"]
    statuses = api_client.get(f"{BASE}/dietary/foods/{food.id}", headers=unique_user.token).json()["statuses"]
    assert next(s for s in statuses if s["restrictionKey"] == "gluten")["status"] == "VERIFIED"


def test_import_errors(api_client: TestClient, unique_user: TestUser, catalog):
    _, state = catalog
    missing = api_client.post(f"{PRODUCTS}/import", json={"barcode": "7610200999999"}, headers=unique_user.token)
    assert missing.status_code == 404

    state["fail"] = True
    down = api_client.post(f"{PRODUCTS}/import", json={"barcode": GF_BUN["code"]}, headers=unique_user.token)
    assert down.status_code == 400
    assert down.json()["detail"]["exception"] == "CATALOG_UNAVAILABLE"


def test_catalog_client_turns_any_network_failure_into_unavailable(monkeypatch: pytest.MonkeyPatch):
    class Boom:
        def __init__(self, *args, **kwargs):
            raise RuntimeError("no network")

    monkeypatch.setattr(product_catalog.safehttp, "SafeTransport", Boom)
    with pytest.raises(ProductCatalogUnavailable):
        OpenFoodFactsClient().search("farine")
    assert OpenFoodFactsClient().lookup("not-a-barcode") is None


# ----------------------------------------------------------------------------------------------------------------
# Inspirations


def test_inspiration_workflow_to_a_validated_recipe(api_client: TestClient, unique_user: TestUser):
    payload = {
        "title": "Tarte aux poireaux de mamie",
        "kind": "LINK",
        "url": "https://example.com/tarte",
        "text": "Vu sur un blog, à tester",
        "tags": ["automne"],
    }
    created = api_client.post(INSPIRATIONS, json=payload, headers=unique_user.token)
    assert created.status_code == 201, created.text
    inspiration = created.json()
    assert inspiration["status"] == "INSPIRATION"
    assert inspiration["recipeId"] is None

    url = f"{INSPIRATIONS}/{inspiration['id']}"

    # an inspiration is not a recipe: it cannot be validated without a draft
    assert api_client.post(f"{url}/validate", headers=unique_user.token).status_code == 400

    draft = api_client.post(f"{url}/draft", headers=unique_user.token).json()
    assert draft["status"] == "DRAFT"
    assert draft["draft"]["name"] == payload["title"]

    # a draft without servings or ingredients is refused
    refused = api_client.post(f"{url}/validate", headers=unique_user.token)
    assert refused.json()["detail"]["exception"] == "DRAFT_SERVINGS_REQUIRED"

    update = {
        **payload,
        "draft": {
            "name": "Tarte aux poireaux",
            "recipeServings": 6,
            "ingredients": ["3 poireaux", "200 ml crème", "  "],
            "instructions": ["Émincer les poireaux.", "Cuire 35 min à 180 °C."],
        },
    }
    assert api_client.put(url, json=update, headers=unique_user.token).status_code == 200

    validated = api_client.post(f"{url}/validate", headers=unique_user.token)
    assert validated.status_code == 200, validated.text
    body = validated.json()
    assert body["status"] == "VALIDATED"
    assert body["recipeSlug"]

    recipe = api_client.get(f"/api/recipes/{body['recipeSlug']}", headers=unique_user.token).json()
    assert recipe["name"] == "Tarte aux poireaux"
    assert recipe["recipeServings"] == 6
    assert [ingredient["note"] for ingredient in recipe["recipeIngredient"]] == ["3 poireaux", "200 ml crème"]
    assert len(recipe["recipeInstructions"]) == 2
    assert recipe["orgURL"] == "https://example.com/tarte"

    assert api_client.post(f"{url}/validate", headers=unique_user.token).status_code == 400
    assert api_client.put(url, json=payload, headers=unique_user.token).status_code == 400

    # the list gives the link to the recipe too
    listed = api_client.get(INSPIRATIONS, params={"perPage": -1}, headers=unique_user.token).json()["items"]
    assert next(item for item in listed if item["id"] == inspiration["id"])["recipeSlug"] == body["recipeSlug"]


def test_inspiration_kinds_filter_and_scoping(api_client: TestClient, unique_user: TestUser, h2_user: TestUser):
    ids = []
    for kind in ("NOTE", "IDEA", "VIDEO", "PHOTO"):
        response = api_client.post(INSPIRATIONS, json={"title": kind.lower(), "kind": kind}, headers=unique_user.token)
        assert response.status_code == 201, response.text
        ids.append(response.json()["id"])

    bad_url = {"title": "x", "kind": "LINK", "url": "javascript:alert(1)"}
    assert api_client.post(INSPIRATIONS, json=bad_url, headers=unique_user.token).status_code == 422

    listed = api_client.get(
        INSPIRATIONS, params={"perPage": -1, "queryFilter": 'status = "INSPIRATION"'}, headers=unique_user.token
    ).json()["items"]
    assert set(ids) <= {item["id"] for item in listed}

    assert api_client.get(f"{INSPIRATIONS}/{ids[0]}", headers=h2_user.token).status_code == 404
    assert api_client.delete(f"{INSPIRATIONS}/{ids[0]}", headers=h2_user.token).status_code == 404
    assert api_client.delete(f"{INSPIRATIONS}/{ids[0]}", headers=unique_user.token).status_code == 200


def test_inspiration_image(api_client: TestClient, unique_user: TestUser, h2_user: TestUser):
    inspiration = api_client.post(
        INSPIRATIONS, json={"title": "photo du marché", "kind": "PHOTO"}, headers=unique_user.token
    ).json()
    url = f"{INSPIRATIONS}/{inspiration['id']}/image"

    assert api_client.get(url, headers=unique_user.token).status_code == 404

    refused = api_client.put(url, files={"image": ("x.txt", b"hello", "text/plain")}, headers=unique_user.token)
    assert refused.status_code == 400

    png = b"\x89PNG\r\n\x1a\n" + b"0" * 32
    stored = api_client.put(url, files={"image": ("x.png", png, "image/png")}, headers=unique_user.token)
    assert stored.status_code == 200, stored.text
    assert stored.json()["image"] == "image.png"

    fetched = api_client.get(url, headers=unique_user.token)
    assert fetched.status_code == 200
    assert fetched.content == png

    assert api_client.get(url, headers=h2_user.token).status_code == 404
    assert api_client.get(url).status_code == 401
