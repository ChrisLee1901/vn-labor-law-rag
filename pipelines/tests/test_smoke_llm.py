"""Tests for scripts/smoke_llm.py against an in-process fake gateway (same response shapes as kaggle/gateway.py)."""

import importlib.util
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

_spec = importlib.util.spec_from_file_location(
    "smoke_llm", Path(__file__).parents[2] / "scripts" / "smoke_llm.py"
)
smoke = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(smoke)

KEY = "k-test-secret"
ANSWER = "Mức lương tối thiểu vùng I là mức lương thấp nhất mà người sử dụng lao động phải trả cho người lao động."


def make_handler(cfg):
    class H(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.0"  # body ends at connection close

        def log_message(self, *a):
            pass

        def _json(self, code, obj):
            body = json.dumps(obj, ensure_ascii=False).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):  # /health needs no auth, like the real gateway
            self._json(200, cfg["health"])

        def do_POST(self):
            if self.headers.get("Authorization") != f"Bearer {KEY}":
                return self._json(401, {"detail": "unauthorized"})
            req = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            cfg["last_chat"] = req if self.path.endswith("/chat/completions") else None
            if self.path == "/v1/embeddings":
                vecs = [
                    [float((ord(t[0]) + j) % 7) for j in range(cfg["dim"])]
                    for t in req["input"]
                ]
                return self._json(
                    200,
                    {
                        "data": [
                            {"index": i, "embedding": v} for i, v in enumerate(vecs)
                        ]
                    },
                )
            if self.path == "/v1/rerank":
                words = req["query"].lower().split()
                scores = [
                    sum(w in d.lower() for w in words) / len(words)
                    for d in req["documents"]
                ]
                if cfg["rerank_wrong"]:
                    scores = [1 - s for s in scores]
                order = sorted(range(len(scores)), key=lambda i: -scores[i])
                return self._json(
                    200,
                    {
                        "results": [
                            {"index": i, "relevance_score": 0.05 + 0.9 * scores[i]}
                            for i in order
                        ]
                    },
                )
            if self.path == "/v1/chat/completions":
                return self._chat()
            self._json(404, {"detail": "nope"})

        def _chat(self):
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.end_headers()

            def send(obj):
                data = (
                    obj if isinstance(obj, str) else json.dumps(obj, ensure_ascii=False)
                )
                self.wfile.write(f"data: {data}\n\n".encode())
                self.wfile.flush()

            send({"choices": [{"delta": {"role": "assistant", "content": None}}]})
            words = cfg["answer"].split(" ")
            for n, w in enumerate(words):
                send(
                    {
                        "choices": [
                            {
                                "delta": {
                                    "content": w + (" " if n < len(words) - 1 else "")
                                }
                            }
                        ]
                    }
                )
                time.sleep(
                    0.003
                )  # realistic gap between tokens; Windows clocks are coarse
                if cfg["cut"] and n == 3:
                    return  # close without [DONE]
            send({"choices": [{"delta": {}, "finish_reason": "stop"}]})
            if cfg["usage"]:
                send({"choices": [], "usage": {"completion_tokens": 42}})
            send("[DONE]")

    return H


@pytest.fixture
def serve(monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", KEY)
    servers = []

    def start(**over):
        cfg = {
            "health": {
                "status": "ok",
                "llm": True,
                "embedder": True,
                "reranker": True,
                "model": "Qwen3-8B-Q5_K_M",
            },
            "dim": 1024,
            "rerank_wrong": False,
            "answer": ANSWER,
            "usage": True,
            "cut": False,
        } | over
        srv = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(cfg))
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        servers.append(srv)
        monkeypatch.setenv("LLM_BASE_URL", f"http://127.0.0.1:{srv.server_port}")
        return cfg

    yield start
    for s in servers:
        s.shutdown()


def run(capsys, *extra):
    code = smoke.main(["--runs", "2", "--timeout", "10", *extra])
    cap = capsys.readouterr()
    return code, cap.out, cap.err


# ---- pure helpers ----


def test_percentile_and_toks_math():
    assert smoke.percentile([3, 1, 2], 50) == 2
    assert smoke.percentile([1, 2, 3, 4], 50) == 2.5
    assert smoke.percentile([1, 2, 3], 95) == pytest.approx(2.9)
    assert smoke.percentile([5], 95) == 5
    assert smoke.tok_per_s(100, total_s=5.0, ttft_s=1.0) == pytest.approx(25.0)
    assert smoke.tok_per_s(100, total_s=1.0, ttft_s=1.0) is None
    assert smoke.tok_per_s(0, total_s=5.0, ttft_s=1.0) is None


def test_check_text_cases():
    assert smoke.check_text(ANSWER) == ([], [])
    assert any("rỗng" in f for f in smoke.check_text("  ")[0])
    assert any(
        "dấu" in f for f in smoke.check_text("Muc luong toi thieu vung I la gi")[0]
    )
    assert any(
        "think" in f for f in smoke.check_text("<think>\n</think>\n" + ANSWER)[0]
    )
    assert any("U+FFFD" in f for f in smoke.check_text(ANSWER + " �")[0])
    assert any("mojibake" in f for f in smoke.check_text("Má»©c lÆ°Æ¡ng Ä‘á»“ng")[0])
    assert any("mojibake" in f for f in smoke.check_text("Ã¡ Ã  " + ANSWER)[0])


def test_check_text_nfd_is_noted_not_failed():
    import unicodedata

    fails, notes = smoke.check_text(unicodedata.normalize("NFD", ANSWER))
    assert fails == [] and notes == ["không NFC"]


def test_mask_and_url_warning():
    assert (
        smoke.mask_url("https://abc-def.ngrok-free.dev")
        == "https://abc***.ngrok-free.dev"
    )
    assert smoke.mask_url("http://127.0.0.1:8000") == "http://127.0.0.1:8000"
    assert smoke.url_warning("https://abc-def.ngrok-free.dev") is None
    assert smoke.url_warning("http://localhost:8000") is None
    assert "offline" in smoke.url_warning("https://example.com")


# ---- end to end against the fake gateway ----


def test_ok_path_prints_result_block(serve, capsys):
    cfg = serve()
    code, out, err = run(capsys)
    assert code == 0, out + err
    assert "=== RESULT smoke_llm" in out and "verdict: PASS" in out
    assert "host: http://127.0.0.1:" in out
    assert "dims=[1024, 1024]" in out and "order=[1," in out
    assert "| run | TTFT (s) |" in out and "| 2 |" in out
    assert "ttft_s: p50=" in out and "p95=" in out and "tok_per_s: median=" in out
    assert "model=Qwen3-8B-Q5_K_M" in out and "timestamp_utc:" in out
    assert "answer_run1: Mức lương tối thiểu vùng I" in out
    assert "usage" in out
    assert KEY not in out + err
    # same request shape as the backend: messages + stream + bounded max_tokens, no thinking params
    body = cfg["last_chat"]
    assert body["stream"] is True and body["max_tokens"] == smoke.CHAT_MAX_TOKENS
    assert [m["role"] for m in body["messages"]] == ["system", "user"]
    assert "chat_template_kwargs" not in body


def test_wrong_key_exits_2_with_hint(serve, capsys, monkeypatch):
    serve()
    monkeypatch.setenv("LLM_API_KEY", "wrong-key-xyz")
    code, out, err = run(capsys)
    assert code == 2 and "LLM_API_KEY" in err
    assert "wrong-key-xyz" not in out + err and KEY not in out + err


def test_usage_absent_labels_chunk_count(serve, capsys):
    serve(usage=False)
    code, out, _ = run(capsys)
    assert code == 0 and "xấp xỉ theo số chunk" in out and "| usage |" not in out


def test_health_llm_down_fails(serve, capsys):
    serve(
        health={
            "status": "loading",
            "llm": False,
            "embedder": True,
            "reranker": True,
            "model": "",
        }
    )
    code, out, _ = run(capsys)
    assert code == 1 and "a_health: FAIL" in out and "llm=False" in out


def test_embedding_dim_768_fails(serve, capsys):
    serve(dim=768)
    code, out, _ = run(capsys)
    assert code == 1 and "b_embeddings: FAIL" in out and "768" in out and "1024" in out


def test_rerank_wrong_order_fails(serve, capsys):
    serve(rerank_wrong=True)
    code, out, _ = run(capsys)
    assert code == 1 and "c_rerank: FAIL" in out and "xếp thứ" in out


@pytest.mark.parametrize(
    ("answer", "needle"),
    [
        ("Muc luong toi thieu vung I la muc luong thap nhat", "dấu"),
        ("<think> ... </think> " + ANSWER, "think"),
        (ANSWER + " �", "U+FFFD"),
        ("Má»©c lÆ°Æ¡ng tá»‘i thiá»ƒu vÃ¹ng I", "mojibake"),
    ],
)
def test_bad_answers_fail(serve, capsys, answer, needle):
    serve(answer=answer)
    code, out, _ = run(capsys)
    assert code == 1 and "d_chat: FAIL" in out and needle in out


def test_ttft_over_threshold_fails(serve, capsys, monkeypatch):
    serve()
    monkeypatch.setattr(smoke, "TTFT_P50_MAX_S", 1e-9)  # any real TTFT exceeds it
    code, out, _ = run(capsys)
    assert code == 1 and "e_ttft_p50: FAIL" in out and "d_chat: PASS" in out


def test_stream_cut_without_done_fails(serve, capsys):
    serve(cut=True)
    code, out, _ = run(capsys)
    assert code == 1 and "d_chat: FAIL" in out and "[DONE]" in out


def test_low_toks_only_warns(serve, capsys, monkeypatch):
    serve()
    monkeypatch.setattr(smoke, "TOKS_WARN_BELOW", 1e12)
    code, out, _ = run(capsys)
    assert code == 0 and "WARN: tok/s median" in out


def test_usage_and_connection_errors(monkeypatch, capsys):
    monkeypatch.delenv("LLM_BASE_URL", raising=False)
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    assert smoke.main([]) == 2
    monkeypatch.setenv("LLM_BASE_URL", "http://127.0.0.1:9")
    monkeypatch.setenv("LLM_API_KEY", KEY)
    assert smoke.main([]) == 2
    assert KEY not in capsys.readouterr().err
