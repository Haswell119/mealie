import pytest

from mealie.services.personal.engine.ideas import (
    daily_rank,
    label_key,
    load_seasons,
    parse_minutes,
    recipe_minutes,
    seasonal_keys,
)


@pytest.mark.parametrize(
    ("text", "minutes"),
    [
        ("45 min", 45),
        ("20 mins", 20),
        ("1 h 30", 90),
        ("1h30", 90),
        ("1h", 60),
        ("1,5 h", 90),
        ("1 heure 15 minutes", 75),
        ("1 hour 5 minutes", 65),
        ("2 Stunden", 120),
        ("1 Stunde 20 Minuten", 80),
        ("PT1H30M", 90),
        ("PT45M", 45),
        ("30", 30),
        ("2 days", 2880),
    ],
)
def test_durations_are_read_in_the_ways_people_type_them(text: str, minutes: int):
    assert parse_minutes(text) == minutes


@pytest.mark.parametrize("text", [None, "", "   ", "quelques minutes", "au feeling", "0 min"])
def test_a_text_without_a_duration_gives_nothing(text):
    assert parse_minutes(text) is None


def test_recipe_duration_prefers_the_total_and_the_stored_seconds():
    assert recipe_minutes("1 h", "10 min", "20 min") == 60
    # without a total, the preparation and the cooking add up
    assert recipe_minutes(None, "10 min", "20 min") == 30
    assert recipe_minutes(None, None, "20 min") == 20
    assert recipe_minutes(None, None, None) is None
    # the number of seconds that the recipe stores wins over its text
    assert recipe_minutes("2 h", total_seconds=1500) == 25
    assert recipe_minutes(None, "1 h", None, prep_seconds=600, perform_seconds=900) == 25
    assert recipe_minutes("au feeling", total_seconds=0) is None


def test_seasonal_produce_depends_on_the_month():
    foods = ["Courge butternut", "Poireaux", "Tomates", "Fraises"]
    assert seasonal_keys(foods, 11) == ["courge", "poireau"]
    assert seasonal_keys(foods, 7) == ["tomate", "fraise"]
    assert seasonal_keys(["Sel", "Riz", "Poivre"], 7) == []
    # the same produce twice is named once
    assert seasonal_keys(["Tomate", "Tomates cerises"], 8) == ["tomate"]


def test_seasonal_matching_skips_lookalikes():
    november = ["Pommes de terre", "Noix de coco", "Jus d'orange", "Vinaigre de pomme", "Chou-fleur surgelé"]
    assert seasonal_keys(november, 11) == ["chou-fleur"]
    # preserved tomatoes are not a summer vegetable; neither is the pepper mill
    august = ["Concentré de tomates", "Tomates pelées", "Poivre", "Raisins secs", "Graines de courge"]
    assert seasonal_keys(august, 8) == []
    assert seasonal_keys(["Pomme", "Noix", "Orange"], 11) == ["pomme", "noix", "agrumes"]


def test_every_season_entry_is_valid():
    seasons = load_seasons()
    assert len(seasons) > 40
    assert len({season.key for season in seasons}) == len(seasons)
    for season in seasons:
        assert season.months and season.months <= set(range(1, 13)), season.key
        assert season.patterns, season.key


def test_the_daily_rank_is_stable_for_a_day_and_changes_with_it():
    assert daily_rank("2026-11-15", "a") == daily_rank("2026-11-15", "a")
    assert daily_rank("2026-11-15", "a") != daily_rank("2026-11-16", "a")
    assert daily_rank("2026-11-15", "a") != daily_rank("2026-11-15", "b")
    assert all(0 <= daily_rank("seed", str(index)) < 1 for index in range(200))


def test_label_keys_ignore_case_and_accents():
    assert label_key("Végétarien") == label_key("vegetarien") == "label:vegetarien"
    assert label_key("Plat  du Dimanche") == "label:plat-du-dimanche"
    assert label_key("!!!") == "label:"
