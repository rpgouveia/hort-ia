"""Load and latency validation test suite for Hort-IA API (WBS 9.7.3-1).

Validates that all core API endpoints respond well below the 5.0-second TAP latency threshold
under simulated concurrent request load.
"""

import time
from concurrent.futures import ThreadPoolExecutor
from starlette.testclient import TestClient

from hort_ia.api.main import app

LATENCY_THRESHOLD_SECONDS = 5.0
CONCURRENT_WORKERS = 10
REQUESTS_PER_ENDPOINT = 20

ENDPOINTS = [
    ("GET", "/"),
    ("GET", "/recommender/planting-calendar?crop_id=alface&region=sul"),
    ("GET", "/recommender/companion-crops?crop_id=tomate"),
    ("GET", "/recommender/what-to-plant?month=11&region=sul"),
    (
        "POST",
        "/recommender/recommendations",
        {"ibge_code": 4106902, "month": 11, "small_space": False, "planted": ["tomate"]},
    ),
    ("GET", "/market/reference-price?product_id=alface&uf=PR"),
    (
        "POST",
        "/nlp/answer",
        {"intent": "planting_time", "crop_id": "alface", "region": "sul", "month": 11},
    ),
    (
        "POST",
        "/nlp/message",
        {"text": "quando eu planto alface?", "ibge_code": 4106902, "month": 11},
    ),
    ("GET", "/finance/price-forecast?product_id=alface&entrepost_id=ceagesp_sp&horizon_months=1"),
]


def _call_endpoint(client: TestClient, method: str, path: str, payload: dict | None = None) -> float:
    start_t = time.perf_counter()
    if method == "GET":
        resp = client.get(path)
    else:
        resp = client.post(path, json=payload or {})
    elapsed = time.perf_counter() - start_t
    assert resp.status_code == 200, f"Endpoint {path} failed with status {resp.status_code}: {resp.text}"
    return elapsed


def test_api_latency_single_requests():
    """Verify that every endpoint responds within the 5.0s threshold in isolated calls."""
    client = TestClient(app)
    for item in ENDPOINTS:
        method = item[0]
        path = item[1]
        payload = item[2] if len(item) > 2 else None
        elapsed = _call_endpoint(client, method, path, payload)
        assert elapsed < LATENCY_THRESHOLD_SECONDS, (
            f"Endpoint {path} took {elapsed:.3f}s, exceeding threshold of {LATENCY_THRESHOLD_SECONDS}s"
        )


def test_api_latency_under_simulated_load():
    """Verify that endpoints sustain response times < 5.0s under concurrent load (WBS 9.7.3-1)."""
    client = TestClient(app)
    # Warm up assistant & cache
    client.get("/")
    client.post("/nlp/message", json={"text": "ola"})

    for item in ENDPOINTS:
        method = item[0]
        path = item[1]
        payload = item[2] if len(item) > 2 else None

        with ThreadPoolExecutor(max_workers=CONCURRENT_WORKERS) as executor:
            futures = [
                executor.submit(_call_endpoint, client, method, path, payload)
                for _ in range(REQUESTS_PER_ENDPOINT)
            ]
            latencies = [f.result() for f in futures]

        max_latency = max(latencies)
        avg_latency = sum(latencies) / len(latencies)

        assert max_latency < LATENCY_THRESHOLD_SECONDS, (
            f"Under load, {path} had max latency of {max_latency:.3f}s (threshold: {LATENCY_THRESHOLD_SECONDS}s)"
        )
        assert avg_latency < 2.0, f"Average latency {avg_latency:.3f}s is higher than expected"

