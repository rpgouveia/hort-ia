"""Acceptance of the conversational engine on the held-out test set (WBS 9.4.2-2, cases U5 and U6).

The criterion of 9.4.1 (`docs/nlu/9.4.1-3_Abordagem_Motor_Conversacional.md`, section 7) is measured on
the whole engine for one message, not on the classifier alone:

- **correct**: the engine answered or confirmed the labeled intent, asked for an entity of that
  intent, or fell back on a message labeled `fallback`;
- **direct wrong**: the engine answered (decision `answer`) a different intent, with no chance for the
  user to correct it. This is the error that weighs most.

Asking the subject ("O que você quer saber sobre a alface?") is neither: it costs the user one turn.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

from .dataset import TestUtterance
from .dialogue import DialogueManager, Reply

MIN_CORRECT = 0.75  # 9.4.1-3, section 7 (proposal)
MAX_DIRECT_WRONG = 0.10
MIN_PER_INTENT = 10  # labeled utterances per intent before the criterion is measured (9.4.2-1, U5)
PROFILE = {"ibge_code": 4106902, "month": 11}  # Curitiba; the profile does not change the decision


@dataclass
class Outcome:
    text: str
    label: str
    decision: str
    predicted: str | None  # None when the engine asked the subject
    confidence: float | None

    @property
    def correct(self) -> bool:
        return self.predicted == self.label

    @property
    def direct_wrong(self) -> bool:
        return self.decision == "answer" and self.predicted != self.label


@dataclass
class Report:
    outcomes: list[Outcome] = field(default_factory=list)

    @property
    def n(self) -> int:
        return len(self.outcomes)

    @property
    def correct_rate(self) -> float:
        return sum(o.correct for o in self.outcomes) / self.n if self.n else 0.0

    @property
    def direct_wrong_rate(self) -> float:
        return sum(o.direct_wrong for o in self.outcomes) / self.n if self.n else 0.0

    @property
    def passes(self) -> bool:
        return self.correct_rate >= MIN_CORRECT and self.direct_wrong_rate <= MAX_DIRECT_WRONG

    def by_intent(self) -> dict[str, tuple[int, int]]:
        """intent -> (correct, total)."""
        totals, hits = Counter(o.label for o in self.outcomes), Counter(o.label for o in self.outcomes if o.correct)
        return {intent: (hits[intent], totals[intent]) for intent in sorted(totals)}


def predicted_intent(reply: Reply) -> str | None:
    if reply.decision == "fallback":
        return "fallback"
    if reply.intent == "clarify":
        return None
    return reply.intent


def evaluate(dialogue: DialogueManager, utterances: list[TestUtterance]) -> Report:
    """Each labeled utterance as the first message of a conversation."""
    report = Report()
    for u in utterances:
        if u.intent is None:
            continue
        reply = dialogue.handle(u.text, **PROFILE)
        report.outcomes.append(Outcome(u.text, u.intent, reply.decision, predicted_intent(reply), reply.confidence))
    return report


def enough_data(utterances: list[TestUtterance], intents: list[str]) -> list[str]:
    """Intents with fewer than MIN_PER_INTENT labeled utterances (empty list = enough to measure)."""
    counts = Counter(u.intent for u in utterances if u.intent is not None)
    return [intent for intent in intents if counts[intent] < MIN_PER_INTENT]


def threshold_grid(
    dialogue: DialogueManager, utterances: list[TestUtterance], values: tuple[float, ...] = (0.2, 0.3, 0.4, 0.5, 0.6)
) -> list[tuple[float, float, Report]]:
    """U6: the report for each (confirm_at, answer_at) pair with confirm_at <= answer_at."""
    rows = []
    for confirm_at in values:
        for answer_at in values:
            if confirm_at > answer_at:
                continue
            trial = DialogueManager(dialogue.nlu, dialogue.responder, answer_at=answer_at, confirm_at=confirm_at)
            rows.append((confirm_at, answer_at, evaluate(trial, utterances)))
    return rows
