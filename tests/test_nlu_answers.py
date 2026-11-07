import itertools

import pytest

from hort_ia.knowledge import load_knowledge_base
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
    a = r.pest_disease(cv_label="Tomato___Late_blight")
    assert "Requeima" in a.text and a.handoff


def test_beneficial_insect_is_not_fought(r):
    assert "Não precisa combater" in r.pest_disease(entry_id="benefico_vespas").text


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
