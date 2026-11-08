"""Core of the validation app (tools/validation_core.py): CSV compatibility with scripts/uat_session.py,
participant code, consent, and the HTTP client against the real API in process (no server)."""

import argparse
import csv
import json

import pytest
from starlette.testclient import TestClient

import validation_core as core
import uat_session  # importable once validation_core has put scripts/ on the path

from hort_ia.api.main import app

PROFILE = {"participant": "P01", "role": "agricultor"}


@pytest.fixture(scope="module")
def api() -> TestClient:
    with TestClient(app) as client:  # runs the lifespan, like uvicorn
        yield client


@pytest.fixture
def sent() -> list[dict]:
    return []  # JSON bodies the client sent, to check what goes over the wire


@pytest.fixture
def client(api: TestClient, sent: list[dict]) -> core.ApiClient:
    def transport(method: str, url: str, body: bytes | None, timeout: float) -> tuple[int, bytes]:
        if body is not None:
            sent.append(json.loads(body))
        response = api.request(method, url, content=body, headers={"Content-Type": "application/json"})
        return response.status_code, response.content

    return core.ApiClient("http://testserver", transport=transport)


def header(path) -> list[str]:
    with path.open(encoding="utf-8") as f:
        return next(csv.reader(f))


def rows(path) -> list[dict]:
    with path.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


# --- one source of truth with the script ----------------------------------------------------


def test_columns_roles_and_top_n_are_the_scripts():
    assert core.REC_FIELDS is uat_session.REC_FIELDS
    assert core.CHAT_FIELDS is uat_session.CHAT_FIELDS
    assert core.ROLES is uat_session.ROLES
    assert core.TOP_N == uat_session.TOP_N == 5


def test_summary_reads_the_csv_written_by_the_core(tmp_path, client, capsys):
    result = client.recommend(ibge_code=4106902, month=11, small_space=True, planted=["tomate"], previous_crop=None)
    first, second = result.data["recommendations"][:2]
    for item, useful in ((first, True), (second, False)):
        core.save_rating(tmp_path, core.rec_row(**PROFILE, ibge_code=4106902, result=result.data, item=item,
                                                useful=useful, comment="ok"))  # fmt: skip
    conversation = core.Conversation(out_dir=tmp_path, keep_text=True, **PROFILE)
    conversation.send(client, "como cuido da minha horta de alface?", ibge_code=4106902, small_space=False)
    conversation.flush("s")

    assert header(tmp_path / "recommendations.csv") == uat_session.REC_FIELDS
    assert header(tmp_path / "chat.csv") == uat_session.CHAT_FIELDS
    uat_session.summary(argparse.Namespace(out=tmp_path))
    out = capsys.readouterr().out
    assert "Recomendações: 1 de 2 úteis (50%)" in out
    assert "P01: 1 de 2" in out
    assert "Assistente: 1 turnos de 1 participantes." in out
    assert "Entendeu e saberia agir: 1 de 1 (100%)." in out


def test_output_folder_by_session_type():
    assert core.SESSION_TYPES["Ensaio (colegas e professores)"].as_posix() == "uat_results/ensaio"
    assert core.SESSION_TYPES["UAT (piloto)"].as_posix() == "uat_results"


# --- participant code and consent ------------------------------------------------------------


@pytest.mark.parametrize("code", ["P01", "P10", "P99"])
def test_participant_code_accepted(code):
    assert core.participant_error(code) is None


@pytest.mark.parametrize("code", ["", "   ", None, "P1", "P001", "p01", "01", "Maria", "Maria P01", "PAB"])
def test_participant_code_rejected_and_says_names_are_not_recorded(code):
    error = core.participant_error(code)
    assert error is not None
    assert "nome não é registrado" in error


def test_without_consent_the_text_is_empty(tmp_path, client):
    conversation = core.Conversation(out_dir=tmp_path, keep_text=False, **PROFILE)
    conversation.send(client, "quando eu planto alface?", ibge_code=4106902, small_space=False)
    conversation.flush("s")
    (row,) = rows(tmp_path / "chat.csv")
    assert row["text"] == ""
    assert row["intent"] == "planting_time"


def test_consent_is_read_when_the_row_is_written(tmp_path, client):
    conversation = core.Conversation(out_dir=tmp_path, keep_text=True, **PROFILE)
    conversation.send(client, "quando eu planto alface?", ibge_code=4106902, small_space=False)
    conversation.keep_text = False  # withdrawn before the facilitator marked the turn
    conversation.flush("n")
    assert rows(tmp_path / "chat.csv")[0]["text"] == ""


# --- client against the real API ---------------------------------------------------------------


def test_health(client):
    result = client.health()
    assert result.ok
    assert result.data["status"] == "ok"


def test_two_turn_conversation_sends_the_context_back_unchanged(tmp_path, client, sent):
    conversation = core.Conversation(out_dir=tmp_path, keep_text=True, **PROFILE)

    first = conversation.send(client, "quando eu planto?", ibge_code=4106902, small_space=False)
    assert first.ok, first.detail
    assert first.data["decision"] == "ask"
    assert first.data["missing_entity"] == "crop"
    assert sent[-1]["context"] is None

    second = conversation.send(client, "alface", ibge_code=4106902, small_space=False)
    assert second.ok, second.detail
    assert sent[-1]["context"] == first.data["context"]
    assert second.data["decision"] == "answer"
    assert second.data["entities"]["crop"] == "alface"
    assert "Alface" in second.data["text"]
    assert second.data["sources"]
    assert second.latency_ms > 0

    conversation.flush("s")
    first_row, second_row = rows(tmp_path / "chat.csv")
    assert (first_row["turn"], first_row["understood"], first_row["text"]) == ("1", "", "quando eu planto?")
    assert (second_row["turn"], second_row["understood"], second_row["decision"]) == ("2", "s", "answer")
    assert second_row["confidence"] == ""  # read as the answer to a pending question


def test_a_turn_is_never_written_twice(tmp_path, client):
    conversation = core.Conversation(out_dir=tmp_path, **PROFILE)
    conversation.send(client, "oi", ibge_code=4106902, small_space=False)
    assert conversation.flush("s") is True
    assert conversation.flush("n") is False
    conversation.reset()
    assert len(rows(tmp_path / "chat.csv")) == 1


def test_new_conversation_writes_the_waiting_turn_and_clears_the_context(tmp_path, client, sent):
    conversation = core.Conversation(out_dir=tmp_path, **PROFILE)
    conversation.send(client, "quando eu planto?", ibge_code=4106902, small_space=False)
    conversation.reset()
    assert (conversation.context, conversation.turns, conversation.pending) == (None, 0, None)
    assert len(rows(tmp_path / "chat.csv")) == 1
    conversation.send(client, "alface", ibge_code=4106902, small_space=False)
    assert sent[-1]["context"] is None


@pytest.mark.parametrize("how", ["button", "shortcut"])
def test_photo_sends_the_cv_label_and_records_it_like_the_script(tmp_path, client, sent, how):
    conversation = core.Conversation(out_dir=tmp_path, keep_text=True, **PROFILE)
    if how == "button":
        result = conversation.send(client, "", cv_label="Tomato___Early_blight", ibge_code=4106902, small_space=False)
    else:
        result = conversation.send(client, "/foto Tomato___Early_blight", ibge_code=4106902, small_space=False)
    assert result.ok, result.detail
    assert sent[-1]["cv_label"] == "Tomato___Early_blight"
    assert sent[-1]["text"] == "foto"
    assert "Pinta-preta" in result.data["text"]
    conversation.flush()
    assert rows(tmp_path / "chat.csv")[0]["text"] == "/foto Tomato___Early_blight"


def test_recommendations_r2_profile(client):
    result = client.recommend(ibge_code=4106902, month=11, small_space=True, planted=["tomate"], previous_crop=None)
    assert result.ok, result.detail
    top = [item["crop_id"] for item in result.data["recommendations"][: core.TOP_N]]
    assert top[:4] == ["manjericao", "cebolinha", "pimentao", "alface"]
    assert all(item["reasons"] and item["reasons"][0]["source"] for item in result.data["recommendations"])
    explained = dict(core.explain_exclusions(result.data["excluded"], core.load_crops()))
    assert "Tomate" in explained["Já está na sua horta."]


def test_recommendation_row_has_the_scripts_values(client):
    result = client.recommend(ibge_code=4106902, month=11, small_space=True, planted=["tomate"], previous_crop=None)
    item = result.data["recommendations"][0]
    row = core.rec_row(**PROFILE, ibge_code=4106902, result=result.data, item=item, useful=False, comment=" longe ")
    assert list(row) == core.REC_FIELDS
    assert (row["useful"], row["comment"], row["model_version"], row["month"]) == ("n", "longe", "1.0.0", 11)


# --- errors become messages, not exceptions ------------------------------------------------------


def test_invalid_ibge_code_422_is_a_friendly_message(client):
    result = client.recommend(ibge_code=9999999, month=11, small_space=False, planted=[], previous_crop=None)
    assert not result.ok
    assert result.data is None
    assert "código da cidade" in result.error
    assert "IBGE" in result.detail


def test_validation_422_is_a_friendly_message(client):
    result = client.message("x" * 501, ibge_code=4106902, small_space=False)
    assert not result.ok
    assert result.error.startswith("A API não aceitou os dados")


def test_failed_turn_is_not_recorded(tmp_path, client):
    conversation = core.Conversation(out_dir=tmp_path, **PROFILE)
    result = conversation.send(client, "oi", ibge_code=9999999, small_space=False)
    assert not result.ok
    assert conversation.pending is None
    assert not (tmp_path / "chat.csv").exists()


def test_api_down_is_a_friendly_message():
    def refused(method, url, body, timeout):
        raise ConnectionRefusedError(111, "Connection refused")

    result = core.ApiClient("http://localhost:1", transport=refused).health()
    assert not result.ok
    assert "Não consegui falar com a API" in result.error


def test_real_urllib_transport_when_nothing_listens():
    result = core.ApiClient("http://127.0.0.1:9", timeout=2).health()  # discard port: nothing listens
    assert not result.ok


# --- form helpers ------------------------------------------------------------------------------


def test_form_lists_come_from_the_knowledge_base():
    crops = core.load_crops()
    assert len(crops) == 15
    assert crops["manjericao"] == "Manjericão"
    labels = core.load_cv_labels()
    assert labels["Tomato___Early_blight"] == "Pinta-preta (Tomato___Early_blight)"
    assert labels["Strawberry___Leaf_scorch"] == "Strawberry___Leaf_scorch"  # no Portuguese name in the base


@pytest.mark.parametrize(("text", "expected"), [("4106902", 4106902), (" 41 ", 41), ("", None), ("41069", None),
                                                ("abc", None), (None, None)])  # fmt: skip
def test_parse_ibge(text, expected):
    assert core.parse_ibge(text) == expected
