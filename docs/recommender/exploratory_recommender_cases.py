# Prototipo do motor de recomendacao e casos de teste de referencia (atividade 9.3.1-3).
# Uso, da raiz do repositorio: uv run python docs/recommender/exploratory_recommender_cases.py
# Dados: base de conhecimento agronomica (data/knowledge/, entregue em 9.3.1-7).
# Reproduz os casos da secao 6 de 9.3.1-3_Abordagem_Motor_Recomendacao.md. E um prototipo para
# fixar as regras; a implementacao de 9.3.1-4 fica em src/hort_ia/recommender/.
from collections import defaultdict

from hort_ia.core.geo import Region, region_from_ibge_code
from hort_ia.knowledge import get_knowledge_base

W_COMPANION = 1.0  # por cultura plantada com relacao favoravel (+) ou desfavoravel (-)
W_REPELLENT = 0.5  # planta repelente, so quando ja ha algo plantado

kb = get_knowledge_base()

PAIRS = defaultdict(set)
for rel in kb.usable_companions():  # decisao D6: pesquisa e fonte nao verificada ficam fora da pontuacao
    PAIRS[frozenset((rel.crop_a, rel.crop_b))].add(rel.relation.value)

REPELLENT = {c.id for c in kb.crops.values() if any(r.role == "pest_repellent" for r in c.companion_roles)}


def relation(a, b):
    """+1 se combinam, -1 se nao combinam (desfavoravel prevalece), 0 sem relacao registrada."""
    found = PAIRS.get(frozenset((a, b)), set())
    return -1 if "harms" in found else 1 if "helps" in found else 0


def months_left(months, month):
    """Meses seguidos, a partir de `month`, dentro da janela (12 = o ano todo)."""
    n, m = 0, month
    while m in months and n < 12:
        n, m = n + 1, m % 12 + 1
    return n


def recommend(region, month, small_space=False, planted=(), previous_crop=None):
    warnings = [f"cultura desconhecida ignorada: {p}" for p in planted if p not in kb.crops]
    planted = [p for p in planted if p in kb.crops]
    if previous_crop and previous_crop not in kb.crops:
        warnings.append(f"cultura anterior desconhecida ignorada: {previous_crop}")
        previous_crop = None
    previous_family = kb.crops[previous_crop].family if previous_crop else None

    items, excluded = [], []
    for crop in kb.crops.values():
        by_variant = crop.planting_months(region)
        if by_variant is None:
            excluded.append((crop.id, "no_region_data"))
            continue
        variants = [v for v, months in by_variant.items() if month in months]
        if not variants:
            excluded.append((crop.id, "out_of_season"))
            continue
        if small_space and crop.small_space_recommended is not True:
            reason = "not_for_small_space" if crop.small_space_recommended is False else "no_small_space_info"
            excluded.append((crop.id, reason))
            continue
        if crop.id in planted:
            excluded.append((crop.id, "already_planted"))
            continue
        if previous_family and crop.family == previous_family:
            excluded.append((crop.id, "same_family_as_previous"))
            continue
        companions = {p: relation(crop.id, p) for p in planted if relation(crop.id, p)}
        repellent = W_REPELLENT if planted and crop.id in REPELLENT else 0.0
        score = W_COMPANION * sum(companions.values()) + repellent
        left = max(months_left(by_variant[v], month) for v in variants)
        items.append((score, left, crop.name_pt, crop.id, companions, repellent, variants))
    items.sort(key=lambda t: (-t[0], t[1], t[2]))  # pontuacao, epoca que termina antes, nome
    return items, excluded, warnings


CASES = [
    ("R1", "Curitiba/PR, novembro", {"region": region_from_ibge_code(4106902), "month": 11}),
    (
        "R2",
        "Curitiba/PR, novembro, pouco espaco, ja planta tomate",
        {"region": Region.SUL, "month": 11, "small_space": True, "planted": ["tomate"]},
    ),
    ("R3", "Curitiba/PR, novembro, ja planta tomate", {"region": Region.SUL, "month": 11, "planted": ["tomate"]}),
    (
        "R4",
        "Curitiba/PR, marco, canteiro anterior: repolho",
        {"region": Region.SUL, "month": 3, "previous_crop": "repolho"},
    ),
    ("R5", "Manaus/AM, novembro", {"region": region_from_ibge_code(1302603), "month": 11}),
    ("R6", "Curitiba/PR, julho, pouco espaco", {"region": Region.SUL, "month": 7, "small_space": True}),
    (
        "R7",
        "Curitiba/PR, novembro, planta tomate e mandioca, canteiro anterior: tomate",
        {"region": Region.SUL, "month": 11, "planted": ["tomate", "mandioca"], "previous_crop": "tomate"},
    ),
    (
        "R8",
        "Sao Paulo/SP, abril, planta alface e cenoura",
        {"region": region_from_ibge_code(3550308), "month": 4, "planted": ["alface", "cenoura"]},
    ),
]


def main():
    for code, title, kwargs in CASES:
        items, excluded, warnings = recommend(**kwargs)
        print(f"\n== {code} — {title} ==")
        for rank, (score, left, _, crop_id, companions, repellent, variants) in enumerate(items, 1):
            variant = "" if variants == [None] else f" variantes={variants}"
            print(
                f"  {rank:2}. {crop_id:<11} {score:+.1f}  meses restantes={left:2}"
                f"  combina={companions or '-'}  repelente={repellent}{variant}"
            )
        print(f"  excluidas: {excluded}")
        if warnings:
            print(f"  avisos: {warnings}")


if __name__ == "__main__":
    main()
