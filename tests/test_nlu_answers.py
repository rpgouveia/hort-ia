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


def responder_with_companions(tmp_path, rows: list[str], sources: list[dict] = ()) -> Responder:
    """Copy of the base with extra companion rows (and extra sources)."""
    target = tmp_path / "knowledge"
    shutil.copytree(DEFAULT_KB_DIR, target)
    with (target / "companions.csv").open("a", encoding="utf-8") as f:
        f.writelines(row + "\n" for row in rows)
    path = target / "sources.json"
    path.write_text(
        json.dumps(json.loads(path.read_text(encoding="utf-8")) + list(sources), ensure_ascii=False), encoding="utf-8"
    )
    return Responder(load_knowledge_base(target), load_templates())


UNVERIFIED = {"id": "fonte_pendente", "title": "Pendente", "publisher": "ATD", "verified": False}


def test_withheld_relations_never_reach_the_answer(tmp_path):
    # D6: research evidence (Petri dish germination tests) and unverified sources stay out of the answer.
    r2 = responder_with_companions(tmp_path, [
        "rucula,alface,harms,false,allelopathy,research,embrapa_ct47_cultivo_hortalicas,12,draft,",
        "rucula,cenoura,helps,true,unknown,technical,fonte_pendente,,validated_by_atd,",
    ], [UNVERIFIED])  # fmt: skip
    a = r2.companion_planting("rucula")
    assert a.text == "Não tenho informações sobre plantas que combinam com rúcula." and a.handoff
    assert "rúcula" not in r2.companion_planting("alface").text
    assert "rúcula" not in r2.companion_planting("cenoura").text


def test_closing_note_follows_the_evidence_shown(r, tmp_path):
    # D9: the "costume" note only when every relation shown is traditional.
    r2 = responder_with_companions(tmp_path, [
        "rucula,tomate,helps,true,unknown,technical,embrapa_ct47_cultivo_hortalicas,12,draft,",
    ])  # fmt: skip
    t = load_templates()["companion_planting"]
    tomate = r2.companion_planting("tomate")
    assert t["mixed_note"] in tomate.text and t["traditional_note"] not in tomate.text
    assert "rúcula" in tomate.text
    assert f"{CT47}, p. 12" in tomate.sources and "Companion Plants" in tomate.sources
    rucula = r2.companion_planting("rucula")
    assert rucula.text == f"Plantas que se dão bem com rúcula: tomate. {t['technical_note']}"
    assert rucula.sources == [f"{CT47}, p. 12"]
    assert t["traditional_note"] in r.companion_planting("tomate").text  # unchanged with the current data


def test_rotation_lists_same_family(r):
    a = r.companion_planting("repolho", rotation=True)
    assert all(name in a.text for name in ("couve", "rabanete", "rúcula"))


# --- pest_disease -----------------------------------------------------------------------


def test_pest_without_management_hands_off(r):
    for label in ("earwig", "weevil"):  # tesourinhas and gorgulhos: no management in the base's sources
        a = r.pest_disease(cv_label=label)
        assert "Ainda não tenho uma orientação conferida" in a.text and a.handoff
        assert "O que ajuda:" not in a.text
        # only the symptom's sources (the earwig got a description with sources in the ATD v3)
        assert a.sources == r.cite(r.kb.by_cv_label(label).symptoms_sources)
    assert not r.pest_disease(cv_label="weevil").sources


def test_entry_not_reviewed_shows_only_safe_actions_and_hands_off_treatment(r):
    a = r.pest_disease(cv_label="Tomato___Late_blight")
    entry = r.kb.by_cv_label("Tomato___Late_blight")
    assert entry.validation_status == "validated_by_atd"  # D1: answers like a draft
    assert a.text.startswith("Parece ser: Requeima.\nComo reconhecer: manchas grandes, escuras")
    lines = a.text.split("\n")
    assert lines[2] == "O que ajuda:"
    for action in entry.management:
        assert (f"- {action.description}" in lines) == (action.type != "alternative"), action.description
    assert "calda" not in a.text.lower()
    assert lines[-1] == TREATMENT_HANDOFF and a.handoff
    # the symptom's source, then the shown actions' source (CT 47 p. 11; not "11, 14" of the hidden calda)
    assert a.sources == ["Circular Técnica 121 (doenças do tomateiro), p. 5", f"{CT47}, p. 11"]


def test_virus_answer_says_there_is_no_cure(r):
    a = r.pest_disease(cv_label="Tomato___Tomato_Yellow_Leaf_Curl_Virus")
    entry = r.kb.by_cv_label("Tomato___Tomato_Yellow_Leaf_Curl_Virus")
    lines = a.text.split("\n")
    assert lines[:2] == [
        "Parece ser: Begomovirose (TYLCV).",
        f"Como reconhecer: {entry.symptoms[:1].lower()}{entry.symptoms[1:]}",
    ]
    assert lines[2] == "O que ajuda:"
    assert lines[3:-1] == [f"- {m.description}" for m in entry.management]  # no alternative action for viruses
    assert lines[3].startswith("- Não há controle depois de detectada") and "mosca-branca" in a.text
    # "No cure" must not end with "how to treat" alone: the closing line asks to confirm the problem first.
    assert lines[-1] == TREATMENT_HANDOFF and "Para tratar, o melhor" not in a.text and a.handoff


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


CALDAS_LAGARTAS = (
    "- Aplicar calda de fumo com pimenta ou preparado de sabão neutro.",
    "- Aplicar calda de cebola, que age como repelente.",
)  # alternative (D2)


def test_reviewed_entry_shows_alternative_actions_without_forced_handoff(r, reviewed_responder):
    draft = r.pest_disease(cv_label="catterpillar")
    reviewed = reviewed_responder.pest_disease(cv_label="catterpillar")
    assert not any(c in draft.text for c in CALDAS_LAGARTAS) and draft.handoff
    assert reviewed.text == (
        "Parece ser: Lagartas.\n"
        "Como reconhecer: comem as folhas; as menores entram em frutos e brotos. A lagarta-rosca vive no solo "
        "e derruba plantas novas à noite.\n"
        "O que ajuda:\n"
        "- Aplicar defensivo biológico: Bacillus thuringiensis ou baculovírus.\n"
        f"{CALDAS_LAGARTAS[0]}\n"
        f"{CALDAS_LAGARTAS[1]}\n"
        "- Preservar inimigos naturais: vespas do gênero Trichogramma parasitam lagartas.\n"
        "- Plantar flores em volta da horta para abrigar predadores naturais.\n"
        "Se tiver dúvida sobre o problema, fale com a Assistência Técnica."
    )
    assert not reviewed.handoff  # the closing line offers Technical Assistance without requiring it
    assert TREATMENT_HANDOFF not in reviewed.text
    assert f"{CT47}, p. 14" in reviewed.sources and f"{CT47}, p. 14" not in draft.sources  # source of the caldas


def responder_with_status(tmp_path, status: str) -> Responder:
    """Copy of the base with every pest and disease entry in `status`."""
    target = tmp_path / status
    shutil.copytree(DEFAULT_KB_DIR, target)
    path = target / "pests_diseases.json"
    entries = json.loads(path.read_text(encoding="utf-8"))
    for entry in entries:
        entry["validation_status"] = status
    path.write_text(json.dumps(entries, ensure_ascii=False), encoding="utf-8")
    return Responder(load_knowledge_base(target), load_templates())


def test_validated_by_atd_entry_answers_like_a_draft(r, tmp_path):
    # D1: validated_by_atd = checked against source and page, not an agronomic endorsement.
    atd = responder_with_status(tmp_path, "validated_by_atd")
    draft = responder_with_status(tmp_path, "draft")
    for entry in r.kb.pests_diseases.values():
        assert atd.pest_disease(cv_label=entry.cv_label) == draft.pest_disease(cv_label=entry.cv_label), entry.id
    lagartas = atd.pest_disease(cv_label="catterpillar")
    assert not any(c in lagartas.text for c in CALDAS_LAGARTAS) and lagartas.handoff
    assert lagartas.text.split("\n")[-1] == TREATMENT_HANDOFF


@pytest.mark.parametrize("status", ["draft", "validated_by_atd"])
def test_no_alternative_action_is_shown_unless_reviewed(r, tmp_path, status):
    # Safety property (D11): homemade preparations only appear in `reviewed` entries, and every answer
    # about a harmful entry that is not reviewed routes treatment to Technical Assistance.
    responder = responder_with_status(tmp_path, status)
    for entry in responder.kb.pests_diseases.values():
        a = responder.pest_disease(cv_label=entry.cv_label)
        for action in entry.management:
            if action.type == "alternative":
                assert action.description not in a.text, (entry.id, action.description)
        if entry.type != "healthy" and not entry.is_beneficial:
            assert a.handoff, entry.id


def test_beneficial_insect_is_not_fought(r):
    assert "Não precisa combater" in r.pest_disease(entry_id="benefico_vespas").text


# --- pest_disease: expected symptom after the identification (card 9.4.1-6.1) -------------------

TREATMENT_HANDOFF = "Para confirmar o problema e saber como tratar, fale com a Assistência Técnica."
CT47 = "Recomendações técnicas para o cultivo de hortaliças em agricultura familiar (Circular Técnica 47)"
HPE = "Horta em pequenos espaços (ISBN 978-85-7035-047-3)"


def test_symptom_follows_the_identification_with_its_source(r):
    a = r.pest_disease(cv_label="Tomato___Spider_mites Two-spotted_spider_mite")
    assert a.text == (
        "Parece ser: Ácaro-rajado.\n"
        "Como reconhecer: colônias muito pequenas no verso das folhas, com teias finas; sugam a seiva da planta.\n"
        "O que ajuda:\n"
        "- Alternar os produtos usados, para não selecionar populações tolerantes.\n"
        "Para confirmar o problema e saber como tratar, fale com a Assistência Técnica."
    )  # the two caldas of the ATD v3 are alternative actions, hidden (D2); the symptom stays ours (D3)
    assert a.sources == [f"{CT47}, p. 12", f"{CT47}, p. 13"] and a.handoff  # a draft entry


def test_symptom_sources_come_first_and_are_not_repeated(r):
    a = r.pest_disease(cv_label="slug")
    assert "Como reconhecer: raspam folhas e ramos novos" in a.text
    # symptom (CT 47 p. 12, HPE p. 29), then the shown actions (HPE p. 29 again, CT 47 p. 14)
    assert a.sources == [f"{CT47}, p. 12", f"{HPE}, p. 29", f"{CT47}, p. 14"]


def test_symptom_is_shown_whatever_the_status(reviewed_responder):
    a = reviewed_responder.pest_disease(cv_label="catterpillar")
    assert a.text.startswith("Parece ser: Lagartas.\nComo reconhecer: comem as folhas;") and not a.handoff
    assert a.sources[0] == f"{CT47}, p. 11"


def test_symptom_is_shown_when_there_is_no_action_to_show(r, monkeypatch):
    entry = r.kb.pests_diseases["praga_gafanhotos"].model_copy(update={"management": []})
    monkeypatch.setitem(r.kb.pests_diseases, "praga_gafanhotos", entry)
    a = r.pest_disease(entry_id="praga_gafanhotos")
    assert (
        a.text
        == (
            "Parece ser: Gafanhotos.\nComo reconhecer: comem ramos e folhas.\n"
            "Ainda não tenho uma orientação conferida para combater isso.\n"
            "Para isso, o melhor é falar com a Assistência Técnica."
        )
        and a.handoff
    )
    assert a.sources == [f"{CT47}, p. 12"]


@pytest.mark.parametrize("label", ["weevil"])  # since the ATD v3, the only harmful entry without a symptom
def test_entries_without_symptom_have_no_symptom_line(r, label):
    assert "Como reconhecer" not in r.pest_disease(cv_label=label).text


def test_healthy_and_beneficial_answers_are_unchanged(r):
    healthy = r.pest_disease(cv_label="Tomato___healthy")
    assert (healthy.text, healthy.sources, healthy.handoff) == ("A planta parece saudável.", [], False)
    wasp = r.pest_disease(cv_label="wasp")  # type "beneficial" since the ATD v3 (D4): same answer
    assert (wasp.text, wasp.handoff) == ("Vespas ajudam a horta: comem outras pragas. Não precisa combater.", False)
    assert wasp.sources == [f"{CT47}, p. 11-14", f"{CT47}, p. 12", f"{CT47}, p. 13"]  # sources of the entry


def test_no_pest_answer_leaves_a_placeholder(r, reviewed_responder):
    for responder in (r, reviewed_responder):
        for entry in responder.kb.pests_diseases.values():
            text = responder.pest_disease(cv_label=entry.cv_label).text
            assert "{" not in text and "}" not in text, text


def test_pest_without_identification_asks_for_photo(r):
    a = r.pest_disease()
    assert (a.text, a.sources, a.handoff) == (
        "Para eu ajudar a identificar, mande uma foto da folha ou da parte da planta com problema.",
        [],
        False,
    )


# --- pest_disease: one part per line, actions as list items ------------------------------------


def test_answer_without_action_has_one_part_per_line(r):
    a = r.pest_disease(cv_label="weevil")
    assert a.text.split("\n") == [
        "Parece ser: Gorgulhos.",
        "Ainda não tenho uma orientação conferida para combater isso.",
        "Para isso, o melhor é falar com a Assistência Técnica.",
    ]
    assert "O que ajuda:" not in a.text and a.handoff


def test_pest_answers_have_clean_lines(r, reviewed_responder):
    for responder in (r, reviewed_responder):
        for entry in responder.kb.pests_diseases.values():
            text = responder.pest_disease(cv_label=entry.cv_label).text
            assert text == text.strip(), repr(text)  # no line break (or space) at the start or the end
            assert "\n\n" not in text, repr(text)  # no blank line
            for line in text.split("\n"):
                assert line == line.rstrip(), repr(line)
            visible = [m for m in entry.management if m.type != "alternative" or entry.validation_status == "reviewed"]
            if visible and entry.type != "healthy":
                assert any(line.startswith("- ") for line in text.split("\n")), entry.id


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
    if answer.intent != "pest_disease":  # only pest and disease answers use one part per line
        assert "\n" not in answer.text, answer.text
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


def test_u9_answers_without_crop_keep_a_single_paragraph(r):
    # The U9 loops above cover the crop, region, product and CV label combinations; these are the rest.
    for answer in (
        r.help(),
        r.fallback(),
        r.unknown_crop("crop_care"),
        r.companion_planting(None),
        r.planting_time(None, "sul", 11),
        r.market_price(None, "PR"),
    ):
        _check(answer)
