from pathlib import Path

import pytest

from rag_pipelines import download
from rag_pipelines.download import parse_file_links

FIXTURE = Path(__file__).parent / "fixtures" / "congbao_page.html"


def test_parse_file_links_prefers_docx_then_doc_then_pdf():
    links = parse_file_links(FIXTURE.read_text(encoding="utf-8"))
    assert links, "no links parsed"
    assert "file_name=" in links[0] and links[0].lower().endswith(".docx")
    assert "&amp;" not in links[0]
    pdfs = [u for u in links if u.lower().endswith(".pdf")]
    assert pdfs and all("congbaocdn" in u for u in pdfs)
    exts = [u.lower().rsplit(".", 1)[1] for u in links]
    assert exts == sorted(exts, key=["docx", "doc", "pdf"].index)


PDF = b"%PDF-1.4 x"


def _yaml(tmp_path, doc: str) -> Path:
    p = tmp_path / "legal_docs.yaml"
    p.write_text("docs:\n" + doc, encoding="utf-8")
    return p


def test_parse_file_links_drops_foreign_hosts():
    html = (
        '<a href="https://evil.example.com/api/download/stream?Url=x&amp;file_name=a.docx">x</a>'
        '<a href="https://evil.example.com/a.pdf">x</a>'
        '<a href="https://g7.cdnchinhphu.vn/api/download/stream?Url=x&amp;file_name=a.doc">ok</a>'
    )
    assert download.parse_file_links(html) == [
        "https://g7.cdnchinhphu.vn/api/download/stream?Url=x&file_name=a.doc"
    ]


def test_run_raises_when_no_links(tmp_path, monkeypatch):
    monkeypatch.setattr(download, "_get", lambda url: b"<html></html>")
    y = _yaml(tmp_path, "  - {code: X1, page: 'https://congbao.chinhphu.vn/p'}\n")
    with pytest.raises(RuntimeError, match="X1: không tìm thấy link tải"):
        download.run(y, tmp_path / "raw", tmp_path / "m.json")


def test_run_rejects_unexpected_extension(tmp_path, monkeypatch):
    monkeypatch.setattr(download, "_get", lambda url: b"x")
    y = _yaml(
        tmp_path, "  - {code: X2, files: ['https://datafiles.chinhphu.vn/a.zip']}\n"
    )
    with pytest.raises(ValueError, match="zip"):
        download.run(y, tmp_path / "raw", tmp_path / "m.json")


def test_run_skips_rewrite_when_sha_matches(tmp_path, monkeypatch):
    monkeypatch.setattr(download, "_get", lambda url: PDF)
    y = _yaml(
        tmp_path, "  - {code: X3, files: ['https://datafiles.chinhphu.vn/a.pdf']}\n"
    )
    download.run(y, tmp_path / "raw", tmp_path / "m.json")
    f = tmp_path / "raw" / "X3" / "X3.part1.pdf"
    f.write_bytes(PDF)  # same bytes
    import os

    os.utime(f, ns=(1_000_000_000, 1_000_000_000))
    download.run(y, tmp_path / "raw", tmp_path / "m.json")
    assert f.stat().st_mtime_ns == 1_000_000_000
