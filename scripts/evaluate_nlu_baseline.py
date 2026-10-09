"""Baseline evaluation of the NLU dataset: TF-IDF (character n-grams) + logistic regression.

Purpose: a quick quality check of data/nlu/intents.yaml while the engine approach (9.4.1-3)
is being decided, NOT the final model. Character n-grams tolerate typos and missing accents.

- Always: stratified 5-fold cross-validation on the training data. With drafted examples this
  is optimistic (same author, same style); treat it as an upper bound.
- If data/nlu/test_utterances.yaml has labeled utterances: trains on all training data and
  reports accuracy on the held-out set, which is the number that counts.

Usage: uv run python scripts/evaluate_nlu_baseline.py
"""

from collections import Counter

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report
from sklearn.model_selection import StratifiedKFold, cross_val_predict
from sklearn.pipeline import make_pipeline

from hort_ia.nlp import check_test_set, load_intents, load_test_set, normalize


def build_model():
    return make_pipeline(
        TfidfVectorizer(preprocessor=normalize, analyzer="char_wb", ngram_range=(2, 5), sublinear_tf=True),
        LogisticRegression(max_iter=2000, C=10),
    )


def main() -> None:
    dataset = load_intents()
    texts, labels = dataset.texts_and_labels()
    print(f"Training data: {len(texts)} examples, {len(set(labels))} intents\n")

    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    predicted = cross_val_predict(build_model(), texts, labels, cv=cv)
    print("== 5-fold cross-validation (optimistic: drafted data) ==")
    print(classification_report(labels, predicted, digits=3, zero_division=0))

    confusions = Counter((t, p) for t, p in zip(labels, predicted) if t != p)
    if confusions:
        print("Most frequent confusions (true -> predicted):")
        for (true, pred), n in confusions.most_common(8):
            examples = [x for x, t, p in zip(texts, labels, predicted) if (t, p) == (true, pred)][:2]
            print(f"  {true} -> {pred}: {n}  e.g. {examples}")

    test = load_test_set()
    if problems := check_test_set(dataset, test):
        raise SystemExit("Test set problems:\n- " + "\n- ".join(problems))
    labeled = test.labeled()
    print(f"\n== Held-out test set: {len(labeled)} labeled utterances ==")
    if not labeled:
        print("Empty. Fill data/nlu/test_utterances.yaml (see data/nlu/README.md).")
        return
    model = build_model().fit(texts, labels)
    test_pred = model.predict([u.text for u in labeled])
    print(classification_report([u.intent for u in labeled], test_pred, digits=3, zero_division=0))
    unlabeled = len(test.utterances) - len(labeled)
    if unlabeled:
        print(f"{unlabeled} utterance(s) with intent: null -> candidates for new intents.")


if __name__ == "__main__":
    main()
