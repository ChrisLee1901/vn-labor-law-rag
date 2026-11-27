from psycopg import AsyncConnection
from psycopg_pool import AsyncConnectionPool


def make_pool(url: str) -> AsyncConnectionPool:
    """Pool size 1 + no prepared statements: required behind the Supabase transaction pooler (port 6543)."""
    return AsyncConnectionPool(
        url,
        min_size=1,
        max_size=1,
        kwargs={"prepare_threshold": None},
        check=AsyncConnectionPool.check_connection,  # kết nối chết sau khi serverless đóng băng thì thay, không 503
        open=False,
    )


async def active_index_version(conn: AsyncConnection) -> int:
    cur = await conn.execute(
        "select value from app_config where key = 'active_index_version'"
    )
    row = await cur.fetchone()
    return int(row[0]) if row else 1
