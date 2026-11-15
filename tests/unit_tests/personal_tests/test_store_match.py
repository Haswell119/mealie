from decimal import Decimal

from mealie.services.personal.engine.store_match import (
    CONFIDENT_SCORE,
    MIN_SCORE,
    dear_limit,
    load_families,
    load_made_products,
    load_other_names,
    load_piece_grams,
    load_terms,
    match_score,
    normalize,
    piece_grams,
    rank,
    search_names,
    search_term,
)


def test_normalize_drops_case_accents_and_punctuation():
    assert normalize("  Crème d'Œuf-Kürbis, 500 g ") == "creme d oeuf kurbis 500 g"
    assert normalize("Weißmehl") == "weissmehl"


def test_a_food_takes_the_german_term_of_the_shops():
    assert search_term("lait") == ("Milch", True)
    assert search_term("Œufs") == ("Eier", True)
    assert search_term("Tomates") == ("Tomaten", True)
    assert search_term("honey") == ("Honig", True)

    # the longest name that the list knows wins
    assert search_term("lait de coco") == ("Kokosmilch", True)
    assert search_term("oignon rouge") == ("Zwiebeln rot", True)
    # "pomme de terre nouvelle" is not in the list: the potatoes of the shop are the nearest answer
    assert search_term("pomme de terre nouvelle") == ("Kartoffeln", True)

    # a food that the list does not know keeps its name
    assert search_term("  galette   de  maïs ") == ("galette de maïs", False)


def test_a_food_without_gluten_never_searches_the_ordinary_product():
    assert search_term("pâtes sans gluten") == ("Teigwaren glutenfrei", True)
    # the list has "farine" and no "farine sans gluten": the term gets the word of the shops
    assert search_term("farine sans gluten") == ("Weissmehl glutenfrei", True)
    assert search_term("pain sans gluten") == ("Brot glutenfrei", True)


def test_the_score_reads_german_compound_words():
    whole = match_score("Milch", "M-Classic Milch UHT 1l")
    compound_end = match_score("Milch", "Bio Bergmilch 1l")
    compound_start = match_score("Milch", "Milchschokolade 100g")

    # the last part of a compound says what the thing is; the first part only qualifies
    assert whole == 1
    # ... but "Knoblauch" is not "Lauch": the end of a compound is proposed and not selected
    assert whole > compound_end >= MIN_SCORE
    assert compound_end < CONFIDENT_SCORE
    assert MIN_SCORE <= match_score("Lauch", "Migros Knoblauch") < CONFIDENT_SCORE
    assert compound_start < MIN_SCORE <= compound_end
    assert match_score("Milch", "Spaghetti") == 0

    # a plural or a case ending is the same word
    assert match_score("Zwiebeln", "Zwiebel gelb") == 1
    assert match_score("Karotten", "Karotte Bio") == 1
    assert match_score("Linsen rot", "Natura rote Linsen") == 1
    assert match_score("Speckwürfeli", "M-Budget Speckwürfel") == 1

    # two words of the search are often one word in the shop
    assert match_score("Basmati Reis", "Prix Garantie Fairtrade Basmatireis") == 1
    assert match_score("Risotto Reis", "Risotto-Reis Bio") == 1
    assert match_score("Risotto Reis", "Safran-Risotto") < CONFIDENT_SCORE
    assert match_score("", "Milch") == 0


def test_a_food_that_is_only_an_ingredient_of_the_product_is_not_selected():
    """The names are the answers of the shops to a search for the food."""
    wrong = [
        ("Milch", "Tafelschokolade, Milch-Haselnuss"),
        ("Milch", "REALFORNO Mürbeteigkekse mit Milch und Reismehl"),
        ("Butter", "Original Dänische Butter Cookies"),
        ("Butter", "DELUXE Pastetli mit Butter"),
        ("Butter", "Ministollen, Butter"),
        ("Eier", "Eier Tagliatelle"),
        ("Zwiebeln", "Rösti Toast, Bergkäse-Zwiebeln"),
        ("Knoblauch", "Baguette, Knoblauch"),
        ("Kartoffeln", "M-Classic Kartoffel Gratin"),
        ("Kartoffeln", "FAVORINA Marzipankartoffeln"),
        ("Lauch", "M-Classic Lauch-Speck-Chüechli"),
        ("Zitronen", "Eistee, Zitrone"),
        ("Zitronen", "Zitronen-Säuerungsmittel"),
        ("Äpfel", "Sternberliner, Apfel-Zimt"),
        ("Spinat", "V-Love Spinat Falafel vegan"),
        ("Spinat", "Kartoffeltaschen, Spinat-Mozzarella"),
        ("Quinoa", "Maiswaffeln Quinoa & Amaranth"),
        ("Kichererbsen", "Gemüse Pasta, Fusilli aus Kichererbsen"),
        ("Olivenöl", "Thunfisch in Olivenöl"),
        ("Basmati Reis", "Anna's Best Chicken Tikka Masala mit Basmati Reis"),
        ("Rahm", "Emmi QimiQ Rahm-Basis"),
        # fresh tomatoes are not a can of chopped tomatoes
        ("Tomaten", "M-Budget Tomaten gehackt"),
        ("Tomaten", "Passierte Tomaten"),
        # a search also finds products that are not food
        ("Salbei", "Natural Cosmetics Deo Vapo Limette Salbei vegan"),
        ("Salbei", "Kräuterli Bonbons, Salbei"),
    ]
    for search, product in wrong:
        assert match_score(search, product) < CONFIDENT_SCORE, (search, product)
    # most of them are not proposed at all
    assert sum(match_score(search, product) < MIN_SCORE for search, product in wrong) >= len(wrong) - 3

    right = [
        ("Milch", "BIO-Milch"),
        ("Milch", "Naturaplan Bio Milch UHT 2,7% Milchfett 6x1l"),
        ("Butter", "Floralp Butter Mödeli"),
        ("Honig", "Wald-Honig in der Spenderflasche"),
        ("Eier", "Naturafarm Eier aus Freilandhaltung 53g+ 10 Stück"),
        ("Lachsfilet", "Prix Garantie Lachsfilet ASC mit Haut 2x140g"),
        ("Speisesalz", "JuraSel Speisesalz mit Jod & Fluor"),
        ("Champignons", "Champignons, geschnitten"),
        ("Gruyère", "Le Gruyère AOP, mild"),
        ("Spinat", "Betty Bossi Jung-Spinat"),
        # the word of the search is the product: it is not "made from" itself
        ("Tomaten gehackt", "Tomaten Bio, gehackt mit Tomatensaft"),
        ("Tomaten gehackt", "Gehackte Tomaten, Basilikum"),
        ("Zartbitterschokolade", "Frey Zartbitterschokolade 72%"),
        # the variety says more about the food
        ("Linsen rot", "Linsen Bio, rot"),
        # after a family of products, the variety is the food itself
        ("Linsen rot", "Hülsenfrüchte, Rote Linsen"),
        ("Kichererbsen", "Mini Pack Hülsenfrüchte, Kichererbsen"),
    ]
    for search, product in right:
        assert match_score(search, product) >= CONFIDENT_SCORE, (search, product)


def test_a_search_without_gluten_refuses_the_ordinary_product():
    # the ordinary product is never proposed for a food without gluten
    assert match_score("Haferflocken glutenfrei", "Haferflocken, zart") == 0
    assert match_score("Teigwaren glutenfrei", "Teigwaren Penne") == 0
    assert match_score("Backpulver glutenfrei", "Dr. Oetker Backpulver 5 Stück") == 0
    assert match_score("Tamari glutenfrei", "Zenbu Bio Tamari Soy Sauce") == 0
    # the name of the food says it in French
    assert match_score("pâtes sans gluten", "Pâtes de maïs 500g") == 0
    assert match_score("pâtes sans gluten", "Pâtes de maïs sans gluten 500g") == 1

    # a product without gluten that is another food is not proposed
    assert match_score("Mehlmischung glutenfrei", "Torte, glutenfrei, Daim") == 0
    assert match_score("Tamari glutenfrei", "Walker's Shortbread glutenfrei") == 0

    assert match_score("Tamari glutenfrei", "Kikkoman Tamari Sojasauce glutenfrei, vegan") == 1
    assert match_score("Teigwaren glutenfrei", "Glutenfreie Teigwaren 500g") == 1
    assert match_score("Mehlmischung glutenfrei", "Mehlmischung aha!, hell, glutenfrei") == 1


def test_the_other_names_of_a_food():
    assert search_names("Kokosmilch") == ["Kokosmilch", "Kokosnussmilch"]
    assert search_names("Lachsfilet") == ["Lachsfilet"]
    # the names of a food without gluten stay without gluten
    names = search_names("Teigwaren glutenfrei")
    assert names[0] == "Teigwaren glutenfrei"
    assert "Fusilli glutenfrei" in names and "Fusilli" not in names

    def best(search: str, product: str) -> float:
        return max(match_score(name, product) for name in search_names(search))

    assert best("Kokosmilch", "Thai Kitchen Kokosnussmilch") == 1
    assert best("Naturejoghurt", "M-Budget Joghurt Nature") == 1
    assert best("Tomatenpüree", "Tomatenmark, dreifach konzentriert") == 1
    assert best("Rahm", "Valflora Vollrahm 35% Milchfett, UHT") == 1
    assert best("Milch", "Valflora Milch Drink 1.5% Fett, UHT") == 1
    assert best("Butternut Kürbis", "Kürbis Butternuss 1 Stück") == 1
    assert best("Butternut Kürbis", "Hipp Butternuss Kürbisbrei Bio, nach 4 Monaten") < CONFIDENT_SCORE
    # the shops name the pasta without gluten by its shape
    assert best("Teigwaren glutenfrei", "Barilla Fusilli glutenfrei") == 1
    assert best("Teigwaren glutenfrei", "Barilla Fusilli") == 0
    assert best("Teigwaren glutenfrei", "Glutenfreie Teigwaren, Penne") == 1
    assert best("Haferflocken glutenfrei", "Naturaplan Bio Haferflöckli glutenfrei") == 1
    assert best("Haferflocken glutenfrei", "Naturaplan Bio Vollkorn Haferflocken") == 0


def test_rank_drops_what_is_off_the_subject_and_keeps_the_order_of_the_shop():
    products = [
        ("Milchschokolade", True),
        ("Kokosnussmilch 400ml", True),
        ("Vollmilch 1l", False),
        ("Milch Drink 1l", True),
        ("Spaghetti", True),
        ("Halbfettmilch 1l", True),
    ]

    ranked = rank(search_names("Milch"), products, limit=5)
    assert [products[entry.index][0] for entry in ranked] == [
        # the same score: a pack that can price the line comes first, then the order of the shop
        "Milch Drink 1l",
        "Halbfettmilch 1l",
        "Vollmilch 1l",
        "Kokosnussmilch 400ml",
    ]
    assert all(entry.score >= MIN_SCORE for entry in ranked)
    assert [entry.confident for entry in ranked] == [True, True, True, False]

    # nothing fits: the person gets no proposal, not a wrong one
    assert rank(["Milch"], [("Spaghetti", True), ("Butter", True)]) == []

    # a product fits when it fits the search text or the name of the food
    assert [entry.index for entry in rank(["Rahm", "crème"], [("Crème entière 25cl", True)])] == [0]


def test_a_cost_far_above_the_others_is_out_of_line():
    # a pack of six bottles against single bottles
    assert dear_limit([1.4, 1.55, 9.9]) == 4.65
    assert dear_limit([2.0, 12.0, 1.9, 8.95, 2.3, 1.5, 1.89]) == 6.0
    # too few costs to compare
    assert dear_limit([1.4, 9.9]) is None
    assert dear_limit([]) is None


def test_the_usual_weight_of_a_piece():
    assert piece_grams("oignon") == Decimal("150")
    assert piece_grams("Œufs") == Decimal("60")
    assert piece_grams("lait") is None
    assert piece_grams(None) is None


def test_the_lists_are_complete():
    terms = load_terms()
    assert len(terms) > 200
    assert all(name and term.strip() for name, term in terms.items())
    weights = load_piece_grams()
    assert all(grams > 0 for grams in weights.values())
    # every usual weight belongs to a food that the shops can be searched for
    assert set(weights) <= set(terms)

    # every other name belongs to a search text of the list
    searched = {normalize(term).replace(" glutenfrei", "") for term in terms.values()}
    others = load_other_names()
    assert others and set(others) <= searched
    assert all(names and all(name.strip() for name in names) for names in others.values())
    assert len(load_made_products()) > 50 and all(load_made_products())
    assert load_families() and all(load_families())
