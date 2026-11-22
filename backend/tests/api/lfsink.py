"""Langfuse giả chạy trên loopback: nhận OTLP/protobuf (span) và POST /api/public/scores đúng như SDK thật gửi.

SDK dùng `requests` cho OTLP nên respx không chặn được; server thật trên 127.0.0.1 giữ nguyên đường code của SDK.
"""

import gzip
import json
import threading
import time
import zlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from opentelemetry.proto.collector.trace.v1.trace_service_pb2 import (
    ExportTraceServiceRequest,
)

SPAN_ATTR = "langfuse.observation."


def _value(v) -> str:
    return v.string_value  # mọi attribute Langfuse cần kiểm là chuỗi


class LangfuseSink:
    def __init__(self, status: int = 200, delay: float = 0.0):
        self.status, self.delay = status, delay
        self.raw: list[bytes] = []  # mọi byte nhận được (để dò PII)
        self.spans: list[dict] = []
        self.scores: list[dict] = []
        sink = self

        class H(BaseHTTPRequestHandler):
            def do_POST(self):
                body = self.rfile.read(int(self.headers.get("content-length", 0)))
                enc = self.headers.get("content-encoding")
                if enc == "gzip":
                    body = gzip.decompress(body)
                elif enc == "deflate":
                    body = zlib.decompress(body)
                if sink.delay:
                    time.sleep(sink.delay)
                sink.raw.append(body)
                if sink.status == 200:
                    sink._ingest(self.path, body)
                self.send_response(sink.status)
                self.send_header("content-type", "application/json")
                self.end_headers()
                self.wfile.write(b"{}")

            def log_message(self, format, *args):
                pass

        self._srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
        self._srv.daemon_threads = True
        threading.Thread(target=self._srv.serve_forever, daemon=True).start()
        self.host = f"http://127.0.0.1:{self._srv.server_port}"

    def _ingest(self, path: str, body: bytes) -> None:
        if path.endswith("/otel/v1/traces"):
            req = ExportTraceServiceRequest()
            req.ParseFromString(body)
            for rs in req.resource_spans:
                for ss in rs.scope_spans:
                    for sp in ss.spans:
                        attrs = {a.key: _value(a.value) for a in sp.attributes}
                        self.spans.append(
                            {
                                "name": sp.name,
                                "trace_id": sp.trace_id.hex(),
                                "start": sp.start_time_unix_nano,
                                "end": sp.end_time_unix_nano,
                                "metadata": {
                                    k.removeprefix(SPAN_ATTR + "metadata."): json.loads(
                                        v
                                    )
                                    for k, v in attrs.items()
                                    if k.startswith(SPAN_ATTR + "metadata.")
                                },
                                "level": attrs.get(SPAN_ATTR + "level"),
                                "attrs": attrs,
                            }
                        )
        elif path.endswith("/api/public/scores"):
            self.scores += json.loads(body)

    def wait_for(self, pred, timeout: float = 5.0) -> bool:
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            if pred():
                return True
            time.sleep(0.02)
        return False

    @property
    def raw_text(self) -> str:
        return b"\n".join(self.raw).decode("utf-8", "replace")

    def close(self) -> None:
        self._srv.shutdown()
