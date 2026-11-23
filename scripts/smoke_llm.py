"""Smoke + benchmark of the live Kaggle gateway through the tunnel (Task 2.3). Stdlib only.

    LLM_BASE_URL=https://<domain> LLM_API_KEY=... python scripts/smoke_llm.py [--runs 3] [--timeout 60]

Steps: (a) /health, (b) embeddings, (c) rerank, (d) chat stream x runs (TTFT, tok/s, answer checks),
(e) verdict (TTFT p50 < TTFT_P50_MAX_S). Exit codes: 0 PASS, 1 FAIL, 2 usage / connection / auth error.
The key is never printed; the printed host is masked.
"""

import argparse
import http.client
import json
import math
import os
import re
import sys
import time
import unicodedata
import urllib.error
import urllib.request
from datetime import datetime, timezone
from urllib.parse import urlsplit

# --- thresholds ---
TTFT_P50_MAX_S = 3.0  # plan Task 2.3: p50 over the chat runs, through the tunnel
TOKS_WARN_BELOW = 10.0  # tok/s is informational (spec); only a warning
EMBED_DIM = 1024
MIN_DIACRITIC_RATIO = (
    0.10  # Vietnamese text has far more; an ASCII-stripped answer has ~0
)
CHAT_MAX_TOKENS = (
    128  # bounded on purpose; the backend sends its own CHAT_MAX_TOKENS (1024)
)
# Same URL allowlist as backend/app/llm/gateway.py (SSRF guard); here it only triggers a warning.
ALLOWED = re.compile(r"^https://[a-z0-9-]+\.ngrok-free\.(app|dev)$")
# ngrok free plan shows an interstitial to browsers; a custom UA + this header avoids mistaking us for one.
HEADERS = {"User-Agent": "smoke-llm/1.0", "ngrok-skip-browser-warning": "1"}

EMBED_TEXTS = [
    "Mức lương tối thiểu vùng I áp dụng đối với người lao động làm việc theo hợp đồng lao động.",
    "Người sử dụng lao động phải trả lương cho người lao động đúng hạn.",
]
RERANK_QUERY = "lương tối thiểu vùng I"
RERANK_DOCS = [
    "Muốn nấu canh chua cá lóc ngon, cần chọn cá tươi, me chua và nêm nếm vừa ăn.",
    "Lương tối thiểu vùng I là mức lương thấp nhất được áp dụng cho người lao động làm việc tại các địa bàn thuộc vùng I.",
    "Lao động nữ được nghỉ thai sản trước và sau khi sinh con theo quy định của pháp luật.",
]
RERANK_RELEVANT = 1  # index in RERANK_DOCS
CHAT_MESSAGES = [
    {
        "role": "system",
        "content": "Bạn là trợ lý pháp luật lao động Việt Nam. Trả lời ngắn gọn bằng tiếng Việt có dấu.",
    },
    {
        "role": "user",
        "content": "Mức lương tối thiểu vùng I là gì? Trả lời ngắn gọn bằng tiếng Việt.",
    },
]

_VI = set("àáảãạăằắẳẵặâầấẩẫậèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵđ")
# UTF-8 read as Latin-1/cp1252: "Ã¡", "Ä‘", "áº", "á»", "Æ°", "â€"
_MOJIBAKE = re.compile("Ã[\u0080-¿]|Ä[\u0080-¿‘’]|áº|á»|Æ[°¡]|â€")


class StepFail(Exception):
    """A check failed; the message is the one-line reason."""


class AuthError(Exception):
    """Gateway answered 401."""


class Unreachable(Exception):
    """Cannot connect at all (health step)."""


def mask_url(url: str) -> str:
    u = urlsplit(url)
    host = u.hostname or ""
    if host.replace(".", "").isdigit() or "." not in host:  # IP or localhost
        return f"{u.scheme}://{u.netloc}"
    first, _, rest = host.partition(".")
    port = f":{u.port}" if u.port else ""
    return f"{u.scheme}://{first[:3]}***.{rest}{port}"


def url_warning(url: str) -> str | None:
    host = urlsplit(url).hostname or ""
    if ALLOWED.match(url) or host in ("localhost", "127.0.0.1"):
        return None
    return (
        "LLM_BASE_URL không khớp regex ngrok của backend "
        "(^https://<tên>.ngrok-free.(app|dev)$): backend sẽ coi gateway này là offline"
    )


def percentile(xs, p):
    """Linear interpolation between closest ranks (numpy default)."""
    s = sorted(xs)
    k = (len(s) - 1) * p / 100
    lo, hi = math.floor(k), math.ceil(k)
    return s[lo] + (s[hi] - s[lo]) * (k - lo)


def tok_per_s(tokens, total_s, ttft_s):
    """Decode throughput = tokens / (total - TTFT). None when it is not measurable."""
    dt = total_s - ttft_s
    return tokens / dt if tokens > 0 and dt > 0 else None


def check_text(text: str):
    """Returns (failures, notes) for one chat answer."""
    fails, notes = [], []
    if not text.strip():
        return ["câu trả lời rỗng"], notes
    if "�" in text:
        fails.append("có ký tự thay thế U+FFFD")
    if _MOJIBAKE.search(text):
        fails.append("có dấu hiệu mojibake (UTF-8 bị đọc như Latin-1)")
    if re.search(r"</?think>", text, re.I):
        fails.append("lộ thẻ <think> (thinking phải tắt)")
    nfc = unicodedata.normalize("NFC", text)
    letters = [c for c in nfc.lower() if c.isalpha()]
    ratio = sum(c in _VI for c in letters) / len(letters) if letters else 0.0
    if ratio < MIN_DIACRITIC_RATIO:
        fails.append(f"thiếu dấu tiếng Việt (tỉ lệ ký tự có dấu {ratio:.2f})")
    if nfc != text:
        notes.append("không NFC")
    return fails, notes


# --- HTTP ---


def _request(url, key, body=None):
    h = dict(HEADERS)
    if key:
        h["Authorization"] = f"Bearer {key}"
    data = None
    if body is not None:
        data = json.dumps(body).encode()
        h["Content-Type"] = "application/json"
    return urllib.request.Request(url, data=data, headers=h)


def _open(req, timeout):
    try:
        return urllib.request.urlopen(req, timeout=timeout)
    except urllib.error.HTTPError as e:
        if e.code == 401:
            raise AuthError from e
        ng = e.headers.get("ngrok-error-code")
        raise StepFail(f"HTTP {e.code}" + (f" (ngrok {ng})" if ng else "")) from e


def _json(req, timeout):
    with _open(req, timeout) as r:
        raw = r.read()
    try:
        return json.loads(raw)
    except ValueError:
        raise StepFail("phản hồi không phải JSON (trang cảnh báo ngrok?)") from None


# --- steps (each returns a one-line detail, or raises StepFail) ---


def step_health(c, res):
    try:
        h = _json(_request(c["base"] + "/health", None), c["timeout"])
    except StepFail:
        raise
    except OSError as e:  # URLError, refused, timeout: not a gateway verdict
        raise Unreachable(f"{type(e).__name__}: {e}") from e
    if not isinstance(h, dict):
        raise StepFail("/health không trả object JSON")
    res["health"] = h
    if not h.get("llm"):
        raise StepFail(f"llm={h.get('llm')!r} (llama-server chưa sẵn sàng)")
    return (
        f"status={h.get('status')} llm={h.get('llm')} model={str(h.get('model'))[:80]}"
    )


def step_embed(c, res):
    ms = []
    for _ in range(2):  # second call = warm repeat timing
        t = time.perf_counter()
        d = _json(
            _request(c["base"] + "/v1/embeddings", c["key"], {"input": EMBED_TEXTS}),
            c["timeout"],
        )
        ms.append((time.perf_counter() - t) * 1000)
    try:
        vecs = [x["embedding"] for x in sorted(d["data"], key=lambda x: x["index"])]
    except (KeyError, TypeError):
        raise StepFail("phản hồi embeddings sai dạng") from None
    res["embed_ms"] = ms
    if len(vecs) != len(EMBED_TEXTS):
        raise StepFail(f"nhận {len(vecs)} vector, mong đợi {len(EMBED_TEXTS)}")
    res["embed_dims"] = [len(v) for v in vecs]
    if any(n != EMBED_DIM for n in res["embed_dims"]):
        raise StepFail(
            f"chiều {res['embed_dims']}, mong đợi {EMBED_DIM} (sai model embedder?)"
        )
    if not all(
        isinstance(x, (int, float)) and math.isfinite(x) for v in vecs for x in v
    ):
        raise StepFail("vector có giá trị không hữu hạn hoặc không phải số")
    if vecs[0] == vecs[1]:
        raise StepFail("hai câu khác nhau cho vector giống hệt nhau")
    na, nb = (math.sqrt(sum(x * x for x in v)) for v in vecs)
    if na == 0 or nb == 0:
        raise StepFail("vector không (norm = 0)")
    res["embed_cos"] = sum(x * y for x, y in zip(*vecs)) / (na * nb)
    return f"2 vector x {EMBED_DIM} chiều, cosine={res['embed_cos']:.3f}"


def step_rerank(c, res):
    d = _json(
        _request(
            c["base"] + "/v1/rerank",
            c["key"],
            {
                "query": RERANK_QUERY,
                "documents": RERANK_DOCS,
                "top_n": len(RERANK_DOCS),
            },
        ),
        c["timeout"],
    )
    try:
        out = [(int(r["index"]), float(r["relevance_score"])) for r in d["results"]]
    except (KeyError, TypeError, ValueError):
        raise StepFail("phản hồi rerank sai dạng") from None
    res["rerank"] = out
    if sorted(i for i, _ in out) != list(range(len(RERANK_DOCS))):
        raise StepFail(f"thứ tự trả về không đủ các đoạn: {[i for i, _ in out]}")
    scores = [s for _, s in out]
    if not all(math.isfinite(s) and 0 <= s <= 1 for s in scores):
        raise StepFail(f"điểm ngoài [0, 1]: {scores}")
    if scores != sorted(scores, reverse=True):
        raise StepFail("kết quả không sắp giảm dần theo điểm")
    if out[0][0] != RERANK_RELEVANT:
        raise StepFail(
            f"đoạn liên quan (index {RERANK_RELEVANT}) xếp thứ "
            f"{[i for i, _ in out].index(RERANK_RELEVANT) + 1}, không phải đầu"
        )
    return f"thứ tự {[i for i, _ in out]}, điểm đầu {scores[0]:.3f}"


def chat_once(c):
    """One streamed chat call. Returns dict(ttft, total, text, chunks, usage_tokens, reasoning)."""
    body = {
        "messages": CHAT_MESSAGES,
        "stream": True,
        "max_tokens": CHAT_MAX_TOKENS,
        # asks llama-server for a final usage chunk; without it we count chunks instead
        "stream_options": {"include_usage": True},
    }
    req = _request(c["base"] + "/v1/chat/completions", c["key"], body)
    t0 = time.perf_counter()
    r = _open(req, c["timeout"])
    ctype = r.headers.get("Content-Type", "")
    if not ctype.startswith("text/event-stream"):
        r.close()
        raise StepFail(f"content-type {ctype!r} (trang cảnh báo ngrok?)")
    ttft, parts, chunks, usage, done, reasoning = None, [], 0, None, False, False
    try:
        with r:
            for raw in iter(r.readline, b""):
                line = raw.decode("utf-8", "replace").strip()
                if not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                if data == "[DONE]":
                    done = True
                    break
                try:
                    obj = json.loads(data)
                except ValueError:
                    continue
                if not isinstance(obj, dict):
                    continue
                if "error" in obj:
                    raise StepFail(f"lỗi trong luồng: {str(obj['error'])[:80]}")
                u = obj.get("usage")
                if isinstance(u, dict) and isinstance(u.get("completion_tokens"), int):
                    usage = u["completion_tokens"]
                try:
                    delta = obj["choices"][0]["delta"]
                except (KeyError, IndexError, TypeError):
                    continue
                if delta.get("reasoning_content"):
                    reasoning = True
                if delta.get("content"):
                    if ttft is None:
                        ttft = time.perf_counter() - t0
                    chunks += 1
                    parts.append(delta["content"])
    except (OSError, http.client.HTTPException) as e:  # reset, timeout, incomplete read
        raise StepFail(f"luồng bị cắt: {type(e).__name__}: {e}") from e
    total = time.perf_counter() - t0
    if not done:
        raise StepFail("luồng kết thúc không có [DONE] (câu trả lời cụt)")
    if ttft is None:
        raise StepFail("không có delta nội dung nào")
    return {
        "ttft": ttft,
        "total": total,
        "text": "".join(parts),
        "chunks": chunks,
        "usage_tokens": usage,
        "reasoning": reasoning,
    }


def step_chat(c, res):
    res["runs"] = []
    fails, notes = [], []
    for i in range(1, c["runs"] + 1):
        try:
            r = chat_once(c)
        except StepFail as e:
            raise StepFail(f"lần {i}: {e}") from e
        r["tokens"] = (
            r["usage_tokens"] if r["usage_tokens"] is not None else r["chunks"]
        )
        r["source"] = (
            "usage" if r["usage_tokens"] is not None else "xấp xỉ theo số chunk"
        )
        r["toks"] = tok_per_s(r["tokens"], r["total"], r["ttft"])
        res["runs"].append(r)
        f, n = check_text(r["text"])
        if r["reasoning"]:
            f.append("lộ reasoning_content (thinking phải tắt)")
        fails += [f"lần {i}: {x}" for x in f]
        notes += [f"lần {i}: {x}" for x in n]
    res["notes"] = notes
    if fails:
        raise StepFail("; ".join(fails))
    return f"{c['runs']} lần, câu trả lời tiếng Việt hợp lệ"


def step_ttft(c, res):
    runs = res.get("runs") or []
    if not runs:
        raise StepFail("không có lần chat nào để tính TTFT")
    p50 = percentile([r["ttft"] for r in runs], 50)
    if p50 >= TTFT_P50_MAX_S:
        raise StepFail(f"TTFT p50 {p50:.2f} s >= {TTFT_P50_MAX_S:.1f} s")
    return f"TTFT p50 {p50:.2f} s < {TTFT_P50_MAX_S:.1f} s"


STEPS = [
    ("a_health", step_health),
    ("b_embeddings", step_embed),
    ("c_rerank", step_rerank),
    ("d_chat", step_chat),
    ("e_ttft_p50", step_ttft),
]


def run_step(name, fn, c, res, steps):
    try:
        ok, msg = True, fn(c, res)
    except StepFail as e:
        ok, msg = False, str(e)
    except (OSError, ValueError, http.client.HTTPException) as e:
        ok, msg = False, f"{type(e).__name__}: {e}"
    steps.append((name, ok, msg))
    print(f"[{name}] {'PASS' if ok else 'FAIL'}: {msg}", flush=True)


def print_result(c, res, steps):
    runs = res.get("runs", [])
    fails = [s for s in steps if not s[1]]
    h = res.get("health") or {}
    print("\n=== RESULT smoke_llm (copy this block) ===")
    print(f"verdict: {'FAIL' if fails else 'PASS'}")
    print(f"timestamp_utc: {datetime.now(timezone.utc):%Y-%m-%d %H:%M:%SZ}")
    print(f"host: {mask_url(c['base'])}")
    print(
        "health: "
        + " ".join(
            f"{k}={str(h.get(k, '(absent)'))[:80]}"
            for k in ("status", "llm", "embedder", "reranker", "model")
        )
    )
    if "embed_dims" in res:
        cos = res.get("embed_cos")
        ms = res.get("embed_ms", [])
        print(
            f"embeddings: dims={res['embed_dims']} "
            f"cosine={'n/a' if cos is None else f'{cos:.3f}'} "
            f"latency_ms first={ms[0]:.0f} repeat={ms[-1]:.0f}"
        )
    if "rerank" in res:
        print(
            f"rerank: order={[i for i, _ in res['rerank']]} "
            f"scores={[round(s, 3) for _, s in res['rerank']]} "
            f"(relevant index {RERANK_RELEVANT})"
        )
    if runs:
        print(f"\nchat (max_tokens={CHAT_MAX_TOKENS}, stream, thinking off):\n")
        print("| run | TTFT (s) | total (s) | tokens | nguồn token | tok/s |")
        print("|---|---|---|---|---|---|")
        for i, r in enumerate(runs, 1):
            ts = "n/a" if r["toks"] is None else f"{r['toks']:.1f}"
            print(
                f"| {i} | {r['ttft']:.2f} | {r['total']:.2f} | {r['tokens']} "
                f"| {r['source']} | {ts} |"
            )
        tt = [r["ttft"] for r in runs]
        tk = [r["toks"] for r in runs if r["toks"] is not None]
        print(
            f"\nttft_s: p50={percentile(tt, 50):.2f} p95={percentile(tt, 95):.2f} "
            f"(gate p50 < {TTFT_P50_MAX_S:.1f})"
        )
        print(
            "tok_per_s: "
            + (
                f"median={percentile(tk, 50):.1f} (decode = tokens / (total - TTFT))"
                if tk
                else "n/a"
            )
        )
        if tk and percentile(tk, 50) < TOKS_WARN_BELOW:
            print(f"WARN: tok/s median < {TOKS_WARN_BELOW:.0f} (không gate, chỉ báo)")
        print(
            "answer_run1: " + " ".join(runs[0]["text"][:200].split()).replace("\n", " ")
        )
    for n in res.get("notes", []):
        print(f"note: {n}")
    print()
    for name, ok, msg in steps:
        print(f"{name}: {'PASS' if ok else 'FAIL'} — {msg}")
    print("=== END RESULT ===")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--runs", type=int, default=3, help="số lần chat stream")
    ap.add_argument(
        "--timeout", type=float, default=60.0, help="giây chờ cho mỗi lần đọc"
    )
    a = ap.parse_args(argv)
    base = os.environ.get("LLM_BASE_URL", "").strip().rstrip("/")
    key = os.environ.get("LLM_API_KEY", "")
    if not base or not key:
        print("cần đặt biến môi trường LLM_BASE_URL và LLM_API_KEY", file=sys.stderr)
        return 2
    if urlsplit(base).scheme not in ("http", "https") or a.runs < 1:
        print("LLM_BASE_URL phải bắt đầu http(s):// và --runs >= 1", file=sys.stderr)
        return 2
    c = {"base": base, "key": key, "timeout": a.timeout, "runs": a.runs}
    print(
        f"checking {mask_url(base)} (đừng dán URL đầy đủ ở nơi công khai)", flush=True
    )
    if w := url_warning(base):
        print(f"WARN: {w}", file=sys.stderr)
    res, steps = {}, []
    try:
        for name, fn in STEPS:
            run_step(name, fn, c, res, steps)
    except AuthError:
        print(
            "401 unauthorized: kiểm tra LLM_API_KEY (phải trùng secret GATEWAY_API_KEY của Kaggle)",
            file=sys.stderr,
        )
        return 2
    except Unreachable as e:
        print(
            f"không kết nối được {mask_url(base)}: {e} (notebook Kaggle đã READY chưa?)",
            file=sys.stderr,
        )
        return 2
    print_result(c, res, steps)
    return 1 if any(not s[1] for s in steps) else 0


if __name__ == "__main__":
    sys.exit(main())
