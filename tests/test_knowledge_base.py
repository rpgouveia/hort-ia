"""Integrity tests for the agronomic knowledge base (evidence for WBS 9.3.2)."""

import json
import shutil
from pathlib import Path

import pytest
from pydantic import ValidationError

from hort_ia.knowledge import load_knowledge_base
from hort_ia.knowledge.loader import DEFAULT_KB_DIR
from hort_ia.knowledge.models import Crop, PlantingWindow

# Scope approved for the MVP (15 crops). Changing it must be a deliberate decision.
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
        if entry.beneficial:
            assert not entry.management, entry.id


def test_aliases_do_not_collide_across_crops(kb):
    seen: dict[str, str] = {}
    for crop in kb.crops.values():
        for name in [crop.name_pt.lower(), *(a.lower() for a in crop.aliases)]:
            assert (
                seen.setdefault(name, crop.id) == crop.id
            ), f"'{name}' is used by '{seen[name]}' and '{crop.id}'"


# --- Validators reject broken data -------------------------------------------


@pytest.fixture
def kb_copy(tmp_path: Path) -> Path:
    target = tmp_path / "knowledge"
    shutil.copytree(DEFAULT_KB_DIR, target)
    return target


def test_unknown_crop_in_companions_is_rejected(kb_copy):
    (kb_copy / "companions.csv").write_text(
        "crop_a,crop_b,relation,source_id,validation_status,notes\n"
        "tomate,mandioca,helps,kaggle_companion_plants,draft,\n",
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


def test_invalid_month_is_rejected():
    with pytest.raises(ValidationError, match="between 1 and 12"):
        PlantingWindow(
            months_by_region={"sul": [0, 13]},
            harvest_start_days={"min": 60, "max": 80},
            source={"source_id": "embrapa_catalogo_hortalicas", "pages": "13"},
        )


# --- Content checks for the first curated version ------------------------------


def test_all_crops_have_required_fields(kb):
    incomplete = {
        c.id: c.missing_fields() for c in kb.crops.values() if c.missing_fields()
    }
    assert not incomplete, incomplete


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
