"""Acceptance of the conversational engine on the held-out test set (9.4.1 criterion, 9.4.2-2 U5/U6).

Runs the whole engine (understanding + dialogue) on data/nlu/test_utterances.yaml and reports the
criterion of 9.4.1-3, section 7, per intent, and the table used to calibrate the confidence thresholds.
scripts/evaluate_nlu_baseline.py remains the quick check of the training data.

Usage: uv run python scripts/evaluate_nlu_engine.py
"""

from collections import Counter

from hort_ia.knowledge import load_knowledge_base
from hort_ia.market.loader import load_market_dataset
from hort_ia.nlp import DialogueManager, Interpreter, Responder, check_test_set, load_intents, load_templates
from hort_ia.nlp.dataset import load_test_set
from hort_ia.nlp.evaluation import MAX_DIRECT_WRONG, MIN_CORRECT, MIN_PER_INTENT, enough_data, evaluate, threshold_grid


def main() -> None:
    dataset, test = load_intents(), load_test_set()
    if problems := check_test_set(dataset, test):
        raise SystemExit("Test set problems:\n- " + "\n- ".join(problems))
    labeled = test.labeled()
    unlabeled = [u.text for u in test.utterances if u.intent is None]
    print(f"Test set: {len(labeled)} labeled, {len(unlabeled)} with intent null.")
    origins = Counter(u.origin.value for u in test.utterances)
    print(f"Origins: {dict(origins)}")
    if not labeled:
        raise SystemExit("Empty. Fill data/nlu/test_utterances.yaml (see data/nlu/README.md).")
    missing = enough_data(labeled, sorted({i.name for i in dataset.intents}))
    if missing:
        print(f"WARNING: fewer than {MIN_PER_INTENT} utterances for {missing}; the figures below are indicative.")

    kb, market = load_knowledge_base(), load_market_dataset()
    dialogue = DialogueManager(Interpreter(kb, market, dataset), Responder(kb, load_templates(), market))
    report = evaluate(dialogue, labeled)
    print(f"\n== Criterion of 9.4.1 (thresholds {dialogue.confirm_at} / {dialogue.answer_at}) ==")
    print(f"Correct intent: {report.correct_rate:.1%} (target >= {MIN_CORRECT:.0%})")
    print(f"Direct wrong answers: {report.direct_wrong_rate:.1%} (target <= {MAX_DIRECT_WRONG:.0%})")
    print(f"Result: {'PASS' if report.passes else 'FAIL'}\n")
    for intent, (hit, total) in report.by_intent().items():
        print(f"  {intent:<20} {hit:>3} / {total:<3}")
    wrong = [o for o in report.outcomes if o.direct_wrong]
    if wrong:
        print("\nDirect wrong answers:")
        for o in wrong:
            print(f"  '{o.text}': {o.label} -> {o.predicted} ({o.confidence:.2f})")
    if unlabeled:
        print("\nIntent null (candidates for a new intent):", unlabeled)

    print("\n== Thresholds (U6): correct / direct wrong ==")
    for confirm_at, answer_at, trial in threshold_grid(dialogue, labeled):
        mark = "  <- in use" if (confirm_at, answer_at) == (dialogue.confirm_at, dialogue.answer_at) else ""
        ok = "pass" if trial.passes else "    "
        print(f"  confirm {confirm_at:.1f}  answer {answer_at:.1f}:  {trial.correct_rate:6.1%}  "
              f"{trial.direct_wrong_rate:6.1%}  {ok}{mark}")  # fmt: skip


if __name__ == "__main__":
    main()
