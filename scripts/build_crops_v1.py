"""One-off generator for the first curated version of crops.json (kept for traceability).

Values were transcribed from:
  CAT  = Catálogo Brasileiro de Hortaliças (Embrapa/Sebrae, 2010) — planting windows,
         harvest start, temperature, frost tolerance (crop pages 9-57)
  HPE  = Horta em Pequenos Espaços (Embrapa, 2012) — Tabela 2, p. 35 (spacing,
         propagation, seedling days); p. 27 (crops suggested for small spaces)
  CT47 = Circular Técnica 47 (Embrapa Hortaliças, 2007) — Tabela 1, p. 4 (yield per
         10 m², batata spacing); p. 2 (crop groups)
"""

import json
from pathlib import Path

CAT, HPE, CT47 = "embrapa_catalogo_hortalicas", "embrapa_horta_pequenos_espacos", "embrapa_ct47_cultivo_hortalicas"
REGIONS = ["sul", "sudeste", "nordeste", "centro_oeste", "norte"]  # column order in CAT
MONTHS = {"jan": 1, "fev": 2, "mar": 3, "abr": 4, "mai": 5, "maio": 5, "jun": 6,
          "jul": 7, "ago": 8, "set": 9, "out": 10, "nov": 11, "dez": 12}


def months(text: str) -> list[int]:
    """'set./maio' -> [9..12, 1..5]; 'ano todo' -> 1..12; '*' -> [] (não recomendável)."""
    text = text.strip().lower()
    if text == "*":
        return []
    if text == "ano todo":
        return list(range(1, 13))
    start, end = (MONTHS[t.strip(" .")] for t in text.split("/"))
    return [((start - 1 + i) % 12) + 1 for i in range((end - start) % 12 + 1)]


def window(variant, cells, harvest, page):
    return {"variant": variant,
            "months_by_region": {r: months(c) for r, c in zip(REGIONS, cells)},
            "harvest_start_days": {"min": harvest[0], "max": harvest[1]},
            "source": {"source_id": CAT, "pages": str(page)}}


def spacing(conv, hpe, source=HPE, page="35"):
    sp = lambda v: v and {"between_rows_cm": v[0], "between_plants_cm": v[1]}
    return {"conventional": sp(conv), "small_spaces": sp(hpe),
            "source": {"source_id": source, "pages": page}}


def yld(lo, hi, unit):
    return {"min": lo, "max": hi, "unit": unit, "area_m2": 10, "source": {"source_id": CT47, "pages": "4"}}


def rng(lo, hi):
    return {"min": lo, "max": hi}


def crop(id, name_pt, sci, family, aliases, names_en, groups, prop, seedling, windows, spc,
         temp, frost, small, yield_, cat_page, notes=None):
    srcs = [{"source_id": CT47, "pages": "2"}, {"source_id": HPE, "pages": "27"}]
    if cat_page:
        srcs.insert(0, {"source_id": CAT, "pages": str(cat_page)})
    return {"id": id, "name_pt": name_pt, "scientific_name": sci, "family": family,
            "aliases": aliases, "names_en": names_en, "crop_groups": groups, "propagation": prop,
            "seedling_days": seedling, "planting_windows": windows, "spacing": spc,
            "optimal_temp_c": temp, "frost_tolerance": frost, "small_space_recommended": small,
            "yield_estimate": yield_, "sources": srcs, "validation_status": "draft", "notes": notes}


S, D = "seedling", "direct"
crops = [
    crop("tomate", "Tomate", "Solanum lycopersicum", "Solanaceae",
         ["tomateiro", "tomate-cereja", "tomate italiano", "tomate santa cruz", "pé de tomate"], ["tomato"],
         ["fruit"], [S], rng(20, 25),
         [window(None, ["set./fev.", "ano todo", "ano todo", "ano todo", "mar./jul."], (100, 120), 57)],
         spacing((100, 50), (70, 35)), None, None, True, yld(50, 100, "kg"), 57,
         "No Catálogo consta como Lycopersicon esculentum (sinônimo). HPE indica ciclo de 90-100 dias."),
    crop("batata", "Batata", "Solanum tuberosum", "Solanaceae",
         ["batata-inglesa", "batatinha"], ["potato"],
         ["tuber"], [D], None,
         [window(None, ["nov./dez.", "abr./maio", "*", "abr./maio", "*"], (90, 120), 17)],
         spacing((90, 30), None, CT47, "4"), rng(15, 25), None, False, yld(20, 30, "kg"), 17,
         "Plantio por tubérculo-semente. Não consta na Tabela 2 do HPE; espaçamento do CT 47 "
         "(impresso '0,90 x ,030', interpretado como 0,90 x 0,30 m). HPE não recomenda tubérculos em pequenos espaços."),
    crop("pimentao", "Pimentão", "Capsicum annuum", "Solanaceae",
         ["pimentão verde", "pimentão vermelho", "pimentão amarelo"], ["bell pepper", "pepper", "sweet pepper"],
         ["fruit"], [S], rng(30, 30),
         [window(None, ["set./fev.", "ago./mar.", "maio/set.", "ago./dez.", "abr./jul."], (100, 120), 49)],
         spacing((100, 50), (70, 35)), rng(15, 25), "none", True, yld(30, 40, "kg"), 49,
         "Requer tutoramento. Catálogo recomenda rotação com outras espécies (ex.: gramíneas)."),
    crop("morango", "Morango", "Fragaria × ananassa", "Rosaceae",
         ["morangueiro", "pé de morango"], ["strawberry"],
         ["fruit"], [S], rng(20, 30),
         [window(None, ["mar./abr.", "mar./abr.", "*", "fev./mar.", "*"], (70, 80), 44)],
         spacing((30, 20), (21, 14)), rng(15, 25), "none", None, yld(30, 40, "kg"), 44,
         "Mudas de estolhos. Grupo 'fruit' atribuído pelo critério de parte comestível (não listado no CT 47). "
         "Não citado na lista de pequenos espaços do HPE, embora a Tabela 2 traga espaçamento HPE."),
    crop("alface", "Alface", "Lactuca sativa", "Asteraceae",
         ["pé de alface", "alface crespa", "alface lisa", "alface americana", "alface roxa"], ["lettuce"],
         ["leafy"], [S], rng(20, 25),
         [window("inverno", ["fev./out.", "fev./jul.", "mar./set.", "mar./set.", "mar./jul."], (60, 80), 13),
          window("verao", ["ano todo"] * 5, (50, 70), 13)],
         spacing((25, 25), (18, 18)), None, None, True, yld(160, 160, "plants"), 13,
         "Época depende da cultivar (de inverno ou de verão)."),
    crop("couve", "Couve", "Brassica oleracea var. acephala", "Brassicaceae",
         ["couve-manteiga", "couve manteiga", "couve-de-folha", "couve de folhas"], ["collard greens", "collards", "kale"],
         ["leafy"], [S, D], rng(30, 30),
         [window(None, ["fev./jul.", "fev./jul.", "abr./ago.", "fev./jul.", "abr./jul."], (80, 90), 29)],
         spacing((90, 50), (63, 35)), None, None, True, yld(16, 16, "bunches"), 29,
         "Propagação mais comum por broto lateral. Exigente em boro e molibdênio (Catálogo)."),
    crop("rucula", "Rúcula", "Eruca vesicaria subsp. sativa", "Brassicaceae",
         ["pinchão", "pé de rúcula"], ["arugula", "rocket"],
         ["leafy"], [D], None,
         [window(None, ["mar./ago.", "mar./ago.", "mar./jul.", "mar./jul.", "*"], (40, 60), 53)],
         spacing((20, 5), (14, 4)), rng(15, 25), None, True, None, 53,
         "No Catálogo consta como Eruca sativa. CONFLITO: HPE indica ciclo de 25-30 dias; Catálogo, "
         "início de colheita em 40-60 dias. Sem produtividade no CT 47."),
    crop("repolho", "Repolho", "Brassica oleracea var. capitata", "Brassicaceae",
         ["repolho roxo", "repolho verde"], ["cabbage"],
         ["leafy"], [S], rng(20, 25),
         [window("inverno", ["fev./set.", "fev./jul.", "fev./jul.", "fev./jul.", "*"], (90, 110), 52),
          window("verao", ["nov./jan.", "out./fev.", "ano todo", "out./fev.", "mar./set."], (90, 110), 52)],
         spacing((80, 40), (56, 28)), rng(15, 25), "tolerant", None, yld(30, 60, "kg"), 52,
         "Grupo 'leafy' atribuído pelo critério de parte comestível (não listado no CT 47). "
         "Exigente em adubação e água constante."),
    crop("cenoura", "Cenoura", "Daucus carota subsp. sativus", "Apiaceae",
         ["pé de cenoura"], ["carrot"],
         ["root"], [D], None,
         [window("inverno", ["fev./ago.", "mar./jul.", "*", "abr./jul.", "*"], (90, 110), 25),
          window("verao", ["nov./jan.", "out./mar.", "out./mar.", "out./mar.", "out./mar."], (85, 100), 25)],
         spacing((20, 10), (14, 7)), None, None, False, yld(20, 30, "kg"), 25,
         "CONFLITO: CT 47 indica 20 x 5 cm; HPE, 20 x 10 cm (adotado). Germinação ideal 20-30 °C. "
         "Solo fofo, sem obstáculos."),
    crop("beterraba", "Beterraba", "Beta vulgaris", "Amaranthaceae",
         ["pé de beterraba"], ["beet", "beetroot"],
         ["root"], [S, D], rng(20, 30),
         [window(None, ["ano todo", "ano todo", "abr./ago.", "abr./ago.", "*"], (60, 70), 21)],
         spacing((20, 10), (14, 7)), rng(15, 25), "tolerant", False, yld(30, 40, "kg"), 21,
         "Catálogo: semente em local definitivo ou mudas; HPE Tabela 2: mudas. Quebrar dormência (molho 24 h)."),
    crop("rabanete", "Rabanete", "Raphanus sativus", "Brassicaceae",
         ["pé de rabanete"], ["radish"],
         ["root"], [D], None,
         [window(None, ["mar./ago.", "mar./ago.", "mar./jul.", "abr./set.", "mar./ago."], (25, 30), 51)],
         spacing((25, 5), (18, 4)), None, "light", False, yld(15, 30, "kg"), 51,
         "Colher antes do tamanho máximo para não ficar esponjoso."),
    crop("cebolinha", "Cebolinha", "Allium fistulosum / Allium schoenoprasum", "Amaryllidaceae",
         ["cebolinha-verde"], ["welsh onion", "green onion", "scallion", "chives"],
         ["leafy", "condiment"], [S], rng(30, 40),
         [window(None, ["ano todo", "ano todo", "mar./jul.", "abr./ago.", "abr./out."], (80, 100), 24)],
         spacing((25, 15), (18, 11)), {"min": None, "max": 25}, None, True, yld(6, 6, "kg"), 24,
         "O Catálogo agrupa as duas espécies como cebolinha. Rebrota: várias colheitas. "
         "'Cheiro-verde' (cebolinha + salsa) deve ser tratado no NLU, não como alias. "
         "CONFLITO menor: HPE indica ciclo de 70-90 dias."),
    crop("salsa", "Salsa", "Petroselinum crispum", "Apiaceae",
         ["salsinha"], ["parsley"],
         ["leafy", "condiment"], [D], None,
         [window(None, ["mar./set.", "mar./set.", "mar./ago.", "mar./ago.", "*"], (60, 70), 54)],
         spacing((25, 10), (18, 7)), None, None, True, yld(6, 6, "kg"), 54,
         "Catálogo: prefere temperaturas em torno de 20 °C. Germinação lenta (molho de uma noite)."),
    crop("manjericao", "Manjericão", "Ocimum basilicum", "Lamiaceae",
         ["alfavaca", "basilicão"], ["basil"],
         ["condiment"], [S], rng(30, 35),
         [{"variant": None,
           "months_by_region": {"sudeste": list(range(1, 13)), "centro_oeste": list(range(1, 13))},
           "harvest_start_days": {"min": 60, "max": 70},
           "source": {"source_id": HPE, "pages": "35"}}],
         spacing((60, 40), (42, 28)), None, None, True, None, None,
         "Não consta no Catálogo. Época 'ano todo' do HPE vale para Sudeste, Centro-Oeste, norte da região Sul "
         "e sul do Nordeste; Sul ficou sem dado. 'Alfavaca' também designa outras espécies de Ocimum."),
    crop("abobrinha", "Abobrinha", "Cucurbita pepo", "Cucurbitaceae",
         ["abobrinha italiana", "abobrinha verde"], ["zucchini", "courgette", "summer squash"],
         ["fruit"], [D], None,
         [window(None, ["set./maio", "ago./maio", "mar./out.", "ano todo", "abr./ago."], (45, 60), 9)],
         spacing((150, 100), (105, 70)), rng(15, 25), "none", None, yld(10, 15, "kg"), 9,
         "Sensível ao transplante e ao excesso de água. Grupo 'fruit' atribuído pelo critério de parte "
         "comestível. CONFLITO: HPE indica ciclo de 60-90 dias."),
]

out = Path(__file__).resolve().parents[1] / "data" / "knowledge" / "crops.json"
out.write_text(json.dumps(crops, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(f"{len(crops)} crops written to {out}")
