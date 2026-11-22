import pytest
from app.api import deps
from app.config import get_settings
from app.main import create_app
from apimock import GW
from fastapi.testclient import TestClient

@pytest.fixture(autouse=True)
def _fresh_caches():
    deps.reset_caches()
    get_settings.cache_clear()
    yield
    deps.reset_caches()
    get_settings.cache_clear()


@pytest.fixture
def env(monkeypatch, tmp_path, db_url):
    """Settings từ env (cwd rỗng nên không đọc .env); test có thể monkeypatch thêm trước khi tạo client."""
    monkeypatch.chdir(tmp_path)
    for k in ("UPSTASH_REDIS_REST_URL", "UPSTASH_REDIS_REST_TOKEN", "LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY", "LANGFUSE_HOST"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("DATABASE_URL", db_url)
    monkeypatch.setenv("LLM_BASE_URL", GW)
    monkeypatch.setenv("LLM_API_KEY", "k")
    monkeypatch.setenv("CRON_SECRET", "s3cret")
    return monkeypatch


@pytest.fixture
def client(env):
    with TestClient(create_app()) as c:
        yield c


@pytest.fixture
def seeded(sync_conn):
    c = sync_conn
    c.execute("delete from canned_answers; delete from feedback; delete from chunks; delete from articles; delete from legal_refs; delete from legal_docs")
    c.execute("update app_config set value = '0.35' where key = 'refusal_tau'")
    c.execute(
        """insert into legal_docs(code, number, title, doc_type, effective_from, status) values
           ('ND293-2025','293/2025/NĐ-CP','Lương tối thiểu','nghi_dinh','2021-01-01','con_hieu_luc'),
           ('ND145-2020','145/2020/NĐ-CP','Hướng dẫn BLLĐ','nghi_dinh','2021-02-01','con_hieu_luc')"""
    )
    for code, art, title, text, na in [
        ("ND293-2025", 3, "Mức lương tối thiểu", "mức lương tối thiểu vùng I là 5.310.000 đồng", "muc luong toi thieu vung I la 5.310.000 dong"),
        ("ND145-2020", 12, "Làm thêm giờ", "điều kiện làm thêm giờ", "dieu kien lam them gio"),
    ]:
        pid = f"{code}:D{art}"
        c.execute(
            "insert into articles(index_version, id, doc_code, number, title, content) values (1, %s, %s, %s, %s, %s)",
            (pid, code, art, title, text),
        )
        c.execute(
            """insert into chunks(index_version, id, parent_id, doc_code, article, clause, content, embed_text, n_tokens, fts_noaccent)
               values (1, %s, %s, %s, %s, 1, %s, %s, 10, to_tsvector('simple', %s))""",
            (f"{pid}:K1", pid, code, art, text, text, na),
        )
    return c
