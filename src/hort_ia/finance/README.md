# Finance: price forecasting (WBS 9.6)

Monthly price forecasts (R$/kg) for the 5 products of the Conab dataset (`data/market/`),
1 and 3 months ahead. Decision record: 9.6.1-3.

- **Methods** (`models.py`): naive, seasonal naive, 3-month moving average, simple exponential smoothing.
  The service picks, per product and horizon, the candidate (naive, seasonal naive, SES) with the lowest MAE
  in rolling-origin validation (`backtest.py`).
- **Origin** (contract with the finance team, item 5.2.3): every forecast carries `method`, `source` (id in `data/market/sources.json`) and `model_version` (`MODEL_VERSION`; bump it when methods, selection or interval rules change).
- **Interval**: 80% (10th-90th percentile) of the validation errors of the chosen method.
- **Stale series**: CEASA/GO stopped publishing after 2026-06; its series ends there (edges are never extended) and the forecast carries a `warning`.
- **Degraded mode**: series with fewer than 22 months (e.g. CEASA/DF) get a flagged naive forecast with no interval.
- **Limits**: the chosen method is selected and scored on the same validation errors (slightly optimistic MAPE); 25 months of data and strongly correlated series; revisit richer models (ETS, SARIMA, gradient
  boosting) when the dataset has at least 3 years. Only prices are covered; production estimates need another source.

```bash
uv run python -m hort_ia.finance   # validation report (MAPE/MAE per method and horizon)
uv run pytest tests/test_finance_forecast.py -v
```

Endpoint: `GET /finance/price-forecast?product_id=alface&entrepost_id=ceagesp_sp&horizon_months=1`

Docs (decision record, indicator sheet, approach comparison) and the exploratory backtest: `docs/finance/`.
