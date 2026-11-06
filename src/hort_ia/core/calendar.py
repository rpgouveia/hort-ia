"""Month formatting shared by the recommendation engine and the conversational assistant."""

from __future__ import annotations


def format_months(months: list[int], names: list[str]) -> str:
    """[2..10] -> 'de fevereiro a outubro'; wraps the year; 12 months -> 'o ano todo'.

    `names` are the 12 month names, January first. Runs keep the order of the source, so a window
    written as set-mai reads "de setembro a maio".
    """
    selected = set(months)
    if len(selected) == 12:
        return "o ano todo"
    runs = []
    for start in sorted(selected):
        if (start - 2) % 12 + 1 in selected:
            continue  # not the start of a run
        end = start
        while end % 12 + 1 in selected:
            end = end % 12 + 1
        runs.append((start, end))
    runs.sort(key=lambda run: months.index(run[0]))
    parts = [f"em {names[s - 1]}" if s == e else f"de {names[s - 1]} a {names[e - 1]}" for s, e in runs]
    return " e ".join(parts)
