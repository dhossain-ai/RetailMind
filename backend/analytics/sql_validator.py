"""SQL safety validator — defense-in-depth layer before handing SQL to the DB.

The real security boundary is the analytics_reader role (SELECT on retail.* only).
This validator is a fast first-pass that rejects obviously dangerous SQL before
it ever reaches the database, and adds a LIMIT cap on detail-row queries.

Two entry points:
  validate(sql)                  — demo analytics against the star schema
  validate_uploaded(sql, dataset_id) — uploaded data analytics; enforces that only
                                       retail.business_sales is queried and that the
                                       WHERE clause filters by the given dataset_id.
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

# Matches any retail.<tablename> reference so we can allowlist in uploaded mode.
_RETAIL_TABLE = re.compile(r"\bretail\.(\w+)", re.IGNORECASE)


def _strip_comments(sql: str) -> str:
    sql = re.sub(r"--[^\n]*", "", sql)
    sql = re.sub(r"/\*[\s\S]*?\*/", "", sql)
    return sql.strip()


def _standard_checks(clean: str) -> None:
    """Run the shared safety checks that apply to both demo and uploaded mode.

    Raises ValueError on the first violation found.
    """
    if not clean:
        raise ValueError("Empty SQL.")

    core = clean.rstrip(";")
    if ";" in core:
        raise ValueError("Multiple SQL statements are not allowed.")

    first_token = clean.split()[0].upper()
    if first_token not in ("SELECT", "WITH"):
        raise ValueError(
            f"Only SELECT or WITH queries are allowed; got {first_token!r}."
        )

    m = _FORBIDDEN.search(clean)
    if m:
        raise ValueError(f"Forbidden keyword: {m.group().upper()}.")

    if _APP_SCHEMA.search(clean):
        raise ValueError("References to the app schema are not allowed.")

    m = _SYSTEM_CATALOGS.search(clean)
    if m:
        raise ValueError(f"System catalog access is not allowed: {m.group()}.")


def validate(sql: str) -> str:
    """Check sql for safety violations and return it (possibly with LIMIT appended).

    Raises ValueError describing the first violation found.
    The returned SQL should be used for execution in place of the original.
    """
    clean = _strip_comments(sql)
    _standard_checks(clean)

    # Add LIMIT 500 if absent to cap runaway detail-row queries.
    result = sql.rstrip().rstrip(";")
    if not _HAS_LIMIT.search(result):
        result += "\nLIMIT 500"

    return result


def validate_uploaded(sql: str, dataset_id: int) -> str:
    """Check uploaded-mode sql and return it (possibly with LIMIT appended).

    Additional rules on top of the standard checks:
      - Only retail.business_sales is permitted; any other retail.<table> is rejected.
      - The query must contain a WHERE filter on dataset_id equal to the given integer.
        Optional table alias prefix is allowed: dataset_id = N, bs.dataset_id = N, etc.

    Raises ValueError describing the first violation found.
    The returned SQL should be used for execution in place of the original.
    """
    clean = _strip_comments(sql)
    _standard_checks(clean)

    # Allowlist: only retail.business_sales may be referenced.
    for m in _RETAIL_TABLE.finditer(clean):
        table_name = m.group(1).lower()
        if table_name != "business_sales":
            raise ValueError(
                f"Uploaded analytics must only query retail.business_sales; "
                f"found retail.{m.group(1)}."
            )

    # Must filter by the exact dataset_id.
    # Allows optional alias prefix: dataset_id = N  or  bs.dataset_id = N
    filter_pattern = re.compile(
        rf"(?:\w+\.)?dataset_id\s*=\s*{re.escape(str(dataset_id))}(?!\d)",
        re.IGNORECASE,
    )
    if not filter_pattern.search(clean):
        raise ValueError(
            f"Uploaded analytics query must filter by dataset_id = {dataset_id}."
        )

    result = sql.rstrip().rstrip(";")
    if not _HAS_LIMIT.search(result):
        result += "\nLIMIT 500"

    return result
