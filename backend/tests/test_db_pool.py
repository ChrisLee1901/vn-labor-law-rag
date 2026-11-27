import psycopg
from app.db import make_pool


async def test_pool_replaces_connection_killed_while_idle(db_url):
    pool = make_pool(db_url)
    await pool.open(wait=True)
    try:
        async with pool.connection() as c:
            pid = (await (await c.execute("select pg_backend_pid()")).fetchone())[0]  # type: ignore[index]
        with psycopg.connect(
            db_url, autocommit=True
        ) as admin:  # mô phỏng serverless đóng băng
            admin.execute("select pg_terminate_backend(%s)", (pid,))
        async with pool.connection() as c:
            assert (await (await c.execute("select 1")).fetchone()) == (1,)
    finally:
        await pool.close()
