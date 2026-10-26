"""Market data and reference price endpoints (Conab/Prohort)."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel

from ..market import MarketDataset, get_market_dataset

router = APIRouter(prefix="/market", tags=["market-commercial"])
MODEL_VERSION = "1.0.0"


class ReferencePriceResponse(BaseModel):
    product_id: str
    product_name_pt: str
    entrepost_id: str | None = None
    entrepost_name: str
    reference_month: str
    price_brl_kg: float
    change_prev_month: float | None = None
    is_national_average: bool
    source: str
    model_version: str = MODEL_VERSION


@router.get(
    "/reference-price",
    response_model=ReferencePriceResponse,
    summary="Get current Conab reference price for a product",
    description="Returns wholesale reference price from the local state Ceasa or national average if not available.",
)
async def reference_price(
    product_id: Annotated[str, Query(description="Product ID or crop ID (e.g. 'alface', 'tomate')")],
    dataset: Annotated[MarketDataset, Depends(get_market_dataset)],
    uf: Annotated[str | None, Query(description="State abbreviation (e.g. 'PR', 'SP')")] = None,
) -> ReferencePriceResponse:
    found = dataset.products.get(product_id) or dataset.product_by_crop_id(product_id) or dataset.product_by_alias(product_id)
    if found is None:
        valid_ids = sorted(dataset.products.keys())
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Produto de mercado não encontrado: {product_id!r}. Produtos disponíveis: {valid_ids}",
        )

    local_entrepost = None
    if uf:
        uf_upper = uf.strip().upper()
        local_entrepost = next((e for e in dataset.entrepostos.values() if e.uf == uf_upper), None)

    ref = dataset.reference_price(found.id, local_entrepost.id) if local_entrepost else None
    is_national = False
    entrepost_name = local_entrepost.name_pt if (ref and local_entrepost) else "Média Nacional Ceasa"
    entrepost_id = local_entrepost.id if (ref and local_entrepost) else None

    if ref is None:
        ref = dataset.reference_price(found.id)
        is_national = True

    if ref is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Nenhum preço de referência disponível para o produto: {found.name_pt!r}.",
        )

    source_label = dataset.sources["conab_boletim_hortigranjeiro"].title if "conab_boletim_hortigranjeiro" in dataset.sources else "Conab Prohort"

    return ReferencePriceResponse(
        product_id=found.id,
        product_name_pt=found.name_pt,
        entrepost_id=entrepost_id,
        entrepost_name=entrepost_name,
        reference_month=ref.reference_month,
        price_brl_kg=ref.price_brl_kg,
        change_prev_month=ref.change_prev_month,
        is_national_average=is_national,
        source=source_label,
    )
