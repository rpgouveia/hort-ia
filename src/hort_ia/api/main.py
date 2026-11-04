"""Hort-IA AI Module API

RESTful endpoints for Computer Vision, Financial Forecasting, Agronomic
Recommendations, Conversational NLP, and Market Intelligence.
Built following Design by Contract principles.
"""

from fastapi import FastAPI

from .cv import router as cv_router
from .finance import router as finance_router
from .market import router as market_router
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
        "description": "Agronomic recommendation engine: planting calendar by macro-region/IBGE, companion crops, and what to plant.",
    },
    {
        "name": "nlp-conversational",
        "description": "Decision support conversational assistant: template-based NLG with citations and extensionist handoff.",
    },
    {
        "name": "market-commercial",
        "description": "Conab/Prohort wholesale reference prices by state Ceasa and national average.",
    },
]

app = FastAPI(
    title="Hort-IA AI API",
    description="REST API Gateway for the AI module of the Hort-IA Community Garden Platform. "
    "Designed following Design by Contract (DbC) principles for seamless integration with Java/Spring Boot consumer modules.",
    version="0.2.0",
    openapi_tags=TAGS_METADATA,
    contact={
        "name": "Equipe Hort-IA / Ângelo Piovezan (Líder de Integração e APIs)",
        "email": "angelo.jorgeto@pucpr.edu.br",
    },
)

# Register routers for all AI subproject domains
app.include_router(cv_router)
app.include_router(finance_router)
app.include_router(recommender_router)
app.include_router(nlp_router)
app.include_router(market_router)


@app.get("/", tags=["health"])
async def root():
    """API health check and module status."""
    return {
        "status": "ok",
        "module": "Hort-IA AI Module",
        "version": "0.2.0",
        "docs_url": "/docs",
        "openapi_url": "/openapi.json",
    }
