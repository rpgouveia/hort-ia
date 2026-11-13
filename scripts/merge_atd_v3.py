"""Merge the ATD delivery v3 into data/knowledge/ (decisions D1-D10 of the integration, Nov 2026).

The Digital Technical Assistance team (ATD) started from the knowledge base of 20/10/2026, before the
pest and disease work, so its files cannot replace ours: validated against the current model they give
126 errors in crops.json, 214 in pests_diseases.json and 5 in guidelines_novas.json, and cite 4
unregistered sources. This script puts the ATD content into the current format and keeps the safety
rules. It reads the base as it was before the merge (git ref BASE_REF) and the delivery as received
(docs/knowledge/atd/entrega_v3/), so running it again reproduces data/knowledge/.

ATD texts (symptoms, actions, notes, statements) are copied as received. What changes is the format:
- pests: each ATD action {action, source} becomes {type, description, source}, with `type` set by the
  keyword rule of D2; the symptom gets `symptoms_sources` by D3; crop_ids stays empty for
  crop_scope "all_vegetables";
- companions: the free text the ATD wrote in `mechanism` moves to the start of `notes`;
- crops: planting windows of brócolis, coentro, espinafre and pimenta from the Catálogo (D8);
- sources: the 4 cited and unregistered sources enter as unverified placeholders (D7).

Usage: uv run python scripts/merge_atd_v3.py [--report DIR] [--comparison FILE]
  --report DIR       also write classificacao_manejo.csv (one row per ATD action) to DIR
  --comparison FILE  also write the table of values that already existed and changed (Markdown)
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import re
import subprocess
import unicodedata
from pathlib import Path

from hort_ia.knowledge.models import Crop, PestDisease

ROOT = Path(__file__).resolve().parents[1]
BASE_REF = "7e1d639"  # main before the merge (PR #124)
DELIVERY = ROOT / "docs" / "knowledge" / "atd" / "entrega_v3" / "knowledge"
OUT = ROOT / "data" / "knowledge"

CT47, HPE = "embrapa_ct47_cultivo_hortalicas", "embrapa_horta_pequenos_espacos"
CATALOGO = "embrapa_catalogo_hortalicas"

# --- D2: management type by keyword, first rule that matches ------------------------------------
# Matched on lower case text without accents, at the start of a word ("nim" must not match "animais").
D2_RULES: list[tuple[str, list[tuple[str, str]]]] = [
    ("alternative", [
        ("calda", r"\bcaldas?\b"), ("extrato", r"\bextratos?\b"), ("preparado", r"\bpreparados?\b"),
        ("defensivo natural", r"\bdefensivos? naturais?\b|\bdefensivo natural\b"), ("óleo", r"\boleos?\b"),
        ("sabão", r"\bsabao\b|\bsaboes\b"), ("fumo", r"\bfumo\b"), ("nim/neem", r"\bnim\b|\bneem\b"),
        ("infusão", r"\binfusao\b|\binfusoes\b"),
    ]),
    ("biological", [
        ("Bacillus thuringiensis", r"\bbacillus thuringiensis\b"), ("baculovírus", r"\bbaculovirus\b"),
        ("Trichogramma", r"\btrichogramma\b"), ("controle biológico", r"\bcontrole biologico\b"),
        ("inimigo natural liberado", r"\binimigos? naturais? liberados?\b"),
    ]),
    ("preventive", [
        ("semente", r"\bsementes?\b"), ("muda sadia", r"\bmudas? sadias?\b"),
        ("cultivar resistente", r"\bcultivar(es)? resistentes?\b"), ("certificada", r"\bcertificad[ao]s?\b"),
    ]),
]  # fmt: skip


def _plain(text: str) -> str:
    return "".join(ch for ch in unicodedata.normalize("NFKD", text.lower()) if not unicodedata.combining(ch))


def classify(action: str) -> tuple[str, str]:
    """(type, rule that classified it), by the D2 order: alternative, biological, preventive, cultural."""
    text = _plain(action)
    for kind, keywords in D2_RULES:
        for keyword, pattern in keywords:
            if re.search(pattern, text):
                return kind, f"{kind}: {keyword}"
    return "cultural", "cultural: nenhuma palavra-chave das outras regras"


# --- D3: symptom sources ------------------------------------------------------------------------


def ref(source_id: str, pages: str) -> dict:
    return {"source_id": source_id, "pages": pages}


# The 10 diseases, as in the ATD validation PDF (request 6).
DISEASE_SYMPTOM_SOURCES = {
    "tomate_pinta_preta": [ref("embrapa_ct121_tomate", "5")],
    "tomate_requeima": [ref("embrapa_ct121_tomate", "5")],
    "tomate_septoriose": [ref("embrapa_ct121_tomate", "6")],
    "tomate_mancha_bacteriana": [ref("embrapa_ct121_tomate", "7"), ref("embrapa_ct84_mancha_bacteriana", "3")],
    "tomate_mancha_alvo": [ref("embrapa_roraima_doc03_tomate", "8")],
    "tomate_cladosporiose": [ref("embrapa_ct31_cladosporiose", "4")],
    "batata_requeima": [ref("embrapa_cpact_batata_organica", "35")],
    "batata_pinta_preta": [ref("embrapa_cpact_batata_organica", "36")],
    "pimentao_mancha_bacteriana": [ref("embrapa_bpd223_pimentao", "10")],
    "morango_leaf_scorch": [ref("embrapa_ct96_morango", "3"), ref("senar_pr0355_morango", "18")],
}
PAGES_TO_CHECK = {"batata_requeima", "batata_pinta_preta"}

# Pests whose new symptom text has its source and page indicated by the ATD notes, the PDF or the text.
PEST_SYMPTOM_SOURCES = {
    "praga_formigas": (
        [ref(CT47, "12"), ref(HPE, "29")],
        "fonte do sintoma indicada pela ATD: CT 47 p. 12 (notas) e HPE p. 29 (notas e PDF de validação, pedido 3).",
    ),
    "praga_besouros": (
        [ref(CT47, "12"), ref(HPE, "29")],
        (
            "fonte do sintoma: HPE p. 29, indicada pela ATD (notas e PDF de validação, pedido 3), e CT 47 p. 12, "
            "fonte do texto anterior, que a ATD manteve (furam folhas, brotos e frutos; vaquinhas e burrinhos)."
        ),
    ),
    "praga_tesourinhas": (
        [ref("senar_pr0306_pragas", "13"), ref("redoan_2013_doru_seletividade", "842")],
        (
            "fonte do sintoma indicada pela ATD (PDF de validação, pedido 3): SENAR-PR PR.0306 p. 13 e Revista "
            "Ciência Agronômica (2013) p. 842. O trecho 'preda ovos e lagartas pequenas' vem da Embrapa Milho e "
            "Sorgo, sem página (o conteúdo do folder não foi consultado e Reis 1988 está sem página): pendente."
        ),
    ),
    "benefico_vespas": (
        [ref(CT47, "12"), ref(CT47, "13")],
        "fonte do sintoma: CT 47 pp. 12 e 13, citadas no próprio texto da ATD.",
    ),
}

# --- D8: planting windows filled by the AI module from the Catálogo -------------------------------

ALL = list(range(1, 13))


def months(first: int, last: int) -> list[int]:
    """Months from `first` to `last`, wrapping the year (set-jan = [9, 10, 11, 12, 1])."""
    out, m = [first], first
    while m != last:
        m = m % 12 + 1
        out.append(m)
    return out


def window(variant, page, sul, sudeste, nordeste, centro_oeste, norte, harvest) -> dict:
    return {
        "variant": variant,
        "months_by_region": {"sul": sul, "sudeste": sudeste, "nordeste": nordeste,
                             "centro_oeste": centro_oeste, "norte": norte},
        "harvest_start_days": {"min": harvest[0], "max": harvest[1]},
        "source": ref(CATALOGO, page),
        "notes": f"Preenchida pelo módulo de IA a partir do Catálogo (p. {page}), pendente de conferência da ATD.",
    }  # fmt: skip


D8_WINDOWS = {
    "brocolis": ("22", [
        window("inverno", "22", months(2, 9), months(2, 7), [], months(2, 5), [], (90, 100)),
        window("verao", "22", months(10, 12), months(9, 1), months(10, 2), months(10, 1), months(4, 7), (80, 100)),
    ]),
    "coentro": ("28", [window(None, "28", months(9, 1), months(8, 2), ALL, months(8, 4), months(4, 10), (50, 60))]),
    "espinafre": ("33", [
        window(None, "33", months(2, 9), months(2, 9), months(3, 8), months(3, 8), months(3, 5), (60, 80)),
    ]),
    "pimenta": ("48", [window(None, "48", months(9, 2), months(8, 3), ALL, months(8, 12), months(7, 12), (90, 120))]),
}  # fmt: skip
D8_SPINACH = (
    " A ficha do Catálogo (p. 33) cobre duas espécies de espinafre; qual delas a base considera é pendência da ATD."
)
# Display names that came without accents (spelling only; the NLU already ignores accents).
NAME_SPELLING = {"brocolis": "Brócolis", "hortela": "Hortelã"}

# --- D7: cited and unregistered sources ---------------------------------------------------------

PENDING_SOURCES = {
    "embrapa_folder_plantas_companheiras": "companions.csv, 3 relações technical (nota da ATD: fonte regional de "
    "Manaus-AM)",
    "embrapa_horta_domestica_portal": "companions.csv, 4 relações technical",
    "embrapa_it134_alface_crespa": "crops.json, alface.irrigation (página 'nao confirmada')",
    "unioeste_alelopatia_couve": "companions.csv, 7 relações research (testes de germinação em placa de Petri)",
}

# --- reading ------------------------------------------------------------------------------------


def base_file(name: str) -> str:
    """A file of data/knowledge/ as it was before the merge."""
    return subprocess.run(
        ["git", "show", f"{BASE_REF}:data/knowledge/{name}"], cwd=ROOT, check=True, capture_output=True, text=True
    ).stdout


def ordered(record: dict, model) -> dict:
    """Keys in the model's field order (unknown keys would fail validation anyway)."""
    return {k: record[k] for k in model.model_fields if k in record}


def note(*parts: str | None) -> str | None:
    text = " ".join(p.strip() for p in parts if p and p.strip())
    return text or None


# --- merge --------------------------------------------------------------------------------------


def merge_crops(current: list[dict], atd: list[dict]) -> list[dict]:
    by_id = {c["id"]: c for c in atd}
    order = [c["id"] for c in current] + [c["id"] for c in atd if c["id"] not in {x["id"] for x in current}]
    merged = []
    for crop_id in order:
        crop = dict(by_id[crop_id])
        crop["name_pt"] = NAME_SPELLING.get(crop_id, crop["name_pt"])
        if crop_id in D8_WINDOWS:
            page, windows = D8_WINDOWS[crop_id]
            crop["planting_windows"] = windows
            crop["validation_status"] = "draft"
            extra = (f"Épocas preenchidas pelo módulo de IA a partir do Catálogo (p. {page}), pendente de "
                     "conferência da ATD.")  # fmt: skip
            crop["notes"] = note(crop.get("notes"), extra, D8_SPINACH if crop_id == "espinafre" else None)
        if crop_id == "hortela":
            crop["notes"] = note(crop.get("notes"), "Sem época de plantio: pendência da ATD.")
        merged.append(ordered(crop, Crop))
    return merged


def merge_companions(current_csv: str, atd_csv: str) -> str:
    """The 37 rows already in the base, verbatim, plus the ATD rows that are new."""
    current_rows = list(csv.DictReader(io.StringIO(current_csv)))
    seen = {tuple(r.values()) for r in current_rows}
    fields = list(current_rows[0])
    out = io.StringIO()
    out.write(current_csv if current_csv.endswith("\n") else current_csv + "\n")
    writer = csv.DictWriter(out, fieldnames=fields, lineterminator="\n")
    for row in csv.DictReader(io.StringIO(atd_csv)):
        if tuple(row.values()) in seen:
            continue
        mechanism = row["mechanism"]
        if mechanism not in ("unknown", ""):  # free text in the ATD file: keep it, at the start of the notes
            row["notes"] = f"{mechanism} | {row['notes']}"
            row["mechanism"] = "allelopathy" if row["evidence"] == "research" else "unknown"
        writer.writerow(row)
    return out.getvalue()


def merge_sources(current: list[dict], atd: list[dict]) -> list[dict]:
    merged = current + [s for s in atd if s["id"] not in {c["id"] for c in current}]
    for source_id, where in PENDING_SOURCES.items():
        merged.append({
            "id": source_id,
            "title": "Pendente: metadados a enviar pela ATD",
            "publisher": "A informar pela ATD",
            "year": None,
            "url": None,
            "license": None,
            "verified": False,
            "notes": f"Citada na entrega v3 da ATD sem registro em sources_novas.json ({where}). Até a ATD enviar "
            "título, editora, ano, URL e licença, nada que dependa desta fonte chega ao usuário (decisão D6).",
        })  # fmt: skip
    return merged


def merge_pests(current: list[dict], atd: list[dict]) -> tuple[list[dict], list[dict]]:
    """Merged entries and the classification of every ATD action (for classificacao_manejo.csv)."""
    cur = {e["id"]: e for e in current}
    merged, classification = [], []
    for entry in atd:
        old, new, extra = cur[entry["id"]], dict(entry), []
        symptoms, symptoms_sources = new.get("symptoms"), []
        if entry["id"] in DISEASE_SYMPTOM_SOURCES:
            symptoms_sources = DISEASE_SYMPTOM_SOURCES[entry["id"]]
            if entry["id"] in PAGES_TO_CHECK:
                extra.append("A página do sintoma foi marcada pela ATD como 'a conferir' (PDF de validação, "
                             "pedido 6): conferir no impresso.")  # fmt: skip
        elif symptoms and symptoms == old.get("symptoms"):
            symptoms_sources = old["symptoms_sources"]
        elif entry["id"] in PEST_SYMPTOM_SOURCES:
            symptoms_sources, why = PEST_SYMPTOM_SOURCES[entry["id"]]
            extra.append(why[:1].upper() + why[1:])
        elif symptoms != old.get("symptoms"):  # D3: no explicit source -> keep ours, back to draft
            symptoms, symptoms_sources = old.get("symptoms"), old.get("symptoms_sources", [])
            new["validation_status"] = "draft"
            if entry.get("symptoms") is None:
                extra.append("A versão da ATD veio sem sintoma; mantido o texto anterior do módulo de IA, com sua "
                             "fonte. Entrada em draft até a ATD confirmar (pendências, item 2).")  # fmt: skip
            elif old.get("symptoms") is None:
                extra.append(f"Texto proposto pela ATD para o sintoma, não gravado por não trazer fonte com página "
                             f"(e por descrever a falta de fonte, não o sintoma): «{entry['symptoms']}» "
                             f"(pendências, item 2).")  # fmt: skip
            else:
                extra.append(f"Sintoma: mantido o texto anterior do módulo de IA, com sua fonte, porque a ATD propôs "
                             f"um texto novo sem indicar fonte e página: «{entry['symptoms']}». Entrada em draft até "
                             f"a ATD indicar a fonte (pendências, item 2).")  # fmt: skip
        new["symptoms"] = symptoms
        new["symptoms_sources"] = symptoms_sources

        actions = []
        for action in entry.get("management", []):
            kind, rule = classify(action["action"])
            actions.append({"type": kind, "description": action["action"], "source": action["source"]})
            classification.append({"entry": entry["id"], "action": action["action"], "type": kind, "rule": rule})
        if entry.get("type") == "beneficial" and actions:  # beneficial entries have no actions (model rule)
            for a in actions:
                extra.append(f"Ação proposta pela ATD, não gravada em management porque entradas benéficas não têm "
                             f"ações: «{a['description']}».")  # fmt: skip
                classification[-len(actions) + actions.index(a)]["rule"] += " (não gravada: entrada benéfica)"
            actions = []
        new["management"] = actions
        new.pop("action", None)

        if new.get("crop_scope") == "all_vegetables":
            new["crop_ids"] = []  # every vegetable, including the 5 new crops (the ATD listed the old 15)

        sources = list(new.get("sources", []))
        for r in [*symptoms_sources, *(a["source"] for a in actions)]:
            if r not in sources:
                sources.append(r)
        new["sources"] = sources
        if extra:
            new["notes"] = note(new.get("notes"), "Integração v3 (módulo de IA):", *extra)
        if not symptoms_sources:
            new.pop("symptoms_sources")
        merged.append(ordered(new, PestDisease))
    return merged, classification


# --- reports ------------------------------------------------------------------------------------


def classification_csv(rows: list[dict], merged: list[dict]) -> str:
    by_id = {e["id"]: e for e in merged}
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\n")
    writer.writerow(["id_entrada", "nome", "acao", "tipo_atribuido", "regra_que_classificou",
                     "aparece_no_assistente", "status_da_entrada"])  # fmt: skip
    for row in rows:
        entry = by_id[row["entry"]]
        registered = any(a["description"] == row["action"] for a in entry["management"])
        shown = registered and (entry["validation_status"] == "reviewed" or row["type"] != "alternative")
        writer.writerow([entry["id"], entry["name_pt"], row["action"], row["type"], row["rule"],
                         "sim" if shown else "não", entry["validation_status"]])  # fmt: skip
    return out.getvalue()


def _cell(value) -> str:
    if value is None or value == []:
        return "(vazio)"
    if isinstance(value, list) and value and isinstance(value[0], dict) and "source_id" in value[0]:
        return "; ".join(f"{r['source_id']} p. {r['pages']}" for r in value)
    if isinstance(value, list) and value and isinstance(value[0], dict):  # management
        return "<br>".join(
            f"[{a['type']}] {a['description']}" if "type" in a else a.get("action", a.get("description")) for a in value
        )
    if isinstance(value, list):
        return ", ".join(map(str, value))
    return str(value).replace("|", "\\|").replace("\n", " ")


def comparison_table(cur_crops, atd_crops, merged_crops, cur_pests, atd_pests, merged_pests) -> str:
    rows = []
    for current, atd, merged in ((cur_crops, atd_crops, merged_crops), (cur_pests, atd_pests, merged_pests)):
        atd_by, merged_by = {e["id"]: e for e in atd}, {e["id"]: e for e in merged}
        for old in current:
            new, final = atd_by[old["id"]], merged_by[old["id"]]
            for field in old:
                if field in ("symptoms_sources",) or field not in new and field != "management":
                    continue
                if field == "management":
                    if [a["description"] for a in old[field]] == [a["action"] for a in new.get(field, [])]:
                        continue
                elif old[field] == new.get(field):
                    continue
                rows.append((old["id"], field, _cell(old[field]), _cell(new.get(field)), _cell(final.get(field))))
    lines = ["| Entrada | Campo | Valor atual | Valor da ATD | O que foi adotado |", "|---|---|---|---|---|"]
    lines += [f"| {a} | {b} | {c} | {d} | {e} |" for a, b, c, d, e in rows]
    return "\n".join(lines) + "\n"


# --- main ---------------------------------------------------------------------------------------


def dump(path: Path, data) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--report", type=Path, help="directory for classificacao_manejo.csv")
    parser.add_argument("--comparison", type=Path, help="Markdown file for the table of changed values")
    args = parser.parse_args()

    def atd(name: str):
        return json.loads((DELIVERY / name).read_text(encoding="utf-8"))

    cur_crops, cur_pests = json.loads(base_file("crops.json")), json.loads(base_file("pests_diseases.json"))
    crops = merge_crops(cur_crops, atd("crops.json"))
    pests, classification = merge_pests(cur_pests, atd("pests_diseases.json"))
    dump(OUT / "crops.json", crops)
    dump(OUT / "pests_diseases.json", pests)
    dump(OUT / "guidelines.json", json.loads(base_file("guidelines.json")) + atd("guidelines_novas.json"))
    dump(OUT / "sources.json", merge_sources(json.loads(base_file("sources.json")), atd("sources_novas.json")))
    companions = merge_companions(base_file("companions.csv"), (DELIVERY / "companions.csv").read_text("utf-8"))
    (OUT / "companions.csv").write_text(companions, encoding="utf-8")

    if args.report:
        args.report.mkdir(parents=True, exist_ok=True)
        (args.report / "classificacao_manejo.csv").write_text(classification_csv(classification, pests), "utf-8")
    if args.comparison:
        table = comparison_table(cur_crops, atd("crops.json"), crops, cur_pests, atd("pests_diseases.json"), pests)
        args.comparison.write_text(table, encoding="utf-8")


if __name__ == "__main__":
    main()
