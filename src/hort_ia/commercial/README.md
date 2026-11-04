# Commercial: reference prices and price comparison (WBS 9.5)

Compares a price (R$/kg) against the closest available Conab reference for the user's location,
for the 5 products of the market dataset (`data/market/`). Decision record: 9.5.1-3, sections 5.1-5.4.
The matching engine and its score are 9.5.1-5 and are not here yet.

- **Reference ladder** (`reference.py`): entrepost(s) in the **UF** (median when the UF has more than
  one, as São Paulo does) → **median of the macro-region**, with the observed min-max → **weighted
  national mean**. Reason for the ladder: an entrepost deviates from the national mean by 19.7% at
  the median and up to 146%, so a single national reference would be wrong by an order of magnitude
  (decision D1). Confidence falls with the level: 1.00 local, 0.70 regional, 0.40 national.
- **Tolerance band** (`bands.py`): the product's own noise, not a fixed percentage — the median
  |month-on-month change| of its series (alface 8%, batata 11%, cenoura 12%, cebola 13%, tomate 16%).
  Measured on `prices_monthly.csv` at construction, never written in the code (decision D3). The
  national level is the exception: a fixed ±30%, the mean deviation observed against the national mean,
  always with `degraded = true`.
- **Stale references** (section 5.3): an entrepost that stopped publishing is used from the last
  observed month of its series while it is at most 3 months behind, with the band widened by the
  median drift of that period (20.3% at 2 months, 27.6% at 3 — also measured on the dataset) and a
  `warning` naming the effective month: CEASA/GO, 2026-06. Above 3 months the entrepost is discarded
  and the ladder descends: CEASA/DF, 22 months behind, so Brasília is answered from the national mean.
  As in 9.6, series edges are never extrapolated and a missing price is never zero.
- **Classification**: `abaixo_da_faixa` | `na_faixa` | `acima_da_faixa`, with `deviation_pct` against
  the reference. Without an informed price the answer carries only the reference and the band, which
  is what the chatbot needs for "quanto está valendo?".
- **Origin** (same contract as 9.6): every comparison carries `source` (id in `data/market/sources.json`),
  `model_version` (`MODEL_VERSION`; bump it when the ladder, the band, the weights or the lag rule
  change), `confidence`, `degraded` and `warning`.
- **Stateless**: nothing is persisted and nothing is learned — there is no offer, demand or negotiation
  history in the repository, so there is no label to train a ranking model on, and no personal data
  reaches the module (9.1.2-4/-7).
- **Limits**: a single monthly source, so an entrepost that stops publishing takes the local reference
  of its UF with it; the Centro-Oeste has no regional reference at all (its two Ceasas are exactly
  GO and DF), so every user there gets a degraded national comparison; 10 of the 27 UFs reach the
  local level; wholesale prices used as a reference for retail/community selling; 5 of the 15 MVP
  crops have a price at all. Full list in section 10 of the decision record.

```bash
uv run python -m hort_ia.commercial   # measured bands and drift, plus the level reached per UF
```

The automated tests of the reference cases C1-C7 are the deliverable of **9.5.2**; until then, the
expected values are in section 9 of the decision record and
`docs/commercial/exploratory_price_spread.py` reproduces every one of them from `data/market/`.

Endpoint: `GET /commercial/price-comparison?product_id=alface&ibge_code=4106902&price_brl_kg=4.30`

The location is given as `ibge_code` (7 digits, or 2 for a UF) **or** `uf`, never both, and is
resolved with `hort_ia.core.geo`. Unknown product or location returns 404; a malformed or
out-of-range parameter returns 422.

Conventions worth knowing before reading the output: `reference_price_brl_kg` keeps **three**
decimals because a median of two two-decimal prices lands on a half cent (3.295 for São Paulo) and
`deviation_pct` is computed from the value that is reported, so a client can recompute it; the band
bounds keep two decimals and the classification uses those rounded bounds. `warning` is written in
Portuguese because the decision record fixes its wording for the reference cases, and it is the one
field that reaches the user.

Docs (approach comparison, decision record) and the exploratory script that reproduces every number
here, including the test cases C1-C7: `docs/commercial/`.
