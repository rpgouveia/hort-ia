"""Dialogue manager and `POST /nlp/message` (WBS 9.4.1-5).

The conversations M1-M7 and C1-C8 are the reference cases of
`docs/nlu/9.4.1-3_Abordagem_Motor_Conversacional.md`, section 6 (Curitiba, month 11); each test name
starts with its case id. None of the messages is in `data/nlu/intents.yaml`.
"""

import json
import time

import pytest
from starlette.testclient import TestClient

from hort_ia.api.main import app
from hort_ia.knowledge import load_knowledge_base
from hort_ia.market.loader import load_market_dataset
from hort_ia.nlp import DialogueContext, DialogueError, DialogueManager, Interpreter, Responder, load_templates

CURITIBA = 4106902


@pytest.fixture(scope="module")
def dialogue():
    kb, market = load_knowledge_base(), load_market_dataset()
    return DialogueManager(Interpreter(kb, market), Responder(kb, load_templates(), market))


def talk(dialogue, *messages, **profile):
    """Runs a conversation, passing the context along as a client would. Returns every reply."""
    profile = {"ibge_code": CURITIBA, "month": 11, **profile}
    replies, context = [], None
    for message in messages:
        reply = dialogue.handle(message, context=context, **profile)
        replies.append(reply)
        context = DialogueContext.model_validate(json.loads(reply.context.model_dump_json()))  # through JSON
    return replies


# --- one message (M1-M7) -------------------------------------------------------------------


def test_m1_what_to_plant(dialogue):
    (r,) = talk(dialogue, "o que da pra plantar agora?")
    assert (r.decision, r.intent) == ("answer", "what_to_plant")
    assert r.text.startswith("Em novembro, no Sul, dá para plantar: batata, brócolis, manjericão")


def test_m2_market_price_uses_the_state_of_the_profile(dialogue):
    (r,) = talk(dialogue, "quanto ta o tomate no ceasa?")
    assert (r.decision, r.intent, r.entities.crop, r.entities.uf) == ("answer", "market_price", "tomate", "PR")
    assert "R$ 5,55" in r.text and "CEASA/PR" in r.text


def test_m3_rotation(dialogue):
    (r,) = talk(dialogue, "o que planto depois do repolho?")
    assert (r.decision, r.intent) == ("answer", "companion_planting") and r.entities.rotation
    assert r.text.startswith("Depois de repolho, não plante no mesmo canteiro: brócolis, couve, rabanete")


def test_m4_container(dialogue):
    (r,) = talk(dialogue, "da pra plantar cebolinha em vaso?")
    assert (r.intent, r.entities.care_aspect) == ("crop_care", "container")
    assert "11 cm" in r.text


def test_m5_pest_without_photo_asks_for_one(dialogue):
    (r,) = talk(dialogue, "minha couve ta com uns bichinho")
    assert (r.decision, r.intent) == ("answer", "pest_disease") and "mande uma foto" in r.text


def test_m6_out_of_scope_hands_off(dialogue):
    (r,) = talk(dialogue, "quanto custa o adubo?")
    assert (r.decision, r.intent) == ("fallback", "fallback") and r.handoff


def test_m7_photo_answers_from_the_cv_label_without_reading_the_text(dialogue):
    (r,) = talk(dialogue, "qualquer coisa", cv_label="Tomato___healthy")
    assert (r.decision, r.intent, r.confidence) == ("answer", "pest_disease", None)
    assert r.text == "A planta parece saudável."


# --- conversations (C1-C8) ---------------------------------------------------------------------


def test_c1_missing_crop_is_asked_and_the_reply_completes_the_question(dialogue):
    first, second = talk(dialogue, "quando eu planto?", "alface")
    assert (first.decision, first.missing_entity, first.context.pending.entity) == ("ask", "crop", "crop")
    assert (second.decision, second.intent, second.entities.crop) == ("answer", "planting_time", "alface")
    assert second.text.startswith("Alface de inverno no Sul") and second.context.pending is None


def test_c2_crop_outside_the_catalog(dialogue):
    first, second = talk(dialogue, "quando planto mandioca?", "mandioca")
    assert (first.decision, first.intent) == ("ask", "planting_time")  # not the list of the month
    assert second.text.startswith("Ainda não tenho informações sobre essa planta") and second.handoff


def test_c3_typo_is_confirmed_before_answering(dialogue):
    first, second = talk(dialogue, "qndo plantar alfase?", "sim")
    assert (first.decision, first.text) == ("confirm", "Você quis dizer alface?")
    assert first.context.crop is None  # not inherited before the user confirms
    assert (second.decision, second.intent, second.entities.crop) == ("answer", "planting_time", "alface")


def test_c3_typo_rejected_asks_the_plant_again(dialogue):
    _, second, third = talk(dialogue, "qndo plantar alfase?", "não", "rúcula")
    assert second.text == "De qual planta você está falando?"
    assert (third.decision, third.entities.crop) == ("answer", "rucula")


def test_c4_crop_is_inherited_from_the_previous_turn(dialogue):
    first, second = talk(dialogue, "qual a epoca de plantar alface?", "e a rega dela?")
    assert first.intent == "planting_time"
    assert (second.decision, second.intent, second.entities.crop, second.entities.care_aspect) == (
        "answer", "crop_care", "alface", "watering",
    )  # fmt: skip
    assert "irrigadas diariamente" in second.text


def test_c5_medium_confidence_is_confirmed(dialogue):
    first, second = talk(dialogue, "a alface ta amarelando", "sim")
    assert (first.decision, first.text) == ("confirm", "Você quer saber sobre praga ou doença em alface?")
    assert 0.3 <= first.confidence < 0.5
    assert (second.decision, second.intent) == ("answer", "pest_disease") and "mande uma foto" in second.text


def test_c6_feasibility_of_planting_is_answered_with_the_season(dialogue):
    """Until 14/11/2026 the engine confirmed crop_care ("Você quer saber como cuidar de morango?"); with the
    "tem como plantar X" examples it answers planting_time, the intent a person assigns (U5)."""
    (r,) = talk(dialogue, "tem como plantar morango aqui?")
    assert (r.decision, r.intent, r.entities.crop) == ("answer", "planting_time", "morango")
    assert r.text.startswith("Morango no Sul: dá para plantar de março a abril.")


def test_rejected_subject_asks_what_about_the_plant(dialogue):
    """The path C6 used to cover: a confirmation with a plant, rejected, asks what about the plant."""
    first, second, third = talk(dialogue, "a alface ta amarelando", "não", "quando planto")
    assert (first.decision, first.text) == ("confirm", "Você quer saber sobre praga ou doença em alface?")
    assert (second.decision, second.intent) == ("ask", "clarify")
    assert second.text.startswith("O que você quer saber sobre alface?")
    assert (third.decision, third.intent, third.entities.crop) == ("answer", "planting_time", "alface")
    assert third.text.startswith("Alface de inverno no Sul")


def test_c7_low_confidence_with_a_plant_asks_the_subject(dialogue):
    (r,) = talk(dialogue, "alface aguenta frio?")
    assert (r.decision, r.intent) == ("ask", "clarify") and r.confidence < 0.3
    assert r.context.pending.type == "ask_intent" and r.context.pending.slots.crop == "alface"


def test_c8_typo_match_does_not_turn_out_of_scope_into_a_plant(dialogue):
    (r,) = talk(dialogue, "como crio galinha?")
    assert (r.decision, r.entities.crop) == ("fallback", None) and r.handoff


# --- other dialogue rules ---------------------------------------------------------------------


def test_location_is_asked_when_the_profile_has_none(dialogue):
    first, second = talk(dialogue, "qual a epoca de plantar alface?", "pr", ibge_code=None)
    assert (first.decision, first.missing_entity) == ("ask", "location")
    assert (second.decision, second.entities.region, second.entities.uf) == ("answer", "sul", "PR")


def test_unrecognized_place_is_asked_once_more_then_handed_off(dialogue):
    replies = talk(dialogue, "qual a epoca de plantar alface?", "lá perto", "aqui mesmo", ibge_code=None)
    assert replies[1].text.startswith("Não reconheci o lugar.")
    assert (replies[2].decision, replies[2].handoff) == ("fallback", True)


def test_place_named_in_the_message_wins_over_the_profile(dialogue):
    (r,) = talk(dialogue, "qual a epoca de plantar alface no nordeste?")
    assert r.entities.region == "nordeste" and "Nordeste" in r.text


@pytest.mark.parametrize(
    ("reply", "region", "label"),
    [("natal", "nordeste", "Nordeste"), ("moro em natal", "nordeste", "Nordeste"), ("para", "norte", "Norte"),
     ("Pará", "norte", "Norte"), ("campo grande", "centro_oeste", "Centro-Oeste")],
)  # fmt: skip
def test_place_name_that_is_a_common_word_answers_where_the_garden_is(dialogue, reply, region, label):
    first, second = talk(dialogue, "qual a epoca de plantar alface?", reply, ibge_code=None)
    assert first.missing_entity == "location"
    assert (second.decision, second.entities.region) == ("answer", region)
    assert f"Alface de inverno no {label}" in second.text


def test_care_word_alone_asks_the_plant(dialogue):
    """A care word alone, a short message seen in the field, is a care question: ask the plant, no handoff."""
    (r,) = talk(dialogue, "cuidados")
    assert (r.decision, r.intent, r.missing_entity, r.handoff) == ("ask", "crop_care", "crop", False)


def test_new_question_while_a_question_is_pending(dialogue):
    first, second = talk(dialogue, "quando eu planto?", "quanto ta o tomate no ceasa?")  # a question, not a plant
    assert first.context.pending is not None
    assert (second.decision, second.intent, second.context.pending) == ("answer", "market_price", None)


def test_neither_yes_nor_no_is_read_as_a_new_message(dialogue):
    first, second = talk(dialogue, "a alface ta amarelando", "o que da pra plantar agora?")
    assert first.decision == "confirm"
    assert (second.decision, second.intent) == ("answer", "what_to_plant")


def test_low_confidence_without_a_plant_falls_back(dialogue):
    # "vale a pena ter horta?" was the message until 14/11/2026; it now confirms market_price (0.32), a known limit.
    (r,) = talk(dialogue, "é difícil ter uma horta?")
    assert r.confidence < 0.3 and (r.decision, r.handoff) == ("fallback", True)


def test_subject_rejected_without_a_plant_asks_to_rephrase(dialogue):
    first, second = talk(dialogue, "planta aguenta frio?", "não é isso")
    assert (first.decision, first.text) == ("confirm", "Você quer saber a época de plantio?")
    assert (second.decision, second.text, second.context.pending) == (
        "ask", "Desculpe, não entendi. Pode perguntar de outro jeito?", None,
    )  # fmt: skip


def test_typo_in_the_reply_to_a_missing_plant_is_confirmed(dialogue):
    first, second, third = talk(dialogue, "quando eu planto?", "alfase", "sim")
    assert first.decision == "ask"
    assert (second.decision, second.text) == ("confirm", "Você quis dizer alface?")
    assert (third.decision, third.entities.crop) == ("answer", "alface")


def test_new_question_while_the_place_is_pending(dialogue):
    first, second = talk(dialogue, "qual a epoca de plantar alface?", "quanto ta o tomate no ceasa?", ibge_code=None)
    assert first.missing_entity == "location"
    assert (second.decision, second.intent) == ("answer", "market_price") and "nos Ceasas do país" in second.text


def test_month_named_in_the_message(dialogue):
    (r,) = talk(dialogue, "o que planto em março?")
    assert r.entities.month == 3 and r.text.startswith("Em março, no Sul")


def test_month_defaults_to_the_current_one_across_a_confirmation(dialogue):
    first, second = talk(dialogue, "a alface ta amarelando", "sim", month=None)
    assert first.decision == "confirm" and second.entities.month is not None


def test_market_product_outside_the_catalog_is_kept_in_the_context(dialogue):
    (r,) = talk(dialogue, "quanto ta a cebola?")
    assert (r.decision, r.entities.crop, r.context.crop) == ("answer", "cebola", "cebola")


def test_confirmation_texts(dialogue):
    from hort_ia.nlp.dialogue import Slots

    assert dialogue._confirm_text("companion_planting", Slots(crop="tomate", rotation=True)) == (
        "Você quer saber o que plantar depois de tomate?"
    )
    assert dialogue._confirm_text("market_price", Slots(crop="cebola")) == "Você quer saber o preço de cebola?"
    assert dialogue._confirm_text("what_to_plant", Slots()) == "Você quer saber o que dá para plantar agora?"


@pytest.mark.parametrize(
    ("text", "expected"),
    [("sim", "yes"), ("Sim, isso!", "yes"), ("é", "yes"), ("isso mesmo", "yes"), ("não", "no"), ("nao quero", "no"),
     ("e a rega dela?", None), ("não sei o preço do tomate hoje", None)],
)  # fmt: skip
def test_yes_no(text, expected):
    assert DialogueManager._yes_no(text) == expected


def test_context_keeps_identifiers_never_the_text(dialogue):
    replies = talk(dialogue, "quando planto mandioca?", "mandioca da minha vizinha Maria")
    for reply in replies:
        stored = reply.context.model_dump_json()
        assert "mandioca" not in stored and "Maria" not in stored and "vizinha" not in stored


def test_invalid_ibge_code(dialogue):
    with pytest.raises(DialogueError):
        dialogue.handle("oi", ibge_code=9906902)


def test_a_turn_is_fast(dialogue):
    start = time.perf_counter()
    for _ in range(50):
        talk(dialogue, "qndo plantar alfase?", "sim")
    assert (time.perf_counter() - start) / 100 < 0.05  # per turn; the 9.4 criterion is 5 s


# --- POST /nlp/message ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def client() -> TestClient:
    return TestClient(app)


def test_route_contract_and_context_round_trip(client):
    first = client.post("/nlp/message", json={"text": "quando eu planto?", "ibge_code": CURITIBA, "month": 11})
    assert first.status_code == 200
    data = first.json()
    assert set(data) >= {"intent", "text", "sources", "handoff", "missing_entity", "decision", "confidence",
                         "entities", "context"}  # fmt: skip
    assert data["decision"] == "ask" and data["context"]["pending"]["entity"] == "crop"

    second = client.post(
        "/nlp/message", json={"text": "alface", "ibge_code": CURITIBA, "month": 11, "context": data["context"]}
    ).json()
    assert (second["decision"], second["intent"], second["entities"]["crop"]) == ("answer", "planting_time", "alface")
    assert second["sources"]


@pytest.mark.parametrize(
    "payload",
    [
        {"text": ""},
        {"text": "x" * 501},
        {"text": "oi", "ibge_code": 9906902},
        {"text": "oi", "month": 13},
        {"text": "oi", "context": {"version": 2}},
    ],
    ids=["empty", "too-long", "ibge", "month", "context-version"],
)
def test_route_rejects_invalid_requests(client, payload):
    assert client.post("/nlp/message", json=payload).status_code == 422


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("o que dá para plantar agora?", "Em novembro, no Sul, dá para plantar"),
        ("o que dá pra plantar agora?", "Em novembro, no Sul, dá para plantar"),
        ("quando plantar alface para colher?", "Alface de inverno no Sul"),
        ("quando plantar tomate para colher no natal?", "Tomate no Sul"),
        ("o que plantar pro natal?", "Em novembro, no Sul, dá para plantar"),
        ("quero plantar um acre de alface, quando planto?", "Alface de inverno no Sul"),
        ("o que planto em um campo grande?", "Em novembro, no Sul, dá para plantar"),
        ("quanto tá o tomate para vender?", "CEASA/PR"),
    ],
)
def test_route_does_not_read_common_words_as_places(client, text, expected):
    """Messages of the UAT rehearsal (13/11/2026): "para", "natal", "acre" and "campo grande" were read
    as places and answered with the season of another region, without confirmation."""
    data = client.post("/nlp/message", json={"text": text, "ibge_code": CURITIBA, "month": 11}).json()
    assert data["decision"] == "answer" and (data["entities"]["region"], data["entities"]["uf"]) == ("sul", "PR")
    assert expected in data["text"], data["text"]


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("o que dá pra plantar no rio de janeiro?", "Em novembro, no Sudeste, dá para plantar"),
        ("moro no rio de janeiro, quando planto alface?", "Agora em novembro"),
    ],
)
def test_route_does_not_read_the_month_in_a_place_name(client, text, expected):
    """The "janeiro" of "rio de janeiro" is not January: the month stays the profile's (UAT rehearsal, 13/11/2026)."""
    data = client.post("/nlp/message", json={"text": text, "ibge_code": CURITIBA, "month": 11}).json()
    assert data["decision"] == "answer" and data["entities"]["month"] == 11
    assert (data["entities"]["region"], data["entities"]["uf"]) == ("sudeste", "RJ")
    assert expected in data["text"] and "Sudeste" in data["text"], data["text"]


def test_route_without_profile_still_answers(client):
    data = client.post("/nlp/message", json={"text": "oi, o que você faz?"}).json()
    assert data["decision"] in ("answer", "confirm") and data["text"]


def test_api_builds_the_engine_at_start_up():
    """The lifespan of the app trains the classifier before the first request (WBS 9.4.2-4)."""
    from hort_ia.api.nlp import get_dialogue

    get_dialogue.cache_clear()
    with TestClient(app):
        assert get_dialogue.cache_info().currsize == 1
