"""NLU dataset for the conversational assistant (WBS 9.4): training intents and test set.

Two files in data/nlu/:
- intents.yaml: training examples per intent (30 to 50 each).
- test_utterances.yaml: held-out utterances, written by someone who has NOT seen the
  training file, or collected verbatim from agronomists and garden coordinators.
  An utterance with `intent: null` fits no current intent and signals a missing one.

Every example records its `origin` so drafted text can be told apart from real questions.
"""

from __future__ import annotations

import os
import re
import unicodedata
from enum import StrEnum
from pathlib import Path
from typing import Self

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

from ..core.sources import ID_PATTERN

# src/hort_ia/nlp/dataset.py -> repository root is parents[3]
DEFAULT_NLU_DIR = Path(__file__).resolve().parents[3] / "data" / "nlu"

MIN_EXAMPLES, MAX_EXAMPLES = 30, 50


def nlu_dir() -> Path:
    return Path(os.environ.get("HORTIA_NLU_DIR", DEFAULT_NLU_DIR))


def normalize(text: str) -> str:
    """Lowercase, strip accents and punctuation, collapse spaces (used for duplicate checks)."""
    text = unicodedata.normalize("NFKD", text.lower())
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"[^\w\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


class Origin(StrEnum):
    DRAFT = "draft"  # drafted (including with AI help), pending replacement by real questions
    TEAM = "team"  # written by a team member
    FIELD = "field"  # collected verbatim from agronomists, coordinators or growers


class EntityType(StrEnum):
    CROP = "crop"
    MONTH = "month"
    REGION = "region"
    LOCATION = "location"
    SPACE = "space"  # vaso, varanda, canteiro
    CARE_ASPECT = "care_aspect"  # rega, espaçamento, colheita, sol, vaso
    PEST = "pest"
    SYMPTOM = "symptom"


class NLUModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Example(NLUModel):
    text: str = Field(min_length=1)
    origin: Origin


class IntentSpec(NLUModel):
    name: str = Field(pattern=ID_PATTERN)
    description: str
    answered_by: str
    required_entities: list[EntityType] = []
    optional_entities: list[EntityType] = []
    examples: list[Example]

    @model_validator(mode="after")
    def _example_count(self) -> Self:
        n = len(self.examples)
        if not MIN_EXAMPLES <= n <= MAX_EXAMPLES:
            raise ValueError(
                f"intent '{self.name}' has {n} examples (expected {MIN_EXAMPLES}-{MAX_EXAMPLES})"
            )
        return self


class IntentDataset(NLUModel):
    version: int
    language: str
    intents: list[IntentSpec]

    @model_validator(mode="after")
    def _consistency(self) -> Self:
        names = [i.name for i in self.intents]
        if len(set(names)) != len(names):
            raise ValueError(f"duplicate intent names: {names}")
        seen: dict[str, str] = {}
        errors = []
        for intent in self.intents:
            for example in intent.examples:
                key = normalize(example.text)
                if key in seen:
                    errors.append(f"'{example.text}' in '{intent.name}' duplicates one in '{seen[key]}'")
                seen.setdefault(key, intent.name)
        if errors:
            raise ValueError("duplicate examples:\n- " + "\n- ".join(errors))
        return self

    def texts_and_labels(self) -> tuple[list[str], list[str]]:
        pairs = [(e.text, i.name) for i in self.intents for e in i.examples]
        return [t for t, _ in pairs], [label for _, label in pairs]


class TestUtterance(NLUModel):
    text: str = Field(min_length=1)
    intent: str | None  # None = fits no current intent (candidate for a new one)
    origin: Origin
    author: str | None = None  # team member who wrote or transcribed it
    collected_from: str | None = None  # role only, never a name (LGPD): "agronomo", "coordenador"
    notes: str | None = None


class TestSet(NLUModel):
    version: int
    language: str
    utterances: list[TestUtterance] = []

    def labeled(self) -> list[TestUtterance]:
        return [u for u in self.utterances if u.intent is not None]


def _read_yaml(path: Path) -> dict:
    with path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        raise ValueError(f"{path.name}: expected a mapping at the top level")
    return data


def load_intents(path: Path | None = None) -> IntentDataset:
    return IntentDataset(**_read_yaml(path or nlu_dir() / "intents.yaml"))


def load_test_set(path: Path | None = None) -> TestSet:
    data = _read_yaml(path or nlu_dir() / "test_utterances.yaml")
    data["utterances"] = data.get("utterances") or []
    return TestSet(**data)


def leakage(train: IntentDataset, test: TestSet) -> list[str]:
    """Test utterances that also appear (normalized) in the training data."""
    train_keys = {normalize(e.text) for i in train.intents for e in i.examples}
    return [u.text for u in test.utterances if normalize(u.text) in train_keys]


def check_test_set(train: IntentDataset, test: TestSet) -> list[str]:
    """Problems that make the test set unusable for evaluation."""
    problems = [f"also in training data: '{t}'" for t in leakage(train, test)]
    known = {i.name for i in train.intents}
    problems += [
        f"unknown intent '{u.intent}' for '{u.text}'"
        for u in test.utterances
        if u.intent is not None and u.intent not in known
    ]
    return problems
