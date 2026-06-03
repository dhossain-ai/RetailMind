"""Run all RetailMind evaluations and optional API checks.

Usage:
    py -3.11 scripts/eval_all.py

Optional API checks require the FastAPI server to be running:
    uvicorn backend.main:app --reload

API checks are silently skipped (not failed) when the server is unreachable.
Exit code: 0 if all non-skipped checks pass, 1 otherwise.
"""
import sys
from pathlib import Path

# Allow importing sibling eval modules when running as a script
sys.path.insert(0, str(Path(__file__).parent))

import eval_analytics  # noqa: E402
import eval_documents  # noqa: E402
import eval_router  # noqa: E402

_API_BASE = "http://localhost:8000"

_API_CHECKS = [
    (
        "GET /health",
        "GET",
        "/health",
        None,
        lambda r: r.get("status") == "ok",
    ),
    (
        "POST /chat -> analytics route",
        "POST",
        "/chat",
        {"message": "What is the top-selling product?"},
        lambda r: r.get("route") == "analytics",
    ),
    (
        "POST /chat -> document route",
        "POST",
        "/chat",
        {"message": "What is the return policy?"},
        lambda r: r.get("route") == "document",
    ),
    (
        "POST /chat -> unknown route",
        "POST",
        "/chat",
        {"message": "What is the capital of France?"},
        lambda r: r.get("route") == "unknown",
    ),
]


def _run_api_checks() -> tuple[int, int, int]:
    """Run optional API checks against the running FastAPI server.

    Returns (passed, failed, skipped).
    """
    try:
        import httpx
    except ImportError:
        print("  [SKIP]  httpx not installed — skipping all API checks")
        return 0, 0, len(_API_CHECKS)

    # Probe availability with /health — fast, no LLM needed.
    try:
        httpx.get(f"{_API_BASE}/health", timeout=3.0)
    except Exception:
        print(f"  [SKIP]  server not reachable at {_API_BASE} — skipping all API checks")
        return 0, 0, len(_API_CHECKS)

    passed = failed = 0
    for name, method, path, body, check in _API_CHECKS:
        url = f"{_API_BASE}{path}"
        try:
            if method == "GET":
                resp = httpx.get(url, timeout=120.0)
            else:
                resp = httpx.post(url, json=body, timeout=120.0)
            resp.raise_for_status()
            data = resp.json()
            ok = check(data)
        except Exception as exc:
            ok = False
            data = {"error": str(exc)}

        status = "PASS" if ok else "FAIL"
        print(f"  [{status}]  API: {name}")
        if not ok:
            preview = str(data)[:200]
            print(f"         response: {preview}")
            failed += 1
        else:
            passed += 1

    return passed, failed, 0


def main() -> int:
    print("=" * 60)
    print("RetailMind - Evaluation v1")
    print("=" * 60)

    # ── Core evaluations ───────────────────────────────────────
    r_passed, r_total = eval_router.run()
    a_passed, a_total = eval_analytics.run()
    d_passed, d_total = eval_documents.run()

    core_passed = r_passed + a_passed + d_passed
    core_total = r_total + a_total + d_total

    # ── Optional API checks ────────────────────────────────────
    print("\nAPI checks  (requires: uvicorn backend.main:app --reload)")
    print("-" * 60)
    api_passed, api_failed, api_skipped = _run_api_checks()
    api_total = len(_API_CHECKS)

    # ── Summary ────────────────────────────────────────────────
    print()
    print("=" * 60)
    print(f"  Router:    {r_passed}/{r_total}")
    print(f"  Analytics: {a_passed}/{a_total}")
    print(f"  Document:  {d_passed}/{d_total}")
    api_note = f"  ({api_skipped} skipped)" if api_skipped else ""
    print(f"  API:       {api_passed}/{api_total - api_skipped}{api_note}")
    print("  " + "-" * 30)
    all_passed = core_passed + api_passed
    all_total = core_total + (api_total - api_skipped)
    print(f"  TOTAL:     {all_passed}/{all_total} passed", end="")
    if api_skipped:
        print(f"  ({api_skipped} API checks skipped)", end="")
    print()
    print("=" * 60)

    any_failed = (core_passed < core_total) or (api_failed > 0)
    return 1 if any_failed else 0


if __name__ == "__main__":
    sys.exit(main())
