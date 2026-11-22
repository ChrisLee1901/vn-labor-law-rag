"""GET /api/docs, /api/docs/{code}: chỉ chỉ mục đang hoạt động; loại văn bản có doc_type/status NULL hoặc ngoài tập hợp lệ."""

from datetime import date

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

from app.api.deps import db_conn
from app.db import active_index_version

router = APIRouter()
CACHE = {"cache-control": "public, s-maxage=3600"}
DOC_TYPES = ["luat", "bo_luat", "vbhn", "nghi_dinh", "thong_tu"]
STATUSES = ["con_hieu_luc", "chua_hieu_luc", "het_hieu_luc"]
VALID = "d.doc_type = any(%(types)s) and d.status = any(%(statuses)s)"
PARAMS = {"types": DOC_TYPES, "statuses": STATUSES}


def _iso(d: date | None) -> str | None:
    return d.isoformat() if d else None


@router.get("/api/docs")
async def list_docs(request: Request):
    async with db_conn(request) as conn:
        iv = await active_index_version(conn)
        cur = await conn.execute(
            f"""select d.code, d.number, d.title, d.doc_type, d.effective_from, d.effective_to, d.status,
                       (select count(*) from articles a
                         where a.doc_code = d.code and a.index_version = %(iv)s and a.kind = 'dieu')
                from legal_docs d where {VALID} order by d.code""",
            {**PARAMS, "iv": iv},
        )
        rows = await cur.fetchall()
    out = [
        {
            "code": c,
            "number": n,
            "title": t,
            "doc_type": dt,
            "effective_from": _iso(ef),
            "effective_to": _iso(et),
            "status": st,
            "articles": cnt,
        }
        for c, n, t, dt, ef, et, st, cnt in rows
    ]
    return JSONResponse(out, headers=CACHE)


@router.get("/api/docs/{code}")
async def get_doc(code: str, request: Request):
    async with db_conn(request) as conn:
        iv = await active_index_version(conn)
        cur = await conn.execute(
            f"""select d.code, d.number, d.title, d.doc_type, d.effective_from, d.effective_to, d.status,
                       d.issuer, d.issued_on, d.replaced_by, d.amends, d.source_url
                from legal_docs d where d.code = %(code)s and {VALID}""",
            {**PARAMS, "code": code},
        )
        d = await cur.fetchone()
        if d is None:
            raise HTTPException(404, "Không tìm thấy văn bản.")
        cur = await conn.execute(
            """select id, number, suffix, title, chapter, coalesce(content, ''), kind from articles
               where doc_code = %s and index_version = %s order by kind, number nulls last, suffix nulls first, id""",
            (code, iv),
        )
        arts = await cur.fetchall()
    doc = {
        "code": d[0],
        "number": d[1],
        "title": d[2],
        "doc_type": d[3],
        "effective_from": _iso(d[4]),
        "effective_to": _iso(d[5]),
        "status": d[6],
        "issuer": d[7],
        "issued_on": _iso(d[8]),
        "replaced_by": d[9],
        "amends": list(d[10] or []),
        "source_url": d[11],
    }
    articles = [
        {
            "id": i,
            "number": n,
            "suffix": s,
            "title": t,
            "chapter": ch,
            "content": c,
            "kind": k,
        }
        for i, n, s, t, ch, c, k in arts
    ]
    return JSONResponse({"doc": doc, "articles": articles}, headers=CACHE)
