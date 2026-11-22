import json
import logging

import httpx
import pytest
import respx
from app import ratelimit
from app.config import Settings
from starlette.requests import Request

URL = "https://fake.upstash.io"
S = Settings(UPSTASH_REDIS_REST_URL=URL, UPSTASH_REDIS_REST_TOKEN="tok", _env_file=None)


class Counter:
    """Emulates Upstash /pipeline: INCR returns the running count per key."""

    def __init__(self):
        self.counts: dict[str, int] = {}
        self.bodies: list[str] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.bodies.append(request.content.decode())
        out = []
        for cmd in json.loads(request.content):
            if cmd[0] == "INCR":
                self.counts[cmd[1]] = self.counts.get(cmd[1], 0) + 1
                out.append({"result": self.counts[cmd[1]]})
            else:
                out.append({"result": 1})
        return httpx.Response(200, json=out)


@pytest.fixture
def up():
    with respx.mock:
        c = Counter()
        route = respx.post(f"{URL}/pipeline").mock(side_effect=c)
        c.route = route
        yield c


async def test_21st_request_in_window_blocked(up):
    res = [await ratelimit.check("1.2.3.4", settings=S, now=1000.0) for _ in range(21)]
    assert res[:20] == [True] * 20 and res[20] is False
    assert up.route.calls.last.request.headers["authorization"] == "Bearer tok"


async def test_other_ip_unaffected(up):
    for _ in range(21):
        await ratelimit.check("1.2.3.4", settings=S, now=1000.0)
    assert await ratelimit.check("5.6.7.8", settings=S, now=1000.0) is True


async def test_window_rollover_resets(up):
    for _ in range(21):
        await ratelimit.check("1.2.3.4", settings=S, now=1000.0)
    assert await ratelimit.check("1.2.3.4", settings=S, now=1000.0 + 600) is True


async def test_global_cap(up):
    async with httpx.AsyncClient() as c:  # one client: building 300 is slow
        for i in range(300):
            assert await ratelimit.check(f"10.0.{i // 250}.{i % 250}", settings=S, client=c, now=1000.0)
        assert await ratelimit.check("9.9.9.9", settings=S, client=c, now=1000.0) is False
        # next day: allowed again
        assert await ratelimit.check("9.9.9.9", settings=S, client=c, now=1000.0 + 86400) is True


async def test_raw_ip_not_sent(up):
    await ratelimit.check("203.0.113.77", settings=S, now=1000.0)
    assert "203.0.113.77" not in "".join(up.bodies)
    cmds = json.loads(up.bodies[0])
    assert [c[0] for c in cmds] == ["INCR", "EXPIRE", "INCR", "EXPIRE"]
    assert cmds[1][2:] == ["600", "NX"] or cmds[1][2:] == [600, "NX"]


async def test_ipv6_normalised_and_invalid_shared(up):
    await ratelimit.check("2001:DB8::1", settings=S, now=1000.0)
    await ratelimit.check("2001:0db8:0:0:0:0:0:1", settings=S, now=1000.0)
    assert max(up.counts.values()) == 2 and len([k for k in up.counts if k.startswith("ip:")]) == 1
    assert ratelimit._ip_key("", 0) == ratelimit._ip_key("garbage", 0)


async def test_timeout_fails_open_and_warns(caplog):
    with respx.mock:
        respx.post(f"{URL}/pipeline").mock(side_effect=httpx.ConnectTimeout("t"))
        with caplog.at_level(logging.WARNING, logger="app.ratelimit"):
            assert await ratelimit.check("1.2.3.4", settings=S, now=1000.0) is True
    assert any(r.levelno == logging.WARNING for r in caplog.records)


@pytest.mark.parametrize("resp", [
    httpx.Response(500, text="boom"),
    httpx.Response(200, text="not json"),
    httpx.Response(200, json=[{"error": "ERR"}]),
    httpx.Response(200, json={"result": 1}),
])
async def test_bad_response_fails_open(resp, caplog):
    with respx.mock:
        respx.post(f"{URL}/pipeline").mock(return_value=resp)
        with caplog.at_level(logging.WARNING, logger="app.ratelimit"):
            assert await ratelimit.check("1.2.3.4", settings=S, now=1000.0) is True
    assert caplog.records


async def test_missing_settings_fails_open(caplog):
    with caplog.at_level(logging.WARNING, logger="app.ratelimit"):
        empty = Settings(_env_file=None)
        assert await ratelimit.check("1.2.3.4", settings=empty) is True
    assert caplog.records


def _req(headers: dict[str, str], client=("9.9.9.9", 1)) -> Request:
    return Request({"type": "http", "headers": [(k.encode(), v.encode()) for k, v in headers.items()],
                    "client": client})


def test_client_ip_precedence():
    h = {"x-vercel-forwarded-for": "1.1.1.1", "x-real-ip": "2.2.2.2", "x-forwarded-for": "3.3.3.3, 4.4.4.4"}
    assert ratelimit.client_ip(_req(h)) == "1.1.1.1"
    del h["x-vercel-forwarded-for"]
    assert ratelimit.client_ip(_req(h)) == "2.2.2.2"
    del h["x-real-ip"]
    assert ratelimit.client_ip(_req(h)) == "3.3.3.3"
    assert ratelimit.client_ip(_req({})) == "9.9.9.9"
    assert ratelimit.client_ip(_req({}, client=None)) == ""
