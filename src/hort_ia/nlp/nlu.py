"""Natural language understanding of the conversational assistant (WBS 9.4.1-4).

Turns a user message into an intent, a confidence and the entities the answers need, as fixed in
`docs/nlu/9.4.1-3_Abordagem_Motor_Conversacional.md`, sections 4.2 and 4.3:

- **Intent** (decision D2): TF-IDF of character 2-5-grams plus word 1-2-grams, logistic regression,
  trained at start-up from `data/nlu/intents.yaml` (about 0.1 s). No model file is versioned: the
  model is always the dataset of the repository.
- **Entities** (D3): a dictionary built from the knowledge base (`name_pt`, `id` and `aliases` of each
  crop) and from the market products, exact match first; a typo-tolerant match only when the exact one
  finds nothing, flagged with `crop_fuzzy` so the dialogue confirms it, and dropped for `help` and
  `fallback`. Month, small space, care aspect, rotation and location by fixed term lists.
- **Entity rule** (D4), one way only: `what_to_plant` with a crop becomes `planting_time`. The reverse
  is not done, so "quando planto mandioca?" (a crop outside the catalog) stays `planting_time` and the
  dialogue asks which plant, instead of answering the list of the month.

What to do with the result (confirm, ask, answer, fall back) is the dialogue manager's job (9.4.1-5).
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from functools import lru_cache

from pydantic import BaseModel
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline, make_pipeline, make_union

from ..core.geo import CODE_BY_UF, Region, region_from_uf
from ..knowledge import KnowledgeBase, get_knowledge_base
from .dataset import IntentDataset, load_intents, normalize

NO_FUZZY_INTENTS = {"help", "fallback"}  # a typo-tolerant crop is ignored for these intents

# --- term lists (normalized: lower case, no accents) --------------------------------------

MONTHS = {
    "janeiro": 1, "fevereiro": 2, "marco": 3, "abril": 4, "maio": 5, "junho": 6,
    "julho": 7, "agosto": 8, "setembro": 9, "outubro": 10, "novembro": 11, "dezembro": 12,
    # Only unambiguous abbreviations: "mar", "mai", "set", "out" and "dez" are common words.
    "jan": 1, "fev": 2, "abr": 4, "jun": 6, "jul": 7, "ago": 8, "nov": 11,
}  # fmt: skip
SMALL_SPACE_TERMS = [
    "vaso", "vasos", "vasinho", "vasinhos", "jardineira", "jardineiras", "varanda", "sacada", "apartamento",
    "apto", "pouco espaco", "pequeno espaco", "espaco pequeno", "quintal pequeno",
]  # fmt: skip
CARE_ASPECT_TERMS = {
    "watering": ["rega", "regar", "rego", "rega-la", "regando", "aguar", "agua", "molhar", "irrigar", "irrigacao"],
    "spacing": ["espacamento", "distancia", "espaco entre", "quanto de espaco", "longe uma da outra"],
    "harvest": ["colher", "colheita", "colho", "colhe", "colhendo", "ponto de colheita"],
}
ROTATION_TERMS = ["depois", "no lugar", "rodizio", "rotacao", "em seguida", "apos", "sucessao", "na sequencia"]
STATES = {
    "acre": "AC", "alagoas": "AL", "amapa": "AP", "amazonas": "AM", "bahia": "BA", "ceara": "CE",
    "distrito federal": "DF", "espirito santo": "ES", "goias": "GO", "maranhao": "MA", "mato grosso": "MT",
    "mato grosso do sul": "MS", "minas gerais": "MG", "minas": "MG", "para": "PA", "paraiba": "PB",
    "parana": "PR", "pernambuco": "PE", "piaui": "PI", "rio de janeiro": "RJ", "rio grande do norte": "RN",
    "rio grande do sul": "RS", "rondonia": "RO", "roraima": "RR", "santa catarina": "SC", "sao paulo": "SP",
    "sergipe": "SE", "tocantins": "TO",
}  # fmt: skip
CAPITALS = {
    "rio branco": "AC",
    "maceio": "AL",
    "macapa": "AP",
    "manaus": "AM",
    "salvador": "BA",
    "fortaleza": "CE",
    "brasilia": "DF",
    "vitoria": "ES",
    "goiania": "GO",
    "sao luis": "MA",
    "cuiaba": "MT",
    "campo grande": "MS",
    "belo horizonte": "MG",
    "belem": "PA",
    "joao pessoa": "PB",
    "curitiba": "PR",
    "recife": "PE",
    "teresina": "PI",
    "natal": "RN",
    "porto alegre": "RS",
    "porto velho": "RO",
    "boa vista": "RR",
    "florianopolis": "SC",
    "aracaju": "SE",
    "palmas": "TO",
}  # fmt: skip  (Rio de Janeiro and São Paulo are covered by the state names)
REGIONS = {
    "norte": Region.NORTE, "nordeste": Region.NORDESTE, "centro oeste": Region.CENTRO_OESTE,
    "sudeste": Region.SUDESTE, "sul": Region.SUL,
}  # fmt: skip
# Place names that are also common words. Missing a place costs nothing, because the profile is used;
# reading a place that was not named answers with the season of another region (9.4.2-1, section 2).
# So these names count only in the context given here, a regex over the normalized text, or as the
# whole answer to "Em qual cidade fica a sua horta?" (`short_reply`, see `EntityExtractor.location`).
AMBIGUOUS_PLACES = {
    "para": r"estado do para",  # the preposition; "Pará" with the accent counts anywhere (ACCENTED_PLACES)
    "acre": r"(?:no|do|ao) acre",  # the unit of area: "um acre", "por acre", "acres"
    "mato grosso": r"(?:em|no|do|ao) mato grosso",  # thick weeds: "tem um mato grosso no canteiro"
    "natal": r"em natal",  # Christmas: "no natal", "pro natal", "árvore de natal"
    "campo grande": r"em campo grande",  # a big field: "tenho um campo grande atrás de casa"
    "belem": r"em belem",  # the "estrela-de-belém" plant, the nativity scene ("presépio de Belém")
    "boa vista": r"em boa vista",  # a good view: "a varanda tem uma boa vista"
    "palmas": r"em palmas",  # the "palma" cactus, the "palma-de-santa-rita" flower, palm leaves, applause
    "vitoria": r"em vitoria(?! regia)",  # victory, the first name, the "vitória-régia" water lily
    "norte": r"(?:no|do|regiao) norte",  # where the sun comes from: "canteiro virado para o norte"
    "sul": r"(?:no|do|regiao) sul",  # idem: "a horta pega sol do lado sul"
}
ACCENTED_PLACES = {"para": "pará"}  # written with the accent, the name can only be the place
SHORT_REPLY_LEAD = r"(?:(?:moro|fico|sou|aqui|aqui e|e) )?(?:(?:em|no|do|de) )?"  # "moro em", "sou do", "é"
# State and capital names with a month in them ("rio de janeiro"): that month is not a month.
PLACES_WITH_A_MONTH = [name for name in (*STATES, *CAPITALS) if set(name.split()) & set(MONTHS)]


def _contains(text: str, term: str) -> bool:
    return re.search(rf"(?<!\w){re.escape(term)}(?!\w)", text) is not None


def _flat(text: str) -> str:
    """`normalize`, with hyphens kept apart so 'centro-oeste' matches 'centro oeste'."""
    return normalize(text.replace("-", " "))


def _names_place(text: str, flat: str, name: str, short_reply: bool) -> bool:
    """Whether the message names this place; names in AMBIGUOUS_PLACES need their context."""
    context = AMBIGUOUS_PLACES.get(name)
    if context is None:
        return _contains(flat, name)
    if short_reply and re.fullmatch(SHORT_REPLY_LEAD + re.escape(name), flat):
        return True
    accented = ACCENTED_PLACES.get(name)
    if accented and _contains(unicodedata.normalize("NFC", text).lower(), accented):
        return True
    return re.search(rf"(?<!\w)(?:{context})(?!\w)", flat) is not None


def levenshtein(a: str, b: str) -> int:
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def build_classifier() -> Pipeline:
    """Model E of the 9.4.1-1 study: characters + words, logistic regression."""

    def tfidf(**kwargs) -> TfidfVectorizer:
        return TfidfVectorizer(preprocessor=normalize, sublinear_tf=True, **kwargs)

    return make_pipeline(
        make_union(tfidf(analyzer="char_wb", ngram_range=(2, 5)), tfidf(ngram_range=(1, 2))),
        LogisticRegression(max_iter=2000, C=10),
    )


# --- result -----------------------------------------------------------------------------


class Location(BaseModel):
    region: Region
    uf: str | None = None  # None when only the region was named


class IntentScore(BaseModel):
    intent: str
    confidence: float


class Interpretation(BaseModel):
    """What the message says. `confidence` is the classifier's probability for its top intent."""

    intent: str
    confidence: float
    alternatives: list[IntentScore]  # the three most likely intents, before the entity rule
    entity_rule_applied: bool = False  # what_to_plant turned into planting_time (D4)
    crops: list[str] = []  # crop or market product ids, in the order they appear
    crop_fuzzy: bool = False  # True when the crop was found only by the typo-tolerant match
    month: int | None = None
    small_space: bool = False
    care_aspect: str | None = None  # watering | spacing | harvest | container
    rotation: bool = False
    location: Location | None = None

    @property
    def crop(self) -> str | None:
        return self.crops[0] if self.crops else None


# --- entities ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CropMatch:
    ids: list[str]
    fuzzy: bool


class EntityExtractor:
    """Dictionary and term-list entities. The crop dictionary is derived from the knowledge base, so a
    new alias in `data/knowledge/crops.json` is understood by the assistant with no code change."""

    def __init__(self, kb: KnowledgeBase, market=None):
        names: dict[str, str] = {}
        for crop in kb.crops.values():
            for name in (crop.name_pt, crop.id, *crop.aliases):
                names[_flat(name)] = crop.id
        if market is not None:  # products with a price but outside the catalog (cebola)
            for product in market.products.values():
                for name in (product.name_pt, product.id, *product.aliases):
                    names.setdefault(_flat(name), product.crop_id or product.id)
        self.names = names
        self._by_length = sorted(names, key=len, reverse=True)  # "tomate cereja" before "tomate"
        self._single_words = {k: v for k, v in names.items() if " " not in k}

    def crops(self, text: str) -> CropMatch:
        text = _flat(text)
        found: list[tuple[int, str]] = []
        masked = f" {text} "
        for name in self._by_length:
            for m in re.finditer(rf"(?<!\w){re.escape(name)}(?!\w)", masked):
                found.append((m.start(), self.names[name]))
            masked = re.sub(rf"(?<!\w){re.escape(name)}(?!\w)", lambda m: " " * len(m.group()), masked)
        if found:
            return CropMatch(ids=list(dict.fromkeys(cid for _, cid in sorted(found))), fuzzy=False)
        fuzzy = []
        for token in text.split():
            for name, crop_id in self._single_words.items():
                limit = 2 if len(name) >= 8 else 1 if len(name) >= 5 else 0
                if limit and abs(len(token) - len(name)) <= limit and levenshtein(token, name) <= limit:
                    fuzzy.append(crop_id)
                    break
        return CropMatch(ids=list(dict.fromkeys(fuzzy)), fuzzy=bool(fuzzy))

    @staticmethod
    def month(text: str) -> int | None:
        """First month named in the message. A month inside a place name ("rio de janeiro") is not one."""
        text = _flat(text)
        for place in PLACES_WITH_A_MONTH:
            text = re.sub(rf"(?<!\w){re.escape(place)}(?!\w)", lambda m: " " * len(m.group()), text)
        hits = [(m.start(), n) for name, n in MONTHS.items() for m in re.finditer(rf"(?<!\w){name}(?!\w)", text)]
        return min(hits)[1] if hits else None

    @staticmethod
    def small_space(text: str) -> bool:
        text = _flat(text)
        return any(_contains(text, term) for term in SMALL_SPACE_TERMS)

    @classmethod
    def care_aspect(cls, text: str) -> str | None:
        flat = _flat(text)
        for aspect, terms in CARE_ASPECT_TERMS.items():
            if any(_contains(flat, term) for term in terms):
                return aspect
        return "container" if cls.small_space(text) else None

    @staticmethod
    def rotation(text: str) -> bool:
        text = _flat(text)
        return any(_contains(text, term) for term in ROTATION_TERMS)

    @staticmethod
    def location(text: str, short_reply: bool = False) -> Location | None:
        """State or capital name, UF abbreviation, or region name.

        UF abbreviations collide with common words ("se", "to", "es", "ma", "pa"), so they count only
        when written in upper case ("PR") in a message that is not all in upper case ("SE CHOVER",
        "PE DE ALFACE") or, with `short_reply`, when the whole message is the abbreviation, as in the
        answer to "Em qual cidade fica a sua horta?".

        Names that collide with common words ("para", "natal", "acre", "campo grande") count only in
        the context listed in AMBIGUOUS_PLACES ("no Pará", "moro em Natal", "sou do Acre"), or with
        `short_reply` when the message is just the place ("natal", "moro em natal").
        """
        flat = _flat(text)
        for names in (CAPITALS, STATES):
            for name in sorted(names, key=len, reverse=True):
                if _names_place(text, flat, name, short_reply):
                    uf = names[name]
                    return Location(region=region_from_uf(uf), uf=uf)
        mixed_case = any(ch.islower() for ch in text)
        upper = re.findall(r"(?<![A-Za-z])([A-Z]{2})(?![A-Za-z])", text) if mixed_case else []
        candidates = upper + ([flat.upper()] if short_reply and len(flat) == 2 else [])
        for uf in candidates:
            if uf in CODE_BY_UF:
                return Location(region=region_from_uf(uf), uf=uf)
        for name in sorted(REGIONS, key=len, reverse=True):
            if _names_place(text, flat, name, short_reply):
                return Location(region=REGIONS[name])
        return None


# --- interpreter ------------------------------------------------------------------------


class Interpreter:
    """Intent and entities of one message. Build once (it trains the classifier) and reuse."""

    def __init__(self, kb: KnowledgeBase, market=None, dataset: IntentDataset | None = None):
        texts, labels = (dataset or load_intents()).texts_and_labels()
        self.classifier = build_classifier().fit(texts, labels)
        self.entities = EntityExtractor(kb, market)

    def interpret(self, text: str) -> Interpretation:
        probabilities = self.classifier.predict_proba([text])[0]
        ranked = sorted(zip(self.classifier.classes_, probabilities), key=lambda p: -p[1])
        intent, confidence = str(ranked[0][0]), float(ranked[0][1])

        crops = self.entities.crops(text)
        if crops.fuzzy and intent in NO_FUZZY_INTENTS:
            crops = CropMatch(ids=[], fuzzy=False)
        rule = intent == "what_to_plant" and bool(crops.ids)
        if rule:
            intent = "planting_time"

        return Interpretation(
            intent=intent,
            confidence=round(confidence, 4),
            alternatives=[IntentScore(intent=str(i), confidence=round(float(p), 4)) for i, p in ranked[:3]],
            entity_rule_applied=rule,
            crops=crops.ids,
            crop_fuzzy=crops.fuzzy,
            month=self.entities.month(text),
            small_space=self.entities.small_space(text),
            care_aspect=self.entities.care_aspect(text),
            rotation=self.entities.rotation(text),
            location=self.entities.location(text),
        )


@lru_cache(maxsize=1)
def get_interpreter() -> Interpreter:
    """Cached instance for the API (use as a dependency). Takes no arguments: see `api.nlp.get_responder`."""
    from ..market import get_market_dataset

    return Interpreter(get_knowledge_base(), get_market_dataset())
