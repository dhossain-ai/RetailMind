"""Evaluate uploaded-dataset analytics mode.

Core checks call Python functions directly (require Postgres + Ollama, no server).
API checks hit the FastAPI server (skipped if not running).

Run from repo root:
    py -3.11 scripts/eval_uploads.py

Exit code: 0 if all non-skipped checks pass, 1 otherwise.
"""
import sys
from pathlib import Path

# Allow sibling imports when running as a script
sys.path.insert(0, str(Path(__file__).parent.parent))

import backend.analytics.agent as analytics_agent
from backend.uploads.agent import ingest as uploads_ingest

_API_BASE = "http://localhost:8000"
_SAMPLE_CSV = Path(__file__).parent.parent / "data" / "sample_docs" / "sample_sales.csv"


def _fmt(ok: bool, label: str, detail: str = "") -> bool:
    status = "PASS" if ok else "FAIL"
    print(f"  [{status}]  {label}")
    if detail:
        print(f"         {detail}")
    return ok


def _ensure_upload() -> int | None:
    """Ingest sample_sales.csv directly and return the new dataset_id."""
    if not _SAMPLE_CSV.exists():
        print(f"  [SKIP]  sample_sales.csv not found at {_SAMPLE_CSV}")
        return None
    try:
        result = uploads_ingest(_SAMPLE_CSV, "sample_sales.csv")
        dataset_id = result["dataset_id"]
        _fmt(True, f"upload sample_sales.csv -> dataset_id={dataset_id}",
             f"row_count={result['row_count']}, skipped={result['skipped_count']}")
        return dataset_id
    except Exception as exc:
        _fmt(False, "upload sample_sales.csv", str(exc))
        return None


def _run_core_checks(dataset_id: int, llm) -> list[bool]:
    """Direct agent calls — no HTTP server required."""
    results: list[bool] = []

    # ── Check 1: top-selling product (uploaded mode) ───────────────────────────
    print()
    print("  Q (uploaded): What is the top-selling product?")
    try:
        r = analytics_agent.run("What is the top-selling product?", llm,
                                dataset_id=dataset_id)
    except Exception as exc:
        results.append(_fmt(False, "uploaded: top product — agent error", str(exc)))
        return results  # cannot proceed without a result

    sql_ok = (
        "business_sales" in r["sql"].lower()
        and f"dataset_id = {dataset_id}" in r["sql"].replace(" ", "").lower().replace(
            "dataset_id=", "dataset_id = "
        )
    )
    row_ok = bool(r["rows"]) and "coffee beans" in str(r["rows"][0]).lower()
    ans_ok = "coffee beans" in r["answer"].lower()
    mode_ok = r.get("mode") == "uploaded"

    _fmt(sql_ok, "uploaded: top product — SQL uses business_sales + dataset_id filter",
         r["sql"][:120].replace("\n", " "))
    _fmt(row_ok, "uploaded: top product — rows[0] is Coffee Beans",
         str(r["rows"][:2]))
    _fmt(ans_ok, "uploaded: top product — answer mentions Coffee Beans",
         f'"{r["answer"][:120].replace(chr(10), " ")}"')
    _fmt(mode_ok, 'uploaded: top product — mode == "uploaded"',
         f"mode={r.get('mode')!r}")

    results.append(sql_ok and row_ok and ans_ok and mode_ok)

    # ── Check 2: total revenue (uploaded mode) ─────────────────────────────────
    print()
    print("  Q (uploaded): What is the total revenue?")
    try:
        r2 = analytics_agent.run("What is the total revenue?", llm,
                                 dataset_id=dataset_id)
    except Exception as exc:
        results.append(_fmt(False, "uploaded: total revenue — agent error", str(exc)))
        return results

    sql2_ok = "business_sales" in r2["sql"].lower()
    rows2_ok = bool(r2["rows"])
    ans2_ok = bool(r2["answer"].strip())

    _fmt(sql2_ok, "uploaded: total revenue — SQL uses business_sales",
         r2["sql"][:120].replace("\n", " "))
    _fmt(rows2_ok, "uploaded: total revenue — result has rows",
         str(r2["rows"][:2]))
    _fmt(ans2_ok, "uploaded: total revenue — answer is non-empty",
         f'"{r2["answer"][:80].replace(chr(10), " ")}"')

    results.append(sql2_ok and rows2_ok and ans2_ok)

    # ── Check 3: revenue by month (uploaded mode) ──────────────────────────────
    print()
    print("  Q (uploaded): What is the best month for sales?")
    try:
        r3 = analytics_agent.run("What is the best month for sales?", llm,
                                 dataset_id=dataset_id)
    except Exception as exc:
        results.append(_fmt(False, "uploaded: best month — agent error", str(exc)))
        return results

    sql3_ok = "business_sales" in r3["sql"].lower()
    # Sample CSV spans Jan–Mar 2024; March has the highest revenue
    rows3_ok = any("2024" in str(cell) for row in r3["rows"] for cell in row)
    ans3_ok = bool(r3["answer"].strip())

    _fmt(sql3_ok, "uploaded: best month — SQL uses business_sales",
         r3["sql"][:120].replace("\n", " "))
    _fmt(rows3_ok, "uploaded: best month — rows contain 2024 dates",
         str(r3["rows"][:2]))
    _fmt(ans3_ok, "uploaded: best month — answer is non-empty",
         f'"{r3["answer"][:80].replace(chr(10), " ")}"')

    results.append(sql3_ok and rows3_ok and ans3_ok)

    return results


def _run_demo_regression(llm) -> list[bool]:
    """Confirm that omitting dataset_id still uses the demo star schema."""
    results: list[bool] = []

    print()
    print("  Q (demo, no dataset_id): What is the top-selling product?")
    try:
        r = analytics_agent.run("What is the top-selling product?", llm)
    except Exception as exc:
        results.append(_fmt(False, "demo regression — agent error", str(exc)))
        return results

    # Demo SQL should reference retail.sales (star schema), not business_sales
    uses_demo = "retail.sales" in r["sql"].lower()
    not_uploaded = "business_sales" not in r["sql"].lower()
    mode_ok = r.get("mode") == "demo"

    _fmt(uses_demo and not_uploaded,
         "demo regression — SQL uses retail.sales not business_sales",
         r["sql"][:120].replace("\n", " "))
    _fmt(mode_ok, 'demo regression — mode == "demo"', f"mode={r.get('mode')!r}")

    results.append(uses_demo and not_uploaded and mode_ok)
    return results


def _run_api_checks(dataset_id: int) -> tuple[int, int, int]:
    """Optional HTTP API checks. Returns (passed, failed, skipped)."""
    try:
        import httpx
    except ImportError:
        print("  [SKIP]  httpx not installed — skipping API checks")
        return 0, 0, 2

    try:
        httpx.get(f"{_API_BASE}/health", timeout=3.0)
    except Exception:
        print(f"  [SKIP]  server not reachable at {_API_BASE} — skipping API checks")
        return 0, 0, 2

    passed = failed = 0

    # API check 1: POST /analytics with dataset_id
    try:
        resp = httpx.post(
            f"{_API_BASE}/analytics",
            json={"question": "What is the top-selling product?", "dataset_id": dataset_id},
            timeout=120.0,
        )
        resp.raise_for_status()
        data = resp.json()
        ok = (
            "business_sales" in data.get("sql", "").lower()
            and data.get("mode") == "uploaded"
        )
    except Exception as exc:
        ok = False
        data = {"error": str(exc)}

    status = "PASS" if ok else "FAIL"
    print(f"  [{status}]  API: POST /analytics with dataset_id={dataset_id}")
    if not ok:
        print(f"         response: {str(data)[:200]}")
        failed += 1
    else:
        passed += 1

    # API check 2: POST /chat with dataset_id (analytics question)
    try:
        resp = httpx.post(
            f"{_API_BASE}/chat",
            json={"message": "What is the top-selling product?", "dataset_id": dataset_id},
            timeout=120.0,
        )
        resp.raise_for_status()
        data = resp.json()
        ok = (
            data.get("route") == "analytics"
            and "business_sales" in data.get("sql", "").lower()
            and data.get("mode") == "uploaded"
        )
    except Exception as exc:
        ok = False
        data = {"error": str(exc)}

    status = "PASS" if ok else "FAIL"
    print(f"  [{status}]  API: POST /chat (analytics) with dataset_id={dataset_id}")
    if not ok:
        print(f"         response: {str(data)[:200]}")
        failed += 1
    else:
        passed += 1

    return passed, failed, 0


def run() -> tuple[int, int]:
    print("\nUploaded dataset analytics evaluation")
    print("-" * 60)

    # Upload fixture
    dataset_id = _ensure_upload()
    if dataset_id is None:
        print("  [SKIP]  cannot proceed without a dataset — skipping all checks")
        return 0, 0

    # Acquire LLM
    try:
        llm = analytics_agent.get_llm_provider()
    except NotImplementedError as exc:
        print(f"\n  [SKIP]  LLM provider not configured: {exc}")
        print("         Skipping all uploaded analytics checks.")
        return 0, 0

    results: list[bool] = []

    # Core checks (direct Python calls)
    results.extend(_run_core_checks(dataset_id, llm))
    results.extend(_run_demo_regression(llm))

    # Optional API checks
    print()
    print("  API checks  (requires: uvicorn backend.main:app --reload)")
    api_passed, api_failed, api_skipped = _run_api_checks(dataset_id)
    api_total = 2  # number of API checks defined above

    core_passed = sum(results)
    core_total = len(results)

    note = f"  ({api_skipped} skipped)" if api_skipped else ""
    print(f"\nUploaded: {core_passed}/{core_total} core"
          f"  |  API: {api_passed}/{api_total - api_skipped}{note}")

    total_passed = core_passed + api_passed
    total = core_total + (api_total - api_skipped)
    return total_passed, total


if __name__ == "__main__":
    passed, total = run()
    sys.exit(0 if passed == total else 1)
