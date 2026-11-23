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
