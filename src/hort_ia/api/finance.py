"""Financial endpoints: price forecasts for the finance module and the chatbot."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from ..finance import ForecastError, Forecaster, PriceForecast, get_forecaster

router = APIRouter(prefix="/finance", tags=["finance"])


@router.get("/price-forecast", response_model=PriceForecast)
async def price_forecast(
    product_id: str,
    entrepost_id: str,
    forecaster: Annotated[Forecaster, Depends(get_forecaster)],
    horizon_months: Annotated[int, Query()] = 1,
) -> PriceForecast:
    """Forecast the monthly price (R$/kg) of a product at an entrepost, 1 or 3 months ahead."""
    try:
        return forecaster.forecast(product_id, entrepost_id, horizon_months)
    except ForecastError as error:
        status = 422 if "horizon" in str(error) else 404
        raise HTTPException(status_code=status, detail=str(error)) from error
