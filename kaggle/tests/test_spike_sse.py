import json

import pytest
from fastapi.testclient import TestClient

import spike_sse

KEY = "secret"
AUTH = {"Authorization": f"Bearer {KEY}"}


@pytest.fixture
def client():
    return TestClient(spike_sse.create_app(KEY, count=5, interval=0.01))


def parse(body: str):
    return [
        dict(ln.split(": ", 1) for ln in blk.splitlines())
        for blk in body.strip().split("\n\n")
    ]


def test_stream_requires_bearer(client):
    for headers in ({}, {"Authorization": "Bearer nope"}, {"Authorization": KEY}):
        r = client.get("/stream", headers=headers)
        assert r.status_code == 401
        assert "detail" in r.json()


def test_health_is_open(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"ok": True}


def test_stream_events_in_order_then_done(client):
    r = client.get("/stream", headers=AUTH)
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/event-stream")
    assert r.headers["cache-control"] == "no-cache, no-transform"
    assert r.headers["x-accel-buffering"] == "no"
    events = parse(r.text)
    data = events[:-1]
    assert [e["id"] for e in data] == ["1", "2", "3", "4", "5"]
    payloads = [json.loads(e["data"]) for e in data]
    assert [p["n"] for p in payloads] == [1, 2, 3, 4, 5]
    assert all(isinstance(p["t"], float) for p in payloads)
    assert payloads == sorted(payloads, key=lambda p: p["t"])
    assert events[-1]["event"] == "done"
    assert json.loads(events[-1]["data"]) == {"n": 5}


def test_empty_token_rejected():
    with pytest.raises(ValueError):
        spike_sse.create_app("")


@pytest.mark.parametrize("minutes", [0, -1, 31])
def test_duration_out_of_range(minutes):
    with pytest.raises(SystemExit):
        spike_sse.parse_args(["--duration-min", str(minutes)])


def test_duration_default_and_max():
    assert spike_sse.parse_args([]).duration_min == 10
    assert spike_sse.parse_args(["--duration-min", "30"]).duration_min == 30


# ---- ngrok authtoken must never reach the cell log (pyngrok puts argv, i.e. the token, in CalledProcessError) ----

SECRET = "SECRET-TOKEN-123"


def _fake_pyngrok(monkeypatch, *, fail_on, kill_fails=False, msg=None):
    import subprocess
    import sys
    import types

    def boom(*a, **k):
        raise (
            subprocess.CalledProcessError(
                1, ["ngrok", "config", "add-authtoken", SECRET]
            )
            if msg is None
            else RuntimeError(msg)
        )

    def kill():
        if kill_fails:
            raise subprocess.CalledProcessError(1, ["ngrok", "kill", SECRET])

    ng = types.SimpleNamespace(
        set_auth_token=boom if fail_on == "auth" else lambda t: None,
        connect=boom if fail_on == "connect" else lambda *a, **k: None,
        kill=kill,
    )
    mod = types.ModuleType("pyngrok")
    mod.ngrok = ng
    monkeypatch.setitem(sys.modules, "pyngrok", mod)


@pytest.mark.parametrize("fail_on", ["auth", "connect"])
def test_open_tunnel_never_prints_authtoken(monkeypatch, capsys, fail_on):
    _fake_pyngrok(monkeypatch, fail_on=fail_on, kill_fails=True)
    with pytest.raises(SystemExit) as ei:
        spike_sse.open_tunnel(8000, "x.ngrok-free.dev", SECRET)
    assert ei.value.code not in (0, None)
    assert ei.value.__cause__ is None and ei.value.__suppress_context__
    out = capsys.readouterr()
    assert SECRET not in out.out + out.err
    assert "CalledProcessError" in out.out


def test_open_tunnel_reports_ngrok_code_redacted(monkeypatch, capsys):
    _fake_pyngrok(
        monkeypatch, fail_on="connect", msg=f"{SECRET} ERR_NGROK_334 already online"
    )
    with pytest.raises(SystemExit):
        spike_sse.open_tunnel(8000, "x.ngrok-free.dev", SECRET)
    out = capsys.readouterr().out
    assert "ERR_NGROK_334" in out and SECRET not in out


def test_main_exits_nonzero_without_leaking(monkeypatch, capsys):
    import sys
    import types

    class FakeServer:
        started = True
        should_exit = False

        def __init__(self, config):
            pass

        def run(self):
            pass

    fake = types.ModuleType("uvicorn")
    fake.Config = lambda *a, **k: None
    fake.Server = FakeServer
    monkeypatch.setitem(sys.modules, "uvicorn", fake)
    _fake_pyngrok(monkeypatch, fail_on="auth")
    monkeypatch.setenv("GATEWAY_API_KEY", "gw")
    monkeypatch.setenv("NGROK_AUTHTOKEN", SECRET)
    monkeypatch.setenv("NGROK_DOMAIN", "x.ngrok-free.dev")
    with pytest.raises(SystemExit) as ei:
        spike_sse.main([])
    assert ei.value.code not in (0, None)
    out = capsys.readouterr()
    assert SECRET not in out.out + out.err
