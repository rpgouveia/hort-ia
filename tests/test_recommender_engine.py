"""Reference cases of the recommendation engine (9.3.1-3, section 6), the acceptance of 9.3.1-4.

The properties of section 6 over the 120 region x month x small-space profiles are the unit test
plan of 9.3.2-1/-2.
"""

import pytest

from hort_ia.core.geo import Region
from hort_ia.knowledge import load_knowledge_base
from hort_ia.recommender import ExclusionReason, Profile, ReasonCode, Recommender, RecommenderError, months_left

CURITIBA, MANAUS, SAO_PAULO = 4106902, 1302603, 3550308


@pytest.fixture(scope="module")
def engine():
    return Recommender(load_knowledge_base())


def ranking(result):
    return [(item.crop_id, item.score) for item in result.recommendations]


def excluded(result):
    return {e.crop_id: e.reason for e in result.excluded}


# --- reference cases (section 6) ------------------------------------------------------


def test_r1_season_and_region_only(engine):
    result = engine.recommend(Profile(ibge_code=CURITIBA, month=11))
    assert result.region is Region.SUL
    assert [c for c, _ in ranking(result)] == [
        "batata", "manjericao", "cenoura", "repolho", "pimentao",
        "tomate", "abobrinha", "alface", "beterraba", "cebolinha",
    ]  # fmt: skip
    assert {s for _, s in ranking(result)} == {0.0}
    assert excluded(result) == dict.fromkeys(
        ["morango", "couve", "rucula", "rabanete", "salsa"], ExclusionReason.OUT_OF_SEASON
    )


def test_r2_small_space_with_tomato(engine):
    result = engine.recommend(Profile(ibge_code=CURITIBA, month=11, small_space=True, planted=["tomate"]))
    assert ranking(result) == [("manjericao", 1.5), ("cebolinha", 1.5), ("pimentao", 1.0), ("alface", 0.0)]
    out = excluded(result)
    assert out["tomate"] is ExclusionReason.ALREADY_PLANTED
    assert {out[c] for c in ("batata", "cenoura", "beterraba")} == {ExclusionReason.NOT_FOR_SMALL_SPACE}
    assert {out[c] for c in ("repolho", "abobrinha")} == {ExclusionReason.NO_SMALL_SPACE_INFO}


def test_r3_unfavorable_companions_go_last_with_a_warning(engine):
    result = engine.recommend(Profile(ibge_code=CURITIBA, month=11, planted=["tomate"]))
    assert ranking(result) == [
        ("manjericao", 1.5), ("cebolinha", 1.5),
        ("cenoura", 1.0), ("repolho", 1.0), ("pimentao", 1.0), ("abobrinha", 1.0),
        ("alface", 0.0), ("batata", -1.0), ("beterraba", -1.0),
    ]  # fmt: skip
    for item in result.recommendations[-2:]:
        assert [w.code for w in item.warnings] == [ReasonCode.COMPANION_BAD]
        assert item.warnings[0].text == "Não combina com tomate (indicação tradicional)."


def test_r4_rotation_excludes_the_family_of_the_previous_crop(engine):
    result = engine.recommend(Profile(ibge_code=CURITIBA, month=3, previous_crop="repolho"))
    assert [c for c, _ in ranking(result)] == [
        "morango", "abobrinha", "cenoura", "salsa", "alface", "beterraba", "cebolinha",
    ]  # fmt: skip
    rotated = [c for c, r in excluded(result).items() if r is ExclusionReason.SAME_FAMILY_AS_PREVIOUS]
    assert sorted(rotated) == ["couve", "rabanete", "repolho", "rucula"]


def test_r5_short_list_is_not_padded(engine):
    result = engine.recommend(Profile(ibge_code=MANAUS, month=11))
    assert result.region is Region.NORTE
    assert [c for c, _ in ranking(result)] == ["cenoura", "alface"]
    out = excluded(result)
    assert out.pop("manjericao") is ExclusionReason.NO_REGION_DATA
    assert set(out.values()) == {ExclusionReason.OUT_OF_SEASON}


def test_r6_season_ending_first(engine):
    result = engine.recommend(Profile(ibge_code=CURITIBA, month=7, small_space=True))
    assert [c for c, _ in ranking(result)] == ["couve", "rucula", "salsa", "alface", "cebolinha"]
    couve = result.recommendations[0]
    assert [r.code for r in couve.reasons] == [ReasonCode.IN_SEASON, ReasonCode.SEASON_ENDING]
    assert couve.reasons[1].text == "A época de plantio termina em julho."


def test_r7_unknown_crops_are_ignored_with_a_warning(engine):
    profile = Profile(ibge_code=CURITIBA, month=11, planted=["tomate", "mandioca"], previous_crop="tomate")
    result = engine.recommend(profile)
    assert ranking(result) == [
        ("manjericao", 1.5), ("cebolinha", 1.5),
        ("cenoura", 1.0), ("repolho", 1.0), ("abobrinha", 1.0),
        ("alface", 0.0), ("beterraba", -1.0),
    ]  # fmt: skip
    out = excluded(result)
    assert out["batata"] is out["pimentao"] is ExclusionReason.SAME_FAMILY_AS_PREVIOUS
    assert result.warnings == ["Planta sem dados na base, ignorada: mandioca."]


def test_r8_two_planted_crops(engine):
    result = engine.recommend(Profile(ibge_code=SAO_PAULO, month=4, planted=["alface", "cenoura"]))
    assert result.region is Region.SUDESTE
    assert ranking(result) == [
        ("cebolinha", 1.5), ("morango", 1.0), ("beterraba", 1.0), ("tomate", 1.0), ("manjericao", 0.5),
        ("abobrinha", 0.0), ("couve", 0.0), ("rabanete", 0.0), ("rucula", 0.0),
        ("batata", -1.0), ("repolho", -1.0), ("salsa", -1.0),
    ]  # fmt: skip
    rabanete = next(i for i in result.recommendations if i.crop_id == "rabanete")
    assert ReasonCode.COMPANION_GOOD in [r.code for r in rabanete.reasons]
    assert [w.code for w in rabanete.warnings] == [ReasonCode.COMPANION_BAD]


@pytest.mark.parametrize("ibge_code", [123, "41069020", 9906902])
def test_e1_invalid_ibge_code(engine, ibge_code):
    with pytest.raises(RecommenderError):
        engine.recommend(Profile(ibge_code=ibge_code, month=11))


@pytest.mark.parametrize("month", [0, 13])
def test_e2_invalid_month(month):
    with pytest.raises(ValueError):
        Profile(ibge_code=CURITIBA, month=month)


def test_location_is_required():
    with pytest.raises(ValueError):
        Profile(month=11)


# --- explanations --------------------------------------------------------------------


def test_every_recommendation_has_a_sourced_in_season_reason(engine):
    result = engine.recommend(Profile(region="sudeste", month=4, planted=["alface", "cenoura"]))
    for item in result.recommendations:
        assert item.reasons[0].code is ReasonCode.IN_SEASON
        assert all(r.source for r in item.reasons + item.warnings)


def test_variant_reason_names_the_cultivar(engine):
    result = engine.recommend(Profile(ibge_code=CURITIBA, month=11))
    alface = next(i for i in result.recommendations if i.crop_id == "alface")
    assert alface.variants == ["verao"]
    assert alface.reasons[0].text == "Alface de verão: no Sul, dá para plantar o ano todo."


def test_repellent_bonus_needs_something_planted(engine):
    alone = engine.recommend(Profile(ibge_code=CURITIBA, month=11))
    with_tomato = engine.recommend(Profile(ibge_code=CURITIBA, month=11, planted=["tomate"]))
    codes = {i.crop_id: [r.code for r in i.reasons] for i in alone.recommendations}
    assert ReasonCode.PEST_REPELLENT not in codes["cebolinha"]
    cebolinha = next(i for i in with_tomato.recommendations if i.crop_id == "cebolinha")
    assert ReasonCode.PEST_REPELLENT in [r.code for r in cebolinha.reasons]


def test_same_profile_same_result(engine):
    profile = Profile(ibge_code=SAO_PAULO, month=4, planted=["cenoura", "alface", "alface"])
    assert engine.recommend(profile) == engine.recommend(profile)


@pytest.mark.parametrize(
    ("months", "month", "left"),
    [(list(range(1, 13)), 5, 12), ([9, 10, 11, 12, 1, 2], 11, 4), ([2, 3, 4, 5, 6, 7], 7, 1), ([11, 12], 12, 1)],
)
def test_months_left(months, month, left):
    assert months_left(months, month) == left
