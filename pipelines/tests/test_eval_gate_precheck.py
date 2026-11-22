import importlib.util
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "eval_gate_precheck",
    Path(__file__).parents[2] / "scripts" / "eval_gate_precheck.py",
)
pc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(pc)


def _touch(root: Path, *rels: str) -> None:
    for r in rels:
        (root / r).parent.mkdir(parents=True, exist_ok=True)
        (root / r).write_text("x")


def test_no_baseline_is_inactive_with_warning(tmp_path, capsys):
    c = tmp_path / "c.md"
    assert pc.main(["--root", str(tmp_path), "--comment", str(c)]) == 0
    assert "::warning" in capsys.readouterr().out
    assert "Gate inactive: no frozen baseline committed yet" in c.read_text(
        encoding="utf-8"
    )


def test_baseline_without_artefacts_fails(tmp_path, capsys):
    _touch(tmp_path, pc.BASELINE)
    c = tmp_path / "c.md"
    assert pc.main(["--root", str(tmp_path), "--comment", str(c)]) == 1
    assert "eval/index/v1.parquet" in c.read_text(encoding="utf-8")
    assert "::error" in capsys.readouterr().out


def test_all_present_is_active(tmp_path, monkeypatch):
    _touch(tmp_path, pc.BASELINE, *pc.REQUIRED)
    out = tmp_path / "out"
    monkeypatch.setenv("GITHUB_OUTPUT", str(out))
    assert pc.main(["--root", str(tmp_path)]) == 0
    assert out.read_text() == "active=true\n"
