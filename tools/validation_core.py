"""Core of the validation app for the recommender (9.3) and the assistant (9.4): everything but the screen.

`tools/validation_app.py` is the Streamlit screen over this module; here there is no Streamlit, so the
logic runs in the normal test suite. Like `scripts/uat_session.py`, it talks to the running API over HTTP
(standard library only), so the response times it records are the ones a client would see, and it writes
the same CSV files, which `uat_session.py summary` reads. Column names, roles, TOP_N and the CSV writer
come from the script itself: one source of truth for both tools.

This is a validation tool for test sessions, not part of the product (the chat interface and the
frontend are outside the scope of the module, Dicionário da EAP).
"""

from __future__ import annotations

import importlib
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

_uat = importlib.import_module("uat_session")  # scripts/ is not a package: it is put on the path above

# One source of truth with scripts/uat_session.py: the app reads these through this module.
CHAT_FIELDS = _uat.CHAT_FIELDS
REC_FIELDS = _uat.REC_FIELDS
ROLES = _uat.ROLES
TOP_N = _uat.TOP_N
append = _uat.append

DEFAULT_API = "http://localhost:8080"
KB_DIR = Path(os.environ.get("HORTIA_KB_DIR", ROOT / "data" / "knowledge"))
RESULTS_DIR = Path("uat_results")  # relative to where the app runs, like the script's --out

# Session type -> output folder. The rehearsal with colleagues and professors does not count for the UAT.
SESSION_TYPES = {
    "Ensaio (colegas e professores)": RESULTS_DIR / "ensaio",
    "UAT (piloto)": RESULTS_DIR,
}
CITIES = {
    "Curitiba (PR)": 4106902,
    "São Paulo (SP)": 3550308,
    "Manaus (AM)": 1302603,
    "Salvador (BA)": 2927408,
    "Goiânia (GO)": 5208707,
}
MONTHS = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro",
          "novembro", "dezembro"]  # fmt: skip

# `excluded[].reason` of POST /recommender/recommendations, in plain words.
EXCLUSION_TEXT = {
    "no_region_data": "Não temos a época de plantio para a sua região.",
    "out_of_season": "Não é época de plantar neste mês.",
    "not_for_small_space": "Precisa de mais espaço do que um vaso.",
    "no_small_space_info": "Não sabemos se dá certo em vaso.",
    "already_planted": "Já está na sua horta.",
    "same_family_as_previous": "É parente da planta que estava antes no canteiro. É melhor variar.",
}

PARTICIPANT = re.compile(r"P\d{2}")
PHOTO_PREFIX = "/foto "


def now() -> str:
    return datetime.now().isoformat(timespec="seconds")


# --- form helpers ----------------------------------------------------------------------------


def participant_error(code: str | None) -> str | None:
    """None when the participant code is valid (P + two digits); otherwise a message for the facilitator."""
    if PARTICIPANT.fullmatch((code or "").strip()):
        return None
    return "Use o código do participante: P e dois números (P01, P02...). O nome não é registrado."


def parse_ibge(text: str | None) -> int | None:
    """IBGE code typed by hand: 7 digits (municipality) or 2 (UF). The API has the final word."""
    digits = (text or "").strip()
    return int(digits) if re.fullmatch(r"\d{2}|\d{7}", digits) else None


def load_crops(kb_dir: Path = KB_DIR) -> dict[str, str]:
    """Crop id -> name, only to fill the form; the recommendations come from the API."""
    with (kb_dir / "crops.json").open(encoding="utf-8") as f:
        return {c["id"]: c["name_pt"] for c in json.load(f)}


def load_cv_labels(kb_dir: Path = KB_DIR) -> dict[str, str]:
    """Label of the computer vision model -> name to show, to simulate a photo."""
    with (kb_dir / "pests_diseases.json").open(encoding="utf-8") as f:
        entries = json.load(f)
    return {
        e["cv_label"]: f"{e['name_pt']} ({e['cv_label']})" if e["name_pt"] else e["cv_label"]
        for e in entries
        if e["cv_label"]
    }


def load_cv_names(kb_dir: Path = KB_DIR) -> dict[str, str]:
    """Label of the computer vision model -> popular name for the participant (the label when there is none)."""
    with (kb_dir / "pests_diseases.json").open(encoding="utf-8") as f:
        return {e["cv_label"]: e["name_pt"] or e["cv_label"] for e in json.load(f) if e["cv_label"]}


def explain_exclusions(excluded: list[dict], names: dict[str, str]) -> list[tuple[str, list[str]]]:
    """`excluded` of the API grouped by reason, in plain words: [(why, [crop names])]."""
    grouped: dict[str, list[str]] = {}
    for item in excluded:
        why = EXCLUSION_TEXT.get(item["reason"], item["reason"])
        grouped.setdefault(why, []).append(names.get(item["crop_id"], item["crop_id"]))
    return list(grouped.items())


def parse_photo(text: str) -> tuple[str, str | None]:
    """The script's shortcut `/foto LABEL`: (text to send, cv_label)."""
    if text.startswith(PHOTO_PREFIX):
        return "foto", text.removeprefix(PHOTO_PREFIX).strip()
    return text, None


def reply_markdown(text: str) -> str:
    """The API `text` as Markdown that keeps its line breaks (pest and disease answers, one part per line).

    Markdown joins single lines, and a line right after a list item would be glued to that item. So plain
    lines end with a hard break and the list gets a blank line before and after it. A one-line text is
    returned unchanged.
    """
    out, previous = [], None
    for line in text.split("\n"):
        item = line.startswith("- ")
        if previous is not None:
            out.append("\n" if item and previous else "\n\n" if item != previous else "  \n")
        out.append(line)
        previous = item
    return "".join(out)


# --- HTTP client -----------------------------------------------------------------------------

# (method, url, JSON body or None, timeout in s) -> (status, body). Raises OSError when there is no answer.
Transport = Callable[[str, str, bytes | None, float], tuple[int, bytes]]


def urllib_transport(method: str, url: str, body: bytes | None, timeout: float) -> tuple[int, bytes]:
    headers = {"Content-Type": "application/json"} if body is not None else {}
    request = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, response.read()
    except urllib.error.HTTPError as err:  # 4xx and 5xx come with a body; the caller decides
        return err.code, err.read()


@dataclass
class ApiResult:
    data: dict | None = None
    error: str | None = None  # message for the screen, in plain words
    detail: str = ""  # what the API said, for the facilitator
    latency_ms: float = 0.0  # from sending the request to the complete response, measured here

    @property
    def ok(self) -> bool:
        return self.error is None


class ApiClient:
    def __init__(self, base_url: str = DEFAULT_API, transport: Transport | None = None, timeout: float = 30):
        self.base_url = base_url.strip().rstrip("/")
        self.transport = transport or urllib_transport
        self.timeout = timeout

    def _call(self, method: str, path: str, payload: dict | None = None, timeout: float | None = None) -> ApiResult:
        body = None if payload is None else json.dumps(payload).encode("utf-8")
        start = time.perf_counter()
        try:
            status, raw = self.transport(method, self.base_url + path, body, timeout or self.timeout)
            data = json.loads(raw.decode("utf-8")) if raw else {}
        except (OSError, ValueError) as err:  # URLError, refused, timeout; invalid URL or JSON
            return ApiResult(
                error=f"Não consegui falar com a API em {self.base_url}. Confira se ela está ligada "
                "(uv run uvicorn hort_ia.api.main:app --port 8080) e o endereço na barra lateral.",
                detail=str(err),
            )
        latency = (time.perf_counter() - start) * 1000
        if status == 200:
            return ApiResult(data=data, latency_ms=latency)
        detail = data.get("detail", data) if isinstance(data, dict) else data
        detail = detail if isinstance(detail, str) else json.dumps(detail, ensure_ascii=False)
        if status == 422:
            if "IBGE" in detail:
                error = "A API não reconheceu o código da cidade (IBGE). Confira a cidade na barra lateral."
            else:
                error = "A API não aceitou os dados enviados. Confira a cidade, o mês e a mensagem."
        else:
            error = f"A API respondeu com erro ({status}). Anote o horário e tente de novo."
        return ApiResult(error=error, detail=detail, latency_ms=latency)

    def health(self) -> ApiResult:
        return self._call("GET", "/", timeout=3)

    def recommend(self, *, ibge_code: int, month: int, small_space: bool, planted: list[str],
                  previous_crop: str | None) -> ApiResult:  # fmt: skip
        payload = {"ibge_code": ibge_code, "month": month, "small_space": small_space, "planted": planted,
                   "previous_crop": previous_crop}  # fmt: skip
        return self._call("POST", "/recommender/recommendations", payload)

    def message(self, text: str, *, ibge_code: int | None, small_space: bool, context: dict | None = None,
                cv_label: str | None = None) -> ApiResult:  # fmt: skip
        payload = {"text": text, "ibge_code": ibge_code, "small_space": small_space, "context": context}
        if cv_label:
            payload["cv_label"] = cv_label
        return self._call("POST", "/nlp/message", payload)

    def warm_up(self) -> ApiResult:
        """Not recorded, like the script: the first message after start-up may be slower."""
        return self.message("oi", ibge_code=None, small_space=False)


# --- CSV rows (same columns and values as scripts/uat_session.py) -------------------------------


def rec_row(*, participant: str, role: str, ibge_code: int | None, result: dict, item: dict, useful: bool,
            comment: str = "") -> dict:  # fmt: skip
    return {
        "timestamp": now(), "participant": participant, "role": role, "ibge_code": ibge_code,
        "month": result["month"], "rank": item["rank"], "crop_id": item["crop_id"], "score": item["score"],
        "useful": "s" if useful else "n", "comment": comment.strip(), "model_version": result["model_version"],
    }  # fmt: skip


def chat_row(*, participant: str, role: str, turn: int, text: str, reply: dict, latency_ms: float,
             understood: str, keep_text: bool) -> dict:  # fmt: skip
    """`understood` is "s", "n" or "" (skipped, or not marked before the next message)."""
    return {
        "timestamp": now(), "participant": participant, "role": role, "turn": turn,
        "text": text if keep_text else "", "intent": reply["intent"], "decision": reply["decision"],
        "confidence": reply["confidence"], "handoff": reply["handoff"], "latency_ms": round(latency_ms),
        "understood": understood,
    }  # fmt: skip


def save_rating(out_dir: Path, row: dict) -> Path:
    path = out_dir / "recommendations.csv"
    append(path, REC_FIELDS, row)
    return path


def save_turn(out_dir: Path, row: dict) -> Path:
    path = out_dir / "chat.csv"
    append(path, CHAT_FIELDS, row)
    return path


@dataclass
class Turn:
    """A turn waiting for the facilitator's mark ("entendeu e saberia o que fazer sem ajuda?")."""

    number: int
    text: str  # as typed; `/foto LABEL` for a photo, like the script
    reply: dict
    latency_ms: float


@dataclass
class Conversation:
    """One conversation with the assistant: the `context` sent back unchanged and the turns to record.

    Each turn becomes one CSV row, written once: when the facilitator marks it or, unmarked, when the next
    message is sent or the conversation ends. Consent is read when the row is written, so a withdrawal
    during the session also applies to the turn still waiting.
    """

    out_dir: Path
    participant: str
    role: str
    keep_text: bool = False
    context: dict | None = None
    turns: int = 0
    pending: Turn | None = None

    def flush(self, understood: str = "") -> bool:
        """Write the waiting turn, if any. True when a row was written."""
        if self.pending is None:
            return False
        turn, self.pending = self.pending, None
        save_turn(self.out_dir, chat_row(
            participant=self.participant, role=self.role, turn=turn.number, text=turn.text, reply=turn.reply,
            latency_ms=turn.latency_ms, understood=understood, keep_text=self.keep_text,
        ))  # fmt: skip
        return True

    def send(self, client: ApiClient, text: str, *, ibge_code: int | None, small_space: bool,
             cv_label: str | None = None) -> ApiResult:  # fmt: skip
        """Send a message (or a photo, with `cv_label` or `/foto LABEL`). The previous turn is written first."""
        self.flush()
        sent, label = parse_photo(text)
        if cv_label:
            sent, label, text = "foto", cv_label, PHOTO_PREFIX + cv_label
        result = client.message(sent, ibge_code=ibge_code, small_space=small_space, context=self.context,
                                cv_label=label)  # fmt: skip
        if result.ok:
            self.context, self.turns = result.data["context"], self.turns + 1
            self.pending = Turn(self.turns, text, result.data, result.latency_ms)
        return result

    def reset(self) -> None:
        """New conversation: the waiting turn is written unmarked, then history and `context` start over."""
        self.flush()
        self.context, self.turns = None, 0
