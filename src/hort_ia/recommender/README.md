# Recommender: what to plant now, for this garden (WBS 9.3)

Given a garden profile, returns the crops worth planting now, best first, each with the rules that
put it there and their sources. Knowledge-based: hard filters on the crop attributes of the knowledge
base (`data/knowledge/`, 9.3.1-7), then a rule-based score. Study of the techniques: 9.3.1-1/-2.
Approach and decision record: 9.3.1-3 (sections 4 and 9). Engine: 9.3.1-4. Profile and routes: 9.3.1-5.

## How it decides

1. **Filters** (`Recommender._exclusion`), applied in this order; the first that applies is recorded
   in `excluded` with its reason:

   | # | Rule | `reason` |
   |---|---|---|
   | F1 | No planting window for the region | `no_region_data` |
   | F2 | The month is in no window of the region | `out_of_season` |
   | F3 | `small_space` and the crop is not suited (`false`) or has no information (`null`) | `not_for_small_space` / `no_small_space_info` |
   | F4 | The crop is already in `planted` | `already_planted` |
   | F5 | Same botanical family as `previous_crop` | `same_family_as_previous` |

   Rotation (F5) is a filter because it has a technical source (Embrapa, Circular Técnica 47).
   Companion planting only orders the list, because all 37 relations of the base are traditional.
2. **Score**: `W_COMPANION` (1.0) per planted crop it combines with, minus 1.0 per planted crop it
   does not combine with; plus `W_REPELLENT` (0.5) for a pest-repellent crop (cebolinha, manjericão)
   when something is already planted. One relation per pair, in either direction; an unfavorable
   record would win over a favorable one.
3. **Order**: score, then the season that ends first (consecutive months left in the window; 12 for
   all-year crops), then the name without accents. The same profile always gives the same list.
4. **Explanation**: every item has `reasons` and `warnings`, each with a `code`, a short Portuguese
   `text` and its `source`:

   | `code` | When | Example |
   |---|---|---|
   | `in_season` | Always, one per cultivar type in season | "Alface de verão: no Sul, dá para plantar o ano todo." |
   | `season_ending` | Up to `SEASON_ENDING_MONTHS` (2) months left | "A época de plantio termina em dezembro." |
   | `companion_good` | One per planted crop it combines with | "Combina com tomate (indicação tradicional)." |
   | `pest_repellent` | Repellent crop and something planted | "Ajuda a afastar pragas das outras plantas da horta." |
   | `companion_bad` (warning) | One per planted crop it does not combine with | "Não combina com tomate (indicação tradicional)." |

Unknown crops in `planted` or `previous_crop` (e.g. mandioca, outside the catalog) are ignored and
reported in `warnings`; the profile comes from another module of the platform and may name crops the
base does not cover yet. An invalid IBGE code raises `RecommenderError` (422 in the API).

**Stateless and not learned.** Nothing is stored between calls and no profile is kept (LGPD). There
is no interaction history to learn from yet; whoever collects the "útil / não útil" ratings (the UAT
form now, the consumer module later) records them with `model_version`, which is the data a future
collaborative step would need (decision D8).

## Using it

```python
from hort_ia.recommender import Profile, get_recommender

result = get_recommender().recommend(Profile(ibge_code=4106902, month=11, small_space=True, planted=["tomate"]))
[(i.crop_id, i.score) for i in result.recommendations]
# [("manjericao", 1.5), ("cebolinha", 1.5), ("pimentao", 1.0), ("alface", 0.0)]
```

```bash
uv run python -m hort_ia.recommender --ibge 4106902 --month 11 --small-space --planted tomate
uv run python -m hort_ia.recommender --region sul --month 3 --previous repolho
```

Endpoint: `POST /recommender/recommendations`

```bash
curl -X POST http://localhost:8080/recommender/recommendations \
  -H "Content-Type: application/json" \
  -d '{"ibge_code": 4106902, "month": 11, "small_space": true, "planted": ["tomate"]}'
```

```json
{
  "region": "sul", "month": 11, "small_space": true,
  "recommendations": [
    {
      "rank": 1, "crop_id": "manjericao", "crop_name_pt": "Manjericão", "score": 1.5, "variants": [],
      "reasons": [
        {"code": "in_season", "text": "No Sul, dá para plantar de novembro a dezembro.", "source": "Manjericão (folder …), p. 1"},
        {"code": "season_ending", "text": "A época de plantio termina em dezembro.", "source": "Manjericão (folder …), p. 1"},
        {"code": "companion_good", "text": "Combina com tomate (indicação tradicional).", "source": "Companion Plants"},
        {"code": "pest_repellent", "text": "Ajuda a afastar pragas das outras plantas da horta.", "source": "… (Circular Técnica 47), p. 12"}
      ],
      "warnings": []
    }
  ],
  "excluded": [{"crop_id": "tomate", "reason": "already_planted"}, {"crop_id": "batata", "reason": "not_for_small_space"}],
  "warnings": [], "approach": "knowledge_based", "model_version": "1.0.0"
}
```

(Abridged: the full answer lists 4 recommendations and 11 exclusions.) Only `month` and one of
`ibge_code` / `region` matter for a first call; `month` defaults to the current one. `ibge_code` wins
over `region`. An invalid location, a missing location or a month outside 1-12 returns 422.

**Other consumers of the same engine**, so the API and the assistant never disagree:

- `GET /recommender/what-to-plant` keeps its 9.7.1-3 contract (parameters, fields, alphabetical
  order) and takes its crops from the engine, with `planted` and `previous_crop` empty.
- `hort_ia.nlp.Responder.what_to_plant` (the conversational assistant) lists the crops in the engine
  order.

## Changing it

| To | Change | Also |
|---|---|---|
| Add a crop, a synonym, a planting window or a companion relation | `data/knowledge/` only; the engine reads the base | Re-check the reference cases (they list crops by name) |
| Change a weight or `SEASON_ENDING_MONTHS` | The constants at the top of `engine.py` | Bump `MODEL_VERSION`; update the reference cases and section 6 of 9.3.1-3 |
| Add or change a filter | `ExclusionReason` in `models.py` and `Recommender._exclusion` | Bump `MODEL_VERSION`; record the decision in 9.3.1-3 |
| Reword an explanation | `texts.yaml` | Keep the writing rules of `data/nlu/README.md` (short sentences, origin explicit when traditional) |

Month names and month ranges ("de setembro a fevereiro") come from `hort_ia.core.calendar`, shared
with the assistant.

## Tests

| File | What it covers |
|---|---|
| `tests/test_recommender_engine.py` | Reference cases R1-R8, E1-E2 of 9.3.1-3 (section 6); explanations, determinism; properties P1-P6 over the 120 profiles, score recomputed from the raw files, ordering, contradictory and empty bases, CLI (cases U1-U13 of 9.3.2-1) |
| `tests/test_recommender_integration.py` | Profile through `POST /recommender/recommendations`, 422s, `what-to-plant` and the assistant agreeing with the engine |

Test plan, coverage target and the definition of a critical failure:
`docs/recommender/9.3.2-1_Plano_Casos_Teste.md`. `docs/recommender/exploratory_recommender_cases.py` is
the prototype that fixed the reference cases.

## Limits

- **15 crops.** Some profiles get a short list (2 crops in Manaus in November); it is never padded with
  crops out of season.
- **Traditional companion relations**: they order, never exclude, and the text says so.
- **No small-space information** for morango, repolho and abobrinha: they leave the list whenever
  `small_space` is on, until the agronomists confirm (9.4.1-9).
- **Arbitrated weights**: recalibrate in the UAT (9.3.2-5).
- **Already planted is always excluded**, which hides staggered planting (alface every few weeks). If
  the UAT points to it, F4 becomes a warning.
- **Community information** (TAP) is only partially met in the MVP: no interaction history yet.

Full list and the decision record: `docs/recommender/9.3.1-3_Abordagem_Motor_Recomendacao.md`, sections 8 and 9.
