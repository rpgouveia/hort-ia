"""Acceptance of the conversational engine (WBS 9.4.2-2, cases U5 and U6 of `docs/nlu/9.4.2-1_Plano_Casos_Teste.md`).

U5 measures the criterion of 9.4.1 on `data/nlu/test_utterances.yaml` and is skipped, with the reason,
until every intent has at least 10 labeled utterances. The metric itself is checked here on the
reference messages of 9.4.1-3, which are outside the training data but were written by the team: they
validate the computation, not the criterion.
"""

import pytest

from hort_ia.knowledge import load_knowledge_base
from hort_ia.market.loader import load_market_dataset
from hort_ia.nlp import DialogueManager, Interpreter, Responder, load_intents, load_templates
from hort_ia.nlp.dataset import Origin, TestUtterance, load_test_set
from hort_ia.nlp.evaluation import MAX_DIRECT_WRONG, MIN_CORRECT, enough_data, evaluate, threshold_grid


@pytest.fixture(scope="module")
def dialogue():
    kb, market = load_knowledge_base(), load_market_dataset()
    return DialogueManager(Interpreter(kb, market), Responder(kb, load_templates(), market))


def team(text: str, intent: str) -> TestUtterance:
    return TestUtterance(text=text, intent=intent, origin=Origin.TEAM)


REFERENCE = [  # 9.4.1-3, section 6, with the intent a person would assign
    team("o que da pra plantar agora?", "what_to_plant"),
    team("quanto ta o tomate no ceasa?", "market_price"),
    team("o que planto depois do repolho?", "companion_planting"),
    team("da pra plantar cebolinha em vaso?", "crop_care"),
    team("minha couve ta com uns bichinho", "pest_disease"),
    team("quanto custa o adubo?", "fallback"),
    team("quando eu planto?", "planting_time"),
    team("quando planto mandioca?", "planting_time"),
    team("qndo plantar alfase?", "planting_time"),
    team("qual a epoca de plantar alface?", "planting_time"),
    team("e a rega dela?", "crop_care"),
    team("a alface ta amarelando", "pest_disease"),
    team("tem como plantar morango aqui?", "planting_time"),  # the engine confirms crop_care: wrong
    team("alface aguenta frio?", "crop_care"),  # the engine asks the subject: neither right nor wrong
    team("como crio galinha?", "fallback"),
]


def test_u5_metric_on_the_reference_messages(dialogue):
    report = evaluate(dialogue, REFERENCE)
    assert report.n == 15
    wrong = {o.text: (o.decision, o.predicted) for o in report.outcomes if not o.correct}
    assert wrong == {
        "tem como plantar morango aqui?": ("confirm", "crop_care"),
        "alface aguenta frio?": ("ask", None),
    }
    assert report.correct_rate == pytest.approx(13 / 15)
    assert report.direct_wrong_rate == 0.0
    assert report.passes


def test_u5_direct_wrong_counts_only_answers(dialogue):
    report = evaluate(dialogue, [team("o que da pra plantar agora?", "market_price")])
    assert report.outcomes[0].direct_wrong and report.direct_wrong_rate == 1.0 and not report.passes


def test_u5_criterion_on_the_test_set(dialogue):
    test = load_test_set().labeled()
    intents = sorted(i.name for i in load_intents().intents)
    missing = enough_data(test, intents)
    if missing:
        pytest.skip(f"test set below 10 utterances for {missing} (9.4.1-9 and UAT); criterion not verified yet")
    report = evaluate(dialogue, test)
    assert report.correct_rate >= MIN_CORRECT, report.by_intent()
    assert report.direct_wrong_rate <= MAX_DIRECT_WRONG


def test_u6_threshold_grid(dialogue):
    rows = threshold_grid(dialogue, REFERENCE)
    pairs = [(c, a) for c, a, _ in rows]
    assert (0.3, 0.5) in pairs and all(c <= a for c, a in pairs)
    by_pair = {(c, a): report for c, a, report in rows}
    # Raising the answer threshold never adds direct answers.
    assert by_pair[(0.3, 0.6)].direct_wrong_rate <= by_pair[(0.3, 0.5)].direct_wrong_rate
    assert by_pair[(0.3, 0.5)].correct_rate == evaluate(dialogue, REFERENCE).correct_rate
