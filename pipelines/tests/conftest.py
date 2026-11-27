import os
import pathlib
import uuid

import psycopg
import pytest
from psycopg import conninfo, sql

BASE_URL = os.environ.get(
    "TEST_DATABASE_URL", "postgresql://postgres:postgres@localhost:54329/postgres"
)
MIGRATIONS = sorted(
    (pathlib.Path(__file__).parents[2] / "supabase" / "migrations").glob("*.sql")
)


@pytest.fixture(scope="session")
def db_url():
    """Throwaway database with all migrations applied (needs `bash scripts/test-db.sh`); skipped if unreachable."""
    name = f"rag_pipe_test_{uuid.uuid4().hex[:8]}"
    try:
        admin = psycopg.connect(BASE_URL, autocommit=True, connect_timeout=3)
    except psycopg.OperationalError as e:
        pytest.skip(f"test database unavailable: {e}")
    with admin:
        admin.execute(sql.SQL("create database {}").format(sql.Identifier(name)))
        try:
            info = conninfo.conninfo_to_dict(BASE_URL)
            info["dbname"] = name
            url = conninfo.make_conninfo(**info)
            with psycopg.connect(url, autocommit=True) as c:
                for f in MIGRATIONS:
                    c.execute(f.read_text(encoding="utf-8"))
            yield url
        finally:
            admin.execute(
                sql.SQL("drop database if exists {} with (force)").format(
                    sql.Identifier(name)
                )
            )


@pytest.fixture
def conn(db_url):
    """Clean tables and active_index_version=1 for every test."""
    with psycopg.connect(db_url, autocommit=True) as c:
        c.execute("truncate chunks, legal_refs, articles, legal_docs cascade")
        c.execute(
            "insert into app_config(key, value) values ('active_index_version', '1') on conflict (key) do update set value = excluded.value"
        )
        yield c
