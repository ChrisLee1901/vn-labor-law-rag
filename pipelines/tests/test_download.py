from pathlib import Path

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
