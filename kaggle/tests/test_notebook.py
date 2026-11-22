import json
import re
from pathlib import Path

import build_notebook

KAGGLE = Path(__file__).resolve().parents[1]
NB_PATH = KAGGLE / "serve.ipynb"
GATEWAY = (
    (KAGGLE / "gateway.py").read_bytes().decode("utf-8").replace("\r\n", "\n")
)  # repo is eol=lf
WRITEFILE = "%%writefile gateway.py\n"

ORDER = ["1", "2", "3", "gateway", "5", "6", "7", "8", "9"]


def _src(cell):
    s = cell["source"]
    return s if isinstance(s, str) else "".join(s)


def _key(cell):
    src = _src(cell)
    if src.startswith(WRITEFILE):
        return "gateway"
    m = re.match(r"# \[(\d+)\] ", src)
    return m.group(1) if m else None


def _nb():
    return json.loads(NB_PATH.read_text(encoding="utf-8"))


def test_valid_nbformat4():
    nb = _nb()
    assert nb["nbformat"] == 4 and isinstance(nb["nbformat_minor"], int)
    assert "kernelspec" in nb["metadata"]
    for c in nb["cells"]:
        assert c["cell_type"] in {"code", "markdown"}
        assert isinstance(c["metadata"], dict)
        if c["cell_type"] == "code":
            assert c["outputs"] == [] and c["execution_count"] is None


def test_cell_order():
    codes = [c for c in _nb()["cells"] if c["cell_type"] == "code"]
    assert [_key(c) for c in codes] == ORDER


def test_embedded_gateway_matches_file():
    cell = next(c for c in _nb()["cells"] if _src(c).startswith(WRITEFILE))
    assert _src(cell)[len(WRITEFILE) :] == GATEWAY


def test_committed_notebook_is_fresh():
    assert _nb() == build_notebook.build()


def test_code_cells_compile():
    for c in _nb()["cells"]:
        src = _src(c)
        if c["cell_type"] == "code" and not src.startswith("%%"):
            compile(src, "<cell>", "exec")


def test_no_secret_values_printed():
    risky = re.compile(
        r"os\.environ|get_secret|AUTHTOKEN|HF_TOKEN|API_KEY|token|key", re.I
    )
    for c in _nb()["cells"]:
        src = _src(c)
        if c["cell_type"] == "code" and not src.startswith("%%"):
            for line in src.splitlines():
                assert not ("print(" in line and risky.search(line)), line
