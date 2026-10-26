"""Integration and contract tests for the Hort-IA API (WBS 9.7.1 and 9.7.2)."""

import pytest
from starlette.testclient import TestClient

from hort_ia.api.main import app


@pytest.fixture(scope="module")
def client() -> TestClient:
    return TestClient(app)


def test_root_health_check(client: TestClient):
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "Hort-IA" in data["module"]
    assert data["docs_url"] == "/docs"


# --- Recommender Endpoints ---


def test_planting_calendar_by_region(client: TestClient):
    response = client.get("/recommender/planting-calendar?crop_id=alface&region=sul")
    assert response.status_code == 200
    data = response.json()
    assert data["crop_id"] == "alface"
    assert data["region"] == "sul"
    assert len(data["windows"]) > 0
    assert data["model_version"] == "1.0.0"


def test_planting_calendar_by_ibge_code(client: TestClient):
    # 4106902 is Curitiba -> Region.SUL
    response = client.get("/recommender/planting-calendar?crop_id=alface&ibge_code=4106902")
    assert response.status_code == 200
    data = response.json()
    assert data["region"] == "sul"


def test_planting_calendar_unknown_crop_returns_404(client: TestClient):
    response = client.get("/recommender/planting-calendar?crop_id=abacaxi_invalido&region=sul")
    assert response.status_code == 404
    assert "Cultura não encontrada" in response.json()["detail"]


def test_planting_calendar_missing_location_returns_422(client: TestClient):
    response = client.get("/recommender/planting-calendar?crop_id=alface")
    assert response.status_code == 422


def test_companion_crops_success(client: TestClient):
    response = client.get("/recommender/companion-crops?crop_id=tomate")
    assert response.status_code == 200
    data = response.json()
    assert data["crop_id"] == "tomate"
    assert isinstance(data["helps"], list)
    assert isinstance(data["hinders"], list)


def test_what_to_plant_success(client: TestClient):
    response = client.get("/recommender/what-to-plant?month=10&region=sul")
    assert response.status_code == 200
    data = response.json()
    assert data["month"] == 10
    assert data["region"] == "sul"
    assert len(data["recommended_crops"]) > 0


def test_what_to_plant_invalid_month_returns_422(client: TestClient):
    response = client.get("/recommender/what-to-plant?month=13&region=sul")
    assert response.status_code == 422


# --- NLP Conversational Assistant Endpoints ---


def test_nlp_answer_planting_time(client: TestClient):
    payload = {
        "intent": "planting_time",
        "crop_id": "alface",
        "region": "sul",
        "month": 10,
    }
    response = client.post("/nlp/answer", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["intent"] == "planting_time"
    assert len(data["text"]) > 10
    assert isinstance(data["sources"], list)
    assert data["handoff"] is False


def test_nlp_answer_companion(client: TestClient):
    payload = {
        "intent": "companion_planting",
        "crop_id": "tomate",
    }
    response = client.post("/nlp/answer", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["intent"] == "companion_planting"
    assert "tomate" in data["text"].lower()


def test_nlp_answer_unknown_intent_returns_422(client: TestClient):
    payload = {
        "intent": "intent_inexistente_123",
    }
    response = client.post("/nlp/answer", json=payload)
    assert response.status_code == 422
    assert "Intenção desconhecida" in response.json()["detail"]


# --- Market Reference Price Endpoints ---


def test_market_reference_price_by_uf(client: TestClient):
    response = client.get("/market/reference-price?product_id=alface&uf=PR")
    assert response.status_code == 200
    data = response.json()
    assert data["product_id"] == "alface"
    assert data["price_brl_kg"] > 0
    assert "Curitiba" in data["entrepost_name"] or "PR" in data["entrepost_name"]


def test_market_reference_price_national_fallback(client: TestClient):
    # Acre (AC) has no Ceasa in dataset, should fallback to national average
    response = client.get("/market/reference-price?product_id=alface&uf=AC")
    assert response.status_code == 200
    data = response.json()
    assert data["is_national_average"] is True


def test_market_reference_price_unknown_product_returns_404(client: TestClient):
    response = client.get("/market/reference-price?product_id=produto_inexistente")
    assert response.status_code == 404
