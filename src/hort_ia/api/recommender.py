"""Agronomic recommendation endpoints (Embrapa knowledge base)."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from ..core.geo import Region, region_from_ibge_code
from ..knowledge import KnowledgeBase, get_knowledge_base

router = APIRouter(prefix="/recommender", tags=["recommender"])
MODEL_VERSION = "1.0.0"


class PlantingWindowInfo(BaseModel):
    variant: str | None = None
    recommended_months: list[int]
    harvest_start_days_min: int | None = None
    harvest_start_days_max: int | None = None


class PlantingCalendarResponse(BaseModel):
    crop_id: str
    crop_name_pt: str
    region: str
    windows: list[PlantingWindowInfo]
    source: str
    model_version: str = MODEL_VERSION


class CompanionPartner(BaseModel):
    partner_id: str
    partner_name_pt: str
    evidence: str
    role: str | None = None


class CompanionCropsResponse(BaseModel):
    crop_id: str
    crop_name_pt: str
    helps: list[CompanionPartner]
    hinders: list[CompanionPartner]
    source: str
    model_version: str = MODEL_VERSION


class RecommendedCropItem(BaseModel):
    crop_id: str
    crop_name_pt: str
    family: str | None = None
    cycle_days: str | None = None


class WhatToPlantResponse(BaseModel):
    month: int
    region: str
    small_space: bool
    recommended_crops: list[RecommendedCropItem]
    source: str
    model_version: str = MODEL_VERSION


def _resolve_region(ibge_code: int | str | None, region: str | None) -> Region:
    if ibge_code is not None:
        try:
            return region_from_ibge_code(ibge_code)
        except ValueError as err:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Código IBGE inválido: {err}",
            ) from err

    if region is not None:
        try:
            return Region(region.strip().lower())
        except ValueError as err:
            valid = [r.value for r in Region]
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Região inválida ({region}). Opções válidas: {valid}",
            ) from err

    raise HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail="É necessário informar ao menos 'ibge_code' ou 'region'.",
    )


@router.get(
    "/planting-calendar",
    response_model=PlantingCalendarResponse,
    summary="Get planting calendar windows for a crop",
    description="Returns recommended planting months and harvest time windows based on Brazilian macro-region or IBGE code.",
)
async def planting_calendar(
    crop_id: Annotated[str, Query(description="Canonical crop ID (e.g., 'alface', 'tomate')")],
    kb: Annotated[KnowledgeBase, Depends(get_knowledge_base)],
    ibge_code: Annotated[int | None, Query(description="IBGE municipality (7 digits) or UF (2 digits) code")] = None,
    region: Annotated[str | None, Query(description="Brazilian macro-region ('sul', 'sudeste', etc.)")] = None,
) -> PlantingCalendarResponse:
    crop = kb.crops.get(crop_id)
    if crop is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Cultura não encontrada: {crop_id!r}. Culturas disponíveis: {sorted(kb.crops.keys())}",
        )

    resolved_region = _resolve_region(ibge_code, region)
    windows_info: list[PlantingWindowInfo] = []

    for window in crop.planting_windows:
        if resolved_region in window.months_by_region:
            months = window.months_by_region[resolved_region]
            windows_info.append(
                PlantingWindowInfo(
                    variant=window.variant,
                    recommended_months=months,
                    harvest_start_days_min=window.harvest_start_days.min if window.harvest_start_days else None,
                    harvest_start_days_max=window.harvest_start_days.max if window.harvest_start_days else None,
                )
            )

    source_label = crop.sources[0].source_id if crop.sources else "embrapa"
    return PlantingCalendarResponse(
        crop_id=crop.id,
        crop_name_pt=crop.name_pt,
        region=resolved_region.value,
        windows=windows_info,
        source=source_label,
    )


@router.get(
    "/companion-crops",
    response_model=CompanionCropsResponse,
    summary="Get companion planting recommendations (consórcio)",
    description="Returns beneficial and antagonistic companion plants with evidence levels (scientific or traditional).",
)
async def companion_crops(
    crop_id: Annotated[str, Query(description="Canonical crop ID (e.g., 'tomate')")],
    kb: Annotated[KnowledgeBase, Depends(get_knowledge_base)],
) -> CompanionCropsResponse:
    crop = kb.crops.get(crop_id)
    if crop is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Cultura não encontrada: {crop_id!r}.",
        )

    helps: list[CompanionPartner] = []
    hinders: list[CompanionPartner] = []

    for rel in kb.companions_of(crop.id):
        partner_id = rel.crop_b if rel.crop_a == crop.id else rel.crop_a
        partner_crop = kb.crops.get(partner_id)
        partner_name = partner_crop.name_pt if partner_crop else partner_id

        # Check role if repellent
        role = None
        if partner_crop and any(r.role == "pest_repellent" for r in partner_crop.companion_roles):
            role = "pest_repellent"

        partner_item = CompanionPartner(
            partner_id=partner_id,
            partner_name_pt=partner_name,
            evidence=rel.evidence.value if hasattr(rel.evidence, "value") else str(rel.evidence),
            role=role,
        )

        if rel.relation == "helps":
            helps.append(partner_item)
        else:
            hinders.append(partner_item)

    source_label = kb.sources["kaggle_companion_plants"].title if "kaggle_companion_plants" in kb.sources else "companion_dataset"
    return CompanionCropsResponse(
        crop_id=crop.id,
        crop_name_pt=crop.name_pt,
        helps=sorted(helps, key=lambda x: x.partner_name_pt),
        hinders=sorted(hinders, key=lambda x: x.partner_name_pt),
        source=source_label,
    )


@router.get(
    "/what-to-plant",
    response_model=WhatToPlantResponse,
    summary="Recommend crops to plant in a given month and region",
    description="Returns list of crops that can be planted in the specified month and location, optionally filtering for small spaces.",
)
async def what_to_plant(
    month: Annotated[int, Query(ge=1, le=12, description="Month of the year (1-12)")],
    kb: Annotated[KnowledgeBase, Depends(get_knowledge_base)],
    ibge_code: Annotated[int | None, Query(description="IBGE municipality code")] = None,
    region: Annotated[str | None, Query(description="Brazilian macro-region")] = None,
    small_space: Annotated[bool, Query(description="Filter only crops suitable for small spaces / containers")] = False,
) -> WhatToPlantResponse:
    resolved_region = _resolve_region(ibge_code, region)
    recommended: list[RecommendedCropItem] = []

    for crop in kb.crops.values():
        by_variant = crop.planting_months(resolved_region) or {}
        if any(month in months for months in by_variant.values()):
            if small_space and crop.small_space_recommended is not True:
                continue

            cycle_str = None
            if crop.planting_windows:
                days = [w.harvest_start_days for w in crop.planting_windows if w.harvest_start_days]
                if days:
                    cycle_str = f"{min(d.min for d in days)} a {max(d.max for d in days)} dias"

            recommended.append(
                RecommendedCropItem(
                    crop_id=crop.id,
                    crop_name_pt=crop.name_pt,
                    family=crop.family,
                    cycle_days=cycle_str,
                )
            )

    return WhatToPlantResponse(
        month=month,
        region=resolved_region.value,
        small_space=small_space,
        recommended_crops=sorted(recommended, key=lambda x: x.crop_name_pt),
        source="embrapa_ct_47_hortalicas",
    )
