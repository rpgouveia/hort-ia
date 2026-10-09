"""Brazilian geography shared by the Hort.IA datasets.

The agronomic knowledge base gives planting windows per macro-region (Embrapa's
Catálogo Brasileiro de Hortaliças), so the platform only needs to turn the user's
municipality into one of the five regions. No dataset is required for that: IBGE
codes encode it. A municipality code has 7 digits, the first 2 are the state (UF)
code, and the first digit of the UF code is the region (1 Norte ... 5 Centro-Oeste).
Example: Curitiba = 4106902 -> UF 41 (PR) -> region 4 (Sul).
"""

from __future__ import annotations

from enum import StrEnum


class Region(StrEnum):
    NORTE = "norte"
    NORDESTE = "nordeste"
    CENTRO_OESTE = "centro_oeste"
    SUDESTE = "sudeste"
    SUL = "sul"


# First digit of the IBGE UF code -> region.
_REGION_BY_DIGIT = {
    "1": Region.NORTE,
    "2": Region.NORDESTE,
    "3": Region.SUDESTE,
    "4": Region.SUL,
    "5": Region.CENTRO_OESTE,
}

# IBGE UF code -> UF abbreviation.
UF_BY_CODE: dict[str, str] = {
    "11": "RO", "12": "AC", "13": "AM", "14": "RR", "15": "PA", "16": "AP", "17": "TO",
    "21": "MA", "22": "PI", "23": "CE", "24": "RN", "25": "PB", "26": "PE", "27": "AL",
    "28": "SE", "29": "BA",
    "31": "MG", "32": "ES", "33": "RJ", "35": "SP",
    "41": "PR", "42": "SC", "43": "RS",
    "50": "MS", "51": "MT", "52": "GO", "53": "DF",
}
CODE_BY_UF: dict[str, str] = {uf: code for code, uf in UF_BY_CODE.items()}


def region_from_uf(uf: str) -> Region:
    """'PR' -> Region.SUL."""
    code = CODE_BY_UF.get(uf.strip().upper())
    if code is None:
        raise ValueError(f"unknown UF: {uf!r}")
    return _REGION_BY_DIGIT[code[0]]


def region_from_ibge_code(code: int | str) -> Region:
    """Region from an IBGE municipality code (7 digits) or UF code (2 digits)."""
    digits = str(code).strip()
    if not digits.isdigit() or len(digits) not in (2, 7):
        raise ValueError(f"IBGE code must have 2 (UF) or 7 (municipality) digits: {code!r}")
    if digits[:2] not in UF_BY_CODE:
        raise ValueError(f"unknown UF code in IBGE code: {code!r}")
    return _REGION_BY_DIGIT[digits[0]]
