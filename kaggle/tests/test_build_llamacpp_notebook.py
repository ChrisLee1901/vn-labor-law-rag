import ast
import json
import re
from pathlib import Path

import pytest

NB_PATH = Path(__file__).resolve().parents[1] / "build_llamacpp.ipynb"
HELPERS = "# [1] config + pure helpers"


def _src(cell):
    s = cell["source"]
    return s if isinstance(s, str) else "".join(s)


def _nb():
    return json.loads(NB_PATH.read_text(encoding="utf-8"))


def _codes():
    return [_src(c) for c in _nb()["cells"] if c["cell_type"] == "code"]


def _all_text():
    return "\n".join(_src(c) for c in _nb()["cells"])


def _strip_magics(src):
    return "\n".join(
        "" if ln.lstrip().startswith(("!", "%")) else ln for ln in src.splitlines()
    )


def test_valid_nbformat45_no_outputs_stable_ids():
    nb = _nb()
    assert nb["nbformat"] == 4 and nb["nbformat_minor"] >= 5
    assert "kernelspec" in nb["metadata"]
    ids = [c["id"] for c in nb["cells"]]
    assert len(ids) == len(set(ids)) and all(
        re.fullmatch(r"[a-z0-9-]+", i) for i in ids
    )
    for c in nb["cells"]:
        assert c["cell_type"] in {"code", "markdown"} and isinstance(
            c["metadata"], dict
        )
        if c["cell_type"] == "code":
            assert c["outputs"] == [] and c["execution_count"] is None
    assert any(
        _src(c).startswith("#") for c in nb["cells"] if c["cell_type"] == "markdown"
    )


def test_code_cells_parse():
    for src in _codes():
        ast.parse(_strip_magics(src))


def test_required_content():
    text = _all_text()
    assert "-DGGML_CUDA=ON -DCMAKE_CUDA_ARCHITECTURES=75" in text
    assert "llamacpp-sm75-bin" in text and "qwen3-8b-gguf" in text
    assert re.search(r"^PASS_TG_TPS = 15\b", text, re.M)
    assert "<KAGGLE_USERNAME>/llamacpp-sm75-bin" in text
    assert "<KAGGLE_USERNAME>/qwen3-8b-gguf" in text
    assert "Qwen3-8B-Q5_K_M.gguf" in text and "Qwen3-8B-Q4_K_M.gguf" in text


def test_ref_pinned_or_flagged():
    m = re.search(r'^LLAMA_CPP_REF = "([^"]+)"', _all_text(), re.M)
    assert m
    if m.group(1) == "master":
        assert "UNPINNED" in _all_text()
    else:
        assert re.fullmatch(r"b\d+", m.group(1))


def test_no_secrets_username_or_keepalive():
    text = _all_text()
    assert not re.search(
        r"hf_[A-Za-z0-9]{20,}|ngrok|[A-Za-z0-9]{40,}",
        text.replace("f5e6915c28f10330885fcb9243a93ae98d3115ab", ""),
    )
    assert "chrislee" not in text.lower()
    for bad in ("while True", "time.sleep", "sleep(", "nohup", "Popen"):
        assert bad not in text, bad
    risky = re.compile(r"os\.environ|get_secret|token|key", re.I)
    for src in _codes():
        for line in src.splitlines():
            assert not ("print(" in line and risky.search(line)), line


@pytest.fixture(scope="module")
def helpers():
    cell = next(s for s in _codes() if s.startswith(HELPERS))
    ns = {}
    exec(compile(cell, "<helpers>", "exec"), ns)
    return ns


def test_parse_bench(helpers):
    out = (
        "ggml_cuda_init: found 1 CUDA devices\n"
        '[\n  {"n_prompt": 4096, "n_gen": 0, "avg_ts": 812.5, "samples_ts": [1, 2]},\n'
        '  {"n_prompt": 0, "n_gen": 256, "avg_ts": 31.25, "samples_ts": [3, 4]}\n]\n'
    )
    assert helpers["parse_bench"](out) == (812.5, 31.25)
    assert helpers["parse_bench"]("oom") == (None, None)


def test_parse_ldd(helpers):
    out = (
        "\tlibllama.so.0 => /x/bin/libllama.so.0 (0x00007f)\n"
        "\tlibcuda.so.1 => not found\n"
        "\tlinux-vdso.so.1 (0x00007ffc)\n"
    )
    assert helpers["parse_ldd"](out) == (
        {"libllama.so.0": "/x/bin/libllama.so.0"},
        ["libcuda.so.1"],
    )


def test_check_flags(helpers):
    text = (
        "-c,    --ctx-size N   size of context\n"
        "-fa,   --flash-attn [on|off|auto]   set Flash Attention use\n"
        "--jinja   use jinja\n"
        "--host HOST   ip\n"
    )
    got = helpers["check_flags"](text)
    assert (
        got["--jinja"]
        and got["-c"]
        and got["-fa"]
        and got["--flash-attn"]
        and got["--host"]
    )
    assert not got["--api-key"] and not got["-np"] and not got["--reasoning-budget"]
    assert helpers["help_line"](text, "--flash-attn").startswith("-fa,")


def test_ld_library_path_keeps_original():
    # serve.ipynb prepends to Kaggle's own LD_LIBRARY_PATH; the spike must test the same thing,
    # so the assigned VALUE (text after the assignment) must reference os.environ
    values = [
        m.group(1)
        for src in _codes()
        for m in re.finditer(r"LD_LIBRARY_PATH\"?\s*[=:]\s*(.*)", src)
    ]
    assert len(values) >= 3
    for v in values:
        assert "os.environ" in v, v


def test_configure_gets_stub_dir_and_runtime_never_does():
    build = next(s for s in _codes() if s.startswith("# [4]"))
    # discovered before configure, passed to configure always, retry variant for cuda_driver
    assert 'f"-DCMAKE_LIBRARY_PATH={stub_dir}"' in build
    assert build.index("glob.glob") < build.index('"cmake", "-B"')
    assert "libcuda.so" in build and "targets" in build
    assert "CUDA_cuda_driver_LIBRARY" in build and "cuda_driver" in build
    # configure errors must not raise before the retry
    assert build.count("check=False") >= 2
    # package + later cells (runtime) never put the stub on LD_LIBRARY_PATH, and assert it does not leak
    runtime = "\n".join(
        s for s in _codes() if s.startswith(("# [5]", "# [7]", "# [8]"))
    )
    for line in runtime.splitlines():
        if "LD_LIBRARY_PATH" in line:
            assert "stub" not in line, line
    assert '"stubs" in x' in runtime
