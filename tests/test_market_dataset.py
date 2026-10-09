"""Integrity tests for the Conab market dataset (evidence for WBS 9.5.1-7, input to 9.5.2)."""

import json
import shutil
from pathlib import Path

import pytest
from pydantic import ValidationError

from hort_ia.knowledge import load_knowledge_base
from hort_ia.market import check_crop_links, load_market_dataset
from hort_ia.market.loader import DEFAULT_MARKET_DIR
from hort_ia.market.models import PriceObservation, PriceReference

# Scope of this version of the bulletin transcription (hortaliças only).
# Changing either set must be a deliberate decision.
EXPECTED_PRODUCTS = {"alface", "batata", "cebola", "cenoura", "tomate"}

EXPECTED_ENTREPOSTOS = {
    "ceagesp_sp",
    "ceasaminas_bh",
    "ceasa_rj",
    "ceasa_sp_campinas",
    "ceasa_es_vitoria",
    "ceasa_pr_curitiba",
    "ceasa_sc_sao_jose",
    "ceasa_go_goiania",
    "ceasa_df_brasilia",
    "ceasa_pe_recife",
    "ceasa_ce_fortaleza",
    "ceasa_ac_rio_branco",
}

# Products that also have an agronomic record among the 15 MVP crops.
LINKED_CROPS = {"alface", "batata", "cenoura", "tomate"}

REFERENCE_MONTH = "2026-08"
SERIES_FIRST, SERIES_LAST, SERIES_MONTHS = "2024-08", "2026-08", 25
QUANTITY_MONTHS = {"2025-08", "2026-07", "2026-08"}

# Entrepostos that published nothing in this edition (source had 0 and #DIV/0!).
NO_DATA_ENTREPOSTOS = {"ceasa_go_goiania", "ceasa_df_brasilia"}


@pytest.fixture(scope="module")
def dataset():
    return load_market_dataset()


@pytest.fixture(scope="module")
def kb():
    return load_knowledge_base()


def test_market_dataset_loads(dataset):
    assert dataset.products and dataset.entrepostos and dataset.prices


def test_product_scope_matches_bulletin(dataset):
    assert set(dataset.products) == EXPECTED_PRODUCTS


def test_entrepost_scope_matches_bulletin(dataset):
    assert set(dataset.entrepostos) == EXPECTED_ENTREPOSTOS


def test_every_product_has_prices(dataset):
    for product_id in dataset.products:
        assert any(p.product_id == product_id for p in dataset.prices), product_id


def test_series_spans_25_months(dataset):
    months = sorted({p.month for p in dataset.prices})
    assert (months[0], months[-1], len(months)) == (SERIES_FIRST, SERIES_LAST, SERIES_MONTHS)


# --- The two facts a careless re-transcription would break --------------------


def test_reference_month_is_august_not_the_edition_month(dataset):
    """Every sheet is titled "Setembro de 2026", but that is the edition, not the data."""
    assert {r.reference_month for r in dataset.price_reference} == {REFERENCE_MONTH}
    assert {r.reference_month for r in dataset.microregion_supply} == {REFERENCE_MONTH}
    assert max(q.month for q in dataset.quantities) == REFERENCE_MONTH


def test_reference_price_matches_the_monthly_series(dataset):
    """The snapshot and the series are two transcription paths to the same number."""
    series = {
        (p.product_id, p.entrepost_id): p.price_brl_kg
        for p in dataset.prices
        if p.month == REFERENCE_MONTH
    }
    checked = 0
    for reference in dataset.price_reference:
        if reference.is_weighted_average:
            continue
        key = (reference.product_id, reference.entrepost_id)
        assert key in series, f"{key} ausente da série em {REFERENCE_MONTH}"
        assert abs(series[key] - reference.price_brl_kg) <= 0.01, key
        checked += 1
    assert checked == 50


# --- Content checks for the tricky source cases -------------------------------


def test_missing_data_is_absent_never_zero(dataset):
    assert all(p.price_brl_kg > 0 for p in dataset.prices)
    assert all(q.quantity_kg > 0 for q in dataset.quantities)
    assert all(r.price_brl_kg > 0 for r in dataset.price_reference)


def test_entrepostos_without_data_are_absent_and_documented(dataset):
    for entrepost_id in NO_DATA_ENTREPOSTOS:
        assert not any(r.entrepost_id == entrepost_id for r in dataset.price_reference)
        assert not any(q.entrepost_id == entrepost_id for q in dataset.quantities)
        assert dataset.entrepostos[entrepost_id].notes, entrepost_id


def test_excel_serial_dates_were_converted(dataset):
    assert dataset.price_series("alface", "ceagesp_sp")[0].month == SERIES_FIRST


def test_sparse_series_is_shorter_not_padded(dataset):
    """CEASA/DF reported only three months; the gap must not be filled with zeros."""
    series = dataset.price_series("alface", "ceasa_df_brasilia")
    assert len(series) == 3
    assert all(p.price_brl_kg > 0 for p in series)


def test_weighted_average_exists_once_per_product_and_is_within_range(dataset):
    for product_id in dataset.products:
        average = dataset.reference_price(product_id)
        assert average is not None and average.is_weighted_average
        quoted = [
            r.price_brl_kg
            for r in dataset.price_reference
            if r.product_id == product_id and not r.is_weighted_average
        ]
        assert min(quoted) <= average.price_brl_kg <= max(quoted), product_id


def test_unchanged_price_keeps_a_zero_variation(dataset):
    """Ceasa/AC quoted alface flat against the previous month: 0 is data, not a gap."""
    reference = dataset.reference_price("alface", "ceasa_ac_rio_branco")
    assert reference.change_prev_month == 0


def test_entrepost_aliases_cover_the_source_name_variants(dataset):
    """The source writes each name in three casings, and calls CEASA/SC by two cities."""
    sc = dataset.entrepostos["ceasa_sc_sao_jose"]
    assert "CEASA/SC - FLORIANOPOLIS" in sc.aliases
    for entrepost in dataset.entrepostos.values():
        assert len(entrepost.aliases) >= 3, entrepost.id


def test_microregion_ranking_is_top20_and_ordered(dataset):
    for product_id in dataset.products:
        ranked = dataset.top_origins(product_id, limit=99)
        assert [r.rank for r in ranked] == list(range(1, 21)), product_id
        quantities = [r.quantity_kg for r in ranked]
        assert quantities == sorted(quantities, reverse=True), product_id


def test_uf_supply_accepts_not_informed(dataset):
    assert any(u.uf == "NI" for u in dataset.uf_supply)


def test_volume_totals_stop_in_august_2026(dataset):
    months = sorted(v.month for v in dataset.volumes)
    assert months[0] == "2024-01"
    assert months[-1] == REFERENCE_MONTH


def test_prices_are_rounded_to_two_decimals(dataset):
    """The source carries full float noise (3.2329679316297173)."""
    assert all(round(p.price_brl_kg, 2) == p.price_brl_kg for p in dataset.prices)


# --- The market/agronomic link ------------------------------------------------


def test_crop_links_resolve(dataset, kb):
    assert check_crop_links(dataset, kb) == []


def test_linked_products_are_exactly_the_overlap(dataset):
    assert {p.id for p in dataset.products.values() if p.crop_id} == LINKED_CROPS


def test_cebola_has_no_agronomic_record_and_says_so(dataset):
    cebola = dataset.products["cebola"]
    assert cebola.crop_id is None
    assert cebola.notes


def test_dataset_loads_without_the_knowledge_base(dataset):
    """The crop link is checked on demand, never at load time."""
    assert dataset.product_by_crop_id("cenoura").id == "cenoura"
    assert dataset.product_by_crop_id("morango") is None


# --- Validators reject broken data -------------------------------------------


@pytest.fixture
def dataset_copy(tmp_path: Path) -> Path:
    target = tmp_path / "market"
    shutil.copytree(DEFAULT_MARKET_DIR, target)
    return target


def append_line(directory: Path, filename: str, line: str) -> None:
    with (directory / filename).open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def test_unknown_product_is_rejected(dataset_copy):
    append_line(dataset_copy, "prices_monthly.csv", "morango,ceagesp_sp,2026-08,9.9")
    with pytest.raises(ValidationError, match="produto desconhecido 'morango'"):
        load_market_dataset(dataset_copy)


def test_unknown_entrepost_is_rejected(dataset_copy):
    append_line(dataset_copy, "prices_monthly.csv", "alface,ceasa_rs_porto_alegre,2026-08,9.9")
    with pytest.raises(ValidationError, match="entreposto desconhecido"):
        load_market_dataset(dataset_copy)


def test_duplicate_observation_is_rejected(dataset_copy):
    append_line(dataset_copy, "prices_monthly.csv", "alface,ceagesp_sp,2024-08,2.69")
    with pytest.raises(ValidationError, match="chave duplicada"):
        load_market_dataset(dataset_copy)


def test_microregion_rank_gap_is_rejected(dataset_copy):
    append_line(dataset_copy, "supply_microregions.csv", "alface,ITU,SP,10,99,2026-08")
    with pytest.raises(ValidationError, match="não são contíguos"):
        load_market_dataset(dataset_copy)


def test_second_weighted_average_is_rejected(dataset_copy):
    append_line(dataset_copy, "prices_reference.csv", "alface,,2026-08,9.9,0.1")
    with pytest.raises(ValidationError, match="esperada 1 média ponderada"):
        load_market_dataset(dataset_copy)


def test_duplicate_product_id_is_rejected(dataset_copy):
    path = dataset_copy / "products.json"
    products = json.loads(path.read_text(encoding="utf-8"))
    products.append(products[0])
    path.write_text(json.dumps(products, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(ValueError, match="duplicate ids"):
        load_market_dataset(dataset_copy)


def test_invalid_month_is_rejected():
    with pytest.raises(ValidationError, match="should match pattern"):
        PriceObservation(
            product_id="alface", entrepost_id="ceagesp_sp", month="2026-13", price_brl_kg=3.23
        )


def test_zero_price_is_rejected():
    with pytest.raises(ValidationError, match="greater_than|greater than 0"):
        PriceObservation(
            product_id="alface", entrepost_id="ceagesp_sp", month="2026-08", price_brl_kg=0
        )


def test_weighted_average_has_no_entrepost(dataset):
    assert all(r.entrepost_id is None for r in dataset.price_reference if r.is_weighted_average)
    assert all(not r.is_weighted_average for r in dataset.price_reference if r.entrepost_id)


def test_reference_without_entrepost_is_the_average():
    assert PriceReference(
        product_id="alface", reference_month="2026-08", price_brl_kg=5.06
    ).is_weighted_average
