"""Mock of the historical data API (WBS 9.6.1-6), used until the finance team sends the real one.

It serves the Conab series under the contract documented in `history.py`, and names itself as the
source so a forecast built from it can never pass as real integration data.

    uv run uvicorn hort_ia.finance.mock_history_api:app --port 8090
    HORTIA_FINANCE_HISTORY_URL=http://localhost:8090 uv run uvicorn hort_ia.api.main:app --port 8080
"""

from fastapi import FastAPI

from ..core.sources import Source
from ..market import get_market_dataset

MOCK_SOURCE = Source(
    id="mock_finance_history_api",
    title="Mock da API de dados históricos (série Conab)",
    publisher="Módulo de IA do Hort.IA",
    notes="Dados de teste; não vêm da equipe de Planejamento Financeiro.",
)

app = FastAPI(title="Hort-IA historical data mock")


@app.get("/history/prices")
async def prices() -> dict:
    return {
        "source": MOCK_SOURCE.model_dump(),
        "prices": [p.model_dump() for p in get_market_dataset().prices],
    }
