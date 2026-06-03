"""Evaluate the analytics agent against the five seeded demo questions.

Also verifies the analytics_reader security boundary (DB-level permission check).

Requires:
  - Docker Postgres running  (docker compose up -d)
  - Ollama running with qwen2.5-coder:7b

Run from repo root:
    py -3.11 scripts/eval_analytics.py
"""
import sys
from typing import Callable

import psycopg
import psycopg.errors

import backend.analytics.agent as analytics_agent
from backend.config import settings

# ---------------------------------------------------------------------------
# Analytics question checks
# ---------------------------------------------------------------------------
# Each entry:  (name, question, row_check, answer_check)
#   row_check:    (columns: list[str], rows: list[list]) -> bool
#   answer_check: (answer: str) -> bool
#
# A check PASSES only when both sub-checks pass.
# row_check is the stronger evidence; answer_check catches LLM reasoning bugs.

_Q_CHECKS: list[tuple[str, str, Callable, Callable]] = [
    (
        "declining category",
        "Which category is declining?",
        # Template A returns (month, category, revenue).
        # Household must appear as a category in the result set.
        lambda cols, rows: any(
            "household" in str(cell).lower() for row in rows for cell in row
        ),
        lambda ans: "household" in ans.lower(),
    ),
    (
        "top-selling product",
        "What is the top-selling product?",
        # SQL is ordered DESC; rows[0] is Coffee Beans.
        lambda cols, rows: bool(rows) and "coffee beans" in str(rows[0]).lower(),
        lambda ans: "coffee beans" in ans.lower(),
    ),
    (
        "best month / seasonality",
        "What is the best month for sales?",
        # Template C returns (month, total_revenue) for all months.
        # December months appear as "YYYY-12" strings.
        lambda cols, rows: any(
            "-12" in str(cell) for row in rows for cell in row
        ),
        lambda ans: "december" in ans.lower(),
    ),
    (
        "store needing attention",
        "Which store needs the most attention?",
        # Template B orders by total_revenue ASC; Warsaw is first.
        lambda cols, rows: bool(rows) and "warsaw" in str(rows[0]).lower(),
        lambda ans: "warsaw" in ans.lower(),
    ),
    (
        "price change",
        "Did any product have a price change?",
        # Template D returns (name, unit_price, first_seen, last_seen).
        # Coffee Beans must appear with both 8.50 and 11.99.
        lambda cols, rows: (
            any("coffee" in str(cell).lower() for row in rows for cell in row)
            and any("8.5" in str(cell) for row in rows for cell in row)
            and any("11.99" in str(cell) for row in rows for cell in row)
        ),
        lambda ans: (
            "coffee beans" in ans.lower()
            and ("8.5" in ans or "8.50" in ans)
            and "11.99" in ans
        ),
    ),
]


def _fmt(ok: bool, label: str, detail: str = "") -> bool:
    status = "PASS" if ok else "FAIL"
    print(f"  [{status}]  {label}")
    if detail:
        print(f"         {detail}")
    return ok


def _check_db_read() -> bool:
    """analytics_reader should be able to SELECT from retail.sales."""
    try:
        with psycopg.connect(settings.analytics_database_url) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM retail.sales")
                count = cur.fetchone()[0]
        return _fmt(True, "security: analytics_reader -> retail.sales",
                    f"row count = {count}")
    except Exception as exc:
        return _fmt(False, "security: analytics_reader -> retail.sales", str(exc))


def _check_db_deny() -> bool:
    """analytics_reader must be denied from app.chat_messages."""
    try:
        with psycopg.connect(settings.analytics_database_url) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM app.chat_messages")
        # Reaching here means the permission was NOT denied.
        return _fmt(False,
                    "security: analytics_reader -> app.chat_messages (should deny)",
                    "access was NOT denied -security boundary broken")
    except psycopg.errors.InsufficientPrivilege:
        return _fmt(True,
                    "security: analytics_reader -> app.chat_messages (should deny)",
                    "access denied as expected")
    except Exception as exc:
        return _fmt(False,
                    "security: analytics_reader -> app.chat_messages (should deny)",
                    f"unexpected error: {exc}")


def run() -> tuple[int, int]:
    print("\nAnalytics evaluation")
    print("-" * 60)

    results: list[bool] = []
    results.append(_check_db_read())
    results.append(_check_db_deny())

    try:
        llm = analytics_agent.get_llm_provider()
    except NotImplementedError as exc:
        print(f"\n  [SKIP]  LLM provider not configured: {exc}")
        print(f"         Skipping all 5 analytics question checks.")
        total = len(results) + len(_Q_CHECKS)
        passed = sum(results)
        print(f"\nAnalytics: {passed}/{total} passed  ({len(_Q_CHECKS)} skipped -no LLM)")
        return passed, total

    for name, question, row_check, answer_check in _Q_CHECKS:
        print()
        print(f"  Q: {question}")
        try:
            result = analytics_agent.run(question, llm)
        except Exception as exc:
            ok = _fmt(False, name, f"agent error: {type(exc).__name__}: {exc}")
            results.append(ok)
            continue

        cols = result["columns"]
        rows = result["rows"]
        ans = result["answer"]

        row_ok = row_check(cols, rows)
        row_preview = str(rows[:2]) if rows else "[]"
        _fmt(row_ok, f"{name} -rows check", row_preview)

        ans_ok = answer_check(ans)
        ans_preview = ans[:120].replace("\n", " ")
        _fmt(ans_ok, f"{name} -answer check", f'"{ans_preview}"')

        results.append(row_ok and ans_ok)

    passed = sum(results)
    total = len(results)
    print(f"\nAnalytics: {passed}/{total} passed")
    return passed, total


if __name__ == "__main__":
    passed, total = run()
    sys.exit(0 if passed == total else 1)
