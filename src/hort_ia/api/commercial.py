"""Commercial endpoints: reference prices and price comparison for the backend and the chatbot."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from ..commercial import (
    InvalidParameterError,
    PriceComparator,
    PriceComparison,
    UnknownIdError,
    get_price_comparator,
)

router = APIRouter(prefix="/commercial", tags=["commercial"])


@router.get("/price-comparison", response_model=PriceComparison)
async def price_comparison(
    product_id: str,
    comparator: Annotated[PriceComparator, Depends(get_price_comparator)],
    ibge_code: Annotated[str | None, Query(description="IBGE code, 7 digits (municipality) or 2 (UF)")] = None,
    uf: Annotated[str | None, Query(description="UF abbreviation, used when there is no IBGE code")] = None,
    price_brl_kg: Annotated[float | None, Query(description="Price to classify; omitted returns only the reference")] = None,
) -> PriceComparison:
    """Compare a price (R$/kg) against the Conab reference for the user's location.

    The reference walks the ladder of 9.5.1-3: entrepost in the UF, then median of the macro-region,
    then the weighted national mean. Give the location as `ibge_code` or `uf`, not both.
    """
    try:
        return comparator.compare(product_id, ibge_code=ibge_code, uf=uf, price_brl_kg=price_brl_kg)
    except UnknownIdError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except InvalidParameterError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
