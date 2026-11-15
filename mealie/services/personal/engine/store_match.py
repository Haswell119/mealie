"""
Find the products of a shop that fit a food. Text only: no database, no network.

The Swiss shops name their products in German. A food of the household has a French or an English name, so the
search text comes from a list of terms. A shop answers a search with products that are near the text, and some
are not the food at all: a search for milk also gives milk chocolate and biscuits made with milk. The score says
how well the name of a product fits the search text.
"""

import json
import re
import unicodedata
from dataclasses import dataclass
from decimal import Decimal
from functools import lru_cache
from pathlib import Path

_TERMS_FILE = Path(__file__).parent.parent / "data" / "store_terms.json"

MIN_SCORE = 0.6
"""Below this score a product is off the subject and is not proposed: a biscuit made with butter is not butter."""
CONFIDENT_SCORE = 0.9
"""From this score the product is selected for the person, who can still change it."""

_WHOLE = 1.0
# In a German compound word the last part says what the thing is: "Vollmilch" is milk. But "Knoblauch" is not
# "Lauch": the product is proposed, and the person chooses it.
_COMPOUND_END = 0.8
# The first part only qualifies: "Milchschokolade" is chocolate.
_COMPOUND_START = 0.5
# "Baguette, Knoblauch": after the comma comes the variety of the product, or its flavour.
_VARIETY = 0.7
# "Biscuits mit Milch", "Milchschokolade", "Spinat Falafel": the food is an ingredient of another product.
_INGREDIENT = 0.5
_ENDING = 2
"""A plural or a case adds at most this many letters: "Zwiebel" and "Zwiebeln"."""
_DEAR_FACTOR = 3

_STOP_WORDS = frozenset({"de", "du", "des", "la", "le", "les", "au", "aux", "en", "et", "und", "mit", "the", "of"})
# After one of these words, the name of a product tells what the product is made with.
_MADE_WITH = frozenset({"mit", "aus", "in", "an", "im", "von", "vom", "avec", "con", "with"})
_GLUTEN_FREE = "glutenfrei"
# How a search and a product say "without gluten". The longest first.
_GLUTEN_FREE_MARKS = ("glutenfreie", "glutenfrei", "sans gluten", "gluten free", "senza glutine")

type _Chunk = tuple[str, ...]
"""One written word of a name, as its parts: "Lauch-Speck-Chüechli" has three parts."""


def _fold(text: str) -> str:
    """Lower case and without accents. The punctuation stays."""
    text = text.replace("œ", "oe").replace("Œ", "oe").replace("ß", "ss").replace("'", " ").replace("’", " ")
    text = unicodedata.normalize("NFKD", text)
    return "".join(char for char in text if not unicodedata.combining(char)).lower()


def normalize(text: str) -> str:
    """Lower case, without accents and without punctuation."""
    return re.sub(r"[^a-z0-9]+", " ", _fold(text)).strip()


def _words(text: str) -> list[str]:
    return [word for word in normalize(text).split() if len(word) >= 2 and word not in _STOP_WORDS]


def _singular(text: str) -> str:
    return " ".join(word[:-1] if len(word) > 3 and word[-1] in "sx" else word for word in text.split())


def _longest_known[T](key: str, known: dict[str, T]) -> T | None:
    """The value of the longest leading part of a normalized name that the list knows, singular or plural."""
    words = key.split()
    for size in range(len(words), 0, -1):
        head = " ".join(words[:size])
        for candidate in (head, _singular(head)):
            if candidate in known:
                return known[candidate]
    return None


@lru_cache(maxsize=1)
def _data() -> dict:
    return json.loads(_TERMS_FILE.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def load_terms() -> dict[str, str]:
    """The search text of the shops for the name of a food. The names are normalized."""
    return {normalize(name): term for name, term in _data()["terms"].items()}


@lru_cache(maxsize=1)
def load_other_names() -> dict[str, tuple[str, ...]]:
    """The other names that the shops give to the food of a search text. The search texts are normalized."""
    return {normalize(term): tuple(names) for term, names in _data()["other_names"].items()}


@lru_cache(maxsize=1)
def load_made_products() -> tuple[str, ...]:
    """Words of products that are made from a food: a biscuit, a soup, a juice. Normalized."""
    return tuple(normalize(word) for word in _data()["made_products"])


@lru_cache(maxsize=1)
def load_families() -> tuple[str, ...]:
    """Words that name a family of products ("Hülsenfrüchte, Rote Linsen"). Normalized."""
    return tuple(normalize(word) for word in _data()["families"])


@lru_cache(maxsize=1)
def load_piece_grams() -> dict[str, Decimal]:
    """The usual weight of one piece of a food, in grams. The names are normalized."""
    return {normalize(name): Decimal(str(grams)) for name, grams in _data()["piece_grams"].items()}


def piece_grams(name: str | None, weights: dict[str, Decimal] | None = None) -> Decimal | None:
    """The usual weight of one piece of the food, or None when the list does not know the food."""
    if not name:
        return None
    weights = load_piece_grams() if weights is None else weights
    return _longest_known(normalize(name), weights)


def _without_gluten_mark(key: str) -> tuple[str, bool]:
    """A normalized text without its words for "without gluten", and whether it had them."""
    marked = False
    for mark in _GLUTEN_FREE_MARKS:
        if mark in key:
            marked = True
            key = key.replace(mark, " ")
    return " ".join(key.split()), marked


def search_term(name: str, terms: dict[str, str] | None = None) -> tuple[str, bool]:
    """
    The text to search in the shops for a food, and whether it is a term of the list.

    "red onion" takes the term of "onion" when the list has no "red onion": the shop then shows its onions.
    A food without a term keeps its own name.
    """
    terms = load_terms() if terms is None else terms
    key = normalize(name)
    term = _longest_known(key, terms)
    if term is None:
        return " ".join(name.split()), False
    # A food "without gluten" must not find the ordinary product.
    if "sans gluten" in key and "gluten" not in normalize(term):
        term = f"{term} {_GLUTEN_FREE}"
    return term, True


def search_names(search: str, names: dict[str, tuple[str, ...]] | None = None) -> list[str]:
    """
    The search text, then the other names that the shops give to the same food.

    A shop finds "Kokosnussmilch" for the search "Kokosmilch": the two names are the same food. The names of a
    food "without gluten" stay "without gluten".
    """
    names = load_other_names() if names is None else names
    key, gluten_free = _without_gluten_mark(normalize(search))
    others = names.get(key, ())
    return [search, *(f"{other} {_GLUTEN_FREE}" if gluten_free else other for other in others)]


def _word_score(wanted: str, word: str) -> float:
    if word == wanted:
        return _WHOLE
    if len(wanted) < 3:
        return 0.0
    longer, shorter = (word, wanted) if len(word) >= len(wanted) else (wanted, word)
    if longer.startswith(shorter) and len(longer) - len(shorter) <= _ENDING and len(shorter) >= 3:
        return _WHOLE
    if word.endswith(wanted):
        return _COMPOUND_END
    if wanted in word:
        return _COMPOUND_START
    return 0.0


def _chunks(text: str) -> list[_Chunk]:
    chunks = []
    for raw in text.split():
        parts = tuple(part for part in re.sub(r"[^a-z0-9-]+", "", raw).split("-") if part)
        if parts:
            chunks.append(parts)
    return chunks


def _zones(product: str) -> tuple[list[_Chunk], list[_Chunk], list[_Chunk]]:
    """
    The name of a product in three zones: what the product is, its variety, and what it is made with.

    "Tomaten Bio, gehackt mit Tomatensaft" gives "Tomaten Bio", then "gehackt", then "Tomatensaft".
    """
    words = _fold(product).split()
    cut = next((i for i, word in enumerate(words) if i > 0 and word.strip(",;.()") in _MADE_WITH), len(words))
    # A comma inside a number ("2,7%") does not start a variety: the comma of a variety has a space after it.
    head, _, variety = " ".join(words[:cut]).partition(", ")
    return _chunks(head), _chunks(variety), _chunks(" ".join(words[cut + 1 :]))


def _chunk_score(wanted: str, chunk: _Chunk) -> float:
    """In "Milch-Haselnuss" the last part says what the thing is, as in a compound word."""
    last = len(chunk) - 1
    return max(
        _word_score(wanted, part) if i == last else min(_word_score(wanted, part), _COMPOUND_START)
        for i, part in enumerate(chunk)
    )


def _fit(wanted: list[str], chunks: list[_Chunk]) -> float:
    """The share of the wanted words that the chunks hold."""
    if not chunks:
        return 0.0
    score = sum(max(_chunk_score(token, chunk) for chunk in chunks) for token in wanted) / len(wanted)
    if len(wanted) > 1:
        # "Basmati Reis" is also written "Basmatireis" and "Basmati-Reis".
        joined = "".join(wanted)
        if any(_word_score(joined, "".join(chunk)) == _WHOLE for chunk in chunks):
            return _WHOLE
    return score


def _best(wanted: list[str], chunks: list[_Chunk]) -> float:
    """The score of the wanted word that the chunks hold best."""
    return max((_chunk_score(token, chunk) for token in wanted for chunk in chunks), default=0.0)


def _holds(chunks: list[_Chunk], words: tuple[str, ...], search: str = "") -> bool:
    """Whether a part of the chunks holds one of the words. A word of the search itself does not count."""
    for word in words:
        if word in search:
            continue
        for chunk in chunks:
            for part in chunk:
                # A short word is only safe at the end of a part: "Eistee", and not a word that has "tee" in it.
                if part.endswith(word) or (len(word) >= 5 and word in part):
                    return True
    return False


def match_score(search: str, product: str) -> float:
    """
    How well the name of a product fits the search, from 0 to 1.

    The words of the search count where the name says what the product is. A food that is only the flavour of
    the product, or one of its ingredients, gets a low score. A search "without gluten" refuses every product
    that does not say that it is without gluten.
    """
    key, gluten_free = _without_gluten_mark(normalize(search))
    if gluten_free and not _without_gluten_mark(normalize(product))[1]:
        return 0.0
    wanted = [word for word in key.split() if len(word) >= 2 and word not in _STOP_WORDS]
    if not wanted:
        return 0.0

    head, variety, made_with = _zones(product)
    named = head + variety
    score = _fit(wanted, named)
    if score > _VARIETY and _best(wanted, head) < _COMPOUND_END and not _holds(head, load_families()):
        # No word of the food says what the product is: the food is only its variety ("Baguette,
        # Knoblauch"). "Linsen Bio, rot" is lentils, and after a family of products the variety is the
        # food itself.
        score = _VARIETY
    if score > _INGREDIENT and _holds(named, load_made_products(), "".join(wanted)):
        score = _INGREDIENT
    if made_with and score < _INGREDIENT:
        score = max(score, min(_fit(wanted, named + made_with), _INGREDIENT))
    return score


@dataclass(frozen=True)
class Ranked:
    index: int
    """The position of the product in the answer of the shop."""
    score: float
    fits: bool

    @property
    def confident(self) -> bool:
        return self.score >= CONFIDENT_SCORE


def rank(searches: list[str], products: list[tuple[str, bool]], limit: int = 3) -> list[Ranked]:
    """
    The products that fit, the best first.

    `searches` holds the search text, the other names of the food and the name of the food: a product fits when
    it fits one of them. `products` gives, for each product of the shop, its name and whether its pack can price
    the line. With the same score, a pack that can price the line comes first, then the order of the shop.
    """
    ranked = [
        Ranked(index, round(max((match_score(search, name) for search in searches), default=0.0), 3), fits)
        for index, (name, fits) in enumerate(products)
    ]
    ranked = [entry for entry in ranked if entry.score >= MIN_SCORE]
    ranked.sort(key=lambda entry: (-entry.score, not entry.fits, entry.index))
    return ranked[:limit]


def dear_limit(costs: list[float]) -> float | None:
    """
    The cost above which a product is out of line with the other products found for the same line.

    A shop sometimes answers with a pack of six or with another product that has the same name. Its cost is then
    several times the cost of the others. None when the costs are too few to compare.
    """
    if len(costs) < 3:
        return None
    ordered = sorted(costs)
    return ordered[len(ordered) // 2] * _DEAR_FACTOR
