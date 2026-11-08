"""Measures API endpoint latency under concurrent load and saves metrics (WBS 9.7.3-1)."""

import json
import statistics
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from starlette.testclient import TestClient

from hort_ia.api.main import app

LATENCY_THRESHOLD_SECONDS = 5.0
CONCURRENT_WORKERS = 10
REQUESTS_PER_ENDPOINT = 25

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


def run_benchmark():
    client = TestClient(app)
    # Warm up
    client.get("/")
    client.post("/nlp/message", json={"text": "oi"})

    results = {}
    for item in ENDPOINTS:
        method = item[0]
        path = item[1]
        payload = item[2] if len(item) > 2 else None

        def call():
            t0 = time.perf_counter()
            if method == "GET":
                r = client.get(path)
            else:
                r = client.post(path, json=payload or {})
            t1 = time.perf_counter()
            assert r.status_code == 200
            return (t1 - t0) * 1000.0  # ms

        with ThreadPoolExecutor(max_workers=CONCURRENT_WORKERS) as pool:
            times = list(pool.map(lambda _: call(), range(REQUESTS_PER_ENDPOINT)))

        key = f"{method} {path.split('?')[0]}"
        results[key] = {
            "method": method,
            "route": path.split("?")[0],
            "query_or_sample": path.split("?")[1] if "?" in path else str(payload or ""),
            "count": len(times),
            "min_ms": round(min(times), 2),
            "avg_ms": round(statistics.mean(times), 2),
            "p95_ms": round(statistics.quantiles(times, n=20)[18], 2) if len(times) >= 20 else round(max(times), 2),
            "max_ms": round(max(times), 2),
            "threshold_ms": LATENCY_THRESHOLD_SECONDS * 1000,
            "passed": max(times) < (LATENCY_THRESHOLD_SECONDS * 1000),
        }

    out_json = Path("docs/api/9.7.3-1_load_test_metrics.json")
    out_json.parent.mkdir(parents=True, exist_ok=True)
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    print(f"Metrics saved to {out_json}")
    for k, v in results.items():
        print(f"{k:<35} | avg: {v['avg_ms']:>6.2f} ms | p95: {v['p95_ms']:>6.2f} ms | max: {v['max_ms']:>6.2f} ms | passed: {v['passed']}")


if __name__ == "__main__":
    run_benchmark()

