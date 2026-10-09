"""One-off generator for the first version of the market dataset (kept for traceability).

Source: Conab, Boletim Hortigranjeiro — tabelas de dados, edição setembro de 2026.
The raw .xlsx is not versioned (see data/market/README.md); pass its path
as the first argument.

    uv run python scripts/build_market_v1.py caminho/para/boletim.xlsx

Scope of this version: hortaliças only (alface, batata, cebola, cenoura, tomate).
Sheets read, and what each produced:

    Preços-Hortaliças        -> prices_reference.csv   (snapshot + média ponderada)
    Preços-<Produto>         -> prices_monthly.csv     (25-month series per entreposto)
    Quantidade-<Produto>     -> quantities.csv          (3 months per entreposto)
    Q-Total-Hortaliças       -> volume_totals.csv       (total traded, by month)
    Microrregiões-Hortaliças -> supply_microregions.csv (top 20 per product)
    UF-Hortaliças            -> supply_uf.csv           (complete partition per product)

Transcription decisions, all verified against the workbook:

  * REFERENCE MONTH IS 2026-08, NOT 2026-09. Every sheet is titled "Setembro de 2026"
    (the edition) and Preços-Hortaliças!E3 holds serial 46266 = 2026-09-01, but the
    snapshot values equal the last column of the monthly series, whose header serial
    46235 = 2026-08-01. Q-Total-Hortaliças!B19 confirms it: "Comparativo ago/26 jul/26
    (mês anterior)". `assert_snapshot_matches_series` below re-checks this on every run.
  * The "Jul/Jun" sub-header in Preços-Hortaliças!C5 is a stale label; the value is the
    ago/jul change (3.2330 / 4.5947 - 1 = -0.2964).
  * Missing data is written as 0 or #DIV/0!, never blank (CEASA/GO and CEASA/DF have no
    data in this edition). A missing price or quantity SKIPS THE ROW and is reported in
    the run summary -- a 0 would poison any price comparison. A change of 0 is kept: it
    is a real "price unchanged" (CEASA/AC, alface).
  * Entrepost labels appear in three casings plus a footnote marker. `key()` normalises
    them and ENTREPOST_BY_KEY resolves them; an unknown label raises, so a future
    edition's rename fails loudly instead of silently dropping rows.
  * Header rows are found, not hardcoded: the sheets carry stray titles (Quantidade-Batata
    row 2), unlabelled total rows, "Acumulado até Agosto" and "Fonte: Conab." footers.
"""

import csv
import json
import re
import sys
import unicodedata
from datetime import date, datetime, timedelta
from pathlib import Path

from openpyxl import load_workbook

CONAB = "conab_boletim_hortigranjeiro"
EXCEL_EPOCH = date(1899, 12, 30)
BULLETIN_EDITION = "2026-09"  # aba Principal: "Setembro de 2026"
REFERENCE_MONTH = "2026-08"  # mês dos dados (ver docstring)
SERIES_FIRST, SERIES_LAST = "2024-08", "2026-08"
QUANTITY_MONTHS = ("2025-08", "2026-07", "2026-08")
MICROREGION_TOP_N = 20

MONTHS_PT = {"janeiro": 1, "fevereiro": 2, "marco": 3, "abril": 4, "maio": 5, "junho": 6,
             "julho": 7, "agosto": 8, "setembro": 9, "outubro": 10, "novembro": 11, "dezembro": 12,
             "jan": 1, "fev": 2, "mar": 3, "abr": 4, "mai": 5, "jun": 6,
             "jul": 7, "ago": 8, "set": 9, "out": 10, "nov": 11, "dez": 12}

UFS = {"AC", "AL", "AM", "AP", "BA", "CE", "DF", "ES", "GO", "MA", "MG", "MS", "MT", "NI",
       "PA", "PB", "PE", "PI", "PR", "RJ", "RN", "RO", "RR", "RS", "SC", "SE", "SP", "TO"}

REGION_BY_UF = {"SP": "sudeste", "MG": "sudeste", "RJ": "sudeste", "ES": "sudeste",
                "PR": "sul", "SC": "sul", "RS": "sul",
                "GO": "centro_oeste", "DF": "centro_oeste",
                "PE": "nordeste", "CE": "nordeste", "BA": "nordeste",
                "AC": "norte"}

NO_DATA_NOTE = "Sem dados publicados nesta edição do boletim (preços 0 e variação #DIV/0!)."


def key(text: str) -> str:
    """'CEASA/SC - SÃO JOSÉ ' and 'Ceasa/SC - São José' -> 'ceasa/sc - sao jose'."""
    stripped = unicodedata.normalize("NFKD", str(text)).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", stripped.replace("*", "")).strip().lower()


def ref(*sheets: str) -> list[dict[str, str]]:
    return [{"source_id": CONAB, "pages": sheet} for sheet in sheets]


def product(id, name_pt, crop_id, notes=None):
    sheets = [f"Preços-{name_pt}", f"Quantidade-{name_pt}"]
    return {"id": id, "name_pt": name_pt, "category": "vegetable", "unit": "kg",
            "crop_id": crop_id, "aliases": [name_pt, name_pt.upper()],
            "sources": ref(*sheets), "notes": notes}


def entrepost(id, name_pt, city, uf, aliases, notes=None):
    return {"id": id, "name_pt": name_pt, "city": city, "uf": uf, "region": REGION_BY_UF[uf],
            "aliases": aliases, "sources": ref("Preços-Hortaliças"), "notes": notes}


# Aliases are every spelling found in the sheets read above; they are the lookup table.
PRODUCTS = [
    product("alface", "Alface", "alface"),
    product("batata", "Batata", "batata"),
    product("cebola", "Cebola", None,
            "Sem registro agronômico: cebola está fora das 15 culturas do MVP em crops.json."),
    product("cenoura", "Cenoura", "cenoura"),
    product("tomate", "Tomate", "tomate"),
]

ENTREPOSTOS = [
    entrepost("ceagesp_sp", "CEAGESP - São Paulo", "São Paulo", "SP",
              ["CEAGESP - São Paulo", "Ceagesp - São Paulo", "CEAGESP - SÃO PAULO"]),
    entrepost("ceasaminas_bh", "CEASAMINAS - Belo Horizonte", "Belo Horizonte", "MG",
              ["CEASAMINAS - Belo Horizonte", "CeasaMinas - Belo Horizonte", "CEASAMINAS - BELO HORIZONTE"]),
    entrepost("ceasa_rj", "CEASA/RJ - Rio de Janeiro", "Rio de Janeiro", "RJ",
              ["CEASA/RJ - Rio de Janeiro", "Ceasa/RJ - Rio de Janeiro", "CEASA/RJ - RIO DE JANEIRO"]),
    entrepost("ceasa_sp_campinas", "CEASA/SP - Campinas", "Campinas", "SP",
              ["CEASA/SP - Campinas", "Ceasa/SP - Campinas", "CEASA/SP - CAMPINAS"]),
    entrepost("ceasa_es_vitoria", "CEASA/ES - Vitória", "Vitória", "ES",
              ["CEASA/ES - Vitória", "Ceasa/ES - Vitória", "CEASA/ES - VITORIA"]),
    entrepost("ceasa_pr_curitiba", "CEASA/PR - Curitiba", "Curitiba", "PR",
              ["CEASA/PR - Curitiba", "Ceasa/PR - Curitiba", "CEASA/PR - CURITIBA"]),
    entrepost("ceasa_sc_sao_jose", "CEASA/SC - São José", "São José", "SC",
              ["CEASA/SC - São José", "Ceasa/SC - São José", "CEASA/SC - SÃO JOSÉ",
               "CEASA/SC - FLORIANOPOLIS"],
              "A lista de 'Ceasas consideradas' em Q-Total chama a mesma unidade de "
              "'CEASA/SC - FLORIANOPOLIS'; é a unidade da Grande Florianópolis, em São José."),
    entrepost("ceasa_go_goiania", "CEASA/GO - Goiânia", "Goiânia", "GO",
              ["CEASA/GO - Goiânia", "Ceasa/GO - Goiânia", "CEASA/GO - GOIANIA"], NO_DATA_NOTE),
    entrepost("ceasa_df_brasilia", "CEASA/DF - Brasília", "Brasília", "DF",
              ["CEASA/DF - Brasília", "Ceasa/DF - Brasília", "CEASA/DF - BRASILIA"], NO_DATA_NOTE),
    entrepost("ceasa_pe_recife", "CEASA/PE - Recife", "Recife", "PE",
              ["CEASA/PE - Recife", "Ceasa/PE - Recife", "CEASA/PE - RECIFE"]),
    entrepost("ceasa_ce_fortaleza", "CEASA/CE - Fortaleza", "Fortaleza", "CE",
              ["CEASA/CE - Fortaleza", "Ceasa/CE - Fortaleza", "CEASA/CE - FORTALEZA"]),
    entrepost("ceasa_ac_rio_branco", "CEASA/AC - Rio Branco", "Rio Branco", "AC",
              ["CEASA/AC - Rio Branco", "Ceasa/AC - Rio Branco", "CEASA/AC - RIO BRANCO"]),
]

ENTREPOST_BY_KEY = {key(a): e["id"] for e in ENTREPOSTOS for a in e["aliases"]}
PRODUCT_BY_KEY = {key(a): p["id"] for p in PRODUCTS for a in p["aliases"]}
WEIGHTED_AVERAGE = key("Média Ponderada")

gaps: list[str] = []


# --- cell readers ------------------------------------------------------------


def month_of(value) -> str:
    """Excel serial, datetime or 'Agosto de 2026' -> 'YYYY-MM'."""
    if isinstance(value, (datetime, date)):
        return f"{value.year:04d}-{value.month:02d}"
    if isinstance(value, (int, float)):
        return (EXCEL_EPOCH + timedelta(days=int(value))).strftime("%Y-%m")
    words = key(value).replace(" de ", " ").split()
    month = next(MONTHS_PT[w] for w in words if w in MONTHS_PT)
    year = next(int(w) for w in words if w.isdigit() and len(w) == 4)
    return f"{year:04d}-{month:02d}"


def _number(value) -> float | None:
    """None for blanks and for the spreadsheet's error strings (#DIV/0!, #N/A...)."""
    if value is None or isinstance(value, str) and (not value.strip() or value.startswith("#")):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def is_month_cell(value) -> bool:
    """A month header: a date-formatted cell (datetime) or a bare Excel serial."""
    return isinstance(value, (datetime, date)) or (_number(value) or 0) > 40000


def price(value) -> float | None:
    number = _number(value)
    return round(number, 2) if number else None  # 0 means "not reported"


def qty(value) -> int | None:
    number = _number(value)
    return int(round(number)) if number else None  # 0 means "not reported"


def ratio(value) -> float | None:
    number = _number(value)
    return None if number is None else round(number, 4)  # 0 is a real "unchanged"


def entrepost_id(label) -> str | None:
    """Resolve a column-A label; None for header, footer and total rows."""
    normalised = key(label or "")
    if not normalised or normalised in {"ceasa", "produto", "mes"} or normalised.startswith(
        ("fonte", "acumulado", "boletim", "comparativo", "preco")
    ):
        return None
    if normalised == WEIGHTED_AVERAGE:
        return WEIGHTED_AVERAGE
    if normalised not in ENTREPOST_BY_KEY:
        raise ValueError(f"entreposto desconhecido na planilha: {label!r}")
    return ENTREPOST_BY_KEY[normalised]


def split_origin(text: str) -> tuple[str, str]:
    """'SÃO JOÃO DA BOA VISTA-SP' -> ('SÃO JOÃO DA BOA VISTA', 'SP'); keeps 'MOGI-MIRIM'."""
    name, _, uf = str(text).strip().rpartition("-")
    if uf.strip().upper() not in UFS:
        raise ValueError(f"microrregião sem UF reconhecível: {text!r}")
    return name.strip(), uf.strip().upper()


def columns_of(row, skip: set[str] = frozenset({"produto"})) -> list[tuple[int, str]]:
    """Product header cells of a wide sheet, as (0-based column index, product_id)."""
    return [
        (i, PRODUCT_BY_KEY[key(cell.value)])
        for i, cell in enumerate(row)
        if cell.value and key(cell.value) not in skip and key(cell.value) in PRODUCT_BY_KEY
    ]


# --- sheet parsers -----------------------------------------------------------


def read_reference(sheet) -> list[dict]:
    """Preços-Hortaliças: one (price, change) column pair per product, per entreposto."""
    rows = list(sheet.iter_rows())
    header = next(r for r in rows if columns_of(r))
    records = []
    for row in rows[rows.index(header) + 1:]:
        who = entrepost_id(row[0].value)
        if who is None:
            continue
        for column, product_id in columns_of(header):
            value, change = price(row[column].value), ratio(row[column + 1].value)
            if value is None:
                gaps.append(f"prices_reference: {product_id} x {who} sem preço")
                continue
            records.append({
                "product_id": product_id,
                "entrepost_id": "" if who == WEIGHTED_AVERAGE else who,
                "reference_month": REFERENCE_MONTH,
                "price_brl_kg": value,
                "change_prev_month": "" if change is None else change,
            })
    return records


def read_series(sheet, product_id: str) -> list[dict]:
    """Preços-<Produto>: the header row holds 25 Excel date serials."""
    rows = list(sheet.iter_rows())
    header = next(r for r in rows if sum(1 for c in r[1:] if is_month_cell(c.value)) > 20)
    months = [(i, month_of(c.value)) for i, c in enumerate(header) if is_month_cell(c.value)]
    records = []
    for row in rows[rows.index(header) + 1:]:
        who = entrepost_id(row[0].value)
        if who is None or who == WEIGHTED_AVERAGE:
            continue
        for column, month in months:
            if (value := price(row[column].value)) is not None:
                records.append({"product_id": product_id, "entrepost_id": who,
                                "month": month, "price_brl_kg": value})
    return records


def read_quantities(sheet, product_id: str) -> list[dict]:
    """Quantidade-<Produto>: three month columns, labelled in the header row."""
    rows = list(sheet.iter_rows())
    header = next(r for r in rows if key(r[0].value or "") == "ceasa")
    months = [(i, month_of(c.value)) for i, c in enumerate(header[1:5], start=1) if c.value]
    records = []
    for row in rows[rows.index(header) + 1:]:
        who = entrepost_id(row[0].value)
        if who is None:
            continue
        for column, month in months:
            if (value := qty(row[column].value)) is None:
                gaps.append(f"quantities: {product_id} x {who} sem volume em {month}")
            else:
                records.append({"product_id": product_id, "entrepost_id": who,
                                "month": month, "quantity_kg": value})
    return records


def read_volumes(sheet) -> list[dict]:
    """Q-Total-Hortaliças: month rows x year columns. Skips 'Acumulado' and the ratios."""
    rows = list(sheet.iter_rows())
    header = next(r for r in rows if key(r[0].value or "") == "mes")
    years = [(i, int(c.value)) for i, c in enumerate(header) if i and _number(c.value)]
    records = []
    for row in rows[rows.index(header) + 1:]:
        label = key(row[0].value or "")
        if label not in MONTHS_PT:  # "acumulado até agosto", the comparison ratios, blanks
            continue
        for column, year in years:
            if (value := qty(row[column].value)) is not None:
                records.append({"category": "vegetable",
                                "month": f"{year}-{MONTHS_PT[label]:02d}",
                                "quantity_kg": value})
    return records


def read_microregions(sheet) -> list[dict]:
    """Microrregiões-Hortaliças: a (microrregião, kg) column pair per product, top 20."""
    rows = list(sheet.iter_rows())
    header = next(r for r in rows if columns_of(r))
    records = []
    for column, product_id in columns_of(header):
        rank = 0
        for row in rows[rows.index(header) + 1:]:
            name, value = row[column].value, qty(row[column + 1].value)
            if not name or key(name) in {"micro regiao", "uf"} or key(name).startswith("fonte"):
                continue
            if value is None:
                continue
            microregion, uf = split_origin(name)
            rank += 1
            records.append({"product_id": product_id, "microregion": microregion, "uf": uf,
                            "quantity_kg": value, "rank": rank,
                            "reference_month": REFERENCE_MONTH})
        assert rank == MICROREGION_TOP_N, f"{product_id}: {rank} microrregiões (esperado 20)"
    return records


def read_uf_supply(sheet) -> list[dict]:
    """UF-Hortaliças: a (UF, kg) column pair per product; a complete partition."""
    rows = list(sheet.iter_rows())
    header = next(r for r in rows if columns_of(r))
    records = []
    for column, product_id in columns_of(header):
        for row in rows[rows.index(header) + 1:]:
            name, value = row[column].value, qty(row[column + 1].value)
            if not name or key(name) in {"uf", "micro regiao"} or key(name).startswith("fonte"):
                continue
            if value is None:
                continue
            uf = str(name).strip().upper()
            assert uf in UFS, f"{product_id}: UF desconhecida {uf!r}"
            records.append({"product_id": product_id, "uf": uf, "quantity_kg": value,
                            "reference_month": REFERENCE_MONTH})
    return records


# --- self-checks -------------------------------------------------------------


def assert_snapshot_matches_series(reference: list[dict], series: list[dict]) -> int:
    """The snapshot must equal the series at REFERENCE_MONTH -- this is what proves the
    data is ago/2026 and not set/2026 (see the module docstring)."""
    by_key = {(r["product_id"], r["entrepost_id"]): r["price_brl_kg"]
              for r in series if r["month"] == REFERENCE_MONTH}
    checked = 0
    for row in reference:
        if not row["entrepost_id"]:
            continue
        expected = by_key.get((row["product_id"], row["entrepost_id"]))
        assert expected is not None, f"{row} sem valor na série em {REFERENCE_MONTH}"
        assert abs(expected - row["price_brl_kg"]) <= 0.01, f"{row} != série {expected}"
        checked += 1
    assert checked, "nenhuma linha do snapshot pôde ser conferida contra a série"
    return checked


# --- write -------------------------------------------------------------------


def main(source: Path, out: Path) -> None:
    book = load_workbook(source, data_only=True, read_only=True)
    out.mkdir(parents=True, exist_ok=True)

    reference = read_reference(book["Preços-Hortaliças"])
    series, quantities = [], []
    for record in PRODUCTS:
        series += read_series(book[f"Preços-{record['name_pt']}"], record["id"])
        quantities += read_quantities(book[f"Quantidade-{record['name_pt']}"], record["id"])
    volumes = read_volumes(book["Q-Total-Hortaliças"])
    microregions = read_microregions(book["Microrregiões-Hortaliças"])
    uf_supply = read_uf_supply(book["UF-Hortaliças"])

    months = {r["month"] for r in series}
    assert (min(months), max(months)) == (SERIES_FIRST, SERIES_LAST), sorted(months)
    assert {r["month"] for r in quantities} == set(QUANTITY_MONTHS)
    assert max(r["month"] for r in quantities) == REFERENCE_MONTH
    assert REFERENCE_MONTH < BULLETIN_EDITION, "o mês de referência precede a edição"
    checked = assert_snapshot_matches_series(reference, series)

    write_json(out / "products.json", PRODUCTS)
    write_json(out / "entrepostos.json", ENTREPOSTOS)
    write_csv(out / "prices_reference.csv", reference,
              ["product_id", "entrepost_id", "reference_month", "price_brl_kg", "change_prev_month"])
    write_csv(out / "prices_monthly.csv", series,
              ["product_id", "entrepost_id", "month", "price_brl_kg"])
    write_csv(out / "quantities.csv", quantities,
              ["product_id", "entrepost_id", "month", "quantity_kg"])
    write_csv(out / "volume_totals.csv", volumes, ["category", "month", "quantity_kg"])
    write_csv(out / "supply_microregions.csv", microregions,
              ["product_id", "microregion", "uf", "quantity_kg", "rank", "reference_month"],
              sort_by=("product_id", "rank"))
    write_csv(out / "supply_uf.csv", uf_supply,
              ["product_id", "uf", "quantity_kg", "reference_month"],
              sort_by=("product_id", "uf"))

    print(f"Edição {BULLETIN_EDITION}, mês de referência {REFERENCE_MONTH} "
          f"({checked} preços do snapshot conferidos contra a série)")
    print(f"{len(reference)} preços de referência | {len(series)} observações mensais | "
          f"{len(quantities)} volumes | {len(volumes)} totais | "
          f"{len(microregions)} microrregiões | {len(uf_supply)} UFs")
    print(f"\nLacunas na fonte ({len(gaps)}):")
    for gap in gaps:
        print(f"  - {gap}")


def write_json(path: Path, records: list[dict]) -> None:
    path.write_text(json.dumps(records, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_csv(path: Path, records: list[dict], header: list[str], sort_by=None) -> None:
    rows = sorted(records, key=lambda r: tuple(str(r[k]) for k in (sort_by or header)))
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=header, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    default = Path(__file__).resolve().parents[2] / "tabelas-de-dados-boletim-hortigranjeiro-setembro-2026.xlsx"
    xlsx = Path(sys.argv[1]) if len(sys.argv) > 1 else default
    if not xlsx.is_file():
        sys.exit(
            f"planilha não encontrada: {xlsx}\n"
            "Baixe as tabelas de dados do Boletim Hortigranjeiro (Conab/Prohort) e passe o "
            "caminho como primeiro argumento."
        )
    main(xlsx, Path(__file__).resolve().parents[1] / "data" / "market")
