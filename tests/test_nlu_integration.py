"""Integration of the assistant with its content sources and the API (WBS 9.4.2-3).

Cases I1-I9 of `docs/nlu/9.4.2-1_Plano_Casos_Teste.md`, section 3; each test name starts with its case
id. The content comes from the module's own sources (knowledge base, market base and the recommendation
engine); every check compares the answer given over HTTP with those files, so a wrong figure in an
answer (critical failure 1) fails here. Calls go through the whole FastAPI app in process.
"""

import json
import shutil
from pathlib import Path

import pytest
import yaml
from starlette.testclient import TestClient

from hort_ia.api.main import app
from hort_ia.api.nlp import get_dialogue
from hort_ia.core.calendar import format_months
from hort_ia.core.geo import CODE_BY_UF, Region
from hort_ia.knowledge import load_knowledge_base
from hort_ia.knowledge.loader import kb_dir
from hort_ia.market.loader import load_market_dataset
from hort_ia.nlp import DialogueManager, Interpreter, Responder, load_intents, load_templates
from hort_ia.nlp.dataset import nlu_dir

KB, MARKET, TEMPLATES = load_knowledge_base(), load_market_dataset(), load_templates()
CITY_BY_REGION = {  # one municipality per macro-region (IBGE codes)
    Region.NORTE: 1302603,  # Manaus
    Region.NORDESTE: 2927408,  # Salvador
    Region.CENTRO_OESTE: 5208707,  # Goiânia
    Region.SUDESTE: 3550308,  # São Paulo
    Region.SUL: 4106902,  # Curitiba
}


@pytest.fixture(scope="module")
def client() -> TestClient:
    return TestClient(app)


def message(client, text, *, context=None, **profile) -> dict:
    response = client.post("/nlp/message", json={"text": text, "context": context, **profile})
    assert response.status_code == 200, response.text
    return response.json()


def ask(client, text, **profile) -> dict:
    """A question as a user would follow it: confirms once if the assistant asks to confirm."""
    reply = message(client, text, **profile)
    if reply["decision"] == "confirm":
        reply = message(client, "sim", context=reply["context"], **profile)
    return reply


def region_label(region: Region) -> str:
    return TEMPLATES["regions"][region.value]


# --- I1: knowledge base -> assistant ------------------------------------------------------


@pytest.mark.parametrize("crop_id", sorted(KB.crops))
@pytest.mark.parametrize("region", list(Region), ids=lambda r: r.value)
def test_i1_planting_time_answers_with_the_months_of_the_base(client, crop_id, region):
    crop = KB.crops[crop_id]
    reply = ask(client, f"quando planto {crop.name_pt.lower()}?", ibge_code=CITY_BY_REGION[region], month=6)
    assert (reply["decision"], reply["intent"], reply["entities"]["crop"]) == ("answer", "planting_time", crop_id)
    windows = crop.planting_months(region)
    if windows is None:
        assert reply["text"].startswith("Não tenho a época de plantio") and reply["handoff"]
        return
    for months in windows.values():
        expected = format_months(months, TEMPLATES["months"]) if months else "não é recomendado plantar"
        assert expected in reply["text"], (expected, reply["text"])
    assert region_label(region) in reply["text"]
    assert reply["sources"]


# --- I2: every name of the base reaches the right crop through the API -------------------------


@pytest.mark.parametrize(
    ("crop_id", "name"), [(c.id, n) for c in KB.crops.values() for n in (c.name_pt, *c.aliases)], ids=str
)
def test_i2_every_name_and_alias_reaches_the_crop(client, crop_id, name):
    reply = ask(client, f"como cuido de {name}?", ibge_code=4106902)
    assert reply["entities"]["crop"] == crop_id, reply


# --- I3: a change only in the data reaches the assistant ----------------------------------------


@pytest.fixture
def data_copy(tmp_path: Path):
    knowledge, nlu = tmp_path / "knowledge", tmp_path / "nlu"
    shutil.copytree(kb_dir(), knowledge)
    shutil.copytree(nlu_dir(), nlu)
    return knowledge, nlu


@pytest.fixture
def api_on(client):
    """Points `/nlp/message` at an assistant built from copies of the data."""

    def use(knowledge: Path, nlu: Path) -> TestClient:
        kb = load_knowledge_base(knowledge)
        dialogue = DialogueManager(
            Interpreter(kb, MARKET, load_intents(nlu / "intents.yaml")),
            Responder(kb, load_templates(nlu / "responses.yaml"), MARKET),
        )
        app.dependency_overrides[get_dialogue] = lambda: dialogue
        return client

    yield use
    app.dependency_overrides.pop(get_dialogue, None)


def test_i3_new_alias_is_understood(api_on, data_copy):
    knowledge, nlu = data_copy
    assert message(api_on(knowledge, nlu), "quando planto alfacinha?", ibge_code=4106902)["entities"]["crop"] is None
    path = knowledge / "crops.json"
    crops = json.loads(path.read_text(encoding="utf-8"))
    next(c for c in crops if c["id"] == "alface")["aliases"].append("alfacinha")
    path.write_text(json.dumps(crops, ensure_ascii=False), encoding="utf-8")
    reply = ask(api_on(knowledge, nlu), "quando planto alfacinha?", ibge_code=4106902)
    assert (reply["decision"], reply["entities"]["crop"]) == ("answer", "alface")


def test_i3_new_answer_text_is_used(api_on, data_copy):
    knowledge, nlu = data_copy
    path = nlu / "responses.yaml"
    templates = yaml.safe_load(path.read_text(encoding="utf-8"))
    templates["fallback"]["text"] = "Ainda não sei falar sobre isso."
    path.write_text(yaml.safe_dump(templates, allow_unicode=True), encoding="utf-8")
    reply = message(api_on(knowledge, nlu), "como crio galinha?")
    assert reply["text"].startswith("Ainda não sei falar sobre isso.") and reply["handoff"]


def test_i3_new_training_examples_change_the_classification(api_on, data_copy):
    knowledge, nlu = data_copy
    before = message(api_on(knowledge, nlu), "alface aguenta frio?", ibge_code=4106902)
    assert before["decision"] == "ask" and before["confidence"] < 0.3
    path = nlu / "intents.yaml"
    dataset = yaml.safe_load(path.read_text(encoding="utf-8"))
    care = next(i for i in dataset["intents"] if i["name"] == "crop_care")
    care["examples"] += [
        {"text": text, "origin": "team"}
        for text in ("a couve aguenta frio?", "tomate aguenta geada?", "a alface resiste ao frio?", "salsa aguenta frio forte?")
    ]  # fmt: skip
    path.write_text(yaml.safe_dump(dataset, allow_unicode=True), encoding="utf-8")
    after = message(api_on(knowledge, nlu), "alface aguenta frio?", ibge_code=4106902)
    assert after["intent"] == "crop_care" and after["confidence"] > before["confidence"]


# --- I4: market base -> assistant ------------------------------------------------------------


def expected_price(product_id: str, uf: str | None) -> tuple[str, str]:
    """(price as written, where) with the same rule as the Responder: the UF's Ceasa, else the national mean."""
    local = next((e for e in MARKET.entrepostos.values() if uf and e.uf == uf), None)
    ref = MARKET.reference_price(product_id, local.id) if local else None
    where = f"no {local.name_pt}" if ref else "nos Ceasas do país"
    ref = ref or MARKET.reference_price(product_id)
    return f"R$ {ref.price_brl_kg:.2f}".replace(".", ","), where


@pytest.mark.parametrize("product_id", sorted(MARKET.products))
@pytest.mark.parametrize("uf", sorted({e.uf for e in MARKET.entrepostos.values()} | {"BA", "AM"}))
def test_i4_price_answers_match_the_market_base(client, product_id, uf):
    name = MARKET.products[product_id].name_pt.lower()
    reply = ask(client, f"quanto ta o {name} no ceasa?", ibge_code=int(CODE_BY_UF[uf]))
    assert (reply["intent"], reply["entities"]["crop"]) == ("market_price", product_id)
    price, where = expected_price(product_id, uf)
    assert price in reply["text"] and where in reply["text"], (price, where, reply["text"])
    assert reply["sources"]


# --- I6: computer vision labels -> assistant ---------------------------------------------------


@pytest.mark.parametrize("entry", [p for p in KB.pests_diseases.values() if p.cv_label], ids=lambda p: p.cv_label)
def test_i6_every_cv_label_is_answered(client, entry):
    reply = message(client, "olha essa foto", cv_label=entry.cv_label)
    assert (reply["decision"], reply["intent"], reply["confidence"]) == ("answer", "pest_disease", None)
    if entry.type == "healthy":
        assert reply["text"] == "A planta parece saudável."
    elif entry.beneficial:
        assert entry.name_pt in reply["text"] and "Não precisa combater" in reply["text"] and reply["sources"]
    else:
        assert f"Parece ser: {entry.name_pt or entry.causal_agent or entry.cv_label}." in reply["text"]
        assert reply["handoff"] == (not entry.management)


def test_i6_unknown_label_asks_for_a_photo(client):
    reply = message(client, "olha essa foto", cv_label="rotulo_que_nao_existe")
    assert "mande uma foto" in reply["text"]


# --- I7: reference conversations over HTTP -------------------------------------------------------

CONVERSATIONS = {
    "C1": ["quando eu planto?", "alface"],
    "C2": ["quando planto mandioca?", "mandioca"],
    "C3": ["qndo plantar alfase?", "sim"],
    "C4": ["qual a epoca de plantar alface?", "e a rega dela?"],
    "C5": ["a alface ta amarelando", "sim"],
    "C6": ["tem como plantar morango aqui?", "não", "quando planto"],
    "C7": ["alface aguenta frio?"],
    "C8": ["como crio galinha?"],
}


@pytest.mark.parametrize("case", sorted(CONVERSATIONS))
def test_i7_conversations_over_http_match_the_engine(client, case):
    direct = DialogueManager(Interpreter(KB, MARKET), Responder(KB, TEMPLATES, MARKET))
    context_http, context_direct = None, None
    for text in CONVERSATIONS[case]:
        over_http = message(client, text, context=context_http, ibge_code=4106902, month=11)
        in_process = direct.handle(text, context=context_direct, ibge_code=4106902, month=11)
        assert over_http["decision"] == in_process.decision and over_http["text"] == in_process.text, text
        context_http, context_direct = over_http["context"], in_process.context


# --- I8: the routes agree with each other ----------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "structured"),
    [
        ("quando planto alface?", {"intent": "planting_time", "crop_id": "alface", "region": "sul", "month": 11}),
        ("qual o espaçamento do pimentão?", {"intent": "crop_care", "crop_id": "pimentao", "aspect": "spacing"}),
        ("o que planto junto do tomate?", {"intent": "companion_planting", "crop_id": "tomate"}),
        ("quanto ta a batata no ceasa?", {"intent": "market_price", "product": "batata", "uf": "PR"}),
        ("o que da pra plantar agora?", {"intent": "what_to_plant", "region": "sul", "month": 11}),
    ],
)
def test_i8_free_text_and_structured_routes_give_the_same_answer(client, text, structured):
    free = ask(client, text, ibge_code=4106902, month=11)
    fixed = client.post("/nlp/answer", json=structured).json()
    assert (free["intent"], free["text"], free["sources"]) == (fixed["intent"], fixed["text"], fixed["sources"])


@pytest.mark.parametrize("crop_id", sorted(KB.crops))
def test_i8_assistant_agrees_with_the_recommender_routes(client, crop_id):
    name = KB.crops[crop_id].name_pt.lower()
    calendar = client.get(f"/recommender/planting-calendar?crop_id={crop_id}&region=sul").json()
    reply = ask(client, f"quando planto {name}?", ibge_code=4106902, month=11)
    for window in calendar["windows"]:
        if window["recommended_months"]:
            assert format_months(window["recommended_months"], TEMPLATES["months"]) in reply["text"]

    partners = client.get(f"/recommender/companion-crops?crop_id={crop_id}").json()
    companion = ask(client, f"o que planto junto de {name}?", ibge_code=4106902)
    assert companion["intent"] == "companion_planting"
    for partner in partners["helps"] + partners["hinders"]:
        assert partner["partner_name_pt"].lower() in companion["text"], (partner, companion["text"])
