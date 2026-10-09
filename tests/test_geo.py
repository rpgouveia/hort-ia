"""Tests for municipality -> region resolution (WBS 9.3, regional adaptation)."""

import pytest

from hort_ia.core.geo import UF_BY_CODE, Region, region_from_ibge_code, region_from_uf


@pytest.mark.parametrize(
    ("code", "region"),
    [
        (4106902, Region.SUL),  # Curitiba (PR)
        ("3550308", Region.SUDESTE),  # São Paulo (SP)
        ("2304400", Region.NORDESTE),  # Fortaleza (CE)
        ("1302603", Region.NORTE),  # Manaus (AM)
        ("5300108", Region.CENTRO_OESTE),  # Brasília (DF)
        ("41", Region.SUL),  # UF code alone
    ],
)
def test_region_from_ibge_code(code, region):
    assert region_from_ibge_code(code) == region


@pytest.mark.parametrize("code", ["410690", "34", "9999999", "abc", ""])
def test_invalid_ibge_code_is_rejected(code):
    with pytest.raises(ValueError):
        region_from_ibge_code(code)


def test_region_from_uf_is_case_insensitive():
    assert region_from_uf("pr") == region_from_uf("PR") == Region.SUL


def test_all_27_ufs_are_mapped():
    assert len(UF_BY_CODE) == 27
    assert {region_from_uf(uf) for uf in UF_BY_CODE.values()} == set(Region)


def test_region_is_shared_by_both_datasets():
    from hort_ia.knowledge import models as knowledge_models
    from hort_ia.market import models as market_models

    assert knowledge_models.Region is market_models.Region is Region
