"""
Hort-IA AI Module API
This module provides RESTful endpoints for computer vision, 
recommendations, NLP, and financial predictions.
"""

from fastapi import FastAPI

from .cv import router as cv_router
from .finance import router as finance_router

app = FastAPI(
    title="Hort-IA AI API",
    description="APIs for the AI module of the Hort-IA platform",
    version="0.1.0"
)

app.include_router(finance_router)
app.include_router(cv_router)


@app.get("/")
async def root():
    """
    API health check endpoint.
    Returns a simple message if the server is running successfully.
    """
    return {"status": "ok", "message": "Hort-IA AI Module is running!"}

# TODO: Add endpoints for CV, Recommender, NLP, Commercial, and Finance
