import os
import pathlib
import uuid

import psycopg
import pytest
from psycopg import sql

BASE_URL = os.environ.get("TEST_DATABASE_URL", "postgresql://postgres:postgres@localhost:54329/postgres")
MIGRATIONS = sorted((pathlib.Path(__file__).parent.parent / "migrations").glob("*.sql"))


@pytest.fixture(scope="session")
def conn():
    name = f"rag_test_{uuid.uuid4().hex[:8]}"
    with psycopg.connect(BASE_URL, autocommit=True) as admin:
        admin.execute(sql.SQL("create database {}").format(sql.Identifier(name)))
        try:
            info = psycopg.conninfo.conninfo_to_dict(BASE_URL)
            info["dbname"] = name
            with psycopg.connect(**info, autocommit=True) as c:
                for f in MIGRATIONS:
                    c.execute(f.read_text(encoding="utf-8"))
                yield c
        finally:
            admin.execute(sql.SQL("drop database if exists {} with (force)").format(sql.Identifier(name)))
