"""Spike Task 0.4 (tạm thời, xóa cùng app/api/spike.py): chỉ gắn khi ENABLE_SPIKE_ENDPOINTS=1."""

import json
import sys

import pytest
from app.main import create_app
from fastapi.testclient import TestClient


@pytest.fixture
def spike_client(monkeypatch):
    monkeypatch.setenv("ENABLE_SPIKE_ENDPOINTS", "1")
    return TestClient(create_app())  # không vào lifespan: spike không cần DB/LLM


@pytest.mark.parametrize("value", [None, "", "0", "true"])
def test_not_mounted_unless_flag_is_exactly_1(monkeypatch, value):
    if value is None:
        monkeypatch.delenv("ENABLE_SPIKE_ENDPOINTS", raising=False)
    else:
        monkeypatch.setenv("ENABLE_SPIKE_ENDPOINTS", value)
    c = TestClient(create_app())
    assert c.get("/api/ping").status_code == 404
    assert c.get("/api/sse").status_code == 404


def test_ping_reports_path_facts(spike_client, monkeypatch):
    monkeypatch.setenv("VERCEL_REGION", "syd1")
    body = spike_client.get("/api/ping").json()
    assert body["ok"] is True
    assert body["path"] == "/api/ping" and body["raw_path"] == "/api/ping"
    assert body["root_path"] == ""
    assert body["vercel_region"] == "syd1"
    assert body["python"] == "%d.%d.%d" % sys.version_info[:3]
    assert set(body) == {
        "ok",
        "path",
        "root_path",
        "raw_path",
        "vercel_region",
        "python",
    }


def test_ping_region_null_when_unset(spike_client, monkeypatch):
    monkeypatch.delenv("VERCEL_REGION", raising=False)
    assert spike_client.get("/api/ping").json()["vercel_region"] is None


def _events(text):
    out = []
    for block in text.strip().split("\n\n"):
        ev = {"event": "message", "id": "", "data": ""}
        for line in block.split("\n"):
            k, _, v = line.partition(": ")
            ev[k] = v
        out.append(ev)
    return out


def test_sse_streams_n_events_in_order_then_done(spike_client):
    r = spike_client.get("/api/sse", params={"count": 5, "interval": 0.01})
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/event-stream")
    assert r.headers["cache-control"] == "no-cache, no-transform"
    assert r.headers["x-accel-buffering"] == "no"
    evs = _events(r.text)
    data, last = evs[:-1], evs[-1]
    assert [e["id"] for e in data] == ["1", "2", "3", "4", "5"]
    assert [json.loads(e["data"])["n"] for e in data] == [1, 2, 3, 4, 5]
    assert all(isinstance(json.loads(e["data"])["t"], float) for e in data)
    assert last["event"] == "done" and json.loads(last["data"]) == {"n": 5}


def test_sse_defaults_to_30_events(spike_client, monkeypatch):
    import app.api.spike as spike

    async def no_sleep(_):
        return None

    monkeypatch.setattr(spike.asyncio, "sleep", no_sleep)
    evs = _events(spike_client.get("/api/sse").text)
    assert len(evs) == 31 and evs[-1]["event"] == "done"


@pytest.mark.parametrize(
    "q", [{"count": 0}, {"count": 61}, {"interval": 0}, {"interval": 3}]
)
def test_sse_bounds_are_enforced(spike_client, q):
    assert spike_client.get("/api/sse", params=q).status_code == 422
