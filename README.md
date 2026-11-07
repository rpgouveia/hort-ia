# Hort-IA AI Module

AI Module for a Community Garden Management Application, designed to integrate with a Java/Spring Boot backend via REST APIs.

## Features
- **Computer Vision**: Pest and disease identification using PyTorch and OpenCV.
- **Agronomic Recommender**: Personalized crop management recommendations.
- **Conversational Assistant**: Lightweight NLP-based decision support.
- **Commercial Matching**: Price comparison against the closest Conab reference (UF → macro-region → national), with matchmaking between producers and buyers planned.
- **Financial Predictive Models**: Monthly price forecasts (1 and 3 months ahead) for the Conab products, with intervals and per-product method selection. Revenue and ROI forecasting are planned.

## Tech Stack
- **Language**: Python 3.14
- **Dependency Management**: `uv`
- **API Framework**: FastAPI
- **Machine Learning / Data**: PyTorch, OpenCV, Scikit-learn, Pandas

## Project Structure
```text
hort-ia/
├── data/                 # Datasets (only the curated ones below are versioned)
│   ├── knowledge/        # Agronomic knowledge base (crops, guidelines, pests, companions)
│   ├── market/           # Conab market dataset (prices, volumes, supply)
│   ├── finance/          # Financial dataset (planned)
│   └── nlu/              # NLU training data for the conversational assistant
├── docs/                 # Project documentation (TAP, WBS, etc.)
│   ├── commercial/       # WBS 9.5.1-3: approach and decision record for price comparison and matching
│   ├── data/             # WBS 9.1.2: data treatment, LGPD and anonymisation reports
│   ├── finance/          # WBS 9.6.1: approach comparison, indicator sheet, decision record
│   └── nlu/              # Interview script for agronomists
├── notebooks/            # Jupyter notebooks for EDA and model training
├── models/               # Saved model weights (.pt, .onnx)
├── src/
│   └── hort_ia/          # Main package
│       ├── api/          # FastAPI routes and schemas
│       ├── knowledge/    # Shared agronomic knowledge base (used by recommender, nlp and cv)
│       ├── market/       # Conab market dataset (prices, volumes, supply) used by commercial
│       ├── cv/           # Computer vision for pest/disease detection
│       ├── recommender/  # Agronomic recommendation engine
│       ├── nlp/          # Conversational assistant logic
│       ├── commercial/   # Reference prices and price comparison (matching engine planned)
│       ├── finance/      # Price forecasting (naive, seasonal naive, SES) with rolling-origin validation
│       └── core/         # Shared building blocks: source models, Brazilian geography (IBGE → region)
├── scripts/              # One-off dataset generators (kept for traceability)
├── tests/                # Unit and integration tests (pytest)
├── pyproject.toml        # Dependencies configuration (managed by uv)
└── uv.lock               # Dependency lockfile
```

## Datasets

Three curated datasets are versioned, each with its own loader:

| Dataset | Directory | Loader | Details |
|---|---|---|---|
| Agronomic knowledge base (15 MVP crops, guidelines, pests/diseases, companion planting) | `data/knowledge/` | `hort_ia.knowledge` | [data/knowledge/README.md](data/knowledge/README.md) |
| Conab market dataset (prices, volumes, supply in 12 Ceasas) | `data/market/` | `hort_ia.market` | [data/market/README.md](data/market/README.md) |
| NLU dataset and response templates for the conversational assistant (8 intents) | `data/nlu/` | `hort_ia.nlp` | [data/nlu/README.md](data/nlu/README.md) |

The knowledge and market datasets have their own `sources.json` registry, and every record cites its source. The market dataset loads on its own and only touches the knowledge
base to check its `crop_id` links.

**Regional adaptation.** Planting windows are given per macro-region. `hort_ia.core.geo` converts
the user's IBGE municipality code into one of the five regions, with no lookup table:

```python
from hort_ia.core import region_from_ibge_code
from hort_ia.knowledge import load_knowledge_base

region = region_from_ibge_code(4106902)  # Curitiba -> PR -> Region.SUL
load_knowledge_base().crops["alface"].planting_months(region)
# {"inverno": [2, ..., 10], "verao": [1, ..., 12]}; [] = "não recomendável", None = no data
```

## Agronomic recommendation

`hort_ia.recommender` tells a grower what to plant now, given the garden: location, month, small
space, what is already planted and the previous crop of the bed. Study, approach and decision
record: [docs/recommender/](docs/recommender/) · module notes: [src/hort_ia/recommender/README.md](src/hort_ia/recommender/README.md).

- **Knowledge-based**: hard filters on the knowledge base — no data for the region, out of season, unsuited to small spaces, already planted, same family as the previous crop (rotation) — each exclusion with its reason. There is no interaction history yet, so nothing is learned.
- **Score**: +1 per planted crop it combines with, −1 per planted crop it does not, +0.5 for a pest-repellent crop when something is planted. Companion relations only order the list because they are traditional; rotation excludes because it has a technical source.
- **Order**: score, then the season that ends first, then the name. Deterministic.
- **Output**: ranked crops with `reasons` and `warnings` (code, Portuguese text, source), excluded crops with their reason, `approach` and `model_version`.
- **Same engine everywhere**: `GET /recommender/what-to-plant` and the conversational assistant take their lists from it.

```bash
curl -X POST http://localhost:8080/recommender/recommendations -H "Content-Type: application/json" \
  -d '{"ibge_code": 4106902, "month": 11, "small_space": true, "planted": ["tomate"]}'
```

An invalid or missing location, or a month outside 1-12, returns 422. Unknown crops in the profile
are ignored and reported in `warnings`.

## Price comparison

`hort_ia.commercial` tells a grower or a buyer how their price compares with the closest Conab
reference available for their location, for the five quoted products. Approach and decision record:
[docs/commercial/](docs/commercial/) · module notes: [src/hort_ia/commercial/README.md](src/hort_ia/commercial/README.md).

- **Reference ladder**: entrepost(s) in the user's **UF** (median when the UF has more than one, as São Paulo does) → **median of the macro-region**, carrying the observed min-max → **weighted national mean**. An entrepost deviates from that national mean by 19.7% at the median and up to 146%, which is why the reference has to be local.
- **Tolerance band**: the product's own volatility, measured on the price history rather than fixed in the code — alface 8%, batata 11%, cenoura 12%, cebola 13%, tomate 16%. At the national level, a flat ±30% with `degraded` set.
- **Output**: reference level and entrepostos used, reference price and month, band, `deviation_pct`, position (`abaixo_da_faixa` / `na_faixa` / `acima_da_faixa`), published monthly change, `confidence` (1.00 local, 0.70 regional, 0.40 national), data `source`, `model_version`, `degraded` and `warning`. Omit the price and the answer carries only the reference and the band.
- **Edge cases**: an entrepost up to 3 months behind is used from the last observed month with a wider band and a `warning` (CEASA/GO, 2026-06); further behind it is discarded and the ladder descends (CEASA/DF, 22 months). The Centro-Oeste has no regional reference, because its two Ceasas are exactly those two.
- **Stateless**: no offer or demand is stored and no personal data reaches the module (9.1.2-4/-7). The engine is deterministic because the project has no negotiation history to learn a ranking from.

```bash
curl "http://localhost:8080/commercial/price-comparison?product_id=alface&ibge_code=4106902&price_brl_kg=4.30"
```

Give the location as `ibge_code` or `uf`, not both. Unknown product (a crop with no Conab quote) or
unknown location returns 404, and a malformed or out-of-range parameter returns 422.

## Price forecasting

`hort_ia.finance` forecasts the monthly price (R$/kg) of the five Conab products (alface, batata,
cebola, cenoura, tomate) at each Ceasa, 1 and 3 months ahead, from `data/market/prices_monthly.csv`.

- **Methods**: naive, seasonal naive and simple exponential smoothing (a 3-month moving average is also available). For each product and horizon the service picks the method with the lowest MAE in rolling-origin validation.
- **Output**: forecast price, change versus the last price, 80% interval (from the validation errors), method, validation MAPE, reference month, data `source` and `model_version`.
- **Edge cases**: series with fewer than 22 months (e.g. CEASA/DF) get a flagged naive forecast with no interval (`degraded`); series that stopped publishing (e.g. CEASA/GO after 2026-06) are forecast from their real end and carry a `warning`.
- **Validation baseline** (55 series, 25 months): MAPE 18.6% at 1 month and 28.2% at 3 months. The history is short, so richer models (ETS, SARIMA, gradient boosting) are postponed. Rationale: [docs/finance/](docs/finance/) and [src/hort_ia/finance/README.md](src/hort_ia/finance/README.md).

```bash
curl "http://localhost:8080/finance/price-forecast?product_id=alface&entrepost_id=ceagesp_sp&horizon_months=1"
```

Unknown product or entrepost returns 404, and a horizon other than 1 or 3 returns 422.

## API Endpoints (Design by Contract)

The API is built using FastAPI following strict *Design by Contract* (DbC) principles. Technical specifications: [docs/api/](docs/api/).

| Endpoint | Method | Domain / Consumer Module | Description |
|---|:---:|---|---|
| `/cv/validate` | `POST` | Computer Vision (Assistência Técnica) | Quality filter checking blur, lighting and contrast |
| `/cv/preprocess` | `POST` | Computer Vision (Assistência Técnica) | Standardizes to 224x224 RGB JPEG (<30KB) and strips EXIF |
| `/finance/price-forecast` | `GET` | Price Forecasting (Financeiro) | Forecasts monthly price (1 and 3 months ahead) with 80% interval |
| `/recommender/planting-calendar` | `GET` | Agronomic Recommender (Gestão / Assistência) | Regional planting windows by IBGE municipality code or macro-region |
| `/recommender/companion-crops` | `GET` | Agronomic Recommender (Gestão de Operação) | Beneficial and antagonistic companion crops (consórcios) |
| `/recommender/what-to-plant` | `GET` | Agronomic Recommender (Gestão / Assistência) | Recommended crops for the current month/location (optional small space filter), from the recommendation engine |
| `/recommender/recommendations` | `POST` | Agronomic Recommender (Gestão / Assistência) | Ranked crops for a garden profile, with reasons, sources and excluded crops |
| `/nlp/answer` | `POST` | Conversational Assistant (Assistência Técnica) | Template-based answers with citation and extensionist handoff flag |
| `/nlp/message` | `POST` | Conversational Assistant (Assistência Técnica) | Free-text message: understands intent and entities, answers, confirms or asks back; stateless `context` round trip |
| `/market/reference-price` | `GET` | Market Intelligence (Comercialização) | Wholesale reference price by state Ceasa or national average |

Interactive Swagger documentation is available at `http://localhost:8080/docs`.

## Setup and Installation

1. Install `uv` (Python Package Manager):
   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```
2. Clone this repository and navigate to the root folder.
3. Install dependencies and create the virtual environment automatically:
   ```bash
   uv sync
   ```

## Running the API

Run the FastAPI server using `uvicorn`. We recommend using port 8080 to avoid conflicts with other services:

```bash
uv run uvicorn hort_ia.api.main:app --reload --port 8080
```

Alternatively, use the project entry point (no auto-reload):

```bash
uv run hort-ia
```

> **Note:** in non-editable installs (e.g. Docker with `uv sync --no-editable`), set the `HORTIA_KB_DIR` environment variable to the `data/knowledge` directory and `HORTIA_MARKET_DIR` to `data/market` so both datasets can be found.

Access the interactive API documentation (Swagger UI) at: `http://localhost:8080/docs`

## Testing

Run the whole suite with `pytest`:

```bash
uv run pytest -v
```

| Test file | What it covers |
|---|---|
| `tests/test_api_contracts.py` | API contract validation: status codes (200, 404, 415, 422), parameter validation and endpoint responses |
| `tests/test_knowledge_base.py` | Knowledge base integrity: crop scope, CV label mapping, planting windows, companion relations, regional planting months |
| `tests/test_market_dataset.py` | Market dataset integrity: scope, reference month, missing data, rounding, `crop_id` links to the knowledge base |
| `tests/test_geo.py` | IBGE municipality/UF code → region, shared `Region` across datasets |
| `tests/test_nlu_dataset.py` | NLU dataset: agreed intent set, 30-50 examples per intent, duplicates, crop coverage, no train/test leakage |
| `tests/test_finance_forecast.py` | Forecasting methods, series building (edges never extended), validation without look-ahead, decision-record numbers and error targets, degraded and stale series, API contract |
| `tests/test_finance_calibration.py` | SES alpha per horizon, validation window, error targets per scenario, out-of-sample numbers |
| `tests/test_finance_integration.py` | Forecast engine over real HTTP: historical data API contract and fallback, monthly dataset update, `/finance/price-forecast` end to end |
| `tests/test_recommender_engine.py` | Recommendation engine: reference cases of 9.3.1-3, properties over all 120 region × month × small-space profiles, score recomputed from the raw files, ordering, CLI |
| `tests/test_recommender_integration.py` | Knowledge files → engine → routes for every profile, data-only changes reaching the API, 422s, `what-to-plant`, the assistant and the other recommender routes agreeing with the engine |
| `tests/test_nlu_interpreter.py` | Message understanding: reference messages of 9.4.1-3, confidence bands, entity rule, crops (aliases, typos, order), month, care aspect, location, classifier figures of the study |
| `tests/test_nlu_dialogue.py` | Dialogue manager and `POST /nlp/message`: reference conversations of 9.4.1-3, confidence bands, pending questions, crop inheritance, location, context without user text |
| `tests/test_nlu_answers.py` | Answer generation: every intent answered from the data, handoff when data is missing, no unfilled template, a source in every technical answer (all crops × regions × aspects, products × states, CV labels) |
| `tests/test_nlu_acceptance.py` | Acceptance criterion of 9.4.1 on the held-out test set (skipped until it has 10 utterances per intent) and threshold calibration |
| `tests/test_nlu_integration.py` | Assistant over HTTP against its content: months of every crop in every region, every alias, prices of every product in every state, every CV label, data-only changes, reference conversations, agreement with `/nlp/answer` and the recommender routes |
| `tests/test_nlu_slow_connection.py` | Reply and request size budgets, and modeled time below 5 s on 2G with a new HTTPS connection per message (9.4.2-4) |
| `tests/test_nlu_properties.py` | Every training sentence and hard inputs as first message and as reply: valid reply, no user text in the context, confidence bands, time, CLI |
| `tests/test_cv_pipeline.py` | Computer Vision quality filtering, 224x224 standardization, EXIF removal (LGPD) and API endpoints |
| `tests/test_privacy_compliance.py` | LGPD consent validation, facial blurring, text PII anonymization |

Run a single file, e.g.:

```bash
uv run pytest tests/test_geo.py -v
```

Print the knowledge base completeness report, and the market dataset coverage report:
```bash
uv run python -m hort_ia.knowledge
uv run python -m hort_ia.market
```

Print the price forecasting validation report (MAPE/MAE per method and horizon):
```bash
uv run python -m hort_ia.finance
```

Recommend crops for a garden profile, with reasons and exclusions:
```bash
uv run python -m hort_ia.recommender --ibge 4106902 --month 11 --small-space --planted tomate
```

Print the measured tolerance bands and staleness drift of the price comparison, and the reference
level each UF reaches:
```bash
uv run python -m hort_ia.commercial
```

Show what the assistant understands of a message (intent, confidence, entities):
```bash
uv run python -m hort_ia.nlp "qndo plantar alfase?"
```

Measure the acceptance criterion of the assistant on the held-out test set, per intent, with the
threshold calibration table:
```bash
uv run python scripts/evaluate_nlu_engine.py
```

Measure the assistant's response time through a throttling proxy (4G to 2G and a stress profile):
```bash
uv run python scripts/measure_slow_connection.py
```

Evaluate the NLU dataset with a baseline classifier (cross-validation, plus the held-out test set when filled):
```bash
uv run python scripts/evaluate_nlu_baseline.py
```

## Rebuilding the datasets

The generators in `scripts/` document how each file was transcribed. Raw inputs are not versioned
(`data/*` is ignored except the curated datasets); `openpyxl` comes with the dev dependencies.

```bash
uv run python scripts/build_crops_v1.py                       # data/knowledge/crops.json
uv run python scripts/build_companions_v1.py path/to/companion_plants.csv
uv run python scripts/build_market_v1.py path/to/boletim.xlsx # data/market/
```