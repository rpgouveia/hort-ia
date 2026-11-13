import json
import re
import shutil
from pathlib import Path

import pytest
from pydantic import ValidationError

from hort_ia.core.sources import SourceRef
from hort_ia.knowledge import load_knowledge_base
from hort_ia.knowledge.loader import DEFAULT_KB_DIR
from hort_ia.knowledge.models import (
    Crop,
    Germination,
    ManagementType,
    PestDisease,
    PlantingWindow,
    SoilPh,
    SowingDepth,
    Sun,
    ValidationStatus,
)

# Scope approved for the MVP (15 crops), plus the 5 crops of the ATD delivery v3 (Nov 2026).
# Changing it must be a deliberate decision.
EXPECTED_CROPS = {
    "tomate",
    "batata",
    "pimentao",
    "morango",
    "alface",
    "couve",
    "rucula",
    "repolho",
    "cenoura",
    "beterraba",
    "rabanete",
    "cebolinha",
    "salsa",
    "manjericao",
    "abobrinha",
    "coentro",  # ATD v3
    "hortela",
    "brocolis",
    "espinafre",
    "pimenta",
}

# Classes kept from the New Plant Diseases Dataset after filtering to garden crops.
PLANT_DISEASE_LABELS = {
    "Tomato___Bacterial_spot",
    "Tomato___Early_blight",
    "Tomato___Late_blight",
    "Tomato___Leaf_Mold",
    "Tomato___Septoria_leaf_spot",
    "Tomato___Spider_mites Two-spotted_spider_mite",
    "Tomato___Target_Spot",
    "Tomato___Tomato_Yellow_Leaf_Curl_Virus",
    "Tomato___Tomato_mosaic_virus",
    "Tomato___healthy",
    "Potato___Early_blight",
    "Potato___Late_blight",
    "Potato___healthy",
    "Pepper,_bell___Bacterial_spot",
    "Pepper,_bell___healthy",
    "Strawberry___Leaf_scorch",
    "Strawberry___healthy",
}

# Classes kept from the Agricultural Pests Image Dataset (bees and earthworms removed).
PEST_LABELS = {
    "ants",
    "beetle",
    "catterpillar",
    "earwig",
    "grasshopper",
    "moth",
    "slug",
    "snail",
    "wasp",
    "weevil",
}


@pytest.fixture(scope="module")
def kb():
    return load_knowledge_base()


def test_knowledge_base_loads(kb):
    assert kb.crops and kb.sources and kb.pests_diseases


def test_crop_scope_matches_approved_list(kb):
    assert set(kb.crops) == EXPECTED_CROPS


def test_every_plant_disease_label_resolves(kb):
    for label in PLANT_DISEASE_LABELS:
        assert kb.by_cv_label(label) is not None, f"no KB entry for CV class '{label}'"


def test_every_pest_label_resolves(kb):
    for label in PEST_LABELS:
        assert kb.by_cv_label(label) is not None, f"no KB entry for CV class '{label}'"


def test_beneficial_pests_have_no_control_actions(kb):
    for entry in kb.pests_diseases.values():
        if entry.is_beneficial:  # `type: beneficial` (ATD v3) or `beneficial: true`
            assert not entry.management, entry.id


def test_wasps_are_beneficial(kb):
    wasps = kb.by_cv_label("wasp")
    assert wasps.type == "beneficial" and wasps.beneficial is True  # D4: both forms are accepted


def test_aliases_do_not_collide_across_crops(kb):
    seen: dict[str, str] = {}
    for crop in kb.crops.values():
        for name in [crop.name_pt.lower(), *(a.lower() for a in crop.aliases)]:
            assert seen.setdefault(name, crop.id) == crop.id, f"'{name}' is used by '{seen[name]}' and '{crop.id}'"


# --- Validators reject broken data -------------------------------------------


@pytest.fixture
def kb_copy(tmp_path: Path) -> Path:
    target = tmp_path / "knowledge"
    shutil.copytree(DEFAULT_KB_DIR, target)
    return target


def test_unknown_crop_in_companions_is_rejected(kb_copy):
    (kb_copy / "companions.csv").write_text(
        "crop_a,crop_b,relation,mutual,mechanism,evidence,source_id,pages,validation_status,notes\n"
        "tomate,mandioca,helps,false,unknown,traditional,kaggle_companion_plants,,draft,\n",
        encoding="utf-8",
    )
    with pytest.raises(ValidationError, match="unknown crop 'mandioca'"):
        load_knowledge_base(kb_copy)


def test_duplicate_crop_id_is_rejected(kb_copy):
    path = kb_copy / "crops.json"
    crops = json.loads(path.read_text(encoding="utf-8"))
    crops.append(crops[0])
    path.write_text(json.dumps(crops, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(ValueError, match="duplicate ids"):
        load_knowledge_base(kb_copy)


def test_reviewed_crop_must_be_complete():
    with pytest.raises(ValidationError, match="missing"):
        Crop(
            id="alface",
            name_pt="Alface",
            scientific_name="Lactuca sativa",
            family="Asteraceae",
            validation_status="reviewed",
        )


def test_validated_by_atd_crop_may_have_gaps():
    # D1: `validated_by_atd` means "checked against source and page", not complete; only `reviewed` is.
    crop = Crop(
        id="hortela",
        name_pt="Hortelã",
        scientific_name="Mentha spp.",
        family="Lamiaceae",
        validation_status="validated_by_atd",
    )
    assert crop.missing_fields()


@pytest.mark.parametrize("status", ["draft", "validated_by_atd"])
def test_pest_entry_with_gaps_is_accepted_unless_reviewed(status):
    ref = {"source_id": "embrapa_ct47_cultivo_hortalicas", "pages": "12"}
    entry = {
        "id": "praga_formigas",
        "cv_dataset": "agricultural_pests_dataset",
        "cv_label": "ants",
        "type": "pest",
        "name_pt": "Formigas",
        "symptoms": "Cortam folhas.",
        "symptoms_sources": [ref],
        "sources": [ref],
    }
    assert PestDisease(**entry, validation_status=status).missing_fields() == ["beneficial", "management"]
    with pytest.raises(ValidationError, match="is 'reviewed' but is missing"):
        PestDisease(**entry, validation_status="reviewed")


# --- Crop facts of the ATD delivery v3 (D5) -----------------------------------------------------

CT47_P10 = {"source_id": "embrapa_ct47_cultivo_hortalicas", "pages": "10-11"}


def test_crop_fact_with_value_needs_a_source_with_page():
    with pytest.raises(ValidationError, match="without a source with page"):
        SoilPh(min=6.0, max=6.5)
    with pytest.raises(ValidationError, match="without a source with page"):
        SoilPh(min=6.0, max=6.5, source={"source_id": "embrapa_plantar_tomate", "pages": None})
    assert SoilPh(min=6.0, max=6.5, source={"source_id": "embrapa_plantar_tomate", "pages": "16"}).filled() == [
        "min", "max"]  # fmt: skip


def test_empty_crop_fact_must_explain_the_gap():
    with pytest.raises(ValidationError, match="explain the gap"):
        Sun(source=None)
    assert Sun(notes="LACUNA: fonte nao informa.").filled() == []
    # a source without values is fine (the source gives only a general rule, recorded in notes)
    assert SowingDepth(source={"source_id": "epagri_bd107_hortalicas", "pages": "38"}, notes="Regra geral.")


def test_crop_fact_ranges_are_checked():
    with pytest.raises(ValidationError, match="greater than"):
        Germination(temp_ideal_min_c=25, temp_ideal_max_c=18, source=CT47_P10)
    with pytest.raises(ValidationError, match="alt_source needs a source with page"):
        Germination(temp_min_c=6, source=CT47_P10, alt_source={"source": {"source_id": "x", "pages": ""}})


def test_crop_fact_sources_are_checked_against_the_registry(kb_copy):
    path = kb_copy / "crops.json"
    crops = json.loads(path.read_text(encoding="utf-8"))
    crops[0]["soil_ph"] = {"min": 6.0, "max": 6.5, "source": {"source_id": "fonte_inexistente", "pages": "1"}}
    crops[0]["rotation"] = {"rotation_group": crops[0]["family"], "avoid_after": ["mandioca"], "source": CT47_P10}
    path.write_text(json.dumps(crops, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(ValidationError) as error:
        load_knowledge_base(kb_copy)
    assert "unknown source 'fonte_inexistente'" in str(error.value)
    assert "unknown crop 'mandioca'" in str(error.value)


# --- Beneficial type and crop scope (D4, D5) ----------------------------------------------------


def test_beneficial_type_is_accepted_and_never_has_control_actions():
    ref = {"source_id": "embrapa_ct47_cultivo_hortalicas", "pages": "12"}
    wasp = {
        "id": "benefico_vespas",
        "cv_dataset": "agricultural_pests_dataset",
        "cv_label": "wasp",
        "type": "beneficial",
        "name_pt": "Vespas",
        "sources": [ref],
    }
    assert PestDisease(**wasp).is_beneficial and PestDisease(**wasp, beneficial=True).is_beneficial
    with pytest.raises(ValidationError, match="beneficial=false"):
        PestDisease(**wasp, beneficial=False)
    with pytest.raises(ValidationError, match="must not have control actions"):
        PestDisease(**wasp, management=[{"type": "cultural", "description": "Teste.", "source": ref}])


def test_crop_scope_agrees_with_crop_ids():
    base = {"id": "praga_teste", "cv_dataset": "agricultural_pests_dataset", "cv_label": "teste", "type": "pest"}
    assert PestDisease(**base, crop_scope="all_vegetables").crop_ids == []
    with pytest.raises(ValidationError, match="must leave crop_ids empty"):
        PestDisease(**base, crop_scope="all_vegetables", crop_ids=["tomate"])
    with pytest.raises(ValidationError, match="needs crop_ids"):
        PestDisease(**base, crop_scope="specific")


def test_invalid_month_is_rejected():
    with pytest.raises(ValidationError, match="between 1 and 12"):
        PlantingWindow(
            months_by_region={"sul": [0, 13]},
            harvest_start_days={"min": 60, "max": 80},
            source={"source_id": "embrapa_catalogo_hortalicas", "pages": "13"},
        )


# --- Content checks for the first curated version ------------------------------


# Crops of the ATD delivery v3 that came without these fields (documented in data/knowledge/README.md).
# Remove a crop from here when its gap is closed.
KNOWN_INCOMPLETE_CROPS = {
    "coentro": ["crop_groups", "propagation", "spacing", "sources"],
    "espinafre": ["crop_groups", "propagation", "spacing", "sources"],
    "brocolis": ["crop_groups", "propagation", "spacing", "sources"],
    "pimenta": ["crop_groups", "propagation", "spacing", "sources"],
    "hortela": ["crop_groups", "propagation", "planting_windows", "spacing", "sources"],
}


def test_all_crops_have_required_fields_except_known_gaps(kb):
    incomplete = {c.id: c.missing_fields() for c in kb.crops.values() if c.missing_fields()}
    assert incomplete == KNOWN_INCOMPLETE_CROPS
    assert all(kb.crops[c].validation_status == "draft" for c in KNOWN_INCOMPLETE_CROPS)


def test_wrapping_planting_window_is_parsed(kb):
    # Catálogo p. 9: abobrinha no Sul de setembro a maio (atravessa a virada do ano)
    window = kb.crops["abobrinha"].planting_windows[0]
    assert window.months_by_region["sul"] == [9, 10, 11, 12, 1, 2, 3, 4, 5]


def test_not_recommended_region_is_empty_list(kb):
    # Catálogo p. 17: batata "não recomendável" no Nordeste e no Norte
    window = kb.crops["batata"].planting_windows[0]
    assert window.months_by_region["nordeste"] == []
    assert window.months_by_region["norte"] == []


def test_small_space_spacing_is_smaller_than_conventional(kb):
    for crop in kb.crops.values():
        if crop.spacing and crop.spacing.small_spaces:
            conv, small = crop.spacing.conventional, crop.spacing.small_spaces
            assert small.between_rows_cm <= conv.between_rows_cm, crop.id
            assert small.between_plants_cm <= conv.between_plants_cm, crop.id


# --- Gap coverage -----------------------------------------------------------------

# Known gaps, documented in data/knowledge/README.md. Remove a crop from here when its gap is closed.
KNOWN_IRRIGATION_GAPS = {"batata", "coentro", "espinafre", "brocolis", "pimenta", "hortela"}  # ATD v3: no crop_groups


def test_every_crop_has_an_irrigation_guideline(kb):
    irrigation = [g for g in kb.guidelines.values() if g.topic == "irrigation"]
    uncovered = set()
    for crop in kb.crops.values():
        covered = any(
            crop.id in g.applies_to_crops or set(crop.crop_groups) & set(g.applies_to_groups)
            for g in irrigation
            if g.applies_to_crops or g.applies_to_groups  # skip rules that only give volumes
        )
        if not covered:
            uncovered.add(crop.id)
    assert uncovered == KNOWN_IRRIGATION_GAPS


def test_manjericao_has_window_for_sul(kb):
    windows = kb.crops["manjericao"].planting_windows
    sul = [w for w in windows if "sul" in w.months_by_region]
    assert len(sul) == 1
    assert sul[0].months_by_region["sul"] == [11, 12]


def test_overlapping_windows_are_rejected():
    window = {
        "months_by_region": {"sul": [11, 12]},
        "harvest_start_days": {"min": 60, "max": 70},
        "source": {"source_id": "embrapa_folder_manjericao", "pages": "1"},
    }
    with pytest.raises(ValidationError, match="defined twice"):
        Crop(
            id="manjericao",
            name_pt="Manjericão",
            scientific_name="Ocimum basilicum",
            family="Lamiaceae",
            planting_windows=[window, window],
        )


# --- Companion planting -----------------------------------------------------------


def test_companions_loaded(kb):
    assert len(kb.companions) >= 30


def test_withheld_relations_are_research_or_unverified(kb):
    # D6: kept in the base, out of every automatic output until the ATD confirms them.
    withheld = [c for c in kb.companions if not kb.is_usable(c)]
    assert len(withheld) == 14
    for c in kb.companions:
        expected = c.evidence == "research" or not kb.sources[c.source_id].verified
        assert (c in withheld) == expected, c
    assert sum(c.evidence == "research" for c in withheld) == 7
    assert {c.evidence for c in kb.usable_companions()} == {"traditional"}  # all 14 new ones are withheld


def test_pending_sources_are_unverified_placeholders(kb):
    # D7: cited by the ATD v3 and not registered; nothing that depends on them reaches the user (D6).
    pending = {"embrapa_folder_plantas_companheiras", "embrapa_horta_domestica_portal",
               "embrapa_it134_alface_crespa", "unioeste_alelopatia_couve"}  # fmt: skip
    for source_id in pending:
        source = kb.sources[source_id]
        assert not source.verified and source.title == "Pendente: metadados a enviar pela ATD", source_id
    unverified = {s.id for s in kb.sources.values() if not s.verified}
    assert unverified == pending | {"new_plant_diseases_dataset", "agricultural_pests_dataset"}


def test_data_shown_to_the_user_cites_only_verified_sources(kb):
    """What the engine and the assistant show: windows, spacing, yield, roles, guidelines, pest entries."""
    refs = []
    for crop in kb.crops.values():
        refs += [w.source for w in crop.planting_windows] + [r.source for r in crop.companion_roles]
        refs += [x.source for x in (crop.spacing, crop.yield_estimate) if x]
    refs += [g.source for g in kb.guidelines.values()]
    for entry in kb.pests_diseases.values():
        refs += [*entry.sources, *entry.symptoms_sources, *(a.source for a in entry.management)]
    refs += [SourceRef(source_id=c.source_id) for c in kb.usable_companions()]
    assert {r.source_id for r in refs if not kb.sources[r.source_id].verified} == set()


def test_no_pair_is_both_helpful_and_harmful_in_same_source(kb):
    relations: dict[tuple, set[str]] = {}
    for c in kb.companions:
        key = (tuple(sorted((c.crop_a, c.crop_b))), c.source_id)
        relations.setdefault(key, set()).add(c.relation)
    contradictory = [k for k, rels in relations.items() if len(rels) > 1]
    assert not contradictory, contradictory


def test_traditional_relations_have_unknown_mechanism(kb):
    # The Kaggle/Wikipedia dataset gives no reason for each relation; inventing one is not allowed.
    for c in kb.companions:
        if c.source_id == "kaggle_companion_plants":
            assert c.evidence == "traditional" and c.mechanism == "unknown"


def test_mutual_relation_applies_both_ways(kb):
    harms = next(c for c in kb.companions if c.mutual and c.relation == "harms")
    assert harms.involves(harms.crop_a, harms.crop_b)
    assert harms.involves(harms.crop_b, harms.crop_a)


def test_repellent_roles_come_from_technical_sources(kb):
    for crop_id in ("manjericao", "cebolinha", "coentro", "hortela"):
        roles = kb.crops[crop_id].companion_roles
        assert roles and all(r.evidence == "technical" for r in roles)


def test_duplicate_pair_from_same_source_is_rejected(kb_copy):
    (kb_copy / "companions.csv").write_text(
        "crop_a,crop_b,relation,mutual,mechanism,evidence,source_id,pages,validation_status,notes\n"
        "tomate,manjericao,helps,false,unknown,traditional,kaggle_companion_plants,,draft,\n"
        "manjericao,tomate,helps,false,unknown,traditional,kaggle_companion_plants,,draft,\n",
        encoding="utf-8",
    )
    with pytest.raises(ValidationError, match="appears twice"):
        load_knowledge_base(kb_copy)


# --- Rotation by family and planting windows of the ATD v3 crops ------------------------------


def test_rotation_avoid_after_matches_the_family_of_the_crops(kb):
    # D5: `rotation.avoid_after` materializes the CT 47 rule; it must agree with `family` of the base.
    for crop in kb.crops.values():
        assert crop.rotation is not None, crop.id
        same_family = sorted(c.id for c in kb.crops.values() if c.family == crop.family and c.id != crop.id)
        assert sorted(crop.rotation.avoid_after) == same_family, crop.id
        assert crop.rotation.rotation_group == crop.family, crop.id


def test_planting_windows_filled_by_the_ai_module_are_drafts(kb):
    # D8: Catálogo Brasileiro de Hortaliças, printed pages; pending the ATD's check.
    pages = {"brocolis": "22", "coentro": "28", "espinafre": "33", "pimenta": "48"}
    for crop_id, page in pages.items():
        crop = kb.crops[crop_id]
        assert crop.validation_status == "draft" and f"Catálogo (p. {page})" in crop.notes, crop_id
        assert {(w.source.source_id, w.source.pages) for w in crop.planting_windows} == {
            ("embrapa_catalogo_hortalicas", page)}  # fmt: skip
    assert kb.crops["brocolis"].planting_months("sul") == {"inverno": list(range(2, 10)), "verao": [10, 11, 12]}
    assert kb.crops["brocolis"].planting_months("norte") == {"inverno": [], "verao": [4, 5, 6, 7]}
    assert kb.crops["coentro"].planting_months("sul") == {None: [9, 10, 11, 12, 1]}
    assert kb.crops["espinafre"].planting_months("norte") == {None: [3, 4, 5]}
    assert kb.crops["pimenta"].planting_months("sudeste") == {None: [8, 9, 10, 11, 12, 1, 2, 3]}
    assert "duas espécies" in kb.crops["espinafre"].notes
    assert kb.crops["hortela"].planting_windows == []


# --- Regional adaptation -----------------------------------------------------------


def test_planting_months_by_region(kb):
    # Catálogo p. 13: alface de inverno no Sul de fevereiro a outubro; de verão, o ano todo
    months = kb.crops["alface"].planting_months("sul")
    assert months == {"inverno": list(range(2, 11)), "verao": list(range(1, 13))}


def test_planting_months_distinguishes_not_recommended_from_no_data(kb):
    assert kb.crops["batata"].planting_months("norte") == {None: []}  # "não recomendável"
    assert kb.crops["manjericao"].planting_months("norte") is None  # sem dado


def test_every_crop_has_planting_data_for_sul(kb):
    # Cobertura completa no Sul (manjericão via folder Embrapa); as outras regiões têm lacunas documentadas.
    # Hortelã (ATD v3) ainda sem época: pendência da ATD.
    missing = [c.id for c in kb.crops.values() if kb.crops[c.id].planting_months("sul") is None]
    assert missing == ["hortela"]


# --- Pests and diseases: management by group (CT 47 pp. 11-14, HPE pp. 28-30 and 37-40) -------

DOSE = re.compile(r"\d+([.,]\d+)?\s*(g\b|ml\b|litros?\b|%)", re.IGNORECASE)


def test_every_management_action_cites_a_registered_source_and_page(kb):
    for entry in kb.pests_diseases.values():
        for action in entry.management:
            assert action.source.source_id in kb.sources, (entry.id, action.description)
            assert action.source.pages, (entry.id, action.description)
            assert action.source in entry.sources, f"'{entry.id}': action source missing from entry sources"


def test_every_symptom_has_its_own_registered_source_with_page(kb):
    with_symptoms = [e for e in kb.pests_diseases.values() if e.symptoms]
    assert len(with_symptoms) == 22  # ATD v3: the 10 diseases, the wasps and the earwigs got symptoms
    for entry in with_symptoms:
        assert entry.symptoms_sources, entry.id
        for ref in entry.symptoms_sources:
            assert ref.source_id in kb.sources and ref.pages, (entry.id, ref)


def test_symptom_sources_are_listed_in_entry_sources(kb):
    for entry in kb.pests_diseases.values():
        for ref in entry.symptoms_sources:
            assert ref in entry.sources, f"'{entry.id}': symptom source {ref} missing from entry sources"


@pytest.mark.parametrize("status", ["draft", "reviewed"])
def test_symptom_without_symptoms_sources_is_rejected(status):
    ref = {"source_id": "embrapa_ct47_cultivo_hortalicas", "pages": "12"}
    with pytest.raises(ValidationError, match="symptoms without symptoms_sources"):
        PestDisease(
            id="praga_teste",
            cv_dataset="agricultural_pests_dataset",
            cv_label="teste",
            type="pest",
            name_pt="Teste",
            beneficial=False,
            symptoms="Comem as folhas.",
            sources=[ref],
            management=[{"type": "cultural", "description": "Teste.", "source": ref}],
            validation_status=status,
        )


def test_unregistered_symptom_source_is_rejected(kb_copy):
    path = kb_copy / "pests_diseases.json"
    entries = json.loads(path.read_text(encoding="utf-8"))
    entry = next(e for e in entries if e["id"] == "praga_lesmas")
    entry["symptoms_sources"] = [{"source_id": "fonte_inexistente", "pages": "1"}]
    path.write_text(json.dumps(entries, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(ValidationError, match="unknown source 'fonte_inexistente'"):
        load_knowledge_base(kb_copy)


# The former test "every alternative action contains 'Peça orientação técnica'" was replaced by a stronger
# property, checked on the answers: no alternative action is shown unless the entry is `reviewed`
# (tests/test_nlu_answers.py::test_no_alternative_action_is_shown_unless_reviewed). The ATD texts are
# kept as received (D10), so the phrase is no longer in the data.


def test_management_type_follows_the_d2_rule(kb):
    # D2: the ATD sends actions without type; the type comes from a keyword rule (scripts/merge_atd_v3.py).
    from merge_atd_v3 import classify

    for entry in kb.pests_diseases.values():
        for action in entry.management:
            assert action.type == classify(action.description)[0], (entry.id, action.description)
    assert classify("Aplicar calda de cebola.")[0] == ManagementType.ALTERNATIVE
    assert classify("Recolher os animais reunidos embaixo.")[0] == ManagementType.CULTURAL  # "nim" in "animais"


def test_only_agronomists_mark_pests_and_diseases_as_reviewed(kb):
    # D1: the ATD uses `validated_by_atd` (checked against source and page); `reviewed` is the agronomists'
    # decision (9.4.1-9), not a data change.
    statuses = {e.validation_status for e in kb.pests_diseases.values()}
    assert statuses == {ValidationStatus.DRAFT, ValidationStatus.VALIDATED_BY_ATD}


# D3: symptom sources of the 10 diseases, as in the ATD validation PDF (request 6).
DISEASE_SYMPTOM_SOURCES = {
    "tomate_pinta_preta": [("embrapa_ct121_tomate", "5")],
    "tomate_requeima": [("embrapa_ct121_tomate", "5")],
    "tomate_septoriose": [("embrapa_ct121_tomate", "6")],
    "tomate_mancha_bacteriana": [("embrapa_ct121_tomate", "7"), ("embrapa_ct84_mancha_bacteriana", "3")],
    "tomate_mancha_alvo": [("embrapa_roraima_doc03_tomate", "8")],
    "tomate_cladosporiose": [("embrapa_ct31_cladosporiose", "4")],
    "batata_requeima": [("embrapa_cpact_batata_organica", "35")],
    "batata_pinta_preta": [("embrapa_cpact_batata_organica", "36")],
    "pimentao_mancha_bacteriana": [("embrapa_bpd223_pimentao", "10")],
    "morango_leaf_scorch": [("embrapa_ct96_morango", "3"), ("senar_pr0355_morango", "18")],
}


def test_disease_symptoms_cite_the_pages_of_the_atd_validation(kb):
    for entry_id, expected in DISEASE_SYMPTOM_SOURCES.items():
        entry = kb.pests_diseases[entry_id]
        assert [(r.source_id, r.pages) for r in entry.symptoms_sources] == expected, entry_id
        assert entry.validation_status == "validated_by_atd"
    for entry_id in ("batata_requeima", "batata_pinta_preta"):  # pages marked "a conferir" by the ATD
        assert "a conferir" in kb.pests_diseases[entry_id].notes


def test_crop_scope_all_vegetables_leaves_crop_ids_empty(kb):
    generic = [e for e in kb.pests_diseases.values() if e.cv_dataset == "agricultural_pests_dataset"]
    assert generic and all(e.crop_scope == "all_vegetables" and e.crop_ids == [] for e in generic)
    assert all(e.crop_scope == "specific" for e in kb.pests_diseases.values() if e not in generic)


def test_no_doses_in_management(kb):
    for entry in kb.pests_diseases.values():
        for action in entry.management:
            assert not DOSE.search(action.description), (entry.id, action.description)


def test_dose_pattern_catches_doses():
    for text in ("dilua 10 ml", "use 2 litros", "50 g por planta", "solução a 1%", "1,5 litro"):
        assert DOSE.search(text), text
    assert not DOSE.search("Evite excesso de água no canteiro.")


# Without content in the base's sources; pending with the agronomists (9.4.1-9).
NO_MANAGEMENT_YET = {"praga_tesourinhas", "praga_gorgulhos"}


def test_every_harmful_entry_has_management_except_known_gaps(kb):
    harmful = [e for e in kb.pests_diseases.values() if e.type != "healthy" and not e.is_beneficial]
    assert len(harmful) == 22
    assert {e.id for e in harmful if not e.management} == NO_MANAGEMENT_YET
