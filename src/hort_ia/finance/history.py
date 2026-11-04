"""Historical price data for the forecast engine (WBS 9.6.1-6).

The engine reads the Conab files by default. When `HORTIA_FINANCE_HISTORY_URL` is set, it reads the
series through the API contract below. The finance team has not sent its API yet, so the contract is
served for now by `hort_ia.finance.mock_history_api`, and its payload names the mock as the source.

    GET {base_url}/history/prices -> {"source": {Source fields}, "prices": [PriceObservation fields]}
"""

from __future__ import annotations

import json
import logging
import os
from urllib.error import URLError
from urllib.request import urlopen

from pydantic import ValidationError

from ..core.sources import Source
from ..market import MarketDataset, get_market_dataset
from ..market.models import PriceObservation

HISTORY_URL_ENV = "HORTIA_FINANCE_HISTORY_URL"
TIMEOUT_SECONDS = 10

logger = logging.getLogger(__name__)


class HistoricalDataError(Exception):
    """The historical data API is unavailable or broke the contract."""


class ApiHistoricalSource:
    def __init__(self, base_url: str, timeout: float = TIMEOUT_SECONDS):
        self.url = f"{base_url.rstrip('/')}/history/prices"
        self.timeout = timeout

    def fetch(self) -> tuple[Source, list[PriceObservation]]:
        try:
            with urlopen(self.url, timeout=self.timeout) as response:
                payload = json.load(response)
            source = Source(**payload["source"])
            prices = [PriceObservation(**row) for row in payload["prices"]]
        except (URLError, TimeoutError, ValueError, KeyError, TypeError, ValidationError) as error:
            raise HistoricalDataError(f"invalid response from {self.url}: {error}") from error
        if not prices:
            raise HistoricalDataError(f"no prices in the response from {self.url}")
        return source, prices

    def load(self, base: MarketDataset) -> MarketDataset:
        """Replace the prices and sources of `base`; the catalogs must already know every id."""
        source, prices = self.fetch()
        seen: set[tuple[str, str, str]] = set()
        for p in prices:
            key = (p.product_id, p.entrepost_id, p.month)
            if key in seen:
                raise HistoricalDataError(f"duplicate price in the response: {key}")
            seen.add(key)
            if p.product_id not in base.products or p.entrepost_id not in base.entrepostos:
                raise HistoricalDataError(f"unknown product or entrepost in the response: {key}")
        return base.model_copy(update={"prices": prices, "sources": {source.id: source}})


def load_history(base: MarketDataset | None = None) -> MarketDataset:
    """Dataset for the engine: the API when configured, the Conab files otherwise or if it fails.

    Falling back keeps the forecast available, and its `source` field still names the data used.
    """
    base = base or get_market_dataset()
    url = os.environ.get(HISTORY_URL_ENV)
    if not url:
        return base
    try:
        return ApiHistoricalSource(url).load(base)
    except HistoricalDataError as error:
        logger.warning("Using the local Conab files: %s", error)
        return base
