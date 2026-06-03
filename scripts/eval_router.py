"""Evaluate router classification accuracy.

No external dependencies — no DB, no LLM, no server required.

Run from repo root:
    py -3.11 scripts/eval_router.py
"""
import sys

from backend.router import _ANALYTICS_RULES, _DOCUMENT_RULES, _score, classify

_CHECKS: list[tuple[str, str]] = [
    ("What is the top-selling product?", "analytics"),
    ("Which category is declining?", "analytics"),
    ("Which store needs attention?", "analytics"),
    ("What is the return policy?", "document"),
    ("What is the supplier vetting process?", "document"),
    ("What are the store operating hours?", "document"),
    ("What is the capital of France?", "unknown"),
]


def _fmt(ok: bool, label: str, detail: str) -> None:
    status = "PASS" if ok else "FAIL"
    print(f"  [{status}]  {label}")
    if not ok or detail:
        print(f"         {detail}")


def run() -> tuple[int, int]:
    print("Router evaluation")
    print("-" * 60)
    passed = 0
    for question, expected in _CHECKS:
        a = _score(question, _ANALYTICS_RULES)
        d = _score(question, _DOCUMENT_RULES)
        got = classify(question)
        ok = got == expected
        passed += ok
        detail = f"a={a} d={d}  ->  {got}"
        if not ok:
            detail += f"  (expected {expected})"
        _fmt(ok, repr(question), detail)
    total = len(_CHECKS)
    print(f"\nRouter: {passed}/{total} passed")
    return passed, total


if __name__ == "__main__":
    passed, total = run()
    sys.exit(0 if passed == total else 1)
