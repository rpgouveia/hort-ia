# Dispersao de precos, bandas e casos de teste do motor de 9.5 (atividade 9.5.1-3).
# Uso, da raiz do repositorio: uv run python docs/commercial/exploratory_price_spread.py
# Dados: data/market/ (base Conab entregue em 9.5.1-7, mes de referencia ago/2026).
# Reproduz todos os numeros citados em 9.5.1-3_Abordagem_Comparacao_e_Matching.md.
import json
import statistics as st
from pathlib import Path

import pandas as pd
from hort_ia.core import region_from_uf  # mesma resolucao UF -> macrorregiao usada pelo motor

MARKET = Path(__file__).resolve().parents[2] / "data" / "market"
PRODUCTS = ["alface", "batata", "cebola", "cenoura", "tomate"]

ent = {e["id"]: e for e in json.loads((MARKET / "entrepostos.json").read_text())}
ref = pd.read_csv(MARKET / "prices_reference.csv")
ser = pd.read_csv(MARKET / "prices_monthly.csv")
qty = pd.read_csv(MARKET / "quantities.csv")
uf = pd.read_csv(MARKET / "supply_uf.csv")

local = ref[ref.entrepost_id.notna()]
national = {r.product_id: r.price_brl_kg for _, r in ref[ref.entrepost_id.isna()].iterrows()}
series = ser.pivot_table(index=["product_id", "entrepost_id"], columns="month", values="price_brl_kg")
series = series.reindex(columns=sorted(ser.month.unique()))


def monthly_changes(product):  # |variacao mes a mes| de todas as series do produto
    out = []
    for _, row in series.loc[[product]].iterrows():
        v = row.dropna()
        out += [abs(v.iloc[i] / v.iloc[i - 1] - 1) for i in range(1, len(v))]
    return out


def band(product):  # banda_p da secao 5.2
    return round(st.median(monthly_changes(product)), 2)


print("== cobertura (secao 2)")
print("entrepostos:", len(ent), "| UFs com Ceasa:", sorted({e["uf"] for e in ent.values()}))
for p in PRODUCTS:
    rows = local[local.product_id == p]
    regions = sorted({ent[e]["region"] for e in rows.entrepost_id})
    print(f"  {p:8s} {len(rows):2d}/12 entrepostos com preco | regioes: {regions}")
gaps = [(p, e) for p in PRODUCTS for e in ent if not ((local.product_id == p) & (local.entrepost_id == e)).any()]
print("  pares sem preco de referencia:", sorted({e for _, e in gaps}))

print("\n== (3a) dispersao entre entrepostos no mes de referencia")
print(f"{'produto':8s} {'nacional':>9s} {'min':>6s} {'mediana':>8s} {'max':>6s} {'max/min':>8s} {'CV':>7s}")
for p in PRODUCTS:
    v = local[local.product_id == p].price_brl_kg.tolist()
    print(f"{p:8s} {national[p]:9.2f} {min(v):6.2f} {st.median(v):8.2f} {max(v):6.2f}"
          f" {max(v) / min(v):7.2f}x {st.pstdev(v) / st.mean(v):7.1%}")
dev = [abs(r.price_brl_kg / national[r.product_id] - 1) for _, r in local.iterrows()]
print(f"  desvio |entreposto vs media nacional| n={len(dev)} mediana={st.median(dev):.1%}"
      f" media={st.mean(dev):.1%} p90={sorted(dev)[int(0.9 * len(dev))]:.1%} max={max(dev):.1%}")

print("\n== (3b) dispersao dentro da regiao (>= 2 entrepostos com preco)")
for p in PRODUCTS:
    rows = local[local.product_id == p]
    for region in sorted({ent[e]["region"] for e in rows.entrepost_id}):
        v = [r.price_brl_kg for _, r in rows.iterrows() if ent[r.entrepost_id]["region"] == region]
        if len(v) >= 2:
            print(f"  {p:8s} {region:12s} n={len(v)} min={min(v):5.2f} max={max(v):5.2f}"
                  f" max/min={max(v) / min(v):.2f}x CV={st.pstdev(v) / st.mean(v):5.1%}")

print("\n== (3c) banda de tolerancia por produto")
for p in PRODUCTS:
    ch = monthly_changes(p)
    print(f"  {p:8s} n={len(ch):4d} mediana={st.median(ch):6.1%} media={st.mean(ch):6.1%}"
          f" p90={sorted(ch)[int(0.9 * len(ch))]:6.1%} -> banda_p = +-{band(p):.0%}")

print("\n== (3d) envelhecimento do preco de referencia")
for k in (1, 2, 3, 6):
    d = []
    for _, row in series.iterrows():
        v = row.dropna()
        d += [abs(v.iloc[i] / v.iloc[i - k] - 1) for i in range(k, len(v))]
    print(f"  k={k}m n={len(d):5d} mediana={st.median(d):5.1%} p90={sorted(d)[int(0.9 * len(d))]:5.1%}")

print("\n== (3e) defasagem: ultimo mes de cada entreposto")
for e, month in ser.groupby("entrepost_id").month.max().items():
    n = (ser.entrepost_id == e).sum()
    print(f"  {e:20s} ate {month} ({n:4d} observacoes)")
print("  volumes publicados apenas em:", sorted(qty.month.unique()))

print("\n== oferta por UF (D8: contexto, fora do score)")
for p in PRODUCTS:
    rows = uf[uf.product_id == p].sort_values("quantity_kg", ascending=False)
    total = rows.quantity_kg.sum()
    top = ", ".join(f"{r.uf} {r.quantity_kg / total:.0%}" for _, r in rows.head(4).iterrows())
    print(f"  {p:8s} UFs={len(rows):2d} | {top}")

# --- Casos de teste da secao 9 ------------------------------------------------


def reference(product, user_uf):
    """Escada da secao 5.1: UF -> macrorregiao -> nacional."""
    rows = local[local.product_id == product]
    same_uf = [r.price_brl_kg for _, r in rows.iterrows() if ent[r.entrepost_id]["uf"] == user_uf]
    if same_uf:  # nivel local: faixa em torno da mediana da UF
        value = st.median(same_uf)
        return "local", value, (value, value), 1.00
    region = region_from_uf(user_uf)
    same_region = [r.price_brl_kg for _, r in rows.iterrows() if ent[r.entrepost_id]["region"] == region]
    if same_region:  # nivel regional: faixa a partir do minimo e do maximo observados
        return "regional", st.median(same_region), (min(same_region), max(same_region)), 0.70
    return "nacional", national[product], (national[product], national[product]), 0.40


def compare(product, user_uf, price=None):
    level, value, (low, high), confidence = reference(product, user_uf)
    b = band(product) if level != "nacional" else 0.30
    lo, hi = round(low * (1 - b), 2), round(high * (1 + b), 2)
    out = (f"  {product:7s} {user_uf} -> {level:8s} ref={value:5.2f} faixa=[{lo:5.2f}; {hi:5.2f}]"
           f" banda=+-{b:.0%} confianca={confidence:.2f}")
    if price is not None:
        deviation = price / value - 1
        position = "na_faixa" if lo <= price <= hi else ("abaixo_da_faixa" if price < lo else "acima_da_faixa")
        out += f" | informado={price:.2f} desvio={deviation:+.1%} {position}"
    print(out + ("  [degraded]" if level == "nacional" else ""))


print("\n== secao 9: comparacao de precos (C1-C4; C5/C6 sao as series defasadas acima)")
compare("alface", "PR", 4.30)   # C1
compare("alface", "SP", 4.00)   # C2
compare("alface", "RS", 4.80)   # C3 - sem Ceasa na UF, cai para a regiao Sul
compare("alface", "MS", 4.80)   # C4 - Centro-Oeste sem referencia regional

WEIGHTS = (0.40, 0.30, 0.30)  # proximidade, quantidade, preco
PROXIMITY = {"cidade": 1.00, "uf": 0.80, "regiao": 0.50, "outra": 0.20}


def match(ask_price, ask_qty, product, user_uf, candidates):
    _, value, _, _ = reference(product, user_uf)
    b = band(product)
    ranked = []
    for name, proximity, cand_qty, cand_price in candidates:
        gap = (cand_price - ask_price) / value          # sinal a favor do requisitante
        if gap < -b:                                    # filtro duro 4 (secao 7.1)
            print(f"  {name:28s} eliminado: gap {gap:+.1%} < -{b:.0%}")
            continue
        quantity = min(ask_qty, cand_qty) / max(ask_qty, cand_qty)
        price = max(0.0, min(1.0, 0.5 + gap / (2 * b)))
        score = WEIGHTS[0] * PROXIMITY[proximity] + WEIGHTS[1] * quantity + WEIGHTS[2] * price
        ranked.append((score, PROXIMITY[proximity], quantity, name, price))
    for score, proximity, quantity, name, price in sorted(ranked, reverse=True):
        print(f"  {name:28s} prox={proximity:.2f} qtd={quantity:.3f} preco={price:.3f} score={score:.2f}")


print("\n== secao 9: matching (oferta de 300 kg de alface em Curitiba/PR a R$ 4,00)")
match(4.00, 300, "alface", "PR", [
    ("D1 Curitiba/PR 300kg 4,20", "cidade", 300, 4.20),
    ("D2 Londrina/PR 500kg 4,60", "uf", 500, 4.60),
    ("D3 Sao Jose/SC 250kg 3,90", "regiao", 250, 3.90),
    ("D4 Recife/PE 300kg 3,40", "outra", 300, 3.40),
])
