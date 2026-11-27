import random
import string
from datetime import date

import pytest
from app.legal.normalize import strip_diacritics
from app.llm.gateway import Gateway, LLMOffline
from app.retrieval.search import extract_query_ids, retrieve
from app.retrieval.tsquery import build_tsquery

OFFLINE = Gateway(None, "k")
TODAY = date(2026, 6, 1)


def emb(seed: int) -> str:
    r = random.Random(seed)
    v = [r.uniform(-1, 1) for _ in range(1024)]
    n = sum(x * x for x in v) ** 0.5
    return "[" + ",".join(f"{x / n:.6f}" for x in v) + "]"


@pytest.fixture(scope="module", autouse=True)
def data(sync_conn):
    c = sync_conn
    c.execute(
        "delete from chunks; delete from articles; delete from legal_refs; delete from legal_docs"
    )
    c.execute(
        """insert into legal_docs(code, number, title, doc_type, effective_from, effective_to, status) values
           ('ND293-2025','293/2025/NĐ-CP','Lương tối thiểu','nghi_dinh','2026-01-01','2027-01-01','het_hieu_luc'),
           ('ND145-2020','145/2020/NĐ-CP','Hướng dẫn BLLĐ','nghi_dinh','2021-02-01',null,'con_hieu_luc')"""
    )
    for i, (code, art, text, na) in enumerate(
        [
            (
                "ND293-2025",
                3,
                "mức lương tối thiểu vùng I",
                "muc luong toi thieu vung I",
            ),
            ("ND145-2020", 12, "điều kiện làm thêm giờ", "dieu kien lam them gio"),
            ("ND145-2020", 13, "nghỉ hằng năm", "nghi hang nam"),
        ]
    ):
        pid = f"{code}:D{art}"
        c.execute(
            "insert into articles(index_version, id, doc_code, number, title, content) values (1, %s, %s, %s, %s, %s)",
            (pid, code, art, f"Điều {art}", text),
        )
        c.execute(
            """insert into chunks(index_version, id, parent_id, doc_code, article, clause, content, embed_text, n_tokens, embedding, fts_noaccent)
               values (1, %s, %s, %s, %s, 1, %s, %s, 10, %s::halfvec, to_tsvector('simple', %s))""",
            (f"{pid}:K1", pid, code, art, text, text, emb(i), na),
        )


async def test_tsquery_no_diacritics_hits_noaccent_column(aconn):
    got = await retrieve(
        "luong toi thieu vung 1", TODAY, OFFLINE, aconn, 1, online=False
    )
    assert got and got[0].parent_id == "ND293-2025:D3" and got[0].rerank is None


async def test_regex_id_pinned_first(aconn):
    got = await retrieve(
        "Điều 12 Nghị định 145/2020 nói gì", TODAY, OFFLINE, aconn, 1, online=False
    )
    assert got[0].parent_id == "ND145-2020:D12" and got[0].rerank == 1.0
    assert len({c.parent_id for c in got}) == len(got)


async def test_pinned_ignored_when_article_missing(aconn):
    got = await retrieve(
        "Điều 99 Nghị định 145/2020", TODAY, OFFLINE, aconn, 1, online=False
    )
    assert all(c.parent_id != "ND145-2020:D99" for c in got)


def test_extract_query_ids_rules():
    assert extract_query_ids("khoản 2 Điều 12 Nghị định 145/2020/NĐ-CP") == [
        "ND145-2020:D12:K2"
    ]
    assert extract_query_ids("Điều 12 quy định gì") == []  # no explicit doc
    assert extract_query_ids("Nghị định 145/2020") == []  # no article
    assert isinstance(
        extract_query_ids("Điều 12 Nghị định 1/2000 " * 5000), list
    )  # capped input


async def test_embed_offline_falls_back_to_fts(aconn):
    class Down(Gateway):
        async def embed(self, texts):
            raise LLMOffline()

    got = await retrieve(
        "luong toi thieu",
        TODAY,
        Down("https://x.ngrok-free.app", "k"),
        aconn,
        1,
        online=True,
    )
    assert got[0].parent_id == "ND293-2025:D3" and got[0].rerank is None


async def test_online_rerank_max_per_parent(aconn):
    class Fake(Gateway):
        async def embed(self, texts):
            return [[0.1] * 1024]

        async def rerank(self, query, docs, top_n):
            # prefer the ND145 D13 text
            return [(i, 0.9 if "nghỉ hằng" in d else 0.2) for i, d in enumerate(docs)]

    got = await retrieve(
        "luong toi thieu", TODAY, Fake(None, "k"), aconn, 1, online=True
    )
    assert got[0].parent_id == "ND145-2020:D13" and got[0].rerank == 0.9
    assert len(got) <= 6


async def test_fuzz_punctuation_never_sql_error(aconn):
    rnd = random.Random(7)
    alphabet = string.punctuation + " \"'\\ừơđ0aé"
    for _ in range(200):
        q = "".join(rnd.choice(alphabet) for _ in range(rnd.randint(1, 40)))
        await aconn.execute(
            "select * from hybrid_search(%s::text, %s::text, null, 1, %s::date)",
            (build_tsquery(q), build_tsquery(strip_diacritics(q)), TODAY),
        )


async def test_retrieve_records_spans(aconn):
    class T:
        names: list[str] = []

        def span(self, name):
            import contextlib

            self.names.append(name)
            return contextlib.nullcontext()

    t = T()
    await retrieve(
        "luong toi thieu vung 1", TODAY, OFFLINE, aconn, 1, online=False, trace=t
    )
    assert t.names == ["hybrid_search"]  # offline: không embed/rerank


async def test_pin_text_adds_refs_from_raw_question_deduped(aconn):
    got = await retrieve(
        "luong toi thieu vung 1",
        TODAY,
        OFFLINE,
        aconn,
        1,
        online=False,
        pin_text="Điều 12 Nghị định 145/2020 thì sao",
    )
    ids = [c.parent_id for c in got]
    assert (
        ids[0] == "ND145-2020:D12"
        and "ND293-2025:D3" in ids
        and len(ids) == len(set(ids))
    )
    same = await retrieve(
        "Điều 12 Nghị định 145/2020",
        TODAY,
        OFFLINE,
        aconn,
        1,
        online=False,
        pin_text="Điều 12 Nghị định 145/2020",
    )
    assert [c.parent_id for c in same].count("ND145-2020:D12") == 1


async def test_unaccented_tsquery_drops_accented_stopwords():
    from app.retrieval.search import _hybrid

    seen = []

    class Conn:
        async def execute(self, sql, params):
            seen.append(params)

            class C:
                async def fetchall(self):
                    return []

            return C()

    await _hybrid(Conn(), "tôi có lương tối thiểu mà đó", TODAY, 1, None)
    assert seen[0][0] == "lương | tối | thiểu"
    assert seen[0][1] == "luong | toi | thieu"  # không có toi|co|ma|do nhiễu


@pytest.mark.parametrize(
    "bad", [[0.1] * 3, [float("nan")] * 1024, [float("inf")] * 1024]
)
async def test_bad_embedding_degrades_to_fts_not_500(aconn, bad):
    class Fake(Gateway):
        async def embed(self, texts):
            return [bad]

    got = await retrieve(
        "luong toi thieu", TODAY, Fake(None, "k"), aconn, 1, online=True
    )
    assert isinstance(got, list)
