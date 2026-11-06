# Comparacao de abordagens de NLU para o assistente conversacional (atividade 9.4.1-1).
# Uso, da raiz do repositorio: uv run python docs/nlu/exploratory_nlu_approaches.py
# Dados: data/nlu/intents.yaml (rascunho, 318 frases) e a base de conhecimento (sinonimos das culturas).
# Reproduz todos os numeros citados em 9.4.1-1_Estudo_Abordagens_NLU.md.
# Todos os resultados sao de validacao cruzada sobre o rascunho: servem para comparar abordagens,
# nao para estimar a acuracia com usuarios reais (ver o conjunto de teste em data/nlu/).
import re
import time

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, f1_score
from sklearn.model_selection import StratifiedKFold, cross_val_predict
from sklearn.naive_bayes import MultinomialNB
from sklearn.pipeline import make_pipeline, make_union
from sklearn.svm import LinearSVC

from hort_ia.knowledge import get_knowledge_base
from hort_ia.nlp import load_intents, normalize

SEEDS = range(5)  # 5 particoes diferentes da validacao cruzada de 5 partes
PAIR = ("planting_time", "what_to_plant")  # a diferenca entre as duas e a presenca de cultura


def char_tfidf():
    return TfidfVectorizer(preprocessor=normalize, analyzer="char_wb", ngram_range=(2, 5), sublinear_tf=True)


def word_tfidf():
    return TfidfVectorizer(preprocessor=normalize, ngram_range=(1, 2), sublinear_tf=True)


MODELS = {
    "A palavras 1-2 + Naive Bayes": lambda: make_pipeline(word_tfidf(), MultinomialNB(alpha=0.1)),
    "B palavras 1-2 + reg. logistica": lambda: make_pipeline(word_tfidf(), LogisticRegression(max_iter=2000, C=10)),
    "C caracteres 2-5 + reg. logistica (linha de base)": lambda: make_pipeline(
        char_tfidf(), LogisticRegression(max_iter=2000, C=10)
    ),
    "D caracteres 2-5 + SVM linear": lambda: make_pipeline(char_tfidf(), LinearSVC(C=1)),
    "E caracteres + palavras + reg. logistica": lambda: make_pipeline(
        make_union(char_tfidf(), word_tfidf()), LogisticRegression(max_iter=2000, C=10)
    ),
}
BASELINE = "C caracteres 2-5 + reg. logistica (linha de base)"
COMBINED = "E caracteres + palavras + reg. logistica"


def cv(seed):
    return StratifiedKFold(n_splits=5, shuffle=True, random_state=seed)


# --- Extracao de cultura por dicionario (nomes, ids e sinonimos da base de conhecimento) ---
kb = get_knowledge_base()
GAZ = {normalize(n): c.id for c in kb.crops.values() for n in (c.name_pt, c.id, *c.aliases)}
KEYS = sorted(GAZ, key=len, reverse=True)  # nomes compostos primeiro ("tomate cereja" antes de "tomate")
SINGLE = {k: v for k, v in GAZ.items() if " " not in k}


def crops_exact(text):
    text, found = f" {normalize(text)} ", []
    for k in KEYS:
        pattern = rf"(?<!\w){re.escape(k)}(?!\w)"
        if re.search(pattern, text):
            found.append(GAZ[k])
            text = re.sub(pattern, " ", text)
    return found


def levenshtein(a, b):
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def crops_fuzzy(text):
    """Exato primeiro; se nada casar, aceita 1 erro em nomes de 5+ letras e 2 erros em nomes de 8+."""
    if found := crops_exact(text):
        return found
    out = []
    for tok in normalize(text).split():
        for k, v in SINGLE.items():
            limit = 2 if len(k) >= 8 else 1 if len(k) >= 5 else 0
            if limit and abs(len(tok) - len(k)) <= limit and levenshtein(tok, k) <= limit:
                out.append(v)
    return out


def crop_rule(pred, has_crop):
    """Entre planting_time e what_to_plant, decide pela presenca de cultura, nao pelo classificador."""
    out = pred.copy()
    for i, p in enumerate(pred):
        if p in PAIR:
            out[i] = PAIR[0] if has_crop[i] else PAIR[1]
    return out


def pair_errors(y, pred):
    return int(sum((t in PAIR) and (p in PAIR) and t != p for t, p in zip(y, pred)))


def main():
    texts, labels = load_intents().texts_and_labels()
    y = np.array(labels)
    intents = sorted(set(labels))
    print(f"Rascunho: {len(texts)} frases, {len(intents)} intencoes\n")

    print("== 1. Classificadores (media e desvio em 5 particoes) ==")
    preds = {}
    for name, build in MODELS.items():
        accs, f1s = [], []
        for s in SEEDS:
            p = cross_val_predict(build(), texts, y, cv=cv(s))
            accs.append(accuracy_score(y, p))
            f1s.append(f1_score(y, p, average="macro"))
            preds.setdefault(name, []).append(p)
        print(f"  {name}: acuracia {np.mean(accs):.1%} (+/- {np.std(accs):.1%}), F1 macro {np.mean(f1s):.1%}")

    per_intent = np.mean([f1_score(y, p, labels=intents, average=None) for p in preds[BASELINE]], axis=0)
    print("  F1 por intencao da linha de base:", {it: f"{v:.0%}" for it, v in zip(intents, per_intent)})

    print("\n== 2. Cobertura do dicionario de culturas por intencao ==")
    exact = np.array([bool(crops_exact(t)) for t in texts])
    fuzzy = np.array([bool(crops_fuzzy(t)) for t in texts])
    print(f"  {len(GAZ)} nomes e sinonimos para {len(kb.crops)} culturas")
    for it in intents:
        m = y == it
        print(f"  {it}: exato {exact[m].mean():.0%} | com erro de digitacao {fuzzy[m].mean():.0%}")
    print("  Deteccoes que so a busca tolerante encontrou:")
    for i in np.where(fuzzy & ~exact)[0]:
        print(f"    '{texts[i]}' -> {crops_fuzzy(texts[i])}")
    print("  planting_time sem cultura detectada:", [texts[i] for i in np.where((y == PAIR[0]) & ~fuzzy)[0]])

    print("\n== 3. Regra da entidade sobre a linha de base (media em 5 particoes) ==")
    base = preds[BASELINE]
    for label, rows in [
        ("so classificador", base),
        ("+ regra com dicionario exato", [crop_rule(p, exact) for p in base]),
        ("+ regra com busca tolerante", [crop_rule(p, fuzzy) for p in base]),
        ("modelo E + regra com busca tolerante", [crop_rule(p, fuzzy) for p in preds[COMBINED]]),
    ]:
        acc = np.mean([accuracy_score(y, p) for p in rows])
        err = np.mean([pair_errors(y, p) for p in rows])
        print(f"  {label}: acuracia {acc:.1%}, confusoes planting_time x what_to_plant {err:.1f}")

    print("\n== 4. Limiar de confianca para fallback (linha de base + regra tolerante, particao 0) ==")
    proba = cross_val_predict(MODELS[BASELINE](), texts, y, cv=cv(0), method="predict_proba")
    top = proba.max(axis=1)
    pred = crop_rule(np.array(intents)[proba.argmax(axis=1)], fuzzy)
    print(f"  Confianca maxima, quantis 10/25/50/75/90%: {np.round(np.quantile(top, [0.1, 0.25, 0.5, 0.75, 0.9]), 2)}")
    print(
        "  limiar | respondidas | acerto nas respondidas | acerto total | fallback reconhecido | validas encaminhadas"
    )
    fb = y == "fallback"
    for thr in [0.0, 0.3, 0.4, 0.5, 0.6]:
        keep = top >= thr
        final = np.where(keep, pred, "fallback")
        print(
            f"  {thr:.1f} | {keep.mean():.0%} | {(pred[keep] == y[keep]).mean():.1%} | {(final == y).mean():.1%}"
            f" | {(final[fb] == 'fallback').mean():.0%} | {int(((final == 'fallback') & ~fb).sum())}"
        )

    print("\n== 5. Tempo de inferencia (linha de base, CPU) ==")
    model = MODELS[BASELINE]().fit(texts, y)
    n, start = 1000, time.perf_counter()
    for _ in range(n):
        model.predict(["quando planto alface em curitiba?"])
    print(f"  {(time.perf_counter() - start) / n * 1000:.2f} ms por mensagem")


if __name__ == "__main__":
    main()
