"""Integration of the recommendation engine with the data pipeline and its consumers (WBS 9.3.1-5, 9.3.2-3).

Cases I1-I9 of the test plan `docs/recommender/9.3.2-1_Plano_Casos_Teste.md`, section 3; each test name
starts with its case id. The path under test is: files in `data/knowledge/` -> `load_knowledge_base` ->
engine -> routes and assistant. The data half of the pipeline (rejecting broken files) is covered by
`test_knowledge_base.py` and `test_geo.py`. Calls go through the whole FastAPI app in process.
"""

import itertools
import json
import shutil
from pathlib import Path

import pytest
from starlette.testclient import TestClient

from hort_ia.api.main import app
from hort_ia.core.geo import Region
from hort_ia.knowledge import load_knowledge_base
from hort_ia.knowledge.loader import kb_dir
from hort_ia.market.loader import load_market_dataset
from hort_ia.nlp import Responder, load_templates
from hort_ia.recommender import Profile, Recommender, get_recommender

CURITIBA = 4106902
PROFILES = list(itertools.product([r.value for r in Region], range(1, 13), (False, True)))  # 120


def profile_id(p):
    return f"{p[0]}-{p[1]}-{p[2]}"


@pytest.fixture(scope="module")
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture(scope="module")
def kb():
    return load_knowledge_base()


@pytest.fixture(scope="module")
def responder(kb):
    return Responder(kb, load_templates(), load_market_dataset())


@pytest.fixture
def kb_copy(tmp_path: Path) -> Path:
    target = tmp_path / "knowledge"
    shutil.copytree(kb_dir(), target)
    return target


@pytest.fixture
def api_on(client):
    """Points the API at an engine built from another copy of the knowledge base."""

    def use(directory: Path) -> TestClient:
        engine = Recommender(load_knowledge_base(directory))
        app.dependency_overrides[get_recommender] = lambda: engine
        return client

    yield use
    app.dependency_overrides.pop(get_recommender, None)


def recommend(client, **payload) -> dict:
    response = client.post("/recommender/recommendations", json=payload)
    assert response.status_code == 200, response.text
    return response.json()


# --- I1: files -> loader -> engine -> route, every profile -------------------------------


@pytest.mark.parametrize("profile", PROFILES, ids=profile_id)
def test_i1_every_profile_through_the_api_is_agronomically_valid(client, kb, profile):
    region, month, small = profile
    for extra in ({}, {"planted": ["tomate"], "previous_crop": "repolho"}):
        data = recommend(client, region=region, month=month, small_space=small, **extra)
        excluded = {e["crop_id"] for e in data["excluded"]}
        assert {i["crop_id"] for i in data["recommendations"]} | excluded == set(kb.crops)
        for item in data["recommendations"]:
            crop = kb.crops[item["crop_id"]]
            windows = crop.planting_months(Region(region)) or {}
            assert any(month in months for months in windows.values()), item["crop_id"]  # critical failure 1
            assert not small or crop.small_space_recommended is True, item["crop_id"]  # critical failure 2
            if extra:
                assert crop.family != kb.crops["repolho"].family, item["crop_id"]  # critical failure 3
                assert item["crop_id"] != "tomate"


# --- I2, I3: a change in the data reaches the API without code changes ---------------------


def test_i2_new_small_space_information_reaches_the_api(api_on, kb_copy):
    profile = {"ibge_code": CURITIBA, "month": 3, "small_space": True}
    before = recommend(api_on(kb_dir()), **profile)
    assert {"crop_id": "morango", "reason": "no_small_space_info"} in before["excluded"]

    path = kb_copy / "crops.json"
    crops = json.loads(path.read_text(encoding="utf-8"))
    next(c for c in crops if c["id"] == "morango")["small_space_recommended"] = True
    path.write_text(json.dumps(crops, ensure_ascii=False), encoding="utf-8")

    after = recommend(api_on(kb_copy), **profile)
    assert "morango" in [i["crop_id"] for i in after["recommendations"]]
    assert all(e["crop_id"] != "morango" for e in after["excluded"])


def test_i3_new_companion_relation_reaches_the_api(api_on, kb_copy):
    profile = {"ibge_code": CURITIBA, "month": 11, "small_space": True, "planted": ["tomate"]}
    before = {i["crop_id"]: i for i in recommend(api_on(kb_dir()), **profile)["recommendations"]}
    assert before["alface"]["score"] == 0.0

    with (kb_copy / "companions.csv").open("a", encoding="utf-8") as f:
        f.write("alface,tomate,helps,true,unknown,traditional,embrapa_ct47_cultivo_hortalicas,,draft,\n")

    after = recommend(api_on(kb_copy), **profile)["recommendations"]
    alface = next(i for i in after if i["crop_id"] == "alface")
    assert alface["score"] == 1.0
    good = [r for r in alface["reasons"] if r["code"] == "companion_good"]
    assert [r["text"] for r in good] == ["Combina com tomate (indicação tradicional)."]
    assert "Circular Técnica 47" in good[0]["source"]
    # alface now ties with pimentão at 1.0 and goes after it: alface (de verão) can be planted all year
    assert [i["crop_id"] for i in after] == ["manjericao", "cebolinha", "pimentao", "alface"]


# --- I4, I5: profile through POST /recommender/recommendations -------------------------------


def test_i4_profile_reaches_the_engine(client):
    data = recommend(client, ibge_code=CURITIBA, month=11, small_space=True, planted=["tomate"])
    assert data["region"] == "sul"
    assert [(i["crop_id"], i["score"]) for i in data["recommendations"]] == [
        ("manjericao", 1.5),
        ("cebolinha", 1.5),
        ("pimentao", 1.0),
        ("alface", 0.0),
    ]  # fmt: skip  (case R2 of 9.3.1-3)
    first = data["recommendations"][0]
    assert first["rank"] == 1
    assert {r["code"] for r in first["reasons"]} == {"in_season", "season_ending", "companion_good", "pest_repellent"}
    assert {"crop_id": "tomate", "reason": "already_planted"} in data["excluded"]
    assert data["approach"] == "knowledge_based" and data["model_version"]


def test_i4_region_instead_of_ibge_code_and_unknown_crops(client):
    data = recommend(client, region="sul", month=11, planted=["tomate", "mandioca"], previous_crop="tomate")
    assert [i["crop_id"] for i in data["recommendations"]][:2] == ["manjericao", "cebolinha"]
    assert data["warnings"] == ["Planta sem dados na base, ignorada: mandioca."]  # case R7


def test_i5_month_defaults_to_the_current_one(client):
    assert client.post("/recommender/recommendations", json={"region": "sul"}).status_code == 200


@pytest.mark.parametrize(
    "payload",
    [
        {"ibge_code": 9906902, "month": 11},  # unknown UF code
        {"region": "marte", "month": 11},
        {"month": 11},  # no location
        {"region": "sul", "month": 13},
    ],
)
def test_i5_invalid_profile_returns_422(client, payload):
    assert client.post("/recommender/recommendations", json=payload).status_code == 422


# --- I6, I7: the other consumers agree with the engine (critical failure 5) -----------------


@pytest.mark.parametrize("profile", PROFILES, ids=profile_id)
def test_i6_what_to_plant_route_lists_the_engine_crops(client, profile):
    region, month, small = profile
    url = f"/recommender/what-to-plant?region={region}&month={month}&small_space={str(small).lower()}"
    response = client.get(url)
    assert response.status_code == 200
    data = response.json()
    engine = get_recommender().recommend(Profile(region=region, month=month, small_space=small))
    assert {c["crop_id"] for c in data["recommended_crops"]} == {i.crop_id for i in engine.recommendations}
    names = [c["crop_name_pt"] for c in data["recommended_crops"]]
    assert names == sorted(names)  # the 9.7.1-3 contract keeps alphabetical order


@pytest.mark.parametrize("profile", PROFILES, ids=profile_id)
def test_i7_assistant_lists_the_engine_crops_in_the_engine_order(responder, profile):
    region, month, small = profile
    engine = get_recommender().recommend(Profile(region=region, month=month, small_space=small))
    names = [i.crop_name_pt.lower() for i in engine.recommendations]
    template = load_templates()["what_to_plant"]["list_small_space" if small else "list"]
    expected = template.format(
        month=responder.month_name(month), region=responder.region_label(region), crops=responder.join(names)
    )
    answer = responder.what_to_plant(region, month, small_space=small)
    assert answer.text == expected and not answer.handoff


def test_i7_assistant_hands_off_when_the_engine_has_nothing(kb_copy):
    path = kb_copy / "crops.json"
    crops = json.loads(path.read_text(encoding="utf-8"))
    for crop in crops:
        for window in crop["planting_windows"]:
            if "norte" in window["months_by_region"]:
                window["months_by_region"]["norte"] = []
    path.write_text(json.dumps(crops, ensure_ascii=False), encoding="utf-8")
    kb = load_knowledge_base(kb_copy)
    responder = Responder(kb, load_templates(), load_market_dataset(), recommender=Recommender(kb))
    answer = responder.what_to_plant("norte", 6)
    assert answer.text == "Em junho, no Norte, nenhuma das plantas que eu conheço está na época."
    assert answer.handoff


def test_i7_assistant_reference_text(responder):
    assert responder.what_to_plant("sul", 11).text == (
        "Em novembro, no Sul, dá para plantar: batata, manjericão, cenoura, repolho, pimentão, tomate, "
        "abobrinha, alface, beterraba e cebolinha."
    )  # case R1 of 9.3.1-3


# --- I8: regression, /nlp/answer used to fail on every call ----------------------------------


def test_i8_nlp_answer_works(client):
    response = client.post("/nlp/answer", json={"intent": "what_to_plant", "region": "sul", "month": 11})
    assert response.status_code == 200
    assert response.json()["text"].startswith("Em novembro, no Sul, dá para plantar: batata, manjericão")


# --- I9: the routes agree with each other ----------------------------------------------------


def test_i9_recommendations_agree_with_calendar_and_companion_routes(client):
    data = recommend(client, ibge_code=CURITIBA, month=11, planted=["tomate"])  # case R3
    companions = client.get("/recommender/companion-crops?crop_id=tomate").json()
    helps = {p["partner_id"] for p in companions["helps"]}
    hinders = {p["partner_id"] for p in companions["hinders"]}
    for item in data["recommendations"]:
        calendar = client.get(f"/recommender/planting-calendar?crop_id={item['crop_id']}&ibge_code={CURITIBA}").json()
        assert any(11 in w["recommended_months"] for w in calendar["windows"]), item["crop_id"]
        codes = [r["code"] for r in item["reasons"]] + [w["code"] for w in item["warnings"]]
        assert ("companion_good" in codes) == (item["crop_id"] in helps), item["crop_id"]
        assert ("companion_bad" in codes) == (item["crop_id"] in hinders), item["crop_id"]
