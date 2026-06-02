"""Database execution layer for the analytics agent.

Connects exclusively via ANALYTICS_DATABASE_URL (analytics_reader role).
analytics_reader has SELECT on retail.* only — it cannot read app.* even if
injected SQL attempts it. Never use DATABASE_URL here.
"""
import psycopg

from backend.config import settings


def run_query(
    sql: str,
    timeout_ms: int = 30_000,
    max_rows: int = 500,
) -> dict:
    """Execute validated sql as analytics_reader; return columns + rows.

    Args:
        sql: A validated SELECT or WITH query.
        timeout_ms: statement_timeout in milliseconds (default 30 s).
        max_rows: Maximum rows fetched from the cursor.

    Returns:
        {"columns": [str, ...], "rows": [[value, ...], ...]}
    """
    with psycopg.connect(settings.analytics_database_url) as conn:
        conn.execute(f"SET statement_timeout = {timeout_ms}")
        with conn.cursor() as cur:
            cur.execute(sql)
            columns = [d.name for d in cur.description]
            rows = [list(row) for row in cur.fetchmany(max_rows)]
    return {"columns": columns, "rows": rows}
