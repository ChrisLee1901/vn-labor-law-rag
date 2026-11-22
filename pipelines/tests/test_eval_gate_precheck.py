import importlib.util
from pathlib import Path

import pytest

_spec = importlib.util.spec_from_file_location(
    "eval_gate_precheck",
    Path(__file__).parents[2] / "scripts" / "eval_gate_precheck.py",
)
pc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(pc)


@pytest.fixture(autouse=True)
def _clean_github_env(monkeypatch):
    """Runner đặt GITHUB_BASE_REF/GITHUB_OUTPUT cho mọi step của PR; test tự đặt lại thứ nó cần."""
    monkeypatch.delenv("GITHUB_BASE_REF", raising=False)
    monkeypatch.delenv("GITHUB_OUTPUT", raising=False)


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


def _base_repo(root: Path, *rels: str) -> None:
    """Throwaway repo whose `origin/main` holds `rels`; the working tree is then the PR head."""
    import subprocess

    _touch(root, *rels)
    for a in (
        ["init", "-q"],
        ["add", "-A"],
        [
            "-c",
            "user.name=t",
            "-c",
            "user.email=t@t",
            "-c",
            "commit.gpgsign=false",
            "commit",
            "-q",
            "--allow-empty",
            "-m",
            "base",
        ],
        ["update-ref", "refs/remotes/origin/main", "HEAD"],
    ):
        subprocess.run(["git", "-C", str(root), *a], check=True, capture_output=True)


def _run(tmp_path, monkeypatch, base="main"):
    out = tmp_path / "out"
    monkeypatch.setenv("GITHUB_OUTPUT", str(out))
    if base:
        monkeypatch.setenv("GITHUB_BASE_REF", base)
    else:
        monkeypatch.delenv("GITHUB_BASE_REF", raising=False)
    code = pc.main(["--root", str(tmp_path), "--comment", str(tmp_path / "c.md")])
    return code, out.read_text()


def test_pr_deleting_baseline_that_base_has_fails(tmp_path, monkeypatch, capsys):
    monkeypatch.delenv("GITHUB_OUTPUT", raising=False)
    _base_repo(tmp_path, pc.BASELINE)
    (tmp_path / pc.BASELINE).unlink()
    assert _run(tmp_path, monkeypatch) == (1, "active=false\n")
    assert "deleted in this PR" in capsys.readouterr().out


def test_pr_deleting_index_that_base_has_fails(tmp_path, monkeypatch):
    monkeypatch.delenv("GITHUB_OUTPUT", raising=False)
    _base_repo(tmp_path, "eval/index/v1.parquet")
    (tmp_path / "eval/index/v1.parquet").unlink()
    assert _run(tmp_path, monkeypatch) == (1, "active=false\n")


def test_pr_emptying_baseline_fails(tmp_path, monkeypatch):
    monkeypatch.delenv("GITHUB_OUTPUT", raising=False)
    _base_repo(tmp_path, pc.BASELINE)
    (tmp_path / pc.BASELINE).write_text("")
    assert _run(tmp_path, monkeypatch) == (1, "active=false\n")


def test_base_and_head_lack_baseline_is_inactive(tmp_path, monkeypatch):
    monkeypatch.delenv("GITHUB_OUTPUT", raising=False)
    _base_repo(tmp_path, "README.md")
    assert _run(tmp_path, monkeypatch) == (0, "active=false\n")


def test_base_and_head_have_everything_is_active(tmp_path, monkeypatch):
    monkeypatch.delenv("GITHUB_OUTPUT", raising=False)
    _base_repo(tmp_path, pc.BASELINE, *pc.REQUIRED)
    (tmp_path / pc.BASELINE).write_text("{}")
    _base_repo_json = _run(tmp_path, monkeypatch)
    assert _base_repo_json == (0, "active=true\n")


def test_no_base_ref_keeps_old_behaviour(tmp_path, monkeypatch):
    monkeypatch.delenv("GITHUB_OUTPUT", raising=False)
    _base_repo(
        tmp_path, pc.BASELINE
    )  # base has it, but with no base ref the check is skipped
    (tmp_path / pc.BASELINE).unlink()
    assert _run(tmp_path, monkeypatch, base=None) == (0, "active=false\n")


def test_unfetched_base_ref_fails_closed(tmp_path, monkeypatch):
    monkeypatch.delenv("GITHUB_OUTPUT", raising=False)
    _base_repo(tmp_path, "README.md")
    assert _run(tmp_path, monkeypatch, base="nope")[0] == 1
