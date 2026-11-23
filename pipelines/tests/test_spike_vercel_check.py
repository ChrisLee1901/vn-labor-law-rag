"""Tests for scripts/spike_vercel_check.py (same precedent as test_spike_sse_check.py)."""

import importlib.util
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

_spec = importlib.util.spec_from_file_location(
    "spike_vercel_check",
    Path(__file__).parents[2] / "scripts" / "spike_vercel_check.py",
)
chk = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(chk)

SECRET = "bypass-secret-xyz"
NEXT_HTML = (
    b"<html><head><title>Tro ly</title></head>"
    b'<body><div id="__next"></div><script src="/_next/a.js"></script></body></html>'
)
PROTECTION_HTML = b"<html><title>Authentication Required</title><body>Authentication Required</body></html>"


def make_handler(mode, count, interval):
    class H(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.0"  # body ends at connection close

        def log_message(self, *a):
            pass

        def reply(self, status, ctype, body, extra=()):
            self.send_response(status)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Server", "Vercel")
            self.send_header("X-Vercel-Id", "sin1::sin1::abc-123")
            for k, v in extra:
                self.send_header(k, v)
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if mode == "protected" or (
                mode == "bypass_needed"
                and self.headers.get("x-vercel-protection-bypass") != SECRET
            ):
                return self.reply(401, "text/html", PROTECTION_HTML)
            if mode == "protected_redirect":
                return self.reply(
                    307,
                    "text/plain",
                    b"",
                    [("Location", "https://vercel.com/sso-api?x=1")],
                )
            if self.path == "/":
                return self.reply(200, "text/html", NEXT_HTML)
            if self.path == "/api/ping":
                if mode == "wrong_path":  # routed to Next.js
                    return self.reply(404, "text/html", b"<html>404</html>")
                if mode == "flag_off":  # FastAPI answers, no such route
                    body = json.dumps({"detail": "Khong tim thay."}).encode()
                    return self.reply(404, "application/json", body)
                path = "/ping" if mode == "stripped" else "/api/ping"
                body = json.dumps(
                    {
                        "ok": True,
                        "path": path,
                        "root_path": "",
                        "raw_path": path,
                        "vercel_region": "iad1" if mode == "region" else "sin1",
                        "python": "3.12.1",
                    }
                ).encode()
                return self.reply(200, "application/json", body)
            if self.path == "/api/sse":
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.send_header("Cache-Control", "no-cache, no-transform")
                self.end_headers()
                n_send = 3 if mode == "cut" else count
                for n in range(1, n_send + 1):
                    msg = f"id: {n}\ndata: {json.dumps({'n': n, 't': time.time()})}\n\n"
                    self.wfile.write(msg.encode())
                    self.wfile.flush()
                    if mode != "clump":
                        time.sleep(interval)
                if mode != "cut":
                    self.wfile.write(
                        f'event: done\ndata: {{"n": {count}}}\n\n'.encode()
                    )
                return
            self.reply(404, "text/plain", b"x")

    return H


@pytest.fixture
def serve():
    servers = []

    def start(mode="ok", count=8, interval=0.25):
        srv = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(mode, count, interval))
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        servers.append(srv)
        return f"http://127.0.0.1:{srv.server_port}"

    yield start
    for s in servers:
        s.shutdown()


@pytest.fixture(autouse=True)
def _loose_timing(monkeypatch):
    # real sockets on a loaded box: widen the timing limits of the shared evaluate() (its own tests stay strict)
    monkeypatch.setattr(chk.sse, "P95_MAX_FACTOR", 8.0)
    monkeypatch.setattr(chk.sse, "MAX_GAP_FACTOR", 20.0)


def run(url, capsys, *extra):
    code = chk.main(["--url", url, "--expect", "8", "--interval", "0.25", *extra])
    return code, capsys.readouterr().out


def test_pass_and_facts(serve, capsys):
    code, out = run(serve("ok"), capsys)
    assert code == 0, out
    assert "verdict: PASS" in out and "events: 8/8" in out
    assert "fastapi_sees_api_prefix: True" in out
    assert "function_region: 'sin1' (expected 'sin1': match)" in out
    assert "x_vercel_id_regions: /=sin1,sin1;" in out
    assert "x-vercel-id=sin1::sin1::abc-123" in out and "server=" in out


def test_protection_page_gives_bypass_hint(serve, capsys):
    code, out = run(serve("protected"), capsys)
    assert code == 1 and "protection: BLOCKED" in out
    assert "--bypass-env" in out and "x-vercel-protection-bypass" in out
    assert "ping:" not in out  # nothing else is checked behind the wall


def test_protection_redirect_to_vercel_sso(serve, capsys):
    code, out = run(serve("protected_redirect"), capsys)
    assert code == 1 and "protection: BLOCKED" in out


def test_bypass_secret_used_and_never_printed(serve, capsys, monkeypatch):
    monkeypatch.setenv("TEST_BYPASS", SECRET)
    code, out = run(serve("bypass_needed"), capsys, "--bypass-env", "TEST_BYPASS")
    assert code == 0, out
    assert "bypass header sent" in out and SECRET not in out


def test_wrong_bypass_secret_is_reported(serve, capsys, monkeypatch):
    monkeypatch.setenv("TEST_BYPASS", "nope")
    code, out = run(serve("bypass_needed"), capsys, "--bypass-env", "TEST_BYPASS")
    assert code == 1 and "rejected" in out and "nope" not in out


def test_ping_routed_to_nextjs_is_diagnosed(serve, capsys):
    code, out = run(serve("wrong_path"), capsys)
    assert code == 1 and "went to Next.js" in out


def test_ping_flag_off_is_diagnosed(serve, capsys):
    code, out = run(serve("flag_off"), capsys)
    assert code == 1 and "ENABLE_SPIKE_ENDPOINTS" in out


def test_prefix_stripped_fails(serve, capsys):
    code, out = run(serve("stripped"), capsys)
    assert code == 1 and "saw path '/ping'" in out
    assert "fastapi_sees_api_prefix: False" in out


def test_other_region_is_info_not_failure(serve, capsys):
    code, out = run(serve("region"), capsys)
    assert code == 0, out
    assert "NO MATCH" in out and "INFO:" in out and "'iad1'" in out


def test_sse_clump_and_cut_fail(serve, capsys):
    code, out = run(serve("clump"), capsys)
    assert code == 1 and "clump" in out
    code, out = run(serve("cut"), capsys)
    assert code == 1 and "3/8" in out


def test_check_root_rejects_non_next_html():
    ok = {"content-type": "text/html; charset=utf-8"}
    assert chk.check_root(200, ok, "<html><title>x</title></html>")
    assert chk.check_root(200, ok, "<title>x</title><div id='__next'>") == []
    assert chk.check_root(500, ok, "")


def test_region_codes():
    assert chk.region_codes("sin1::iad1::abc-123") == ["sin1", "iad1"]
    assert chk.region_codes("abc-123") == []
    assert chk.region_codes("") == []


def test_usage_and_connection_errors(monkeypatch):
    assert chk.main(["--url", "ftp://x"]) == 2
    monkeypatch.delenv("TEST_BYPASS", raising=False)
    assert chk.main(["--url", "http://127.0.0.1:9", "--bypass-env", "TEST_BYPASS"]) == 2
    assert chk.main(["--url", "http://127.0.0.1:9"]) == 2
