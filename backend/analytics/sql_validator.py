"""SQL safety validator — defense-in-depth layer before handing SQL to the DB.

The real security boundary is the analytics_reader role (SELECT on retail.* only).
This validator is a fast first-pass that rejects obviously dangerous SQL before
it ever reaches the database, and adds a LIMIT cap on detail-row queries.
"""
import re

_FORBIDDEN = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|TRUNCATE|GRANT|REVOKE|COPY|CALL|EXECUTE)\b",
    re.IGNORECASE,
)
_SYSTEM_CATALOGS = re.compile(
    r"\b(pg_catalog|information_schema|pg_class|pg_tables|pg_namespace)\b",
    re.IGNORECASE,
)
_APP_SCHEMA = re.compile(r"\bapp\.", re.IGNORECASE)
_HAS_LIMIT = re.compile(r"\bLIMIT\b", re.IGNORECASE)


def _strip_comments(sql: str) -> str:
    sql = re.sub(r"--[^\n]*", "", sql)
    sql = re.sub(r"/\*[\s\S]*?\*/", "", sql)
    return sql.strip()


def validate(sql: str) -> str:
    """Check sql for safety violations and return it (possibly with LIMIT appended).

    Raises ValueError describing the first violation found.
    The returned SQL should be used for execution in place of the original.
    """
    clean = _strip_comments(sql)

    # 1. Empty
    if not clean:
        raise ValueError("Empty SQL.")

    # 2. Multiple statements: strip trailing semicolon, then reject any remaining one
    core = clean.rstrip(";")
    if ";" in core:
        raise ValueError("Multiple SQL statements are not allowed.")

    # 3. Must begin with SELECT or WITH (CTEs)
    first_token = clean.split()[0].upper()
    if first_token not in ("SELECT", "WITH"):
        raise ValueError(
            f"Only SELECT or WITH queries are allowed; got {first_token!r}."
        )

    # 4. Forbidden DML / DDL keywords
    m = _FORBIDDEN.search(clean)
    if m:
        raise ValueError(f"Forbidden keyword: {m.group().upper()}.")

    # 5. app schema references
    if _APP_SCHEMA.search(clean):
        raise ValueError("References to the app schema are not allowed.")

    # 6. System catalog access
    m = _SYSTEM_CATALOGS.search(clean)
    if m:
        raise ValueError(f"System catalog access is not allowed: {m.group()}.")

    # 7. Add LIMIT 500 if absent to cap runaway detail-row queries.
    #    This does not change the result of aggregate queries (they naturally
    #    return few rows); it only caps queries that return individual sales rows.
    result = sql.rstrip().rstrip(";")
    if not _HAS_LIMIT.search(result):
        result += "\nLIMIT 500"

    return result
