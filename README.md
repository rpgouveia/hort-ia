# Hort-IA AI Module

AI Module for a Community Garden Management Application, designed to integrate with a Java/Spring Boot backend via REST APIs.

## Features
- **Computer Vision**: Pest and disease identification using PyTorch and OpenCV.
- **Agronomic Recommender**: Personalized crop management recommendations.
- **Conversational Assistant**: Lightweight NLP-based decision support.
- **Commercial Matching**: Matchmaking algorithms between producers and buyers.
- **Financial Predictive Models**: Revenue and ROI forecasting.

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
│       ├── commercial/   # Commercial matching and pricing
│       ├── finance/      # Financial predictive models
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
| NLU dataset for the conversational assistant (8 intents, training + held-out test set) | `data/nlu/` | `hort_ia.nlp` | [data/nlu/README.md](data/nlu/README.md) |

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
| `tests/test_knowledge_base.py` | Knowledge base integrity: crop scope, CV label mapping, planting windows, companion relations, regional planting months |
| `tests/test_market_dataset.py` | Market dataset integrity: scope, reference month, missing data, rounding, `crop_id` links to the knowledge base |
| `tests/test_geo.py` | IBGE municipality/UF code → region, shared `Region` across datasets |
| `tests/test_nlu_dataset.py` | NLU dataset: agreed intent set, 30-50 examples per intent, duplicates, crop coverage, no train/test leakage |

Run a single file, e.g.:

```bash
uv run pytest tests/test_geo.py -v
```

Print the knowledge base completeness report, and the market dataset coverage report:
```bash
uv run python -m hort_ia.knowledge
uv run python -m hort_ia.market
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