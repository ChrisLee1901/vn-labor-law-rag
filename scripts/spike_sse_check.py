"""Checker for the Task 0.3 SSE spike (temporary; delete with kaggle/spike_sse.py). Stdlib only.

    python scripts/spike_sse_check.py --url https://<domain>/stream --token-env GATEWAY_API_KEY [--expect 150]

Exit codes: 0 PASS, 1 FAIL, 2 usage or connection error. The token is never printed; the printed host is masked.
"""

import argparse
import json
import os
import statistics
import sys
import time
import urllib.error
import urllib.request
from urllib.parse import urlsplit

# --- thresholds (S = server interval) ---
# p95 gap must sit in [0.5 S, 2 S]: below = events were queued and flushed together, above = slow or stalling.
P95_MIN_FACTOR, P95_MAX_FACTOR = 0.5, 2.0
# An event arriving < min(50 ms, S/4) after the previous one was not paced by the server: proxy buffering.
# A few can happen after a network hiccup, a stream of them is buffering.
CLUMP_WINDOW_S, CLUMP_FRACTION, MAX_CLUMPED = 0.05, 0.25, 3
# One gap longer than 5 S is a stall, even if everything arrives eventually.
MAX_GAP_FACTOR = 5.0
# ngrok free plan shows an interstitial to browsers; docs: bypass with the ngrok-skip-browser-warning header
# or a custom User-Agent. We send both so a plain client is never mistaken for a browser.
HEADERS = {"User-Agent": "spike-sse-check/1.0", "ngrok-skip-browser-warning": "1"}


def mask_url(url: str) -> str:
    u = urlsplit(url)
    host = u.hostname or ""
    if host.replace(".", "").isdigit() or "." not in host:  # IP or localhost
        return f"{u.scheme}://{u.netloc}"
    first, _, rest = host.partition(".")
    port = f":{u.port}" if u.port else ""
    return f"{u.scheme}://{first[:3]}***.{rest}{port}"


def parse_sse(lines):
    """Yield {'event','data','id'} per blank-line-terminated block; lines are raw bytes, read incrementally."""
    ev = {"event": "message", "data": "", "id": ""}
    seen = False
    for raw in lines:
        line = raw.decode("utf-8", "replace").rstrip("\r\n")
        if line == "":
            if seen:
                yield ev
            ev, seen = {"event": "message", "data": "", "id": ""}, False
        elif line.startswith(":"):
            continue
        else:
            k, _, v = line.partition(":")
            if k in ev:
                ev[k] = v[1:] if v.startswith(" ") else v
                seen = True


def evaluate(events, done, cut, expect, interval):
    """events: [(arrival_seconds, n)] for data events. Returns (failures, stats)."""
    ns = [n for _, n in events]
    gaps = [b[0] - a[0] for a, b in zip(events, events[1:])]
    clump_at = min(CLUMP_WINDOW_S, CLUMP_FRACTION * interval)
    st = {
        "n": len(events),
        "clumped": sum(g < clump_at for g in gaps),
        "min": min(gaps, default=0.0),
        "median": statistics.median(gaps) if gaps else 0.0,
        "p95": sorted(gaps)[min(len(gaps) - 1, int(0.95 * len(gaps)))] if gaps else 0.0,
        "longest": max(gaps, default=0.0),
        "wall": events[-1][0] - events[0][0] if events else 0.0,
    }
    f = []
    if len(events) != expect:
        f.append(f"received {len(events)}/{expect} events")
    if ns != list(range(1, len(ns) + 1)):
        f.append("events out of order or with a gap in the sequence numbers")
    if cut:
        f.append(f"stream cut: {cut}")
    elif not done:
        f.append("stream ended without the final 'done' event (cut early)")
    if gaps and not P95_MIN_FACTOR * interval <= st["p95"] <= P95_MAX_FACTOR * interval:
        f.append(
            f"p95 gap {st['p95']:.3f}s outside [{P95_MIN_FACTOR * interval:.3f}, {P95_MAX_FACTOR * interval:.3f}]s"
        )
    if st["clumped"] > MAX_CLUMPED:
        f.append(
            f"{st['clumped']} events arrived <{clump_at * 1000:.0f} ms after the previous one (buffered clump)"
        )
    if st["longest"] > MAX_GAP_FACTOR * interval:
        f.append(
            f"stall: longest gap {st['longest']:.2f}s > {MAX_GAP_FACTOR * interval:.2f}s"
        )
    return f, st


def get_status(url, headers, timeout):
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status
    except urllib.error.HTTPError as e:
        return e.code


def stream(url, token, timeout):
    """Returns (status, headers, events, done, cut)."""
    req = urllib.request.Request(
        url,
        headers={
            **HEADERS,
            "Authorization": f"Bearer {token}",
            "Accept": "text/event-stream",
        },
    )
    events, done, cut = [], False, None
    try:
        r = urllib.request.urlopen(req, timeout=timeout)
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers), events, done, None
    t0 = None
    try:
        with r:
            for ev in parse_sse(iter(r.readline, b"")):
                now = time.monotonic()
                if ev["event"] == "done":
                    done = True
                    break
                t0 = now if t0 is None else t0
                try:
                    events.append((now - t0, int(json.loads(ev["data"])["n"])))
                except (ValueError, KeyError, TypeError):
                    cut = f"unparseable event data: {ev['data'][:60]!r}"
                    break
    except Exception as e:  # reset / timeout / incomplete read mid-stream = cut
        cut = f"{type(e).__name__}: {e}"
    return r.status, dict(r.headers), events, done, cut


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--url", required=True)
    ap.add_argument(
        "--token-env",
        required=True,
        help="name of the env var holding the bearer token",
    )
    ap.add_argument("--expect", type=int, default=150)
    ap.add_argument(
        "--interval", type=float, default=1.0, help="server interval in seconds"
    )
    a = ap.parse_args(argv)
    token = os.environ.get(a.token_env, "")
    if not token:
        print(f"env var {a.token_env} is empty or not set", file=sys.stderr)
        return 2
    if urlsplit(a.url).scheme not in ("http", "https"):
        print("--url must start with http:// or https://", file=sys.stderr)
        return 2
    gap_timeout = max(10.0, 5 * a.interval)  # max wait for any single read
    print(
        f"checking {mask_url(a.url)} (do not paste the full URL publicly: it is the production tunnel)",
        flush=True,
    )
    try:
        s_none = get_status(a.url, HEADERS, 15)
        s_bad = get_status(
            a.url, {**HEADERS, "Authorization": "Bearer wrong-" + token[::-1]}, 15
        )
        status, headers, events, done, cut = stream(a.url, token, gap_timeout)
    except (urllib.error.URLError, OSError) as e:
        print(f"cannot connect: {type(e).__name__}: {e}", file=sys.stderr)
        return 2

    fails = []
    if s_none != 401:
        fails.append(f"request without token returned {s_none}, expected 401")
    if s_bad != 401:
        fails.append(f"request with wrong token returned {s_bad}, expected 401")
    ctype = headers.get("Content-Type", headers.get("content-type", ""))
    if status != 200:
        fails.append(f"stream request returned HTTP {status}")
    elif not ctype.startswith("text/event-stream"):
        fails.append(f"content-type is {ctype!r} (ngrok interstitial HTML?)")
    sf, st = evaluate(events, done, cut, a.expect, a.interval)
    fails += sf if status == 200 else []

    low = {k.lower(): v for k, v in headers.items()}
    seen = [
        "content-type",
        "cache-control",
        "x-accel-buffering",
        "transfer-encoding",
        "server",
    ]
    seen += sorted(k for k in low if "ngrok" in k)
    print("\n=== RESULT spike_sse (copy this block) ===")
    print(f"verdict: {'FAIL' if fails else 'PASS'}")
    print(f"host: {mask_url(a.url)}")
    print(f"no_token_status: {s_none} (expect 401)")
    print(f"wrong_token_status: {s_bad} (expect 401)")
    print(f"stream_http_status: {status}")
    print("headers: " + "; ".join(f"{k}={low.get(k, '(absent)')}" for k in seen))
    print(
        f"events: {st['n']}/{a.expect}  done_event: {'yes' if done else 'no'}  cut: {cut or 'no'}"
    )
    print(f"wall_time_s: {st['wall']:.2f}")
    print(
        f"inter_arrival_s: min={st['min']:.3f} median={st['median']:.3f} "
        f"p95={st['p95']:.3f} max(longest_gap)={st['longest']:.3f}"
    )
    print(f"clumped_events: {st['clumped']} (max tolerated {MAX_CLUMPED})")
    for x in fails:
        print(f"FAIL: {x}")
    print("=== END RESULT ===")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
