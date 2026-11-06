"""Conversational assistant (NLP) endpoints (templates & knowledge base)."""

from datetime import datetime
from functools import lru_cache
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from ..core.geo import Region, region_from_ibge_code
from ..knowledge import get_knowledge_base
from ..market import get_market_dataset
from ..nlp import (
    Answer,
    DialogueContext,
    DialogueError,
    DialogueManager,
    Reply,
    Responder,
    get_interpreter,
    load_templates,
)
from ..recommender import get_recommender

router = APIRouter(prefix="/nlp", tags=["nlp-conversational"])


@lru_cache(maxsize=1)
def get_responder() -> Responder:
    """Cached instance for the routes (use as a dependency).

    It takes no arguments on purpose: `lru_cache` hashes its arguments, and the knowledge base and the
    market dataset are not hashable (they hold dicts). Receiving them through `Depends` made every
    call fail with `TypeError: unhashable type: 'dict'`.
    """
    kb = get_knowledge_base()
    return Responder(kb=kb, templates=load_templates(), market=get_market_dataset(), recommender=get_recommender())


@lru_cache(maxsize=1)
def get_dialogue() -> DialogueManager:
    """Cached dialogue manager (trains the intent classifier on first use, about 0.1 s)."""
    return DialogueManager(get_interpreter(), get_responder())


class NlpAnswerRequest(BaseModel):
    intent: str = Field(description="Identified user intent (e.g. 'planting_time', 'companion_planting')")
    crop_id: str | None = Field(default=None, description="Canonical crop ID (e.g. 'alface')")
    ibge_code: int | None = Field(default=None, description="IBGE municipality code (7 digits)")
    region: str | None = Field(default=None, description="Macro-region ('sul', 'sudeste', etc.)")
    month: int = Field(default_factory=lambda: datetime.now().month, ge=1, le=12, description="Reference month (1-12)")
    aspect: str | None = Field(default=None, description="Crop care aspect: 'spacing', 'harvest', 'watering', 'container'")
    small_space: bool = Field(default=False, description="Filter for small space cultivation")
    cv_label: str | None = Field(default=None, description="CV model label for pest/disease")
    entry_id: str | None = Field(default=None, description="Direct ID of pest/disease")
    product: str | None = Field(default=None, description="Product name or ID for market price")
    uf: str | None = Field(default=None, description="User state (e.g. 'PR', 'SP')")
    rotation: bool = Field(default=False, description="Whether inquiry is about crop rotation")


def _resolve_region(ibge_code: int | None, region: str | None) -> Region | None:
    if ibge_code is not None:
        try:
            return region_from_ibge_code(ibge_code)
        except ValueError:
            return None
    if region is not None:
        try:
            return Region(region.strip().lower())
        except ValueError:
            return None
    return None


@router.post(
    "/answer",
    response_model=Answer,
    summary="Generate conversational answer from agronomic/market data",
    description="Fills response templates with curated data. Never alucinates; returns handoff=True when information is missing.",
)
async def generate_answer(
    req: NlpAnswerRequest,
    responder: Annotated[Responder, Depends(get_responder)],
) -> Answer:
    intent = req.intent.strip().lower()
    reg = _resolve_region(req.ibge_code, req.region)

    if intent == "planting_time":
        return responder.planting_time(req.crop_id, reg, req.month)
    elif intent == "what_to_plant":
        return responder.what_to_plant(reg, req.month, req.small_space)
    elif intent == "crop_care":
        return responder.crop_care(req.crop_id, req.aspect)
    elif intent == "companion_planting":
        return responder.companion_planting(req.crop_id, req.rotation)
    elif intent == "pest_disease":
        return responder.pest_disease(req.cv_label, req.entry_id)
    elif intent == "market_price":
        return responder.market_price(req.product or req.crop_id, req.uf)
    elif intent == "help":
        return responder.help()
    elif intent in ("fallback", "general"):
        return responder.fallback()
    else:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"Intenção desconhecida: {req.intent!r}. Intenções válidas: 'planting_time', 'what_to_plant', 'crop_care', 'companion_planting', 'pest_disease', 'market_price', 'help', 'fallback'",
        )


class NlpMessageRequest(BaseModel):
    """A user message in free text, with the garden profile and the context of the previous reply."""

    text: str = Field(min_length=1, max_length=500, description="User message, as typed")
    ibge_code: int | None = Field(default=None, description="IBGE municipality (7 digits) or UF (2 digits) code")
    small_space: bool = Field(default=False, description="The garden is in pots or a small space")
    cv_label: str | None = Field(default=None, description="CV model label, when the message comes with a photo")
    month: int | None = Field(default=None, ge=1, le=12, description="Reference month (default: current)")
    context: DialogueContext | None = Field(default=None, description="`context` of the previous reply, as received")


@router.post(
    "/message",
    response_model=Reply,
    summary="Answer a free-text message (conversational engine)",
    description="Understands the message (intent and entities), decides whether to answer, confirm, ask or fall back, "
    "and answers from curated templates. Stateless: send back the `context` of each reply with the next message. "
    "Decision record: docs/nlu/9.4.1-3_Abordagem_Motor_Conversacional.md.",
)
async def message(
    req: NlpMessageRequest,
    dialogue: Annotated[DialogueManager, Depends(get_dialogue)],
) -> Reply:
    try:
        return dialogue.handle(
            req.text,
            ibge_code=req.ibge_code,
            small_space=req.small_space,
            month=req.month,
            cv_label=req.cv_label,
            context=req.context,
        )
    except DialogueError as err:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(err)) from err
