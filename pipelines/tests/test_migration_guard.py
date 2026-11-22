import importlib.util
from pathlib import Path

import pytest

_spec = importlib.util.spec_from_file_location(
    "migration_guard",
    Path(__file__).parents[2] / "scripts" / "migration_guard.py",
)
mg = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mg)

N = "20261201000400_x.sql"
DRY = (
    f"DRY RUN: migrations will *not* be pushed.\nWould push these migrations:\n • {N}\n"
)


def run(tmp_path, sql, dry=DRY):
    (tmp_path / N).write_text(sql, encoding="utf-8")
    f = tmp_path / "dry.txt"
    f.write_text(dry, encoding="utf-8")
    return mg.main([str(f), "--migrations", str(tmp_path)])


@pytest.mark.parametrize(
    "sql",
    [
        "drop table feedback;",
        "ALTER TABLE chunks\n  DROP   COLUMN fts;",
        "truncate chunks;",
        "Delete  From articles where true;",
    ],
)
def test_destructive_sql_fails(tmp_path, capsys, sql):
    assert run(tmp_path, sql) == 1
    assert N in capsys.readouterr().out


def test_additive_and_commented_sql_passes(tmp_path):
    sql = "-- drop table x\n/* truncate y;\n delete from z */\nalter table a add column b int;"
    assert run(tmp_path, sql) == 0


def test_override_marker_allows(tmp_path):
    assert run(tmp_path, "-- allow-destructive: bỏ cột thử nghiệm\ndrop table t;") == 0
    assert run(tmp_path, "-- allow-destructive:\ndrop table t;") == 1


def test_up_to_date_has_nothing_to_check(tmp_path):
    assert run(tmp_path, "drop table t;", dry="Remote database is up to date.\n") == 0


def test_unparseable_would_push_fails_closed(tmp_path):
    assert run(tmp_path, "select 1;", dry="Would push these migrations:\n") == 1


def test_unrecognized_wording_fails_closed(tmp_path, capsys):
    assert run(tmp_path, "drop table t;", dry="Nothing to see here.\n") == 1
    assert "Không nhận ra" in capsys.readouterr().out


def test_parsed_and_clean_passes(tmp_path):
    assert run(tmp_path, "alter table a add column b int;") == 0


def test_existing_migrations_are_clean():
    root = Path(__file__).parents[2] / "supabase" / "migrations"
    dry = "Would push these migrations:\n" + "\n".join(
        f" • {f.name}" for f in root.glob("*.sql")
    )
    assert mg.check(dry, root) == []
