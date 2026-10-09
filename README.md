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
├── data/                 # Raw and processed datasets
├── docs/                 # Project documentation (TAP, WBS, etc.)
├── notebooks/            # Jupyter notebooks for EDA and model training
├── models/               # Saved model weights (.pt, .onnx)
├── src/                  # Main source code
│   ├── api/              # FastAPI routes and schemas
│   ├── cv/               # Computer vision for pest/disease detection
│   ├── recommender/      # Agronomic recommendation engine
│   ├── nlp/              # Conversational assistant logic
│   ├── commercial/       # Commercial matching and pricing
│   ├── finance/          # Financial predictive models
│   └── core/             # Telemetry, logging, and utilities
├── tests/                # Unit and integration tests (pytest)
├── pyproject.toml        # Dependencies configuration (managed by uv)
└── uv.lock               # Dependency lockfile
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

Access the interactive API documentation (Swagger UI) at: `http://localhost:8080/docs`

## Testing
Run unit and integration tests using `pytest`:

Example command to run tests for the knowledge base module:
```bash
uv run pytest tests/test_knowledge_base.py -v
```