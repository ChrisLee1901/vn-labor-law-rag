import asyncio
import os
import pathlib
import sys
import uuid

import psycopg
import pytest
import pytest_asyncio
from psycopg import conninfo, sql

# psycopg async needs a selector loop; the default Proactor loop on Windows does not work.
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

BASE_URL = os.environ.get(
    "TEST_DATABASE_URL", "postgresql://postgres:postgres@localhost:54329/postgres"
)
MIGRATIONS = sorted(
    (pathlib.Path(__file__).parents[2] / "supabase" / "migrations").glob("*.sql")
)


@pytest.fixture(scope="session")
def db_url():
    """Throwaway database with all migrations applied (needs `bash scripts/test-db.sh`)."""
    name = f"rag_api_test_{uuid.uuid4().hex[:8]}"
    with psycopg.connect(BASE_URL, autocommit=True) as admin:
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


@pytest.fixture(scope="session")
def sync_conn(db_url):
    with psycopg.connect(db_url, autocommit=True) as c:
        yield c


@pytest_asyncio.fixture
async def aconn(db_url):
    async with await psycopg.AsyncConnection.connect(db_url, autocommit=True) as c:
        yield c
