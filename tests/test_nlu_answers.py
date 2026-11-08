import itertools
import json
import shutil

import pytest

from hort_ia.knowledge import load_knowledge_base
from hort_ia.knowledge.loader import DEFAULT_KB_DIR
from hort_ia.market.loader import load_market_dataset
from hort_ia.nlp import Responder, load_templates
from hort_ia.nlp.dataset import EntityType


@pytest.fixture(scope="module")
def r():
    return Responder(load_knowledge_base(), load_templates(), load_market_dataset())


# --- formatting --------------------------------------------------------------------


@pytest.mark.parametrize(
    ("months", "text"),
    [
        (list(range(1, 13)), "o ano todo"),
        ([9, 10, 11, 12, 1, 2, 3, 4, 5], "de setembro a maio"),
        ([3], "em março"),
        ([11, 12], "de novembro a dezembro"),
    ],
)
def test_format_months(r, months, text):
    assert r.format_months(months) == text


# --- planting_time -------------------------------------------------------------------


def test_planting_time_with_variants(r):
    a = r.planting_time("alface", "sul", month=10)
    assert "de inverno no Sul: dá para plantar de fevereiro a outubro" in a.text
    assert "de verão no Sul: dá para plantar o ano todo" in a.text
    assert "Agora em outubro está na época" in a.text
    assert a.sources and not a.handoff


def test_planting_time_out_of_season(r):
    assert "Agora em julho não é a época" in r.planting_time("abobrinha", "sul", month=7).text


def test_not_recommended_differs_from_no_data(r):
    not_recommended = r.planting_time("batata", "norte", month=5)
    no_data = r.planting_time("manjericao", "norte", month=5)
    assert "não é recomendado" in not_recommended.text and not not_recommended.handoff
    assert "Não tenho" in no_data.text and no_data.handoff


def test_missing_crop_asks_for_it(r):
    assert r.planting_time(None, "sul", month=1).missing_entity == EntityType.CROP


def test_missing_region_asks_for_location(r):
    assert r.planting_time("alface", None, month=1).missing_entity == EntityType.LOCATION


def test_unknown_crop_lists_known_crops_and_hands_off(r):
    a = r.planting_time("mandioca", "sul", month=1)
    assert a.handoff and "alface" in a.text


# --- what_to_plant / crop_care ----------------------------------------------------------


def test_what_to_plant_filters_by_month_and_space(r):
    everything = r.what_to_plant("sul", month=10).text
    small = r.what_to_plant("sul", month=10, small_space=True).text
    assert "abobrinha" in everything and "abobrinha" not in small
    assert "alface" in small


def test_crop_care_watering_prefers_crop_specific_rule(r):
    assert "uma vez por dia" in r.crop_care("manjericao", "watering").text
    assert "2 ou 3 dias" in r.crop_care("tomate", "watering").text


def test_crop_care_container_for_roots_is_not_recommended(r):
    a = r.crop_care("cenoura", "container")
    assert "não é indicado" in a.text and "Raízes" in a.text


# --- companion_planting -------------------------------------------------------------------


def test_traditional_relations_are_labeled_as_such(r):
    a = r.companion_planting("tomate")
    assert "manjericão" in a.text and "batata" in a.text
    assert "Não são recomendação técnica" in a.text


def test_repellent_role_is_attributed_to_embrapa(r):
    assert "recomendado pela Embrapa" in r.companion_planting("manjericao").text


def test_rotation_lists_same_family(r):
    a = r.companion_planting("repolho", rotation=True)
    assert all(name in a.text for name in ("couve", "rabanete", "rúcula"))


# --- pest_disease -----------------------------------------------------------------------


def test_pest_without_management_hands_off(r):
    for label in ("earwig", "weevil"):  # tesourinhas and gorgulhos: no content in the base's sources
        a = r.pest_disease(cv_label=label)
        assert "Ainda não tenho uma orientação conferida" in a.text and a.handoff
        assert "O que ajuda:" not in a.text and not a.sources


def test_draft_entry_shows_only_safe_actions_and_hands_off_treatment(r):
    a = r.pest_disease(cv_label="Tomato___Late_blight")
    entry = r.kb.by_cv_label("Tomato___Late_blight")
    assert entry.validation_status == "draft"
    assert a.text.startswith("Parece ser: Requeima. O que ajuda:")
    for action in entry.management:
        assert (action.description in a.text) == (action.type != "alternative"), action.description
    assert "calda" not in a.text.lower()
    assert a.text.endswith("Para tratar, o melhor é falar com a Assistência Técnica.") and a.handoff
    assert a.sources == ["Recomendações técnicas para o cultivo de hortaliças em agricultura familiar "
                         "(Circular Técnica 47), p. 11"]  # only the shown actions' source (no HPE p. 29)


def test_virus_answer_says_there_is_no_cure(r):
    a = r.pest_disease(cv_label="Tomato___Tomato_Yellow_Leaf_Curl_Virus")
    assert "Não há cura" in a.text and "mosca-branca" in a.text and a.handoff


@pytest.fixture
def reviewed_responder(tmp_path):
    """Copy of the base with `praga_lagartas` marked as reviewed by the agronomists."""
    target = tmp_path / "knowledge"
    shutil.copytree(DEFAULT_KB_DIR, target)
    path = target / "pests_diseases.json"
    entries = json.loads(path.read_text(encoding="utf-8"))
    next(e for e in entries if e["id"] == "praga_lagartas")["validation_status"] = "reviewed"
    path.write_text(json.dumps(entries, ensure_ascii=False), encoding="utf-8")
    return Responder(load_knowledge_base(target), load_templates())


def test_reviewed_entry_shows_alternative_actions_without_forced_handoff(r, reviewed_responder):
    draft = r.pest_disease(cv_label="catterpillar")
    reviewed = reviewed_responder.pest_disease(cv_label="catterpillar")
    assert "nim" not in draft.text and draft.handoff
    entry = reviewed_responder.kb.by_cv_label("catterpillar")
    assert all(action.description in reviewed.text for action in entry.management)
    assert "nim" in reviewed.text and not reviewed.handoff
    assert "Assistência Técnica" not in reviewed.text
    assert any("Horta em pequenos espaços" in s for s in reviewed.sources)  # source of the nim action


def test_beneficial_insect_is_not_fought(r):
    assert "Não precisa combater" in r.pest_disease(entry_id="benefico_vespas").text


# --- pest_disease: expected symptom after the identification (card 9.4.1-6.1) -------------------

CT47 = "Recomendações técnicas para o cultivo de hortaliças em agricultura familiar (Circular Técnica 47)"
HPE = "Horta em pequenos espaços (ISBN 978-85-7035-047-3)"


def test_symptom_follows_the_identification_with_its_source(r):
    a = r.pest_disease(cv_label="Tomato___Spider_mites Two-spotted_spider_mite")
    assert a.text.startswith("Parece ser: Ácaro-rajado. Como reconhecer: colônias muito pequenas no verso das folhas")
    assert f"{CT47}, p. 12" in a.sources
    assert "O que ajuda:" in a.text and a.handoff  # still a draft entry
    assert a.text.endswith("Para tratar, o melhor é falar com a Assistência Técnica.")


def test_symptom_sources_come_first_and_are_not_repeated(r):
    a = r.pest_disease(cv_label="slug")
    assert "Como reconhecer: raspam folhas e ramos novos" in a.text
    # symptom (CT 47 p. 12, HPE p. 29), then the shown actions (HPE p. 29 again, CT 47 p. 14)
    assert a.sources == [f"{CT47}, p. 12", f"{HPE}, p. 29", f"{CT47}, p. 14"]


def test_symptom_is_shown_whatever_the_status(reviewed_responder):
    a = reviewed_responder.pest_disease(cv_label="catterpillar")
    assert a.text.startswith("Parece ser: Lagartas. Como reconhecer: comem as folhas;") and not a.handoff
    assert a.sources[0] == f"{CT47}, p. 11"


def test_symptom_is_shown_when_there_is_no_action_to_show(r, monkeypatch):
    entry = r.kb.pests_diseases["praga_gafanhotos"].model_copy(update={"management": []})
    monkeypatch.setitem(r.kb.pests_diseases, "praga_gafanhotos", entry)
    a = r.pest_disease(entry_id="praga_gafanhotos")
    assert a.text.startswith("Parece ser: Gafanhotos. Como reconhecer: comem ramos e folhas.")
    assert "Ainda não tenho uma orientação conferida" in a.text and a.handoff
    assert a.sources == [f"{CT47}, p. 12"]


@pytest.mark.parametrize("label", ["earwig", "Tomato___Late_blight"])
def test_entries_without_symptom_have_no_symptom_line(r, label):
    assert "Como reconhecer" not in r.pest_disease(cv_label=label).text


def test_healthy_and_beneficial_answers_are_unchanged(r):
    healthy = r.pest_disease(cv_label="Tomato___healthy")
    assert (healthy.text, healthy.sources, healthy.handoff) == ("A planta parece saudável.", [], False)
    wasp = r.pest_disease(cv_label="wasp")
    assert (wasp.text, wasp.sources, wasp.handoff) == (
        "Vespas ajudam a horta: comem outras pragas. Não precisa combater.", [f"{CT47}, p. 12"], False)


def test_no_pest_answer_leaves_a_placeholder(r, reviewed_responder):
    for responder in (r, reviewed_responder):
        for entry in responder.kb.pests_diseases.values():
            text = responder.pest_disease(cv_label=entry.cv_label).text
            assert "{" not in text and "}" not in text, text


def test_pest_without_identification_asks_for_photo(r):
    assert "foto" in r.pest_disease().text


# --- market_price / help / fallback ------------------------------------------------------


def test_market_price_uses_local_ceasa(r):
    a = r.market_price("tomate", uf="PR")
    assert "Curitiba" in a.text and "R$" in a.text and "atacado" in a.text


def test_market_price_falls_back_to_national_average(r):
    assert "nos Ceasas do país" in r.market_price("cebola", uf="AM").text


def test_market_price_for_untracked_crop(r):
    assert "Não tenho o preço de rúcula" in r.market_price("rucula", uf="PR").text


def test_fallback_always_hands_off(r):
    assert r.fallback().handoff


def test_every_template_placeholder_is_filled(r):
    calls = [
        r.planting_time("alface", "sul", 10),
        r.planting_time("batata", "norte", 1),
        r.what_to_plant("sul", 10),
        r.crop_care("alface"),
        r.crop_care("cenoura", "container"),
        r.companion_planting("tomate"),
        r.companion_planting("repolho", rotation=True),
        r.pest_disease(cv_label="Tomato___Early_blight"),
        r.market_price("tomate", "PR"),
        r.help(),
        r.fallback(),
    ]
    for answer in calls:
        assert "{" not in answer.text and "}" not in answer.text, answer.text


# --- U9 (9.4.2-2): every combination of intent, crop, region and aspect ----------------------

NO_SOURCE_EXPECTED = {  # answers that use no curated data, so they cite nothing
    "Para eu ajudar a identificar, mande uma foto",  # pest_disease without a photo
    "A planta parece saudável.",
    "Não tenho o preço de",  # market product without a price: lists the ones there are
}


def _check(answer):
    assert "{" not in answer.text and "}" not in answer.text, answer.text
    assert answer.text.strip()
    if answer.handoff or answer.missing_entity is not None or answer.intent in ("help", "fallback"):
        return
    if any(answer.text.startswith(prefix) for prefix in NO_SOURCE_EXPECTED):
        return
    assert answer.sources, f"technical answer without a source: {answer.text}"


def test_u9_every_crop_region_month_and_aspect(r):
    from hort_ia.core.geo import Region

    for crop in r.kb.crops:
        for region, month in itertools.product([*Region, None], range(1, 13)):
            _check(r.planting_time(crop, region, month))
        for aspect in (None, "spacing", "harvest", "watering", "container"):
            _check(r.crop_care(crop, aspect))
        for rotation in (False, True):
            _check(r.companion_planting(crop, rotation))
    for region, month, small in itertools.product(Region, range(1, 13), (False, True)):
        _check(r.what_to_plant(region, month, small))


def test_u9_every_product_and_state(r):
    from hort_ia.core.geo import UF_BY_CODE

    for product in [*r.market.products, *r.kb.crops, "mandioca", None]:
        for uf in [*UF_BY_CODE.values(), None]:
            _check(r.market_price(product, uf))


def test_u9_every_cv_label_and_no_photo(r):
    labels = [p.cv_label for p in r.kb.pests_diseases.values() if p.cv_label]
    assert labels
    for label in [*labels, None, "rotulo_desconhecido"]:
        _check(r.pest_disease(cv_label=label))


def test_u9_unknown_crop_hands_off(r):
    for answer in (r.planting_time("mandioca", "sul", 11), r.crop_care("mandioca"), r.unknown_crop("crop_care")):
        assert answer.handoff and answer.text.startswith("Ainda não tenho informações sobre essa planta")
