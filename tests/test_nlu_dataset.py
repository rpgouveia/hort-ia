"""Integrity tests for the NLU dataset (WBS 9.4)."""

import pytest
from pydantic import ValidationError

from hort_ia.knowledge import load_knowledge_base
from hort_ia.nlp import check_test_set, load_intents, load_test_set, normalize
from hort_ia.nlp.dataset import IntentDataset

# Intent set agreed for the MVP. Changing it must be a deliberate decision.
EXPECTED_INTENTS = {
    "planting_time", "what_to_plant", "crop_care", "companion_planting",
    "pest_disease", "market_price", "help", "fallback",
}


@pytest.fixture(scope="module")
def intents():
    return load_intents()


def test_intent_set_matches_agreed_list(intents):
    assert {i.name for i in intents.intents} == EXPECTED_INTENTS


def test_every_kb_crop_appears_in_training_examples(intents):
    # The classifier must learn intents across crops, not tie an intent to one crop.
    corpus = " ".join(normalize(e.text) for i in intents.intents for e in i.examples)
    kb = load_knowledge_base()
    missing = [
        crop.id for crop in kb.crops.values()
        if not any(normalize(name) in corpus for name in [crop.name_pt, *crop.aliases])
    ]
    assert not missing, missing


def test_test_set_is_valid_and_has_no_leakage(intents):
    assert check_test_set(intents, load_test_set()) == []


def test_normalize_ignores_case_accents_and_punctuation():
    assert normalize("Quando planto ALFACE?!") == normalize("quando  planto alface") == "quando planto alface"


def test_same_text_in_two_intents_is_rejected(intents):
    data = intents.model_dump()
    data["intents"][1]["examples"][0] = dict(data["intents"][0]["examples"][0])
    with pytest.raises(ValidationError, match="duplicates"):
        IntentDataset(**data)


def test_intent_with_too_few_examples_is_rejected(intents):
    data = intents.model_dump()
    data["intents"][0]["examples"] = data["intents"][0]["examples"][:5]
    with pytest.raises(ValidationError, match="expected 30-50"):
        IntentDataset(**data)
