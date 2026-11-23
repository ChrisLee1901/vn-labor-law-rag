"""TEMPORARY spike (Task 0.3): SSE over ngrok for 150 s. Delete this file after the spike (plan: "bo di sau spike").

Server: GET /stream (bearer, 1 event/s) and GET /health (open). Launcher opens the tunnel the same way
kaggle/serve.ipynb cell 7 does (pyngrok, ngrok.connect(port, "http", domain=...)) and EXITS by itself after
--duration-min (max 30). Nothing here keeps the notebook alive or restarts it (Kaggle ToS, CLAUDE.md rule 8).

    python kaggle/spike_sse.py --duration-min 10          # on Kaggle (3 secrets)
    python kaggle/spike_sse.py --no-tunnel --count 10 --interval 0.2   # local dry run
"""

import argparse
import asyncio
import hmac
import json
import os
import re
import threading
import time

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, StreamingResponse

MAX_DURATION_MIN = 30


def create_app(token: str, count: int = 150, interval: float = 1.0) -> FastAPI:
    if not token:
        raise ValueError("token must not be empty")
    app = FastAPI()

    @app.get("/health")
    async def health():
        return {"ok": True}

    async def events():
        for n in range(1, count + 1):
            yield f"id: {n}\ndata: {json.dumps({'n': n, 't': time.time()})}\n\n"
            await asyncio.sleep(interval)
        yield f"event: done\ndata: {json.dumps({'n': count})}\n\n"

    @app.get("/stream")
    async def stream(request: Request):
        got = request.headers.get("authorization", "")
        if not hmac.compare_digest(got.encode(), f"Bearer {token}".encode()):
            return JSONResponse({"detail": "unauthorized"}, status_code=401)
        return StreamingResponse(
            events(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache, no-transform",
                "X-Accel-Buffering": "no",
            },
        )

    return app


def parse_args(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument(
        "--duration-min",
        type=float,
        default=10,
        help=f"stop by itself after N min (max {MAX_DURATION_MIN})",
    )
    ap.add_argument(
        "--count", type=int, default=int(os.environ.get("SPIKE_COUNT", 150))
    )
    ap.add_argument(
        "--interval", type=float, default=float(os.environ.get("SPIKE_INTERVAL", 1.0))
    )
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--no-tunnel", action="store_true", help="local server only")
    a = ap.parse_args(argv)
    if not 0 < a.duration_min <= MAX_DURATION_MIN:
        ap.error(f"--duration-min must be in (0, {MAX_DURATION_MIN}]")
    if a.count < 1 or a.interval <= 0:
        ap.error("--count must be >= 1 and --interval > 0")
    return a


def _secret(name: str) -> str:
    value = os.environ.get(name, "")
    if not value:
        try:  # only exists inside Kaggle
            from kaggle_secrets import UserSecretsClient

            value = UserSecretsClient().get_secret(name) or ""
        except Exception:
            pass
    return value.strip()


def _describe(e: Exception, secret: str) -> str:
    """Type name plus an ERR_NGROK_nnn code, never the message: pyngrok puts argv (the authtoken) in it."""
    code = re.search(r"ERR_NGROK_\d+", str(e).replace(secret, "***"))
    return type(e).__name__ + (f" {code.group()}" if code else "")


def open_tunnel(port: int, domain: str, authtoken: str):
    from pyngrok import ngrok  # lazy: tests/CI never need it

    try:
        ngrok.set_auth_token(authtoken)
        ngrok.connect(port, "http", domain=domain)  # same call as serve.ipynb cell 7
    except Exception as e:
        print(f"ngrok setup failed: {_describe(e, authtoken)}", flush=True)
        try:
            ngrok.kill()
        except Exception:
            pass
        raise SystemExit(3) from None
    return ngrok


def main(argv=None) -> int:
    a = parse_args(argv)
    token = _secret("GATEWAY_API_KEY")
    if not token:
        print("GATEWAY_API_KEY missing (env var or Kaggle Secret)")
        return 2
    domain = ""
    if not a.no_tunnel:
        authtoken = _secret("NGROK_AUTHTOKEN")
        domain = _secret("NGROK_DOMAIN").removeprefix("https://").rstrip("/")
        if not authtoken or not domain:
            print("NGROK_AUTHTOKEN / NGROK_DOMAIN missing (env var or Kaggle Secret)")
            return 2

    import uvicorn

    server = uvicorn.Server(
        uvicorn.Config(
            create_app(token, a.count, a.interval),
            host="127.0.0.1",
            port=a.port,
            log_level="warning",
        )
    )
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.monotonic() + a.duration_min * 60
    while not server.started:
        if not thread.is_alive() or time.monotonic() > deadline:
            print("server failed to start (port busy?)")
            return 2
        time.sleep(0.05)

    ngrok = None
    try:
        if a.no_tunnel:
            print(f"READY http://127.0.0.1:{a.port}", flush=True)
        else:
            ngrok = open_tunnel(a.port, domain, authtoken)
            print(f"READY https://{domain}", flush=True)
        print(f"stops by itself in {a.duration_min:g} min (or Ctrl-C)", flush=True)
        while time.monotonic() < deadline and thread.is_alive():
            time.sleep(0.5)
    except KeyboardInterrupt:
        pass
    finally:
        if ngrok:
            try:
                ngrok.kill()  # closes tunnel(s) and the ngrok process
            except Exception as e:
                print("ngrok shutdown:", _describe(e, authtoken))
        server.should_exit = True
        thread.join(timeout=5)
        print("STOPPED", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
