"""Properties of the conversational engine over every message (WBS 9.4.2-2, cases U7, U8, U10-U13 of
`docs/nlu/9.4.2-1_Plano_Casos_Teste.md`). Each test name starts with its case id.
"""

import itertools
import json
import re
import runpy
import sys
import time

import pytest

from hort_ia.core.geo import UF_BY_CODE, Region
from hort_ia.knowledge import load_knowledge_base
from hort_ia.market.loader import load_market_dataset
from hort_ia.nlp import (
    DialogueContext,
    DialogueManager,
    Interpreter,
    Responder,
    load_intents,
    load_templates,
    normalize,
)
from hort_ia.nlp.dialogue import Pending, Slots

TRAINING = load_intents().texts_and_labels()[0]
HARD = [
    " ", "   ", "???", "!!!", "...", "🌱🌱🌱", "🍅?", "12345", "2026", "ok", "a", "kkkkkk",
    "when should I plant lettuce?", "x" * 500, "alface " * 60, "quando planto alface? " * 20,
    "<script>alert(1)</script>", "'; drop table crops; --", "{crop}", "{0}", "%s", "\\n\\t",
    "moro na rua das flores 123, sou a maria da silva", "meu cpf é 123.456.789-00",
]  # fmt: skip
DECISIONS = {"answer", "confirm", "ask", "fallback"}


@pytest.fixture(scope="module")
def kb():
    return load_knowledge_base()


@pytest.fixture(scope="module")
def dialogue(kb):
    market = load_market_dataset()
    return DialogueManager(Interpreter(kb, market), Responder(kb, load_templates(), market))


def contexts():
    """No context plus one of each pending question, so every message is also tried as a reply."""
    slots = Slots(region=Region.SUL, uf="PR", month=11, crop="alface")
    yield None
    yield DialogueContext(pending=Pending(type="entity", intent="planting_time", entity="crop", slots=slots))
    yield DialogueContext(pending=Pending(type="entity", intent="planting_time", entity="location", slots=Slots()))
    yield DialogueContext(pending=Pending(type="confirm_intent", intent="crop_care", slots=slots))
    yield DialogueContext(pending=Pending(type="confirm_crop", intent="planting_time", slots=slots))
    yield DialogueContext(pending=Pending(type="ask_intent", slots=slots), crop="alface")


# --- U7: robustness ----------------------------------------------------------------------


@pytest.mark.parametrize("context", list(contexts()), ids=["none", "crop", "location", "confirm", "typo", "subject"])
def test_u7_every_message_gets_a_valid_reply(dialogue, context):
    for text in TRAINING + HARD:
        for profile in ({"ibge_code": 4106902, "month": 11}, {}):
            reply = dialogue.handle(text, context=context, **profile)
            assert reply.decision in DECISIONS, text
            assert reply.text.strip(), text
            again = DialogueContext.model_validate(json.loads(reply.context.model_dump_json()))
            assert again == reply.context, text


# --- U8: the context never keeps the user's text --------------------------------------------


def allowed_words(kb) -> set[str]:
    words = set(kb.crops) | {r.value for r in Region} | {uf.lower() for uf in UF_BY_CODE.values()}
    words |= {"cebola"} | set(DialogueContext.model_json_schema()["$defs"]) | {"null", "true", "false"}
    return {normalize(w) for w in words}


@pytest.mark.parametrize("context", list(contexts()), ids=["none", "crop", "location", "confirm", "typo", "subject"])
def test_u8_context_keeps_identifiers_only(dialogue, kb, context):
    allowed = allowed_words(kb)
    structure = normalize(DialogueContext(pending=Pending(type="entity", slots=Slots())).model_dump_json())
    for text in TRAINING + HARD:
        stored = normalize(dialogue.handle(text, context=context, ibge_code=4106902).context.model_dump_json())
        for word in set(normalize(text).split()):
            if len(word) < 4 or word in allowed or word in structure:
                continue
            assert not re.search(rf"(?<![a-z0-9]){re.escape(word)}(?![a-z0-9])", stored), (word, text)


# --- U10: dialogue texts --------------------------------------------------------------------


def test_u10_every_intent_has_its_confirmation_texts(dialogue):
    intents = [i for i in dialogue.nlu.classifier.classes_ if i != "fallback"]
    rephrase = dialogue.t["rephrase"]
    for intent, crop, rotation in itertools.product(intents, ["alface", "cebola", None], [False, True]):
        text = dialogue._confirm_text(intent, Slots(crop=crop, rotation=rotation))
        assert text != rephrase and "{" not in text and "}" not in text, (intent, crop)
        assert text.startswith("Você quer saber"), text
    for key in ("confirm_crop", "ask_intent", "ask_location_again", "rephrase"):
        assert "{" not in dialogue.t[key].replace("{crop}", ""), key


# --- U11: confidence bands --------------------------------------------------------------------


def test_u11_decision_follows_the_confidence_bands(dialogue):
    for text in TRAINING:
        nlu = dialogue.nlu.interpret(text)
        reply = dialogue.handle(text, ibge_code=4106902, month=11)
        if nlu.intent == "fallback":
            expected = {"fallback"}
        elif nlu.confidence >= dialogue.answer_at:
            expected = {"confirm"} if nlu.crop_fuzzy and nlu.crops else {"answer", "ask"}  # ask = missing entity
        elif nlu.confidence >= dialogue.confirm_at:
            expected = {"confirm"}
        else:
            expected = {"ask"} if nlu.crops and not nlu.crop_fuzzy else {"fallback"}
        assert reply.decision in expected, (text, nlu.intent, nlu.confidence, reply.decision)
        if reply.decision == "ask" and nlu.confidence >= dialogue.answer_at:
            assert reply.missing_entity is not None, text


# --- U12: time ----------------------------------------------------------------------------------


def test_u12_turn_time(dialogue):
    times = []
    for text in TRAINING:
        start = time.perf_counter()
        dialogue.handle(text, ibge_code=4106902, month=11)
        times.append(time.perf_counter() - start)
    times.sort()
    assert times[int(len(times) * 0.95)] < 0.05  # p95 below 50 ms, without network


# --- U13: command line ---------------------------------------------------------------------------


def test_u13_cli_prints_the_interpretation(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["python -m hort_ia.nlp", "qndo plantar alfase?"])
    runpy.run_module("hort_ia.nlp", run_name="__main__")
    out = capsys.readouterr().out
    assert "> qndo plantar alfase?" in out
    data = json.loads(out.split("\n", 1)[1])
    assert data["intent"] == "planting_time" and data["crops"] == ["alface"] and data["crop_fuzzy"] is True
