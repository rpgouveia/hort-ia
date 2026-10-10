"""Financial endpoints: price forecasts for the finance module and the chatbot."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from ..finance import (
    Forecaster,
    PriceForecast,
    UnknownIdError,
    UnsupportedHorizonError,
    get_forecaster,
)

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
    except UnknownIdError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except UnsupportedHorizonError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
