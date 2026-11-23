"""Checker for the Task 0.4 Vercel Services spike (temporary; delete with spike-deploy.yml and backend/app/api/spike.py). Stdlib only.

    python scripts/spike_vercel_check.py --url https://<preview>.vercel.app [--bypass-env VERCEL_AUTOMATION_BYPASS_SECRET]

Checks `/` (Next.js), `/api/ping` (FastAPI path facts) and `/api/sse` (streams, not clumped). Reuses parse_sse/evaluate from
scripts/spike_sse_check.py (Task 0.3), so delete both scripts together. Exit codes: 0 PASS, 1 FAIL, 2 usage or connection error.
The bypass secret is never printed and never sent to another host (redirects are not followed).
"""

import argparse
import importlib.util
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlsplit

_spec = importlib.util.spec_from_file_location(
    "spike_sse_check", Path(__file__).with_name("spike_sse_check.py")
)
sse = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sse)

EXPECTED_REGION = "sin1"  # vercel.json: services.api.functions regions
UA = {"User-Agent": "spike-vercel-check/1.0"}
NEXT_MARKERS = ("__next", "/_next/", "__NEXT_DATA__", "self.__next_f")
SEEN_HEADERS = (
    "x-vercel-id",
    "server",
    "content-type",
    "cache-control",
    "x-vercel-cache",
)


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):
        return None  # the 3xx surfaces as HTTPError: we inspect it, never follow it


OPENER = urllib.request.build_opener(_NoRedirect)


def open_url(url, headers, timeout):
    try:
        return OPENER.open(
            urllib.request.Request(url, headers=headers), timeout=timeout
        )
    except urllib.error.HTTPError as e:  # also a readable response
        return e


def lower(headers):
    return {k.lower(): v for k, v in dict(headers).items()}


def fetch(url, headers, timeout=30):
    """(status, lowercase headers, body text capped at 200 KB)."""
    r = open_url(url, headers, timeout)
    with r:
        return r.getcode(), lower(r.headers), r.read(200_000).decode("utf-8", "replace")


def is_protected(status, headers, body, base_host):
    """Vercel Deployment Protection: 401 HTML 'Authentication Required', or a redirect to vercel.com SSO."""
    if status in (301, 302, 303, 307, 308):
        host = urlsplit(headers.get("location", "")).hostname or ""
        return host != base_host and host.endswith("vercel.com")
    return (
        status in (401, 403)
        and "text/html" in headers.get("content-type", "")
        and "Authentication Required" in body
    )


def region_codes(x_vercel_id):
    """x-vercel-id looks like `sin1::iad1::abc-123-xyz` (format not documented in detail: we keep the raw value too)."""
    parts = x_vercel_id.split("::")
    return (
        [p for p in parts[:-1] if re.fullmatch(r"[a-z]{3,4}\d", p)]
        if len(parts) > 1
        else []
    )


def check_root(status, headers, body):
    f = []
    if status != 200:
        f.append(f"/ returned HTTP {status}, expected 200")
    elif "text/html" not in headers.get("content-type", ""):
        f.append(
            f"/ content-type is {headers.get('content-type')!r}, expected text/html"
        )
    elif not any(m in body for m in NEXT_MARKERS) or "<title" not in body:
        f.append(
            "/ is HTML but does not look like the Next.js app (no <title> or __next / _next markers)"
        )
    return f


def check_ping(status, headers, body):
    """Returns (failures, facts). A FastAPI 404 vs an HTML 404 tells 'flag not applied' from 'routed to Next.js'."""
    ctype = headers.get("content-type", "")
    facts, f = {}, []
    if status != 200:
        if "application/json" in ctype:
            f.append(
                f"/api/ping returned HTTP {status} JSON: FastAPI answered but the route is absent, "
                "so ENABLE_SPIKE_ENDPOINTS=1 did not reach the function (see docs/spikes.md#vercel, env)"
            )
        elif "text/html" in ctype:
            f.append(
                f"/api/ping returned HTTP {status} HTML: request went to Next.js, not FastAPI (rewrite/services routing wrong)"
            )
        else:
            f.append(f"/api/ping returned HTTP {status}")
        return f, facts
    try:
        j = json.loads(body)
    except ValueError:
        return [f"/api/ping body is not JSON (content-type {ctype!r})"], facts
    if j.get("ok") is not True:
        f.append(f"/api/ping JSON has ok={j.get('ok')!r}")
    facts = {
        k: j.get(k)
        for k in ("path", "root_path", "raw_path", "vercel_region", "python")
    }
    if facts["path"] != "/api/ping":
        f.append(
            f"FastAPI saw path {facts['path']!r}, expected '/api/ping' (prefix stripped? then routes in app/ must change)"
        )
    return f, facts


def stream(url, headers, timeout=30):
    """Returns (status, headers, events, done, cut) in the shape sse.evaluate wants."""
    r = open_url(url, {**headers, "Accept": "text/event-stream"}, timeout)
    status, h = r.getcode(), lower(r.headers)
    events, done, cut, t0 = [], False, None, None
    if status != 200:
        r.close()
        return status, h, events, done, cut
    try:
        with r:
            for ev in sse.parse_sse(iter(r.readline, b"")):
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
    except Exception as e:  # reset / timeout mid-stream = cut
        cut = f"{type(e).__name__}: {e}"
    return status, h, events, done, cut


def fmt_headers(h):
    return "; ".join(f"{k}={h.get(k, '(absent)')}" for k in SEEN_HEADERS)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument(
        "--url",
        required=True,
        help="deployment origin, e.g. https://<preview>.vercel.app",
    )
    ap.add_argument(
        "--bypass-env",
        help="name of the env var holding the Protection Bypass for Automation secret",
    )
    ap.add_argument("--expect", type=int, default=30)
    ap.add_argument(
        "--interval", type=float, default=1.0, help="server interval in seconds"
    )
    a = ap.parse_args(argv)
    u = urlsplit(a.url)
    if u.scheme not in ("http", "https") or not u.hostname:
        print("--url must start with http:// or https://", file=sys.stderr)
        return 2
    base = f"{u.scheme}://{u.netloc}"
    headers = dict(UA)
    if a.bypass_env:
        secret = os.environ.get(a.bypass_env, "")
        if not secret:
            print(f"env var {a.bypass_env} is empty or not set", file=sys.stderr)
            return 2
        headers["x-vercel-protection-bypass"] = secret
    print(f"checking {sse.mask_url(base)}", flush=True)

    fails, info = [], []
    try:
        r_status, r_h, r_body = fetch(base + "/", headers)
        if is_protected(r_status, r_h, r_body, u.hostname):
            state = (
                "bypass secret was sent but rejected (wrong or revoked secret?)"
                if a.bypass_env
                else "no bypass secret given"
            )
            fails.append(
                f"Deployment Protection blocked the request ({state}). Create Protection Bypass for Automation "
                "(Vercel, Project, Settings, Deployment Protection), export it and rerun with "
                "--bypass-env VERCEL_AUTOMATION_BYPASS_SECRET (sent as the x-vercel-protection-bypass header)"
            )
            blocked = True
        else:
            blocked = False
            fails += check_root(r_status, r_h, r_body)
            p_status, p_h, p_body = fetch(base + "/api/ping", headers)
            pf, facts = check_ping(p_status, p_h, p_body)
            fails += pf
            s_status, s_h, events, done, cut = stream(base + "/api/sse", headers)
            ctype = s_h.get("content-type", "")
            if s_status != 200:
                fails.append(f"/api/sse returned HTTP {s_status}")
            elif not ctype.startswith("text/event-stream"):
                fails.append(
                    f"/api/sse content-type is {ctype!r}, expected text/event-stream"
                )
            ef, st = sse.evaluate(events, done, cut, a.expect, a.interval)
            fails += ef if s_status == 200 else []
    except (urllib.error.URLError, OSError) as e:
        print(f"cannot connect: {type(e).__name__}: {e}", file=sys.stderr)
        return 2

    print("\n=== RESULT spike_vercel (copy this block) ===")
    print(f"verdict: {'FAIL' if fails else 'PASS'}")
    print(f"host: {sse.mask_url(base)}")
    print(
        f"protection: {'BLOCKED' if blocked else 'passed'} (bypass header {'sent' if a.bypass_env else 'not sent'})"
    )
    print(f"root: status={r_status} {fmt_headers(r_h)}")
    if not blocked:
        region = facts.get("vercel_region")
        print(f"ping: status={p_status} {fmt_headers(p_h)}")
        print(f"ping_facts: {json.dumps(facts, ensure_ascii=False)}")
        print(
            f"fastapi_sees_api_prefix: {facts['path'].startswith('/api/') if facts.get('path') else 'unknown'}"
        )
        print(
            f"function_region: {region!r} (expected {EXPECTED_REGION!r}: {'match' if region == EXPECTED_REGION else 'NO MATCH'})"
        )
        ids = [
            (n, region_codes(h.get("x-vercel-id", "")))
            for n, h in (("/", r_h), ("/api/ping", p_h), ("/api/sse", s_h))
        ]
        print(
            "x_vercel_id_regions: "
            + "; ".join(f"{n}={','.join(c) or '(unparsed)'}" for n, c in ids)
        )
        print(f"sse: status={s_status} {fmt_headers(s_h)}")
        print(
            f"events: {st['n']}/{a.expect}  done_event: {'yes' if done else 'no'}  cut: {cut or 'no'}"
        )
        print(f"wall_time_s: {st['wall']:.2f}")
        print(
            f"inter_arrival_s: min={st['min']:.3f} median={st['median']:.3f} "
            f"p95={st['p95']:.3f} max(longest_gap)={st['longest']:.3f}"
        )
        print(f"clumped_events: {st['clumped']} (max tolerated {sse.MAX_CLUMPED})")
        if region != EXPECTED_REGION:
            info.append(
                f"function region {region!r} is not {EXPECTED_REGION!r}: record it, region config may not have applied"
            )
    for x in info:
        print(f"INFO: {x}")
    for x in fails:
        print(f"FAIL: {x}")
    print("=== END RESULT ===")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
