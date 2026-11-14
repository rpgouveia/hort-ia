"""Natural language understanding of the assistant (WBS 9.4.1-4).

The single-message reference cases M1-M6 and the first turn of C1-C8 come from
`docs/nlu/9.4.1-3_Abordagem_Motor_Conversacional.md`, section 6; the classifier figures, from the
9.4.1-1 study (reproduced by `docs/nlu/exploratory_nlu_approaches.py`). None of the reference messages
is in `data/nlu/intents.yaml`.
"""

import time

import numpy as np
import pytest
from sklearn.metrics import accuracy_score
from sklearn.model_selection import StratifiedKFold, cross_val_predict

from hort_ia.core.geo import Region
from hort_ia.knowledge import load_knowledge_base
from hort_ia.market.loader import load_market_dataset
from hort_ia.nlp import EntityExtractor, Interpreter, build_classifier, load_intents, normalize


@pytest.fixture(scope="module")
def nlu():
    return Interpreter(load_knowledge_base(), load_market_dataset())


@pytest.fixture(scope="module")
def entities():
    return EntityExtractor(load_knowledge_base(), load_market_dataset())


# --- reference cases (9.4.1-3, section 6) ------------------------------------------------

REFERENCE = [
    # (message, intent, crops, extra fields)
    ("o que da pra plantar agora?", "what_to_plant", [], {}),  # M1
    ("quanto ta o tomate no ceasa?", "market_price", ["tomate"], {}),  # M2
    ("o que planto depois do repolho?", "companion_planting", ["repolho"], {"rotation": True}),  # M3
    ("da pra plantar cebolinha em vaso?", "crop_care", ["cebolinha"], {"care_aspect": "container"}),  # M4
    ("minha couve ta com uns bichinho", "pest_disease", ["couve"], {}),  # M5
    ("quanto custa o adubo?", "fallback", [], {}),  # M6
    ("quando eu planto?", "planting_time", [], {}),  # C1
    ("quando planto mandioca?", "planting_time", [], {}),  # C2: not turned into what_to_plant
    ("qndo plantar alfase?", "planting_time", ["alface"], {"crop_fuzzy": True}),  # C3
    ("qual a epoca de plantar alface?", "planting_time", ["alface"], {}),  # C4, 1st turn
    ("e a rega dela?", "crop_care", [], {"care_aspect": "watering"}),  # C4, 2nd turn: crop from the context
    ("a alface ta amarelando", "pest_disease", ["alface"], {}),  # C5
    ("tem como plantar morango aqui?", "crop_care", ["morango"], {}),  # C6
    ("alface aguenta frio?", "planting_time", ["alface"], {}),  # C7
    ("como crio galinha?", "fallback", [], {}),  # C8: the typo match to "salsinha" is dropped
]


@pytest.mark.parametrize(("message", "intent", "crops", "extra"), REFERENCE, ids=[r[0] for r in REFERENCE])
def test_reference_messages(nlu, message, intent, crops, extra):
    result = nlu.interpret(message)
    assert result.intent == intent
    assert result.crops == crops
    for field, value in extra.items():
        assert getattr(result, field) == value, field


@pytest.mark.parametrize(
    ("message", "band"),
    [
        ("o que da pra plantar agora?", "answer"),  # M1, 0.99
        ("e a rega dela?", "answer"),  # C4, 0.56
        ("a alface ta amarelando", "confirm"),  # C5, 0.43
        ("tem como plantar morango aqui?", "confirm"),  # C6, 0.33
        ("alface aguenta frio?", "low"),  # C7, 0.27
    ],
)
def test_confidence_band_of_the_reference_cases(nlu, message, band):
    """Bands of 9.4.1-3, section 4.4 (0.5 and 0.3): the dialogue (9.4.1-5) relies on them."""
    confidence = nlu.interpret(message).confidence
    assert {"answer": confidence >= 0.5, "confirm": 0.3 <= confidence < 0.5, "low": confidence < 0.3}[band]


def test_alternatives_are_the_three_most_likely_intents(nlu):
    result = nlu.interpret("vale a pena plantar batata?")
    scores = [a.confidence for a in result.alternatives]
    assert len(scores) == 3 and scores == sorted(scores, reverse=True)
    assert result.alternatives[0].confidence == result.confidence


# --- entity rule (D4) ----------------------------------------------------------------------


def test_what_to_plant_with_a_crop_becomes_planting_time(nlu):
    message = "o que plantar agora, tomate ou alface?"
    assert nlu.classifier.predict([message])[0] == "what_to_plant"
    result = nlu.interpret(message)
    assert result.intent == "planting_time" and result.entity_rule_applied
    assert result.crops == ["tomate", "alface"]


def test_entity_rule_never_turns_planting_time_into_what_to_plant(nlu):
    result = nlu.interpret("quando planto mandioca?")
    assert result.intent == "planting_time" and not result.entity_rule_applied


# --- crops -------------------------------------------------------------------------------


def test_every_name_and_alias_of_the_base_is_understood(entities):
    kb = load_knowledge_base()
    for crop in kb.crops.values():
        for name in (crop.name_pt, *crop.aliases):
            match = entities.crops(f"como cuido de {name}?")
            assert match.ids == [crop.id] and not match.fuzzy, name


def test_crops_keep_the_order_of_the_message(entities):
    assert entities.crops("posso por cebolinha perto da alface?").ids == ["cebolinha", "alface"]
    assert entities.crops("alface com tomate e alface de novo").ids == ["alface", "tomate"]


def test_market_product_outside_the_catalog(entities):
    assert entities.crops("quanto ta a cebola?").ids == ["cebola"]


@pytest.mark.parametrize(("text", "crop"), [("tomatte", "tomate"), ("alfase", "alface"), ("cenora", "cenoura")])
def test_typos_are_found_but_flagged(entities, text, crop):
    match = entities.crops(f"quando planto {text}")
    assert match.ids == [crop] and match.fuzzy


def test_exact_match_wins_over_typo_match(entities):
    assert not entities.crops("alfase e tomate").fuzzy  # tomate exact, so no typo search


def test_unknown_plant_gives_no_crop(entities):
    assert entities.crops("quando planto mandioca?").ids == []


# --- other entities --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "month"),
    [("quero plantar em março", 3), ("e em Setembro?", 9), ("plantio em jan", 1), ("colhe em dez dias", None),
     ("vou plantar mais tarde", None)],
)  # fmt: skip
def test_month(entities, text, month):
    assert entities.month(text) == month


@pytest.mark.parametrize(
    ("text", "aspect"),
    [("de quanto em quanto tempo rego o tomate?", "watering"), ("qual o espaçamento do pimentão?", "spacing"),
     ("quando colho a cenoura?", "harvest"), ("alface em vaso dá certo?", "container"), ("e o tomate?", None)],
)  # fmt: skip
def test_care_aspect(entities, text, aspect):
    assert entities.care_aspect(text) == aspect


def test_small_space_and_rotation(entities):
    assert entities.small_space("moro em apartamento, o que planto?")
    assert not entities.small_space("tenho um quintal grande")
    assert entities.rotation("o que planto no lugar do tomate?")
    assert not entities.rotation("o que planto junto do tomate?")


@pytest.mark.parametrize(
    ("text", "short", "uf", "region"),
    [
        ("moro em curitiba", False, "PR", Region.SUL),
        ("sou do rio grande do sul", False, "RS", Region.SUL),  # not just "sul"
        ("aqui é Goiás", False, "GO", Region.CENTRO_OESTE),
        ("fico no PR", False, "PR", Region.SUL),
        ("pr", True, "PR", Region.SUL),
        ("região centro-oeste", False, None, Region.CENTRO_OESTE),
    ],
)
def test_location(entities, text, short, uf, region):
    location = entities.location(text, short_reply=short)
    assert location is not None and location.uf == uf and location.region is region


@pytest.mark.parametrize("text", ["se der eu planto", "pr", "vou plantar tomate"])
def test_lowercase_uf_abbreviations_are_not_locations(entities, text):
    assert entities.location(text) is None


# Messages of the UAT rehearsal (13/11/2026) and other common words that are also place names.
COMMON_WORDS_THAT_ARE_NOT_PLACES = [
    "o que dá para plantar agora?",  # "para", the preposition, is not the state of Pará
    "o que dá pra plantar agora?",
    "quando plantar alface para colher?",
    "quando plantar tomate para colher no natal?",  # Christmas, not the capital of RN
    "o que plantar pro natal?",
    "quero plantar um acre de alface, quando planto?",  # the unit of area
    "o que planto em um campo grande?",  # a big field, not the capital of MS
    "quanto tá o tomate para vender?",
    "dá para plantar alface em vaso?",
    "presente de natal",
    "árvore de natal",
    "comprei um acre",
    "tenho um campo grande atrás de casa",
    "como plantar vitória-régia?",
    "a horta fica virada para o norte, o que planto?",
    "QUANDO PLANTO ALFACE SE CHOVER?",  # all in upper case: "SE" is not Sergipe
    "QUANTOS PE DE ALFACE POR METRO?",
]


@pytest.mark.parametrize("text", COMMON_WORDS_THAT_ARE_NOT_PLACES)
def test_common_words_are_not_places(entities, text):
    assert entities.location(text) is None


@pytest.mark.parametrize(
    ("text", "uf", "region"),
    [
        ("quando planto alface no Pará?", "PA", Region.NORTE),
        ("quando planto alface no estado do para?", "PA", Region.NORTE),
        ("MORO NO PARÁ", "PA", Region.NORTE),
        ("moro em Natal", "RN", Region.NORDESTE),
        ("aqui em Campo Grande", "MS", Region.CENTRO_OESTE),
        ("sou do Acre", "AC", Region.NORTE),
        ("moro em mato grosso", "MT", Region.CENTRO_OESTE),
        ("sou de mato grosso do sul", "MS", Region.CENTRO_OESTE),
        ("canteiro no sul de minas", "MG", Region.SUDESTE),  # not the Sul region
        ("moro no norte", None, Region.NORTE),
        ("região sul", None, Region.SUL),
    ],
)
def test_ambiguous_place_names_count_in_context(entities, text, uf, region):
    location = entities.location(text)
    assert location is not None and location.uf == uf and location.region is region


@pytest.mark.parametrize(
    ("text", "uf"),
    [("natal", "RN"), ("para", "PA"), ("Pará", "PA"), ("campo grande", "MS"), ("em natal", "RN"),
     ("moro em natal", "RN"), ("aqui é natal", "RN"), ("acre", "AC")],
)  # fmt: skip
def test_ambiguous_place_names_count_as_the_answer_to_where_the_garden_is(entities, text, uf):
    location = entities.location(text, short_reply=True)
    assert location is not None and location.uf == uf


def test_a_new_question_is_not_read_as_the_answer_to_where_the_garden_is(entities):
    assert entities.location("o que dá para plantar agora?", short_reply=True) is None


@pytest.mark.parametrize(
    ("text", "month"),
    [("o que dá pra plantar no rio de janeiro?", None), ("moro no rio de janeiro, quando planto alface?", None),
     ("quando planto alface em janeiro no rio de janeiro?", 1)],
)  # fmt: skip
def test_month_inside_a_place_name_is_not_a_month(entities, text, month):
    location = entities.location(text)
    assert entities.month(text) == month and location is not None and location.uf == "RJ"


# --- classifier ------------------------------------------------------------------------------


def test_classifier_reproduces_the_study():
    """Model E with the one-way entity rule: 77.2% in the 9.4.1-3 table (mean of 5 partitions).
    Partition 0 alone is checked here, against the range of the 5 partitions."""
    texts, labels = load_intents().texts_and_labels()
    y = np.array(labels)
    entities = EntityExtractor(load_knowledge_base())
    pred = cross_val_predict(build_classifier(), texts, y, cv=StratifiedKFold(5, shuffle=True, random_state=0))
    for i, text in enumerate(texts):
        if pred[i] == "what_to_plant" and entities.crops(text).ids:
            pred[i] = "planting_time"
    assert 0.74 <= accuracy_score(y, pred) <= 0.81


def test_same_message_same_result(nlu):
    assert nlu.interpret("qndo plantar alfase?") == nlu.interpret("qndo plantar alfase?")


def test_interpretation_is_fast(nlu):
    start = time.perf_counter()
    for _ in range(200):
        nlu.interpret("quando planto alface em vaso no apartamento em março?")
    assert (time.perf_counter() - start) / 200 < 0.02  # well under the 5 s criterion of 9.4


def test_reference_messages_are_not_in_the_training_data():
    trained = {normalize(t) for t in load_intents().texts_and_labels()[0]}
    assert not [m for m, *_ in REFERENCE if normalize(m) in trained]
