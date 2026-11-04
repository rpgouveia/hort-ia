"""Integration tests of the forecast engine with the historical data (9.6.2-3).

Everything runs over real HTTP against servers started here. Plan: docs/finance/9.6.2-1.
"""

import json
import shutil
import socket
import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from socketserver import TCPServer
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import urlopen

import pytest
import uvicorn

from hort_ia.api.main import app as api_app
from hort_ia.finance import ApiHistoricalSource, Forecaster, HistoricalDataError, load_history
from hort_ia.finance.history import HISTORY_URL_ENV
from hort_ia.finance.mock_history_api import MOCK_SOURCE
from hort_ia.finance.mock_history_api import app as mock_app
from hort_ia.market import get_market_dataset, load_market_dataset
from hort_ia.market.loader import market_dir

VOLATILE = {"source"}


@contextmanager
def serve(app) -> Iterator[str]:
    """Run an ASGI app with uvicorn on a free port and yield its base URL."""
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    server = uvicorn.Server(uvicorn.Config(app, log_level="error"))
    thread = threading.Thread(target=server.run, kwargs={"sockets": [sock]}, daemon=True)
    thread.start()
    while not server.started:
        time.sleep(0.01)
    try:
        yield f"http://127.0.0.1:{sock.getsockname()[1]}"
    finally:
        server.should_exit = True
        thread.join(timeout=5)
        sock.close()


@contextmanager
def serve_raw(status: int, body: bytes) -> Iterator[str]:
    """A misbehaving history API: every GET answers with the given status and body."""

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(status)
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    server = TCPServer(("127.0.0.1", 0), Handler)  # HTTPServer would do a slow reverse DNS lookup
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}"
    finally:
        server.shutdown()
        server.server_close()


def payload(prices: list[dict]) -> bytes:
    return json.dumps({"source": MOCK_SOURCE.model_dump(), "prices": prices}).encode()


ROW = {"product_id": "alface", "entrepost_id": "ceagesp_sp", "month": "2026-08", "price_brl_kg": 3.2}


@pytest.fixture(scope="module")
def mock_url() -> Iterator[str]:
    with serve(mock_app) as url:
        yield url


@pytest.fixture(scope="module")
def api_url() -> Iterator[str]:
    with serve(api_app) as url:
        yield url


def get_json(base: str, path: str, **params) -> tuple[int, dict]:
    url = f"{base}{path}?{urlencode(params)}"
    try:
        with urlopen(url, timeout=30) as response:
            return response.status, json.load(response)
    except HTTPError as error:
        return error.code, json.load(error)


# --- history API -> engine ---


def test_mock_api_serves_the_whole_conab_series(mock_url):
    source, prices = ApiHistoricalSource(mock_url).fetch()
    assert source.id == MOCK_SOURCE.id
    assert len(prices) == len(get_market_dataset().prices)


def test_forecast_from_the_api_matches_the_files_and_names_the_mock(mock_url):
    local = Forecaster(get_market_dataset())
    remote = Forecaster(ApiHistoricalSource(mock_url).load(get_market_dataset()))
    assert remote.series == local.series
    for args in [("alface", "ceagesp_sp", 1), ("tomate", "ceasa_go_goiania", 3), ("alface", "ceasa_df_brasilia", 1)]:
        from_api, from_files = remote.forecast(*args), local.forecast(*args)
        assert from_api.model_dump(exclude=VOLATILE) == from_files.model_dump(exclude=VOLATILE)
        assert from_api.source == MOCK_SOURCE.id != from_files.source


def test_load_history_uses_the_api_when_configured(mock_url, monkeypatch):
    monkeypatch.setenv(HISTORY_URL_ENV, mock_url)
    assert list(load_history().sources) == [MOCK_SOURCE.id]


def test_load_history_uses_the_files_by_default(monkeypatch):
    monkeypatch.delenv(HISTORY_URL_ENV, raising=False)
    assert load_history() is get_market_dataset()


def test_load_history_falls_back_to_the_files_and_logs(monkeypatch):
    warnings = []
    monkeypatch.setattr("hort_ia.finance.history.logger.warning", lambda *args: warnings.append(args))
    with serve_raw(500, b"down") as url:
        monkeypatch.setenv(HISTORY_URL_ENV, url)
        dataset = load_history()
    assert dataset is get_market_dataset()
    assert "local Conab files" in warnings[0][0]


def test_unreachable_api_raises():
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    with pytest.raises(HistoricalDataError):
        ApiHistoricalSource(f"http://127.0.0.1:{port}", timeout=1).fetch()


@pytest.mark.parametrize(
    "status,body",
    [
        (500, b"down"),
        (200, b"not json"),
        (200, b"[]"),
        (200, b'{"prices": []}'),
        (200, payload([])),
        (200, payload([{**ROW, "price_brl_kg": -1}])),
        (200, payload([{**ROW, "month": "agosto"}])),
        (200, payload([{**ROW, "product_id": "banana"}])),
        (200, payload([{**ROW, "entrepost_id": "ceasa_inexistente"}])),
        (200, payload([ROW, ROW])),
    ],
    ids=["500", "not-json", "not-object", "no-source", "empty", "negative-price", "bad-month",
         "unknown-product", "unknown-entrepost", "duplicate"],
)
def test_contract_violations_raise(status, body):
    with serve_raw(status, body) as url:
        with pytest.raises(HistoricalDataError):
            ApiHistoricalSource(url).load(get_market_dataset())


# --- files -> pipeline: monthly update ---


def test_new_month_in_the_files_moves_the_forecast(tmp_path: Path):
    """Decision record: the validation is re-run at each monthly update of the dataset."""
    directory = tmp_path / "market"
    shutil.copytree(market_dir(), directory)
    with (directory / "prices_monthly.csv").open("a", encoding="utf-8") as f:
        f.write("alface,ceagesp_sp,2026-09,4.00\n")
    before = Forecaster(get_market_dataset()).forecast("alface", "ceagesp_sp", 1)
    updated = Forecaster(load_market_dataset(directory))
    after = updated.forecast("alface", "ceagesp_sp", 1)
    assert before.reference_month == "2026-08" and after.reference_month == "2026-09"
    assert after.last_price_brl_kg == 4.00
    assert updated.latest == "2026-09"
    # series that did not get the new month are now flagged as stale
    assert "2026-08" in updated.forecast("batata", "ceagesp_sp", 1).warning


# --- full path: HTTP client -> route -> service -> pipeline -> files ---


def test_route_returns_the_contract_over_http(api_url):
    status, body = get_json(api_url, "/finance/price-forecast", product_id="alface", entrepost_id="ceagesp_sp")
    assert status == 200
    assert set(body) == {
        "product_id", "entrepost_id", "horizon_months", "reference_month", "target_month",
        "last_price_brl_kg", "forecast_price_brl_kg", "change_pct", "lower_brl_kg", "upper_brl_kg",
        "method", "validation_mape", "source", "model_version", "degraded", "warning",
    }
    assert body["source"] == "conab_boletim_hortigranjeiro"
    assert body["lower_brl_kg"] <= body["forecast_price_brl_kg"] <= body["upper_brl_kg"]


@pytest.mark.parametrize("horizon", [1, 3])
def test_every_validated_series_answers_over_http(api_url, horizon):
    forecaster = Forecaster(get_market_dataset())
    for product, entrepost in sorted(forecaster.series)[:: len(forecaster.series) // 5]:
        status, body = get_json(
            api_url, "/finance/price-forecast", product_id=product, entrepost_id=entrepost, horizon_months=horizon
        )
        assert status == 200 and body["forecast_price_brl_kg"] > 0 and not body["degraded"]


def test_stale_series_over_http(api_url):
    status, body = get_json(api_url, "/finance/price-forecast", product_id="tomate", entrepost_id="ceasa_go_goiania")
    assert status == 200 and "2026-06" in body["warning"] and not body["degraded"]


def test_degraded_series_over_http(api_url):
    status, body = get_json(api_url, "/finance/price-forecast", product_id="alface", entrepost_id="ceasa_df_brasilia")
    assert status == 200 and body["degraded"] and body["lower_brl_kg"] is None


@pytest.mark.parametrize(
    "params,expected",
    [
        ({"product_id": "banana", "entrepost_id": "ceagesp_sp"}, 404),
        ({"product_id": "alface", "entrepost_id": "ceasa_inexistente"}, 404),
        ({"product_id": "alface", "entrepost_id": "ceagesp_sp", "horizon_months": 2}, 422),
        ({"product_id": "alface", "entrepost_id": "ceagesp_sp", "horizon_months": "x"}, 422),
        ({"entrepost_id": "ceagesp_sp"}, 422),
    ],
)
def test_invalid_requests_over_http(api_url, params, expected):
    status, body = get_json(api_url, "/finance/price-forecast", **params)
    assert status == expected and body["detail"]
