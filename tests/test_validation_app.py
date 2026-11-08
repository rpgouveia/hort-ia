"""Smoke test of the validation app screen (tools/validation_app.py) with Streamlit's AppTest.

Skipped when the `validation` dependency group is not installed (uv sync --group validation). The app
talks to the real API in process: the core's HTTP transport is swapped for the FastAPI TestClient.
"""

import csv
from pathlib import Path

import pytest
from starlette.testclient import TestClient

pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest  # noqa: E402

import validation_core as core  # noqa: E402

from hort_ia.api.main import app  # noqa: E402

APP = Path(__file__).resolve().parents[1] / "tools" / "validation_app.py"


@pytest.fixture
def screen(monkeypatch, tmp_path) -> AppTest:
    client = TestClient(app)

    def transport(method: str, url: str, body: bytes | None, timeout: float) -> tuple[int, bytes]:
        response = client.request(method, url, content=body, headers={"Content-Type": "application/json"})
        return response.status_code, response.content

    monkeypatch.setattr(core, "urllib_transport", transport)
    monkeypatch.chdir(tmp_path)  # the CSV files go to tmp_path/uat_results
    at = AppTest.from_file(str(APP), default_timeout=60)
    at.session_state["api_url"] = "http://testserver"
    return at.run()


def rows(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def test_without_a_valid_participant_nothing_is_recorded(screen, tmp_path):
    assert not screen.exception
    assert screen.sidebar.success[0].value == "API ligada"
    assert any("código do participante" in w.value for w in screen.warning)
    for code in ("Ana", "P1"):  # the field takes at most 3 characters, so a full name cannot be typed
        screen.text_input(key="participant").input(code).run()
        assert any("nome não é registrado" in e.value for e in screen.sidebar.error)
        assert any("código do participante" in w.value for w in screen.warning)
    assert not screen.main.subheader  # no recommendation cards
    assert not (tmp_path / "uat_results").exists()


def test_recommendations_are_rated_once_each(screen, tmp_path):
    screen.text_input(key="participant").input("P01").run()
    screen.checkbox(key="small_space").check()
    screen.selectbox(key="month").select(11)
    screen.multiselect(key="planted").select("tomate")
    screen.button(key="rec_submit").click().run()
    assert not screen.exception
    titles = [s.value for s in screen.main.subheader]
    assert titles[:4] == ["1. Manjericão", "2. Cebolinha", "3. Pimentão", "4. Alface"]

    screen.text_input(key="comment_1_1").input("já tenho em casa")
    screen.button(key="useful_1_1").click().run()
    screen.button(key="not_useful_1_2").click().run()
    assert screen.button(key="useful_1_1").disabled
    assert "2 de" in screen.get("progress")[0].proto.text

    first, second = rows(tmp_path / "uat_results" / "ensaio" / "recommendations.csv")
    assert (first["participant"], first["crop_id"], first["useful"], first["comment"]) == (
        "P01", "manjericao", "s", "já tenho em casa")  # fmt: skip
    assert (second["crop_id"], second["useful"]) == ("cebolinha", "n")


def test_assistant_turn_is_recorded_when_marked(screen, tmp_path):
    screen.text_input(key="participant").input("P02").run()
    screen.session_state["tab"] = "Assistente"
    screen.run()
    screen.chat_input[0].set_value("qndo plantar alfase?").run()
    assert not screen.exception
    assert screen.button(key="confirm_yes_1")  # "Você quis dizer alface?" with Sim/Não

    screen.button(key="confirm_yes_1").click().run()  # sends "sim": turn 1 is written unmarked
    screen.button(key="understood_s_2").click().run()
    first, second = rows(tmp_path / "uat_results" / "ensaio" / "chat.csv")
    assert (first["turn"], first["decision"], first["understood"], first["text"]) == ("1", "confirm", "", "")
    assert (second["turn"], second["decision"], second["understood"]) == ("2", "answer", "s")
