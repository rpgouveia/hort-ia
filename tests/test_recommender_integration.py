"""Integration of the recommendation engine with the profile and the routes (WBS 9.3.1-5).

The engine's reference cases are in test_recommender_engine.py; here only what the integration adds:
the profile reaching the engine through the API, and the API and the assistant agreeing with it.
"""

import pytest
from starlette.testclient import TestClient

from hort_ia.api.main import app
from hort_ia.knowledge import load_knowledge_base
from hort_ia.market.loader import load_market_dataset
from hort_ia.nlp import Responder, load_templates
from hort_ia.recommender import Profile, get_recommender

CURITIBA = 4106902


@pytest.fixture(scope="module")
def client() -> TestClient:
    return TestClient(app)


# --- POST /recommender/recommendations -------------------------------------------------


def test_profile_reaches_the_engine(client):
    payload = {"ibge_code": CURITIBA, "month": 11, "small_space": True, "planted": ["tomate"]}
    response = client.post("/recommender/recommendations", json=payload)
    assert response.status_code == 200
    data = response.json()
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


def test_region_instead_of_ibge_code_and_unknown_crops(client):
    payload = {"region": "sul", "month": 11, "planted": ["tomate", "mandioca"], "previous_crop": "tomate"}
    data = client.post("/recommender/recommendations", json=payload).json()
    assert [i["crop_id"] for i in data["recommendations"]][:2] == ["manjericao", "cebolinha"]
    assert data["warnings"] == ["Planta sem dados na base, ignorada: mandioca."]  # case R7


def test_month_defaults_to_the_current_one(client):
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
def test_invalid_profile_returns_422(client, payload):
    assert client.post("/recommender/recommendations", json=payload).status_code == 422


# --- the other consumers agree with the engine -----------------------------------------


@pytest.mark.parametrize(("region", "month", "small"), [("sul", 11, False), ("sul", 7, True), ("norte", 11, False)])
def test_what_to_plant_route_lists_the_engine_crops(client, region, month, small):
    url = f"/recommender/what-to-plant?region={region}&month={month}&small_space={str(small).lower()}"
    data = client.get(url).json()
    engine = get_recommender().recommend(Profile(region=region, month=month, small_space=small))
    assert {c["crop_id"] for c in data["recommended_crops"]} == {i.crop_id for i in engine.recommendations}
    names = [c["crop_name_pt"] for c in data["recommended_crops"]]
    assert names == sorted(names)  # the 9.7.1-3 contract keeps alphabetical order


def test_assistant_lists_crops_in_the_engine_order():
    responder = Responder(load_knowledge_base(), load_templates(), load_market_dataset())
    text = responder.what_to_plant("sul", 11).text
    assert text == (
        "Em novembro, no Sul, dá para plantar: batata, manjericão, cenoura, repolho, pimentão, tomate, "
        "abobrinha, alface, beterraba e cebolinha."
    )  # case R1 of 9.3.1-3


# --- regression: /nlp/answer used to fail on every call ---------------------------------


def test_nlp_answer_works(client):
    payload = {"intent": "what_to_plant", "region": "sul", "month": 11}
    response = client.post("/nlp/answer", json=payload)
    assert response.status_code == 200
    assert response.json()["text"].startswith("Em novembro, no Sul, dá para plantar: batata, manjericão")
