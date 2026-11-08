"""Validation app for the recommender (9.3) and the assistant (9.4): the Streamlit screen.

A graphical alternative to `scripts/uat_session.py` for the test sessions (rehearsal with colleagues and
professors, UAT with the pilot). It is a validation tool, not part of the product. All the logic is in
`validation_core.py`; this file only draws the screen and calls it. Roteiro: docs/recommender/9.3.2-4_Roteiro_UAT.md.

    uv sync --group validation
    uv run uvicorn hort_ia.api.main:app --port 8080            # in another terminal
    uv run --group validation streamlit run tools/validation_app.py
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path

import streamlit as st

import validation_core as core

OTHER_CITY = "Outra cidade (código IBGE)"
REGIONS = {"norte": "Norte", "nordeste": "Nordeste", "centro_oeste": "Centro-Oeste", "sudeste": "Sudeste",
           "sul": "Sul"}  # fmt: skip

st.set_page_config(page_title="Hort.IA · Validação", page_icon="🌱")
ss = st.session_state
ss.setdefault("api_url", core.DEFAULT_API)
ss.setdefault("history", [])


@dataclass
class Session:
    client: core.ApiClient
    out_dir: Path
    participant: str | None  # None while the code is invalid: nothing is recorded
    role: str
    keep_text: bool
    ibge_code: int | None
    small_space: bool


@st.cache_data
def crop_names() -> dict[str, str]:
    return core.load_crops()


@st.cache_data
def cv_labels() -> dict[str, str]:
    return core.load_cv_labels()


# --- sidebar ---------------------------------------------------------------------------------


def sidebar() -> Session:
    with st.sidebar:
        st.header("Sessão de teste")
        st.text_input("Endereço da API", key="api_url")
        client = core.ApiClient(ss.api_url)
        health = client.health()
        if health.ok:
            st.success("API ligada", icon="✅")
        else:
            st.error("API desligada ou fora do ar", icon="⛔")
            st.caption(health.error)

        session_type = st.radio("Tipo de sessão", list(core.SESSION_TYPES), key="session_type")
        out_dir = core.SESSION_TYPES[session_type]
        st.caption(f"Os resultados são gravados em `{out_dir}/`.")

        code = st.text_input("Código do participante", key="participant", placeholder="P01", max_chars=3).strip()
        error = core.participant_error(code)
        if error:
            (st.error if code else st.info)(error)
        role = st.selectbox("Papel", core.ROLES, key="role")
        keep_text = st.checkbox("Pode guardar as mensagens (sem nome)", key="consent")
        if not keep_text:
            st.caption("Sem essa marcação, o texto das mensagens não é gravado.")

        st.subheader("Horta")
        city = st.selectbox("Cidade", [*core.CITIES, OTHER_CITY], key="city")
        if city == OTHER_CITY:
            ibge_code = core.parse_ibge(st.text_input("Código IBGE da cidade", key="ibge_other", max_chars=7))
            if ibge_code is None:
                st.error("Digite o código IBGE com 7 números (ex.: 4106902).")
        else:
            ibge_code = core.CITIES[city]
        small_space = st.checkbox("Horta em vaso ou pouco espaço", key="small_space")

    return Session(client, out_dir, None if error else code, role, keep_text, ibge_code, small_space)


def ready(s: Session) -> bool:
    if s.participant is None:
        st.warning("Para começar, escreva o código do participante na barra lateral (P01, P02...). "
                   "Nada é gravado sem ele.")  # fmt: skip
        return False
    if s.ibge_code is None:
        st.warning("Escolha a cidade da horta na barra lateral.")
        return False
    return True


def sources_of(*groups: list[dict]) -> list[str]:
    return list(dict.fromkeys(r["source"] for group in groups for r in group if r.get("source")))


def show_sources(sources: list[str]) -> None:
    if sources:
        with st.expander("Fontes"):
            for source in sources:
                st.markdown(f"- {source}")


# --- tab "Recomendações" ---------------------------------------------------------------------


def rate(s: Session, rec: dict, item: dict, useful: bool) -> None:
    if item["rank"] in rec["rated"]:  # never the same row twice
        return
    comment = ss.get(f"comment_{rec['id']}_{item['rank']}", "")
    row = core.rec_row(participant=rec["participant"], role=s.role, ibge_code=rec["ibge_code"], result=rec["data"],
                       item=item, useful=useful, comment=comment)  # fmt: skip
    core.save_rating(rec["out_dir"], row)
    rec["rated"][item["rank"]] = useful


def recommendations_tab(s: Session) -> None:
    names = crop_names()
    with st.form("rec_form"):
        month = st.selectbox("Mês", range(1, 13), index=date.today().month - 1, key="month",
                             format_func=lambda m: core.MONTHS[m - 1].capitalize())  # fmt: skip
        planted = st.multiselect("Plantas que já estão na horta", list(names), format_func=names.get, key="planted",
                                 placeholder="Nenhuma")  # fmt: skip
        previous = st.selectbox("Planta que estava antes no canteiro", [None, *names], key="previous",
                                format_func=lambda c: "Não sei ou nenhuma" if c is None else names[c])  # fmt: skip
        submitted = st.form_submit_button("Ver recomendações", type="primary", key="rec_submit")

    if submitted:
        with st.spinner("Buscando recomendações..."):
            result = s.client.recommend(ibge_code=s.ibge_code, month=month, small_space=s.small_space,
                                        planted=planted, previous_crop=previous)  # fmt: skip
        ss.rec_id = ss.get("rec_id", 0) + 1  # new keys for the rating widgets of each request
        ss.rec_error = None if result.ok else (result.error, result.detail)
        ss.rec = None if not result.ok else {
            "id": ss.rec_id, "data": result.data, "latency_ms": result.latency_ms, "rated": {},
            "participant": s.participant, "out_dir": s.out_dir, "ibge_code": s.ibge_code,
        }  # fmt: skip

    if ss.get("rec_error"):
        st.error(ss.rec_error[0])
        st.caption(ss.rec_error[1])
    rec = ss.get("rec")
    if not rec or (rec["participant"], rec["out_dir"]) != (s.participant, s.out_dir):
        return  # another participant: ask again

    data = rec["data"]
    items = data["recommendations"][: core.TOP_N]
    region = REGIONS.get(data["region"], data["region"])
    st.caption(f"Região {region}, {core.MONTHS[data['month'] - 1]}. Resposta em {rec['latency_ms']:.0f} ms.")
    for warning in data["warnings"]:
        st.warning(warning)
    if not items:
        st.info("Nenhuma planta para essa horta neste mês.")
    else:
        st.progress(len(rec["rated"]) / len(items), text=f"{len(rec['rated'])} de {len(items)} avaliadas")

    for item in items:
        done = item["rank"] in rec["rated"]
        with st.container(border=True):
            st.subheader(f"{item['rank']}. {item['crop_name_pt']}")
            for reason in item["reasons"]:
                st.markdown(f"- {reason['text']}")
            for warning in item["warnings"]:
                st.warning(warning["text"], icon="⚠️")
            show_sources(sources_of(item["reasons"], item["warnings"]))
            key = f"{rec['id']}_{item['rank']}"
            st.text_input("Comentário (opcional)", key=f"comment_{key}", disabled=done)
            useful, not_useful = st.columns(2)
            useful.button("👍 Útil", key=f"useful_{key}", disabled=done, width="stretch",
                          on_click=rate, args=(s, rec, item, True))  # fmt: skip
            not_useful.button("👎 Não útil", key=f"not_useful_{key}", disabled=done, width="stretch",
                              on_click=rate, args=(s, rec, item, False))  # fmt: skip
            if done:
                st.success("Avaliada: útil." if rec["rated"][item["rank"]] else "Avaliada: não útil.")

    if data["excluded"]:
        with st.expander("Por que algumas plantas não aparecem"):
            for why, crops in core.explain_exclusions(data["excluded"], names):
                st.markdown(f"**{why}** {', '.join(crops)}.")


# --- tab "Assistente" ------------------------------------------------------------------------


def sync_conversation(s: Session) -> core.Conversation | None:
    """The conversation belongs to one participant: when the sidebar changes, its waiting turn is written."""
    conv: core.Conversation | None = ss.get("conv")
    if conv is not None and (conv.participant, conv.role, conv.out_dir) != (s.participant, s.role, s.out_dir):
        conv.flush()
        conv = ss.conv = None
        ss.history = []
    if conv is None and s.participant is not None:
        conv = ss.conv = core.Conversation(out_dir=s.out_dir, participant=s.participant, role=s.role)
    if conv is not None:
        conv.keep_text = s.keep_text
    return conv


def queue(text: str, cv_label: str | None = None) -> None:
    ss.outbox = (text, cv_label)


def mark(number: int, understood: str) -> None:
    conv: core.Conversation = ss.conv
    if conv.pending is not None and conv.pending.number == number:
        conv.flush(understood)


def new_conversation() -> None:
    ss.conv.reset()
    ss.history = []


def show_user(text: str) -> None:
    with st.chat_message("user"):
        if text.startswith(core.PHOTO_PREFIX):
            label = text.removeprefix(core.PHOTO_PREFIX)
            st.markdown(f"📷 Foto: {cv_labels().get(label, label)}")
        else:
            st.markdown(text)


def show_reply(entry: dict, last: bool) -> None:
    reply = entry["reply"]
    with st.chat_message("assistant"):
        st.markdown(reply["text"])
        if reply["handoff"]:
            st.warning("**Encaminhar para a Assistência Técnica.** Oriente a pessoa a procurar a Assistência "
                       "Técnica da horta para essa pergunta.", icon="🧑‍🌾")  # fmt: skip
        show_sources([{"source": source} for source in reply["sources"]])
        if ss.get("tech"):
            confidence = "—" if reply["confidence"] is None else f"{reply['confidence']:.2f}"
            st.caption(f"Decisão: {reply['decision']} · Intenção: {reply['intent']} · Confiança: {confidence} · "
                       f"Tempo: {entry['latency_ms']:.0f} ms")  # fmt: skip
        if last and reply["decision"] == "confirm":
            yes, no = st.columns(2)
            yes.button("Sim", key=f"confirm_yes_{entry['turn']}", width="stretch", on_click=queue, args=("sim",))
            no.button("Não", key=f"confirm_no_{entry['turn']}", width="stretch", on_click=queue, args=("não",))


def chat_tab(s: Session, conv: core.Conversation) -> None:
    if ss.get("warmed") != s.client.base_url:
        with st.spinner("Preparando o assistente..."):
            warm = s.client.warm_up()  # not recorded
        if not warm.ok:
            st.error(warm.error)
            return
        ss.warmed = s.client.base_url

    tech, new = st.columns(2)
    tech.toggle("Mostrar detalhes técnicos", key="tech")
    new.button("Nova conversa", on_click=new_conversation, width="stretch")

    box = st.container()  # the history goes above the input, filled after sending
    labels = cv_labels()
    with st.expander("Simular foto"):
        label = st.selectbox("O que a foto mostra (rótulo do modelo de visão)", [None, *labels], key="cv_label",
                             format_func=lambda x: "Escolha" if x is None else labels[x])  # fmt: skip
        st.button("📷 Enviar foto", disabled=label is None, on_click=queue, args=("", label))
    prompt = st.chat_input("Digite exatamente o que o participante disser", max_chars=500)

    outgoing = ss.pop("outbox", None) or ((prompt, None) if prompt else None)
    if outgoing:
        text, cv_label = outgoing
        with box, st.spinner("O assistente está respondendo..."):
            result = conv.send(s.client, text, ibge_code=s.ibge_code, small_space=s.small_space, cv_label=cv_label)
        ss.history.append({"role": "user", "text": core.PHOTO_PREFIX + cv_label if cv_label else text})
        if result.ok:
            ss.history.append({"role": "assistant", "reply": result.data, "latency_ms": result.latency_ms,
                               "turn": conv.turns})  # fmt: skip
        else:
            ss.history.append({"role": "error", "text": result.error, "detail": result.detail})

    with box:
        if not ss.history:
            st.info("Digite abaixo o que o participante disser, do jeito que ele falar. Não corrija os erros.")
        for i, entry in enumerate(ss.history):
            if entry["role"] == "user":
                show_user(entry["text"])
            elif entry["role"] == "error":
                st.error(entry["text"])
                st.caption(entry["detail"])
            else:
                show_reply(entry, last=i == len(ss.history) - 1)
        if conv.pending is not None:
            number = conv.pending.number
            with st.container(border=True):
                st.markdown("**Para o facilitador:** entendeu e saberia o que fazer sem ajuda?")
                yes, no, skip = st.columns(3)
                yes.button("Sim", key=f"understood_s_{number}", width="stretch", on_click=mark, args=(number, "s"))
                no.button("Não", key=f"understood_n_{number}", width="stretch", on_click=mark, args=(number, "n"))
                skip.button("Pular", key=f"understood_skip_{number}", width="stretch", on_click=mark,
                            args=(number, ""))  # fmt: skip


# --- page ------------------------------------------------------------------------------------

st.title("Hort.IA · Sessão de teste")
st.caption("Ferramenta de validação do módulo de IA. Não é o aplicativo final.")
session = sidebar()
conversation = sync_conversation(session)
rec_tab, assistant_tab = st.tabs(["Recomendações", "Assistente"], key="tab", on_change="rerun")
with rec_tab:
    if rec_tab.open and ready(session):
        recommendations_tab(session)
with assistant_tab:
    if assistant_tab.open and ready(session) and conversation is not None:
        chat_tab(session, conversation)
