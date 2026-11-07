"""Response size and modeled time over a slow connection (WBS 9.4.2-4).

The measurement with a throttling proxy is `scripts/measure_slow_connection.py` (results in
`docs/nlu/9.4.2-4_slow_connection_metrics.json`). These tests keep its conclusion true as the code
changes: the replies stay small, and on the 2G profile, opening an HTTPS connection for every message,
the time a user waits stays below the 5 s criterion of 9.4. The model below reproduced the proxy
measurement within 0.05 s.
"""

import json
from pathlib import Path

import pytest
from starlette.testclient import TestClient

from hort_ia.api.main import app

EDGE = {"rtt_s": 0.8, "down_bps": 100_000, "up_bps": 50_000}  # profile "2G (EDGE)" of 9.4.2-4
HEADERS = 200  # bytes of HTTP headers in each direction (uvicorn sends about 130)
TLS_12_RTT = 2
TARGET_S = 5.0
MAX_REPLY_BYTES = 4096  # budget for one /nlp/message reply
MAX_REQUEST_BYTES = 1024  # budget for one /nlp/message request, context included

TURNS = [  # reference messages and conversations of 9.4.1-3, section 6
    ["o que da pra plantar agora?"], ["quanto ta o tomate no ceasa?"], ["o que planto depois do repolho?"],
    ["da pra plantar cebolinha em vaso?"], ["minha couve ta com uns bichinho"], ["quanto custa o adubo?"],
    ["quando eu planto?", "alface"], ["quando planto mandioca?", "mandioca"], ["qndo plantar alfase?", "sim"],
    ["qual a epoca de plantar alface?", "e a rega dela?"], ["a alface ta amarelando", "sim"],
    ["tem como plantar morango aqui?", "não", "quando planto"], ["alface aguenta frio?"], ["como crio galinha?"],
]  # fmt: skip


def modeled_seconds(request_bytes: int, reply_bytes: int, server_s: float) -> float:
    """New TCP + TLS 1.2 connection for the message, then one request and one reply."""
    rtt = EDGE["rtt_s"]
    transfer = (request_bytes + HEADERS) * 8 / EDGE["up_bps"] + (reply_bytes + HEADERS) * 8 / EDGE["down_bps"]
    return rtt * (1 + TLS_12_RTT) + rtt + transfer + server_s


@pytest.fixture(scope="module")
def exchanges():
    client, rows = TestClient(app), []
    client.post("/nlp/message", json={"text": "oi"})  # warm-up, as the API would be in use
    for conversation in TURNS:
        context = None
        for text in conversation:
            body = json.dumps({"text": text, "ibge_code": 4106902, "month": 11, "context": context}).encode()
            response = client.post("/nlp/message", content=body, headers={"Content-Type": "application/json"})
            context = response.json()["context"]
            rows.append((text, len(body), len(response.content)))
    return rows


def test_replies_and_requests_stay_small(exchanges):
    for text, sent, received in exchanges:
        assert received <= MAX_REPLY_BYTES, (text, received)
        assert sent <= MAX_REQUEST_BYTES, (text, sent)


def test_every_turn_stays_below_5_seconds_on_2g_with_https(exchanges):
    times = [modeled_seconds(sent, received, server_s=0.05) for _, sent, received in exchanges]
    assert max(times) < TARGET_S
    assert sum(times) / len(times) < TARGET_S


def test_recommendations_stay_below_5_seconds_on_2g_with_https():
    response = TestClient(app).post("/recommender/recommendations", json={"ibge_code": 4106902, "month": 11})
    assert len(response.content) <= 8192
    assert modeled_seconds(60, len(response.content), server_s=0.05) < TARGET_S


def test_model_matches_the_proxy_measurement():
    """The committed measurement (HTTP, no TLS) and the model agree, so the model can stand in for it."""
    path = Path(__file__).parents[1] / "docs" / "nlu" / "9.4.2-4_slow_connection_metrics.json"
    metrics = json.loads(path.read_text(encoding="utf-8"))
    measured = metrics["profiles"]["2G (EDGE)"]["new_connection"]["mean_s"]
    turns = metrics["turns"][:-1]  # the last one is the recommendations call
    rtt = EDGE["rtt_s"]
    modeled = [
        rtt * 2 + (t["request_bytes"] + HEADERS) * 8 / EDGE["up_bps"] + (t["response_bytes"] + HEADERS) * 8 / EDGE["down_bps"]
        for t in turns
    ]  # fmt: skip
    assert abs(sum(modeled) / len(modeled) - measured) < 0.1
