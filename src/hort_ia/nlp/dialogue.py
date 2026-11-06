"""Dialogue manager of the conversational assistant (WBS 9.4.1-5).

Implements `docs/nlu/9.4.1-3_Abordagem_Motor_Conversacional.md`, sections 4.4 and 5: given a message,
the garden profile and the context returned by the previous turn, decides whether to answer, confirm,
ask or fall back, and returns the reply with a new context.

- **Stateless** (decision D6): nothing is kept on the server. The context travels with each request
  and holds identifiers only (intent, crop id, pending question), never the user's text (LGPD).
- **Pending question first** (D7): a short reply ("sim", "tomate", "PR") is read as the answer to the
  assistant's last question before it is classified as a new message.
- **Crop inheritance** (D8): "e a rega dela?" uses the crop of the previous turn.
- **Confidence bands** (D5): answer at 0.5 or more, confirm the subject from 0.3, below that ask the
  subject when a plant was recognized, otherwise fall back. Initial values, to recalibrate in 9.4.2-2.

Answers come from the `Responder` (9.4.1-6), which only fills curated templates with data.
"""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel

from ..core.geo import UF_BY_CODE, Region, region_from_ibge_code
from .answers import Answer, Responder
from .dataset import EntityType, normalize
from .nlu import Interpretation, Interpreter

ANSWER_AT = 0.5  # confidence to answer directly
CONFIRM_AT = 0.3  # confidence to confirm the subject; below, ask it or fall back
MAX_LOCATION_ATTEMPTS = 2
NEW_QUESTION_MIN_WORDS = 3  # a reply to a pending question with more words may be a new question

CROP_INTENTS = {"planting_time", "crop_care", "companion_planting", "pest_disease", "market_price"}
YES = {"sim", "s", "isso", "isso mesmo", "e", "e sim", "exato", "claro", "certo", "ok", "okay", "aham", "uhum",
       "quero", "pode ser", "pode", "com certeza", "positivo", "sim sim", "isso ai", "correto"}  # fmt: skip
NO = {"nao", "n", "nao e", "negativo", "errado", "nada disso", "nem", "nao nao", "de jeito nenhum", "nao quero"}

Decision = Literal["answer", "confirm", "ask", "fallback"]


class DialogueError(ValueError):
    """Invalid request (unknown IBGE code); the API turns it into 422."""


class Slots(BaseModel):
    """Entities used to answer. Free text never goes here."""

    crop: str | None = None
    region: Region | None = None
    uf: str | None = None
    month: int | None = None
    care_aspect: str | None = None
    rotation: bool = False
    small_space: bool = False


class Pending(BaseModel):
    type: Literal["entity", "confirm_intent", "confirm_crop", "ask_intent"]
    intent: str | None = None
    entity: EntityType | None = None  # for type "entity": crop or location
    attempts: int = 1
    slots: Slots = Slots()


class DialogueContext(BaseModel):
    """Returned with every reply; the client sends it back with the next message."""

    version: Literal[1] = 1
    last_intent: str | None = None
    crop: str | None = None  # crop of the previous turn, for "e a rega dela?"
    pending: Pending | None = None


class Reply(Answer):
    """`intent` is "clarify" when the assistant asks something before knowing the subject."""

    decision: Decision
    confidence: float | None = None  # classifier confidence when the message was classified this turn
    entities: Slots
    context: DialogueContext


class DialogueManager:
    def __init__(self, interpreter: Interpreter, responder: Responder):
        self.nlu = interpreter
        self.responder = responder
        self.t = responder.templates["dialogue"]

    # --- public API ------------------------------------------------------------------

    def handle(
        self,
        text: str,
        *,
        ibge_code: int | str | None = None,
        small_space: bool = False,
        month: int | None = None,
        cv_label: str | None = None,
        context: DialogueContext | None = None,
    ) -> Reply:
        context = context or DialogueContext()
        base = self._profile_slots(ibge_code, small_space, month)

        if cv_label:  # 1. a photo: answer from the CV label, without classifying the text
            answer = self.responder.pest_disease(cv_label=cv_label)
            return self._reply(answer, "answer", base, context, confidence=None)

        if context.pending is not None:  # 2. pending question first (D7)
            reply = self._resolve_pending(text, base, context)
            if reply is not None:
                return reply

        return self._new_message(text, base, context)  # 3-6

    # --- steps -----------------------------------------------------------------------

    def _new_message(self, text: str, base: Slots, context: DialogueContext, *, after_ask: bool = False,
                     crop: str | None = None) -> Reply:  # fmt: skip
        nlu = self.nlu.interpret(text)
        slots = self._slots(nlu, base)
        if crop and not slots.crop:
            slots.crop = crop
        if not slots.crop and nlu.intent in CROP_INTENTS and context.crop:  # 4. inheritance (D8)
            slots.crop = context.crop
        clean = context.model_copy(update={"pending": None})

        # 5. confidence bands (D5)
        if nlu.intent == "fallback":
            return self._reply(self.responder.fallback(), "fallback", slots, clean, nlu.confidence)
        if nlu.confidence >= ANSWER_AT:
            if nlu.crop_fuzzy and slots.crop:
                pending = Pending(type="confirm_crop", intent=nlu.intent, slots=slots)
                text_ = self.t["confirm_crop"].format(crop=self._crop_label(slots.crop))
                return self._ask(nlu.intent, text_, "confirm", pending, slots, clean, nlu.confidence)
            return self._execute(nlu.intent, slots, clean, nlu.confidence)
        if nlu.confidence >= CONFIRM_AT:
            pending = Pending(type="confirm_intent", intent=nlu.intent, slots=slots)
            return self._ask(nlu.intent, self._confirm_text(nlu.intent, slots), "confirm", pending, slots, clean,
                             nlu.confidence)  # fmt: skip
        if slots.crop and not nlu.crop_fuzzy and not after_ask:
            pending = Pending(type="ask_intent", slots=slots)
            text_ = self.t["ask_intent"].format(crop=self._crop_label(slots.crop))
            return self._ask(None, text_, "ask", pending, slots, clean, nlu.confidence)
        return self._reply(self.responder.fallback(), "fallback", slots, clean, nlu.confidence)

    def _resolve_pending(self, text: str, base: Slots, context: DialogueContext) -> Reply | None:
        """The reply to the assistant's last question, or None when the message is a new question."""
        pending = context.pending
        clean = context.model_copy(update={"pending": None})
        slots = self._merge(pending.slots, base)

        if pending.type in ("confirm_intent", "confirm_crop"):
            answer = self._yes_no(text)
            if answer == "yes":
                return self._execute(pending.intent, slots, clean, None)
            if answer == "no":
                if pending.type == "confirm_crop":
                    retry = Pending(type="entity", intent=pending.intent, entity=EntityType.CROP,
                                    slots=slots.model_copy(update={"crop": None}))  # fmt: skip
                    return self._ask(pending.intent, self.responder.templates["common"]["ask_crop"], "ask", retry,
                                     retry.slots, clean, None)  # fmt: skip
                if slots.crop:
                    ask = Pending(type="ask_intent", slots=slots)
                    text_ = self.t["ask_intent"].format(crop=self._crop_label(slots.crop))
                    return self._ask(None, text_, "ask", ask, slots, clean, None)
                return self._ask(None, self.t["rephrase"], "ask", None, slots, clean, None)
            return None  # neither yes nor no: a new message

        if pending.type == "ask_intent":
            return self._new_message(text, base, clean, after_ask=True, crop=slots.crop)

        if pending.entity == EntityType.CROP:
            if self._is_new_question(text):  # "quanto ta o tomate?" is a question, not just a plant
                return None
            match = self.nlu.entities.crops(text)
            if match.ids:
                slots.crop = match.ids[0]
                if match.fuzzy:
                    confirm = Pending(type="confirm_crop", intent=pending.intent, slots=slots)
                    text_ = self.t["confirm_crop"].format(crop=self._crop_label(slots.crop))
                    return self._ask(pending.intent, text_, "confirm", confirm, slots, clean, None)
                return self._execute(pending.intent, slots, clean, None)
            answer = self.responder.unknown_crop(pending.intent)
            return self._reply(answer, "answer", slots.model_copy(update={"crop": None}), clean, None)

        if pending.entity == EntityType.LOCATION:
            location = self.nlu.entities.location(text, short_reply=True)
            if location is not None:
                slots.region, slots.uf = location.region, location.uf
                return self._execute(pending.intent, slots, clean, None)
            if self._is_new_question(text):
                return None
            if pending.attempts < MAX_LOCATION_ATTEMPTS:
                retry = pending.model_copy(update={"attempts": pending.attempts + 1, "slots": slots})
                return self._ask(pending.intent, self.t["ask_location_again"], "ask", retry, slots, clean, None)
            return self._reply(self.responder.fallback(), "fallback", slots, clean, None)

        return None

    def _execute(self, intent: str, slots: Slots, context: DialogueContext, confidence: float | None) -> Reply:
        """6. Fill what is missing from the profile and the clock, and let the Responder answer."""
        r, month = self.responder, slots.month or date.today().month
        slots = slots.model_copy(update={"month": month})
        match intent:
            case "planting_time":
                answer = r.planting_time(slots.crop, slots.region, month)
            case "what_to_plant":
                answer = r.what_to_plant(slots.region, month, slots.small_space)
            case "crop_care":
                answer = r.crop_care(slots.crop, slots.care_aspect)
            case "companion_planting":
                answer = r.companion_planting(slots.crop, slots.rotation)
            case "pest_disease":
                answer = r.pest_disease()
            case "market_price":
                answer = r.market_price(slots.crop, slots.uf)
            case "help":
                answer = r.help()
            case _:
                return self._reply(r.fallback(), "fallback", slots, context, confidence)
        if answer.missing_entity in (EntityType.CROP, EntityType.LOCATION):
            pending = Pending(type="entity", intent=intent, entity=answer.missing_entity, slots=slots)
            context = context.model_copy(update={"pending": pending})
            return self._reply(answer, "ask", slots, context, confidence)
        return self._reply(answer, "answer", slots, context, confidence)

    # --- helpers ---------------------------------------------------------------------

    def _reply(self, answer: Answer, decision: Decision, slots: Slots, context: DialogueContext,
               confidence: float | None) -> Reply:  # fmt: skip
        # The crop answered about becomes the one to inherit; a crop still to be confirmed does not.
        crop = context.crop
        if decision == "answer" and slots.crop is not None:
            crop = slots.crop if self._crop_label(slots.crop, None) else None
        context = context.model_copy(update={"last_intent": answer.intent, "crop": crop})
        return Reply(**answer.model_dump(), decision=decision, confidence=confidence, entities=slots, context=context)

    def _ask(self, intent: str | None, text: str, decision: Decision, pending: Pending | None, slots: Slots,
             context: DialogueContext, confidence: float | None) -> Reply:  # fmt: skip
        answer = Answer(intent=intent or "clarify", text=text)
        return self._reply(answer, decision, slots, context.model_copy(update={"pending": pending}), confidence)

    def _confirm_text(self, intent: str, slots: Slots) -> str:
        options = self.t["confirm_intent"]
        key = intent
        if intent == "companion_planting" and slots.rotation:
            key = "companion_planting_rotation"
        if intent in CROP_INTENTS and not slots.crop:
            key = f"{intent}_no_crop"
        template = options.get(key) or options.get(intent) or self.t["rephrase"]
        return template.format(crop=self._crop_label(slots.crop) if slots.crop else "")

    def _crop_label(self, crop_id: str | None, default: str | None = "essa planta") -> str | None:
        if crop_id in self.responder.kb.crops:
            return self.responder.kb.crops[crop_id].name_pt.lower()
        market = self.responder.market
        if market is not None and crop_id in market.products:
            return market.products[crop_id].name_pt.lower()
        return default

    def _is_new_question(self, text: str) -> bool:
        """A full, confident question instead of a short reply ("alface", "PR", "lá perto")."""
        if len(normalize(text).split()) <= NEW_QUESTION_MIN_WORDS:
            return False
        nlu = self.nlu.interpret(text)
        return nlu.confidence >= ANSWER_AT and nlu.intent not in ("help", "fallback")

    @staticmethod
    def _yes_no(text: str) -> Literal["yes", "no"] | None:
        flat = normalize(text)
        if flat in YES:
            return "yes"
        if flat in NO:
            return "no"
        words = flat.split()
        if words and len(words) <= 3 and words[0] in {"sim", "isso", "claro", "exato"}:
            return "yes"
        if words and len(words) <= 3 and words[0] == "nao":
            return "no"
        return None

    def _slots(self, nlu: Interpretation, base: Slots) -> Slots:
        slots = base.model_copy()
        slots.crop = nlu.crop
        slots.care_aspect = nlu.care_aspect
        slots.rotation = nlu.rotation
        slots.small_space = base.small_space or nlu.small_space
        if nlu.month is not None:
            slots.month = nlu.month
        if nlu.location is not None:  # a place named in the message wins over the profile
            slots.region = nlu.location.region
            slots.uf = nlu.location.uf or (base.uf if base.region == nlu.location.region else None)
        return slots

    @staticmethod
    def _merge(pending: Slots, base: Slots) -> Slots:
        """Slots of the pending question, completed with the current profile."""
        merged = pending.model_copy()
        if merged.region is None:
            merged.region, merged.uf = base.region, base.uf
        if merged.month is None:
            merged.month = base.month
        merged.small_space = merged.small_space or base.small_space
        return merged

    @staticmethod
    def _profile_slots(ibge_code: int | str | None, small_space: bool, month: int | None) -> Slots:
        region = uf = None
        if ibge_code is not None:
            try:
                region = region_from_ibge_code(ibge_code)
            except ValueError as err:
                raise DialogueError(f"código IBGE inválido: {err}") from err
            uf = UF_BY_CODE.get(str(ibge_code)[:2])
        return Slots(region=region, uf=uf, month=month, small_space=small_space)
