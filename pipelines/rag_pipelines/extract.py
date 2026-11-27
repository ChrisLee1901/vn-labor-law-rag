"""Trích text từ corpus: DOCX (đã chuyển) > DOCX gốc > PDF có text layer; bỏ header Công báo, NFC, giữ ngắt dòng."""

import re
import shutil
import subprocess
import unicodedata
from pathlib import Path

import pymupdf
from docx import Document
from docx.table import Table
from docx.text.paragraph import Paragraph


def _corpus_dir() -> Path:
    for p in Path(__file__).resolve().parents:
        if (p / "docs" / "corpus").is_dir():
            return p / "docs" / "corpus"
    raise FileNotFoundError("docs/corpus not found above " + __file__)


_CONGBAO = re.compile(
    r"^\s*CÔNG\s*BÁO\s*/\s*Số\s*[\d\s+,.\-]+/\s*Ngày\s*[\d\s\-./]+$", re.I
)
_CONTINUED = re.compile(
    r"^\s*\(\s*(Xem\s+)?tiếp\s+theo\s+Công\s+báo\s+số\b[^)]*\)\s*$", re.I
)
_PAGENO = re.compile(r"^\s*\d{1,4}\s*$")
# Con dấu chữ ký số của PDF Công báo: khối bắt đầu bằng "Ký bởi:"/"Người ký:" rồi các dòng thuộc tính.
_SIG_START = re.compile(r"^\s*(Ký bởi|Người ký)\s*:", re.I)
_SIG_FIELD = re.compile(r"^\s*(Email|Cơ quan|Thời gian ký|Ngày ký)\s*:", re.I)


def strip_congbao_headers(text: str, page_numbers: bool = True) -> str:
    """Bỏ header Công báo, khối chữ ký số và (tùy chọn) dòng chỉ gồm số trang. Không đụng thân văn bản."""
    out, in_sig = [], False
    for line in unicodedata.normalize("NFC", text).split(
        "\n"
    ):  # NFC trước để regex khớp cả đầu vào NFD
        if _SIG_START.match(line):
            in_sig = True
            continue
        if _SIG_FIELD.match(line) and (
            in_sig or line.lstrip().lower().startswith(("thời gian ký", "ngày ký"))
        ):
            continue
        in_sig = False
        if (
            _CONGBAO.match(line)
            or _CONTINUED.match(line)
            or (page_numbers and _PAGENO.match(line))
        ):
            continue
        out.append(line.rstrip())
    return re.sub(r"\n{3,}", "\n\n", "\n".join(out)).strip("\n")


def _docx_text(path: Path) -> str:
    doc = Document(str(path))
    lines = []
    for el in doc.element.body.iterchildren():
        if el.tag.endswith("}p"):
            lines.append(Paragraph(el, doc).text)
        elif el.tag.endswith("}tbl"):
            for row in Table(el, doc).rows:
                seen, cells = set(), []
                for c in row.cells:  # ô gộp trả về cùng một _tc
                    if id(c._tc) not in seen:
                        seen.add(id(c._tc))
                        cells.append(c.text.replace("\n", " ").strip())
                lines.append(" | ".join(cells))
    return strip_congbao_headers("\n".join(lines), page_numbers=False)


def _page_trim_numbers(page_text: str) -> str:
    """Bỏ số trang chỉ ở 3 dòng đầu/cuối mỗi trang (tránh xóa số thứ tự trong bảng)."""
    lines = page_text.split("\n")
    idx = [i for i, ln in enumerate(lines) if ln.strip()]
    edge = set(idx[:3] + idx[-3:])
    return "\n".join(
        ln for i, ln in enumerate(lines) if not (i in edge and _PAGENO.match(ln))
    )


def _pdf_text(path: Path) -> str:
    with pymupdf.open(str(path)) as pdf:
        pages = [_page_trim_numbers(p.get_text()) for p in pdf]
    return strip_congbao_headers("\n".join(pages), page_numbers=False)


def _sources(code: str) -> list[Path]:
    """Mỗi part: docx đã chuyển > docx gốc > pdf; sắp theo số part."""
    corpus = _corpus_dir()
    raw, conv = corpus / "raw" / code, corpus / "docx"
    pat = re.compile(rf"^{re.escape(code)}\.part(\d+)\.(docx|doc|pdf)$")
    parts = {
        int(m.group(1))
        for d in (raw, conv)
        if d.is_dir()
        for f in d.iterdir()
        if (m := pat.match(f.name))
    }
    if not parts:
        raise FileNotFoundError(f"no source files for {code}")
    out = []
    for n in sorted(parts):
        name = f"{code}.part{n}"
        cand = [conv / f"{name}.docx", raw / f"{name}.docx", raw / f"{name}.pdf"]
        src = next((c for c in cand if c.is_file()), None)
        if src is None:
            raise FileNotFoundError(
                f"{name}: only .doc available; run convert_docs() (needs soffice) or provide a PDF"
            )
        out.append(src)
    return out


def extract_text(code: str) -> str:
    texts = [
        _docx_text(p) if p.suffix == ".docx" else _pdf_text(p) for p in _sources(code)
    ]
    return unicodedata.normalize("NFC", "\n".join(texts))


def convert_docs() -> list[Path]:
    """Tùy chọn: .doc -> docs/corpus/docx/*.docx bằng LibreOffice nếu có `soffice`; không có thì bỏ qua."""
    soffice = shutil.which("soffice")
    if not soffice:
        print(
            "soffice not found: skipping .doc conversion (extract_text falls back to PDF)"
        )
        return []
    corpus = _corpus_dir()
    outdir = corpus / "docx"
    outdir.mkdir(exist_ok=True)
    done = []
    for f in sorted((corpus / "raw").glob("*/*.doc")):
        subprocess.run(
            [
                soffice,
                "--headless",
                "--convert-to",
                "docx",
                "--outdir",
                str(outdir),
                str(f),
            ],
            check=True,
        )
        done.append(outdir / (f.stem + ".docx"))
    return done


if __name__ == "__main__":
    convert_docs()
