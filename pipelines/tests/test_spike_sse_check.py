"""Tests for scripts/spike_sse_check.py (same precedent as test_migration_guard.py: scripts are tested from here)."""

import importlib.util
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

_spec = importlib.util.spec_from_file_location(
    "spike_sse_check",
    Path(__file__).parents[2] / "scripts" / "spike_sse_check.py",
)
chk = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(chk)

KEY = "k-test"


def steady(n=10, gap=1.0):
    return [(i * gap, i + 1) for i in range(n)]


def test_evaluate_steady_stream_passes():
    fails, st = chk.evaluate(steady(), done=True, cut=None, expect=10, interval=1.0)
    assert fails == []
    assert st["clumped"] == 0 and st["p95"] == pytest.approx(1.0)


def test_evaluate_cut_fails():
    fails, _ = chk.evaluate(
        steady(5), done=False, cut="read timeout", expect=10, interval=1.0
    )
    assert any("5/10" in f for f in fails) and any("cut" in f for f in fails)


def test_evaluate_clump_fails():
    ev = [(0.0 + i * 0.001, i + 1) for i in range(10)]  # all in 9 ms
    fails, st = chk.evaluate(ev, done=True, cut=None, expect=10, interval=1.0)
    assert st["clumped"] == 9
    assert any("clump" in f for f in fails) and any("p95" in f for f in fails)


def test_evaluate_few_clumped_is_tolerated():
    ev = steady(10)
    ev[5] = (ev[4][0] + 0.01, 6)  # one burst after a stall is below MAX_CLUMPED
    fails, _ = chk.evaluate(ev, done=True, cut=None, expect=10, interval=1.0)
    assert not any("clump" in f for f in fails)


def test_evaluate_missing_and_out_of_order():
    ev = steady(10)
    del ev[3]
    fails, _ = chk.evaluate(ev, done=True, cut=None, expect=10, interval=1.0)
    assert any("order" in f or "gap" in f for f in fails)


def test_evaluate_long_stall_fails():
    ev = [(t + (6.0 if n > 5 else 0), n) for t, n in steady(10)]
    fails, st = chk.evaluate(ev, done=True, cut=None, expect=10, interval=1.0)
    assert st["longest"] > 6 and any("stall" in f for f in fails)


def test_evaluate_missing_done_fails():
    fails, _ = chk.evaluate(steady(), done=False, cut=None, expect=10, interval=1.0)
    assert any("done" in f for f in fails)


def test_mask_url():
    assert chk.mask_url("https://abc-def.ngrok-free.dev/stream") == (
        "https://abc***.ngrok-free.dev"
    )
    assert chk.mask_url("http://127.0.0.1:8000/stream") == "http://127.0.0.1:8000"


def test_parse_sse_incremental():
    lines = [
        b"id: 1\n",
        b'data: {"n": 1, "t": 1.5}\n',
        b"\n",
        b": comment\n",
        b"event: done\n",
        b'data: {"n": 1}\n',
        b"\n",
    ]
    evs = list(chk.parse_sse(iter(lines)))
    assert [(e["event"], e["data"]) for e in evs] == [
        ("message", '{"n": 1, "t": 1.5}'),
        ("done", '{"n": 1}'),
    ]


# ---- in-process fake servers (localhost only) ----


def make_handler(mode, count, interval):
    class H(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.0"  # body ends at connection close

        def log_message(self, *a):
            pass

        def do_GET(self):
            authed = self.headers.get("Authorization") == f"Bearer {KEY}"
            if not authed and mode != "open":
                body = b'{"detail": "unauthorized"}'
                self.send_response(401)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache, no-transform")
            self.end_headers()
            n_send = 4 if mode == "cut" else count
            for n in range(1, n_send + 1):
                msg = f"id: {n}\ndata: {json.dumps({'n': n, 't': time.time()})}\n\n"
                self.wfile.write(msg.encode())
                self.wfile.flush()
                if mode != "clump":
                    time.sleep(interval)
            if mode != "cut":
                self.wfile.write(f'event: done\ndata: {{"n": {count}}}\n\n'.encode())
                self.wfile.flush()

    return H


@pytest.fixture
def serve(monkeypatch):
    monkeypatch.setenv("TEST_TOKEN", KEY)
    servers = []

    def start(mode, count=10, interval=0.1):
        srv = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(mode, count, interval))
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        servers.append(srv)
        return f"http://127.0.0.1:{srv.server_port}/stream"

    yield start
    for s in servers:
        s.shutdown()


def run(url, capsys, expect=10, interval=0.1):
    code = chk.main(
        [
            "--url",
            url,
            "--token-env",
            "TEST_TOKEN",
            "--expect",
            str(expect),
            "--interval",
            str(interval),
        ]
    )
    return code, capsys.readouterr().out


def test_main_pass(serve, capsys):
    code, out = run(serve("ok"), capsys)
    assert code == 0, out
    assert "verdict: PASS" in out and KEY not in out


def test_main_cut_at_4_fails(serve, capsys):
    code, out = run(serve("cut"), capsys)
    assert code == 1 and "verdict: FAIL" in out and "4/10" in out


def test_main_clump_fails(serve, capsys):
    code, out = run(serve("clump"), capsys)
    assert code == 1 and "clump" in out


def test_main_missing_401_fails(serve, capsys):
    code, out = run(serve("open"), capsys)
    assert code == 1 and "401" in out and "verdict: FAIL" in out


def test_main_usage_and_connection_errors(monkeypatch, capsys):
    monkeypatch.delenv("TEST_TOKEN", raising=False)
    assert (
        chk.main(["--url", "http://127.0.0.1:9/stream", "--token-env", "TEST_TOKEN"])
        == 2
    )
    monkeypatch.setenv("TEST_TOKEN", KEY)
    assert (
        chk.main(["--url", "http://127.0.0.1:9/stream", "--token-env", "TEST_TOKEN"])
        == 2
    )
