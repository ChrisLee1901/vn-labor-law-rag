"""Tải văn bản gốc từ Công báo theo legal_docs.yaml; ghi manifest.json (code, file, url, bytes, sha256)."""
import argparse
import hashlib
import html
import json
import re
import sys
import time
import urllib.request
from urllib.parse import urlparse
from pathlib import Path

import yaml

UA = "real-rag-corpus-fetcher/0.1"
DELAY = 1.5
_HREF = re.compile(r'href="([^"]+)"')
_last = 0.0
_SIG = {"pdf": b"%PDF", "docx": b"PK\x03\x04", "doc": b"\xd0\xcf\x11\xe0"}
_HOSTS = (".chinhphu.vn", ".cdnchinhphu.vn")  # trang Công báo là dữ liệu không tin cậy


def _trusted(url: str) -> bool:
    host = urlparse(url).hostname or ""
    return host.endswith(_HOSTS)


def parse_file_links(page_html: str) -> list[str]:
    """Link file của trang Công báo: docx (g7) > doc (g7) > pdf (congbaocdn); giữ thứ tự trang trong mỗi loại."""
    out: dict[str, list[str]] = {"docx": [], "doc": [], "pdf": []}
    for raw in _HREF.findall(page_html):
        url = html.unescape(raw)
        if not _trusted(url):
            continue
        low = url.lower()
        if "download/stream" in low and "file_name=" in low:
            ext = low.rsplit(".", 1)[-1]
            if ext in ("docx", "doc"):
                out[ext].append(url)
        elif "congbaocdn" in low and low.endswith(".pdf"):
            out["pdf"].append(url)
    return out["docx"] + out["doc"] + out["pdf"]


def _get(url: str) -> bytes:
    global _last
    wait = DELAY - (time.monotonic() - _last)
    if wait > 0:
        time.sleep(wait)
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.read()
    finally:
        _last = time.monotonic()


def _sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _file_urls(doc: dict) -> list[str]:
    if doc.get("files"):
        return list(doc["files"])
    return parse_file_links(_get(doc["page"]).decode("utf-8", "replace"))


def run(docs_path: Path, out_dir: Path, manifest_path: Path) -> list[dict]:
    docs = yaml.safe_load(docs_path.read_text(encoding="utf-8"))["docs"]
    entries = []
    for doc in docs:
        code = doc["code"]
        (out_dir / code).mkdir(parents=True, exist_ok=True)
        part: dict[str, int] = {}
        urls = _file_urls(doc)
        if not urls:
            raise RuntimeError(f"{code}: không tìm thấy link tải")
        for url in urls:
            ext = url.lower().rsplit(".", 1)[-1]
            if ext not in _SIG:
                raise ValueError(f"{code}: phần mở rộng không hỗ trợ '.{ext}' ({url})")
            part[ext] = part.get(ext, 0) + 1
            name = f"{code}.part{part[ext]}.{ext}"
            path = out_dir / code / name
            data = _get(url)
            sig = {"pdf": b"%PDF", "docx": b"PK\x03\x04", "doc": b"\xd0\xcf\x11\xe0"}[ext]
            if not data.startswith(sig):
                raise RuntimeError(f"{code}: {url} is not a real .{ext}")
            digest = _sha(data)
            if not (path.exists() and _sha(path.read_bytes()) == digest):
                path.write_bytes(data)
            entries.append({"code": code, "file": f"{code}/{name}", "url": url, "bytes": len(data), "sha256": digest})
            print(f"{code}: {name} {len(data)} bytes", file=sys.stderr)
    manifest_path.write_text(json.dumps({"files": entries}, ensure_ascii=False, indent=1), encoding="utf-8")
    return entries


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--docs", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    run(a.docs, a.out, a.docs.parent / "manifest.json")


if __name__ == "__main__":
    main()
