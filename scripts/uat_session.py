"""Facilitator's tool for the joint UAT of the recommender (9.3) and the assistant (9.4).

Roteiro: docs/recommender/9.3.2-4_Roteiro_UAT.md. Talks to the running API over HTTP, so the response
times it records are the ones a client would see. Writes CSV files to `uat_results/` (ignored by git:
the raw results stay on the facilitator's machine). Participants are identified by a code (P01, P02...),
never by name, and the text of their messages is kept only with `--keep-text`, after consent.

    uv run uvicorn hort_ia.api.main:app --port 8080            # in another terminal
    uv run python scripts/uat_session.py recommend --participant P01 --role agricultor --ibge 4106902 \\
        --small-space --planted tomate
    uv run python scripts/uat_session.py chat --participant P01 --role agricultor --ibge 4106902 --keep-text
    uv run python scripts/uat_session.py summary

Only the standard library: nothing to install on the session notebook beyond the project itself.
"""

from __future__ import annotations

import argparse
import csv
import json
import statistics
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

TOP_N = 5  # recommendations rated per participant (9.3.1-3, section 7)
ROLES = ["agricultor", "coordenador", "agronomo", "outro"]
REC_FIELDS = ["timestamp", "participant", "role", "ibge_code", "month", "rank", "crop_id", "score", "useful",
              "comment", "model_version"]  # fmt: skip
CHAT_FIELDS = ["timestamp", "participant", "role", "turn", "text", "intent", "decision", "confidence", "handoff",
               "latency_ms", "understood"]  # fmt: skip


def post(api: str, path: str, payload: dict) -> tuple[dict, float]:
    request = urllib.request.Request(
        api.rstrip("/") + path,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    start = time.perf_counter()
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            body = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as err:
        raise SystemExit(f"API respondeu {err.code}: {err.read().decode('utf-8')}") from err
    except urllib.error.URLError as err:
        raise SystemExit(
            f"API fora do ar em {api}: {err.reason}. Suba com: uv run uvicorn hort_ia.api.main:app"
        ) from err
    return body, (time.perf_counter() - start) * 1000


def append(path: Path, fields: list[str], row: dict) -> None:
    new = not path.exists()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        if new:
            writer.writeheader()
        writer.writerow(row)


def ask(prompt: str, options: set[str] | None = None) -> str:
    while True:
        answer = input(prompt).strip().lower()
        if options is None or answer in options:
            return answer
        print(f"  Responda com: {', '.join(sorted(o or 'enter' for o in options))}")


def now() -> str:
    return datetime.now().isoformat(timespec="seconds")


# --- part A: recommendations (9.3) ---------------------------------------------------------


def recommend(args: argparse.Namespace) -> None:
    payload = {
        "ibge_code": args.ibge,
        "small_space": args.small_space,
        "planted": [c.strip() for c in args.planted.split(",") if c.strip()],
        "previous_crop": args.previous,
    }
    if args.month:
        payload["month"] = args.month
    result, latency = post(args.api, "/recommender/recommendations", payload)
    items = result["recommendations"][:TOP_N]
    print(f"\nRegião {result['region']}, mês {result['month']} ({latency:.0f} ms). {len(items)} recomendações.\n")
    for warning in result["warnings"]:
        print(f"  Aviso: {warning}")
    for item in items:
        print(f"{item['rank']}. {item['crop_name_pt']}")
        for reason in item["reasons"]:
            print(f"   + {reason['text']}")
        for warning in item["warnings"]:
            print(f"   ! {warning['text']}")
        useful = ask("   Útil para você? [s/n] ", {"s", "n"})
        comment = input("   Comentário (enter para pular): ").strip()
        append(args.out / "recommendations.csv", REC_FIELDS, {
            "timestamp": now(), "participant": args.participant, "role": args.role, "ibge_code": args.ibge,
            "month": result["month"], "rank": item["rank"], "crop_id": item["crop_id"], "score": item["score"],
            "useful": useful, "comment": comment, "model_version": result["model_version"],
        })  # fmt: skip
    print(f"\nRegistrado em {args.out / 'recommendations.csv'}.")


# --- part B: assistant (9.4) ---------------------------------------------------------------


def chat(args: argparse.Namespace) -> None:
    print("\nDigite a mensagem do participante como ele disse. '/foto RÓTULO' simula uma foto; linha vazia encerra.\n")
    post(args.api, "/nlp/message", {"text": "oi"})  # warm-up: the first call trains the classifier; not recorded
    context, turn = None, 0
    while True:
        text = input("Participante> ").strip()
        if not text or text == "/fim":
            break
        payload = {"text": text, "ibge_code": args.ibge, "small_space": args.small_space, "context": context}
        if text.startswith("/foto "):
            payload["cv_label"], payload["text"] = text.removeprefix("/foto ").strip(), "foto"
        reply, latency = post(args.api, "/nlp/message", payload)
        context, turn = reply["context"], turn + 1
        print(f"Assistente> {reply['text']}")
        confidence = "" if reply["confidence"] is None else f", confiança {reply['confidence']:.2f}"
        print(f"   [{reply['decision']}, {reply['intent']}{confidence}, {latency:.0f} ms]")
        understood = ask("   Entendeu e saberia o que fazer sem ajuda? [s/n/enter=não se aplica] ", {"s", "n", ""})
        append(args.out / "chat.csv", CHAT_FIELDS, {
            "timestamp": now(), "participant": args.participant, "role": args.role, "turn": turn,
            "text": text if args.keep_text else "", "intent": reply["intent"], "decision": reply["decision"],
            "confidence": reply["confidence"], "handoff": reply["handoff"], "latency_ms": round(latency),
            "understood": understood,
        })  # fmt: skip
    print(f"\n{turn} turnos registrados em {args.out / 'chat.csv'}.")


# --- summary (input for 9.3.2-6) -------------------------------------------------------------


def read(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def summary(args: argparse.Namespace) -> None:
    recs, turns = read(args.out / "recommendations.csv"), read(args.out / "chat.csv")
    if recs:
        useful = sum(r["useful"] == "s" for r in recs)
        print(f"Recomendações: {useful} de {len(recs)} úteis ({useful / len(recs):.0%}); meta da 9.3: 70%.")
        for participant in sorted({r["participant"] for r in recs}):
            mine = [r for r in recs if r["participant"] == participant]
            print(f"  {participant}: {sum(r['useful'] == 's' for r in mine)} de {len(mine)}")
    if turns:
        latencies = [int(t["latency_ms"]) for t in turns]
        rated = [t for t in turns if t["understood"] in ("s", "n")]
        print(f"Assistente: {len(turns)} turnos de {len({t['participant'] for t in turns})} participantes.")
        print(
            f"  Tempo de resposta: média {statistics.mean(latencies):.0f} ms, máximo {max(latencies)} ms; meta < 5000."
        )
        if rated:
            ok = sum(t["understood"] == "s" for t in rated)
            print(f"  Entendeu e saberia agir: {ok} de {len(rated)} ({ok / len(rated):.0%}).")
        decisions = {d: sum(t["decision"] == d for t in turns) for d in ("answer", "confirm", "ask", "fallback")}
        print(f"  Decisões: {decisions}")
        # Only messages the engine classified (not replies such as "sim" or "alface", not photos).
        kept = [t for t in turns if t["text"] and t["confidence"] and not t["text"].startswith("/foto")]
        if kept:
            print("  Perguntas para o conjunto de teste (origin: field; collected_from: papel; rotular à mão):")
            for t in kept:
                print(f"    - [{t['role']}] {t['text']}  (motor: {t['intent']})")
    if not recs and not turns:
        print(f"Nada registrado em {args.out}.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--api", default="http://localhost:8080")
    parser.add_argument("--out", type=Path, default=Path("uat_results"))
    sub = parser.add_subparsers(dest="part", required=True)
    for name in ("recommend", "chat"):
        p = sub.add_parser(name)
        p.add_argument("--participant", required=True, help="código, nunca o nome (P01, P02...)")
        p.add_argument("--role", required=True, choices=ROLES)
        p.add_argument("--ibge", type=int, help="código IBGE do município da horta")
        p.add_argument("--small-space", action="store_true")
        if name == "recommend":
            p.add_argument("--planted", default="", help="ids separados por vírgula (tomate,alface)")
            p.add_argument("--previous", help="cultura anterior do canteiro")
            p.add_argument("--month", type=int)
        else:
            p.add_argument("--keep-text", action="store_true", help="guarda o texto das mensagens (com consentimento)")
    sub.add_parser("summary")
    args = parser.parse_args()
    {"recommend": recommend, "chat": chat, "summary": summary}[args.part](args)


if __name__ == "__main__":
    main()
