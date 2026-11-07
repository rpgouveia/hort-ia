"""Response time of the assistant over slow connections (WBS 9.4.2-4).

Starts the API (uvicorn) and a throttling TCP proxy in front of it, then replays the reference messages
and conversations of 9.4.1-3 through the proxy under several network profiles, measuring the time a
client waits for each reply. The proxy adds the round-trip time (also to open each connection, like the
TCP handshake) and paces every byte at the profile's bandwidth, in both directions.

Usage: uv run python scripts/measure_slow_connection.py [--out docs/nlu/9.4.2-4_slow_connection_metrics.json]
Takes a few minutes: the slowest profile spends seconds per message by design.
"""

from __future__ import annotations

import argparse
import asyncio
import http.client
import json
import socket
import statistics
import subprocess
import sys
import threading
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Self


@dataclass(frozen=True)
class Profile:
    name: str
    rtt_ms: int
    down_kbps: int  # server -> client
    up_kbps: int  # client -> server


PROFILES = [  # assumptions of 9.4.2-4, section 2
    Profile("4G fraco", 150, 1600, 750),
    Profile("3G lento", 400, 400, 400),
    Profile("2G (EDGE)", 800, 100, 50),
    Profile("pior caso", 2000, 50, 25),
]
TARGET_S = 5.0  # criterion of 9.4: mean response time below 5 s
TLS_EXTRA_RTT = {"TLS 1.3": 1, "TLS 1.2": 2}  # extra round trips to open an HTTPS connection

PROFILE_BODY = {"ibge_code": 4106902, "month": 11}
SINGLE = [  # M1-M6 of 9.4.1-3
    "o que da pra plantar agora?", "quanto ta o tomate no ceasa?", "o que planto depois do repolho?",
    "da pra plantar cebolinha em vaso?", "minha couve ta com uns bichinho", "quanto custa o adubo?",
]  # fmt: skip
CONVERSATIONS = [  # C1-C8 of 9.4.1-3
    ["quando eu planto?", "alface"], ["quando planto mandioca?", "mandioca"], ["qndo plantar alfase?", "sim"],
    ["qual a epoca de plantar alface?", "e a rega dela?"], ["a alface ta amarelando", "sim"],
    ["tem como plantar morango aqui?", "não", "quando planto"], ["alface aguenta frio?"], ["como crio galinha?"],
]  # fmt: skip


# --- throttling proxy ------------------------------------------------------------------------


class ThrottlingProxy:
    def __init__(self, upstream_port: int, profile: Profile):
        self.upstream_port, self.profile = upstream_port, profile
        self.loop = asyncio.new_event_loop()
        self.port = free_port()
        self.server = None

    def __enter__(self) -> Self:
        ready = threading.Event()

        def run() -> None:
            asyncio.set_event_loop(self.loop)
            self.server = self.loop.run_until_complete(asyncio.start_server(self._handle, "127.0.0.1", self.port))
            ready.set()
            self.loop.run_forever()

        threading.Thread(target=run, daemon=True).start()
        ready.wait()
        return self

    def __exit__(self, *exc) -> None:
        asyncio.run_coroutine_threadsafe(self._shutdown(), self.loop).result(timeout=10)
        self.loop.call_soon_threadsafe(self.loop.stop)

    async def _shutdown(self) -> None:
        self.server.close()
        tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)

    async def _handle(self, client_reader, client_writer) -> None:
        await asyncio.sleep(self.profile.rtt_ms / 1000)  # connection set-up costs one round trip
        upstream_reader, upstream_writer = await asyncio.open_connection("127.0.0.1", self.upstream_port)
        await asyncio.gather(
            self._pipe(client_reader, upstream_writer, self.profile.up_kbps),
            self._pipe(upstream_reader, client_writer, self.profile.down_kbps),
            return_exceptions=True,
        )

    async def _pipe(self, reader, writer, kbps: int) -> None:
        loop, one_way = asyncio.get_running_loop(), self.profile.rtt_ms / 2000
        try:
            while data := await reader.read(4096):
                await asyncio.sleep(len(data) * 8 / (kbps * 1000))  # bandwidth: time to put the bytes on the wire
                loop.call_later(one_way, writer.write, data)  # latency: they arrive half a round trip later
            loop.call_later(one_way + 0.001, writer.close)
        except ConnectionError:
            writer.close()


# --- client --------------------------------------------------------------------------------------


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def post(conn_factory, path: str, payload: dict, conn=None) -> tuple[dict, float, int, int]:
    body = json.dumps(payload).encode("utf-8")
    start = time.perf_counter()
    conn = conn or conn_factory()
    conn.request("POST", path, body=body, headers={"Content-Type": "application/json"})
    response = conn.getresponse()
    data = response.read()
    elapsed = time.perf_counter() - start
    assert response.status == 200, data
    return json.loads(data), elapsed, len(body), len(data)


def run_turns(port: int, keep_alive: bool) -> list[dict]:
    def factory() -> http.client.HTTPConnection:
        return http.client.HTTPConnection("127.0.0.1", port, timeout=60)

    shared = factory() if keep_alive else None
    rows = []
    for conversation in [[m] for m in SINGLE] + CONVERSATIONS:
        context = None
        for text in conversation:
            payload = {"text": text, "context": context, **PROFILE_BODY}
            conn = shared
            if not keep_alive:
                conn = factory()
            reply, elapsed, sent, received = post(factory, "/nlp/message", payload, conn)
            if not keep_alive:
                conn.close()
            context = reply["context"]
            rows.append({"text": text, "decision": reply["decision"], "seconds": round(elapsed, 3),
                         "request_bytes": sent, "response_bytes": received})  # fmt: skip
    reply, elapsed, sent, received = post(factory, "/recommender/recommendations", PROFILE_BODY, shared)
    rows.append({"text": "POST /recommender/recommendations", "decision": "-", "seconds": round(elapsed, 3),
                 "request_bytes": sent, "response_bytes": received})  # fmt: skip
    if shared:
        shared.close()
    return rows


# --- server --------------------------------------------------------------------------------------


def start_api() -> tuple[subprocess.Popen, int]:
    port = free_port()
    command = [sys.executable, "-m", "uvicorn", "hort_ia.api.main:app", "--port", str(port), "--log-level", "warning"]
    process = subprocess.Popen(command)
    for _ in range(300):
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.2):
                return process, port
        except OSError:
            time.sleep(0.1)
    process.kill()
    raise SystemExit("the API did not start")


def summarize(rows: list[dict], profile: Profile, new_connection: bool) -> dict:
    chat = [r["seconds"] for r in rows if r["decision"] != "-"]
    summary = {
        "mean_s": round(statistics.mean(chat), 3),
        "max_s": round(max(chat), 3),
        "turns": len(chat),
        "max_response_bytes": max(r["response_bytes"] for r in rows if r["decision"] != "-"),
        "recommendations_s": rows[-1]["seconds"],
    }
    # HTTPS is not simulated: opening a connection costs TLS_EXTRA_RTT more round trips. Without
    # keep-alive every message pays it; with keep-alive it is paid once and spread over the turns.
    rtt, share = profile.rtt_ms / 1000, 1 if new_connection else 1 / len(chat)
    summary["mean_with_https_s"] = {
        name: round(summary["mean_s"] + extra * rtt * share, 3) for name, extra in TLS_EXTRA_RTT.items()
    }
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, default=Path("docs/nlu/9.4.2-4_slow_connection_metrics.json"))
    args = parser.parse_args()

    process, api_port = start_api()
    results = {"target_s": TARGET_S, "profiles": {}}
    try:
        # Cold start: the first message trains the intent classifier (about 0.1 s) on the slowest real profile.
        with ThrottlingProxy(api_port, PROFILES[2]) as proxy:
            _, cold, _, _ = post(lambda: http.client.HTTPConnection("127.0.0.1", proxy.port, timeout=60),
                                 "/nlp/message", {"text": "oi", **PROFILE_BODY})  # fmt: skip
        results["cold_start_s"] = {"profile": PROFILES[2].name, "seconds": round(cold, 3)}

        direct = run_turns(api_port, keep_alive=True)  # no proxy: the server's own time
        results["no_network"] = {"mean_s": round(statistics.mean(r["seconds"] for r in direct), 4)}
        for profile in PROFILES:
            entry = {"profile": asdict(profile)}
            for mode, keep_alive in (("new_connection", False), ("keep_alive", True)):
                with ThrottlingProxy(api_port, profile) as proxy:
                    rows = run_turns(proxy.port, keep_alive)
                entry[mode] = summarize(rows, profile, new_connection=not keep_alive)
                worst = entry[mode]["mean_with_https_s"]["TLS 1.2"]
                status = "OK" if worst < TARGET_S else "ABOVE TARGET"
                print(f"{profile.name:<10} {mode:<15} mean {entry[mode]['mean_s']:6.2f} s  "
                      f"(HTTPS {worst:5.2f} s)  max {entry[mode]['max_s']:6.2f} s  {status}", flush=True)  # fmt: skip
            results["profiles"][profile.name] = entry
        results["turns"] = [{k: r[k] for k in ("text", "request_bytes", "response_bytes")} for r in direct]
    finally:
        process.terminate()
        process.wait(timeout=10)

    args.out.write_text(json.dumps(results, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"\nCold start ({results['cold_start_s']['profile']}): {results['cold_start_s']['seconds']} s")
    print(f"Server only: {results['no_network']['mean_s'] * 1000:.1f} ms per turn")
    print(f"Written to {args.out}")


if __name__ == "__main__":
    main()
