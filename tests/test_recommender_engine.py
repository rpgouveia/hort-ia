"""Unit tests of the recommendation engine (WBS 9.3.1-4 and 9.3.2-2).

U1-U5 are the reference cases of 9.3.1-3, section 6 (the acceptance of 9.3.1-4); U6-U13 are the
cases of the test plan `docs/recommender/9.3.2-1_Plano_Casos_Teste.md`, section 2. Each test name
starts with its case id.
"""

import csv
import functools
import itertools
import json
import runpy
import shutil
import sys
import unicodedata
from pathlib import Path

import pytest

from hort_ia.core.geo import Region
from hort_ia.knowledge import load_knowledge_base
from hort_ia.knowledge.loader import kb_dir
from hort_ia.recommender import (
    W_COMPANION,
    W_REPELLENT,
    ExclusionReason,
    Profile,
    ReasonCode,
    Recommender,
    RecommenderError,
    months_left,
)

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


# === 9.3.2-2: cases U6-U13 of the test plan ============================================

KB_DIR = kb_dir()
ALL_PROFILES = [
    Profile(region=region, month=month, small_space=small)
    for region, month, small in itertools.product(Region, range(1, 13), (False, True))
]  # 5 x 12 x 2 = 120


@pytest.fixture(scope="module")
def kb():
    return load_knowledge_base()


def violations(kb, profile, result):
    """Properties P1-P5 of 9.3.1-3, section 6 (P6 is checked by the caller). Empty list = OK."""
    found = []
    previous_family = kb.crops[profile.previous_crop].family if profile.previous_crop in kb.crops else None
    for item in result.recommendations:
        crop = kb.crops[item.crop_id]
        windows = crop.planting_months(result.region) or {}
        if not any(profile.month in months for months in windows.values()):  # P1
            found.append(f"P1 {item.crop_id} out of season")
        if profile.small_space and crop.small_space_recommended is not True:  # P2
            found.append(f"P2 {item.crop_id} not for small space")
        if item.crop_id in profile.planted or (previous_family and crop.family == previous_family):  # P3
            found.append(f"P3 {item.crop_id} planted or same family as the previous crop")
        if not any(r.code is ReasonCode.IN_SEASON and r.source for r in item.reasons):  # P5
            found.append(f"P5 {item.crop_id} without a sourced in_season reason")
    recommended = [i.crop_id for i in result.recommendations]
    excluded = [e.crop_id for e in result.excluded]
    if sorted(recommended + excluded) != sorted(kb.crops) or set(recommended) & set(excluded):  # P4
        found.append("P4 catalog not split between recommendations and excluded")
    return found


@pytest.mark.parametrize("profile", ALL_PROFILES, ids=lambda p: f"{p.region}-{p.month}-{p.small_space}")
def test_u6_properties_hold_for_every_region_month_and_space(engine, kb, profile):
    result = engine.recommend(profile)
    assert violations(kb, profile, result) == []
    assert engine.recommend(profile) == result  # P6


@pytest.mark.parametrize("crop_id", sorted(load_knowledge_base().crops))
def test_u6_rotation_and_planted_hold_for_every_crop(engine, kb, crop_id):
    """P3 repeated with each of the 15 crops as `planted` and as `previous_crop`, over the 120 profiles."""
    for base in ALL_PROFILES:
        for profile in (
            base.model_copy(update={"planted": [crop_id]}),
            base.model_copy(update={"previous_crop": crop_id}),
        ):
            assert violations(kb, profile, engine.recommend(profile)) == [], profile


@functools.cache
def raw_companions() -> tuple[dict[frozenset, set[str]], set[str]]:
    """Relations by pair and pest-repellent crops, read straight from the files (U7)."""
    relations: dict[frozenset, set[str]] = {}
    with (KB_DIR / "companions.csv").open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            relations.setdefault(frozenset((row["crop_a"], row["crop_b"])), set()).add(row["relation"])
    crops = json.loads((KB_DIR / "crops.json").read_text(encoding="utf-8"))
    repellents = {c["id"] for c in crops if any(r["role"] == "pest_repellent" for r in c.get("companion_roles", []))}
    return relations, repellents


def independent_score(candidate: str, planted: list[str]) -> float:
    """Recomputed from the raw files, without the engine's index (U7)."""
    relations, repellents = raw_companions()
    score = 0.0
    for partner in planted:
        found = relations.get(frozenset((candidate, partner)), set())
        score += -W_COMPANION if "harms" in found else W_COMPANION if "helps" in found else 0.0
    if planted and candidate in repellents:
        score += W_REPELLENT
    return score


@pytest.mark.parametrize("planted", sorted(load_knowledge_base().crops))
def test_u7_score_matches_the_raw_companion_file(engine, planted):
    checked = 0
    for region, month in itertools.product(Region, range(1, 13)):
        result = engine.recommend(Profile(region=region, month=month, planted=[planted]))
        for item in result.recommendations:
            assert item.score == independent_score(item.crop_id, [planted]), (region, month, item.crop_id)
            checked += 1
    assert checked > 0


def _plain(text: str) -> str:
    return "".join(ch for ch in unicodedata.normalize("NFKD", text.lower()) if not unicodedata.combining(ch))


@pytest.mark.parametrize("planted", [[], ["tomate"], ["alface", "cenoura"]], ids=["nothing", "tomate", "two"])
def test_u8_order_is_score_then_season_end_then_name(engine, kb, planted):
    for base in ALL_PROFILES:
        result = engine.recommend(base.model_copy(update={"planted": planted}))
        keys = []
        for item in result.recommendations:
            windows = kb.crops[item.crop_id].planting_months(result.region)
            left = max(months_left(m, base.month) for m in windows.values() if base.month in m)
            keys.append((-item.score, left, _plain(item.crop_name_pt)))
        assert keys == sorted(keys), (base, [i.crop_id for i in result.recommendations])
        assert [i.rank for i in result.recommendations] == list(range(1, len(keys) + 1))


def test_u9_unknown_previous_crop_is_ignored_with_a_warning(engine):
    result = engine.recommend(Profile(ibge_code=CURITIBA, month=11, previous_crop="mandioca"))
    assert result.warnings == ["Planta anterior sem dados na base, ignorada: mandioca."]
    assert ExclusionReason.SAME_FAMILY_AS_PREVIOUS not in {e.reason for e in result.excluded}
    assert len(result.recommendations) == 10  # same as R1


@pytest.fixture
def kb_copy(tmp_path: Path) -> Path:
    target = tmp_path / "knowledge"
    shutil.copytree(KB_DIR, target)
    return target


def test_u10_unfavorable_record_wins_over_a_favorable_one(kb_copy):
    with (kb_copy / "companions.csv").open("a", encoding="utf-8") as f:
        f.write("cebolinha,tomate,harms,true,unknown,traditional,embrapa_ct47_cultivo_hortalicas,,draft,\n")
    engine = Recommender(load_knowledge_base(kb_copy))
    result = engine.recommend(Profile(ibge_code=CURITIBA, month=11, planted=["tomate"]))
    cebolinha = next(i for i in result.recommendations if i.crop_id == "cebolinha")
    assert cebolinha.score == -W_COMPANION + W_REPELLENT  # was +1.5 with the favorable record only
    assert [w.code for w in cebolinha.warnings] == [ReasonCode.COMPANION_BAD]
    assert ReasonCode.COMPANION_GOOD not in [r.code for r in cebolinha.reasons]


def test_u11_empty_list_is_an_answer_not_an_error(kb_copy):
    path = kb_copy / "crops.json"
    crops = json.loads(path.read_text(encoding="utf-8"))
    for crop in crops:
        for window in crop["planting_windows"]:
            if "norte" in window["months_by_region"]:
                window["months_by_region"]["norte"] = []  # "não recomendável" all year
    path.write_text(json.dumps(crops, ensure_ascii=False), encoding="utf-8")
    result = Recommender(load_knowledge_base(kb_copy)).recommend(Profile(region="norte", month=6))
    assert result.recommendations == []
    assert len(result.excluded) == len(crops)
    assert {e.reason for e in result.excluded} <= {ExclusionReason.OUT_OF_SEASON, ExclusionReason.NO_REGION_DATA}


@pytest.mark.parametrize("planted", [[], ["tomate"], ["alface", "cenoura"]], ids=["nothing", "tomate", "two"])
def test_u12_no_unfilled_template_and_no_empty_source(engine, planted):
    for base in ALL_PROFILES:
        result = engine.recommend(base.model_copy(update={"planted": planted, "previous_crop": "repolho"}))
        texts = [r for item in result.recommendations for r in item.reasons + item.warnings]
        for reason in texts:
            assert "{" not in reason.text and "}" not in reason.text, reason.text
            assert reason.source, reason
        assert all("{" not in w for w in result.warnings)


def run_cli(monkeypatch, *args):
    monkeypatch.setattr(sys, "argv", ["python -m hort_ia.recommender", *args])
    runpy.run_module("hort_ia.recommender", run_name="__main__")


def test_u13_cli_prints_the_ranked_list(monkeypatch, capsys):
    run_cli(monkeypatch, "--ibge", str(CURITIBA), "--month", "11", "--small-space", "--planted", "tomate")
    out = capsys.readouterr().out
    assert " 1. Manjericão (+1.5)" in out and " 4. Alface (+0.0)" in out
    assert "+ Combina com tomate (indicação tradicional)." in out
    assert "tomate (already_planted)" in out


def test_u13_cli_rejects_an_invalid_location(monkeypatch, capsys):
    with pytest.raises(SystemExit) as exit_info:
        run_cli(monkeypatch, "--ibge", "9906902", "--month", "11")
    assert exit_info.value.code == 2
    assert "código IBGE inválido" in capsys.readouterr().err
