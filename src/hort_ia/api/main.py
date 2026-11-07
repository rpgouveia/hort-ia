"""Hort-IA AI Module API

RESTful endpoints for Computer Vision, Financial Forecasting, Agronomic
Recommendations, Conversational NLP, and Market Intelligence.
Built following Design by Contract principles.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from .commercial import router as commercial_router
from .cv import router as cv_router
from .finance import router as finance_router
from .market import router as market_router
from .nlp import get_dialogue
from .nlp import router as nlp_router
from .recommender import router as recommender_router

TAGS_METADATA = [
    {
        "name": "computer-vision",
        "description": "Image quality filtering, standardization (224x224 RGB, LGPD compliant) and phytosanitary diagnosis.",
    },
    {
        "name": "finance",
        "description": "Monthly price forecasting (1 and 3 months ahead) with empirical confidence intervals and backtested accuracy.",
    },
    {
        "name": "recommender",
        "description": "Agronomic recommendation engine: planting calendar by macro-region/IBGE, companion crops, what to plant, and ranked recommendations for a garden profile.",
    },
    {
        "name": "nlp-conversational",
        "description": "Decision support conversational assistant: free-text messages (intent, entities and dialogue), template-based NLG with citations and extensionist handoff.",
    },
    {
        "name": "market-commercial",
        "description": "Conab/Prohort wholesale reference prices by state Ceasa and national average.",
    },
]


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Builds the conversational engine at start-up, so the first user does not wait for the intent
    classifier to train (about 0.1 s of CPU; 1.9 s for the first message on 2G, WBS 9.4.2-4)."""
    get_dialogue()
    yield


app = FastAPI(
    title="Hort-IA AI API",
    description="REST API Gateway for the AI module of the Hort-IA Community Garden Platform. "
    "Designed following Design by Contract (DbC) principles for seamless integration with Java/Spring Boot consumer modules.",
    version="0.2.0",
    openapi_tags=TAGS_METADATA,
    lifespan=lifespan,
    contact={
        "name": "Equipe Hort-IA / Ângelo Piovezan (Líder de Integração e APIs)",
        "email": "angelo.jorgeto@pucpr.edu.br",
    },
)

app.include_router(commercial_router)
app.include_router(cv_router)
app.include_router(finance_router)
app.include_router(recommender_router)
app.include_router(nlp_router)
app.include_router(market_router)


@app.get("/", tags=["health"])
async def root():
    """
    API health check endpoint.
    Returns module status and documentation URLs.
    """
    return {
        "status": "ok",
        "module": "Hort-IA AI Module",
        "message": "Hort-IA AI Module is running!",
        "version": "0.2.0",
        "docs_url": "/docs",
        "openapi_url": "/openapi.json",
    }
