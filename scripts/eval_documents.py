"""Evaluate the document agent against sample_policy.pdf.

If ChromaDB is empty the script ingests data/sample_docs/sample_policy.pdf
automatically before running checks.

Requires:
  - Docker Postgres running  (docker compose up -d)
  - Ollama running with qwen2.5-coder:7b
  - data/sample_docs/sample_policy.pdf present

Run from repo root:
    py -3.11 scripts/eval_documents.py
"""
import sys
from pathlib import Path

import chromadb

import backend.documents.agent as document_agent
from backend.config import settings
from backend.documents.vectorstore import COLLECTION_NAME

SAMPLE_PDF = Path("data/sample_docs/sample_policy.pdf")

# ---------------------------------------------------------------------------
# Document question checks
# ---------------------------------------------------------------------------
# Each entry: (name, question, answer_check, requires_sources)
#   answer_check: (answer: str) -> bool
#   requires_sources: bool -whether sources must be non-empty and have metadata

_Q_CHECKS: list[tuple[str, str, object, bool]] = [
    (
        "return policy",
        "What is the return policy?",
        # Must mention the 30-day window.
        lambda ans: "30" in ans,
        True,
    ),
    (
        "supplier vetting process",
        "What is the supplier vetting process?",
        # Must mention at least one step from the documented process.
        lambda ans: any(
            kw in ans.lower()
            for kw in ["audit", "vetting", "trial", "code of conduct",
                       "documentation", "supplier", "onboarding"]
        ),
        True,
    ),
    (
        "store operating hours",
        "What are the store operating hours?",
        # Must mention at least one hour or day reference.
        lambda ans: any(
            kw in ans.lower()
            for kw in ["08:00", "8:00", "20:00", "monday", "saturday",
                       "sunday", "hours", "open"]
        ),
        True,
    ),
    (
        "unrelated question -honest refusal",
        "What is the capital of France?",
        # LLM must refuse; sources may be non-empty (retrieval still runs).
        lambda ans: "cannot find" in ans.lower(),
        False,
    ),
]


def _chroma_count() -> int:
    try:
        client = chromadb.PersistentClient(path=settings.chroma_path)
        coll = client.get_collection(COLLECTION_NAME)
        return coll.count()
    except Exception:
        return 0


def _source_has_metadata(source: str) -> bool:
    """Return True if the citation string contains page and chunk info."""
    return "page" in source and "chunk" in source


def _fmt(ok: bool, label: str, detail: str = "") -> bool:
    status = "PASS" if ok else "FAIL"
    print(f"  [{status}]  {label}")
    if detail:
        print(f"         {detail}")
    return ok


def _ensure_ingested() -> bool:
    """Ingest sample_policy.pdf if ChromaDB is empty. Returns True on success."""
    count = _chroma_count()
    if count > 0:
        print(f"  [INFO]  ChromaDB has {count} chunks -skipping ingestion")
        return True

    if not SAMPLE_PDF.exists():
        print(f"  [ERROR] {SAMPLE_PDF} not found. Cannot auto-ingest.")
        return False

    print(f"  [INFO]  ChromaDB is empty -ingesting {SAMPLE_PDF} ...")
    try:
        result = document_agent.ingest(SAMPLE_PDF)
        print(f"  [INFO]  Ingested: document_id={result['document_id']}, "
              f"chunks={result['chunk_count']}")
        return True
    except Exception as exc:
        print(f"  [ERROR] Ingestion failed: {exc}")
        return False


def run() -> tuple[int, int]:
    print("\nDocument evaluation")
    print("-" * 60)

    results: list[bool] = []

    if not _ensure_ingested():
        total = len(_Q_CHECKS)
        print(f"\nDocument: 0/{total} passed  (ingestion failed -all skipped)")
        return 0, total

    for name, question, answer_check, requires_sources in _Q_CHECKS:
        print()
        print(f"  Q: {question}")

        try:
            result = document_agent.run(question)
        except Exception as exc:
            ok = _fmt(False, name, f"agent error: {type(exc).__name__}: {exc}")
            results.append(ok)
            continue

        ans = result["answer"]
        sources = result["sources"]

        # Answer key-fact check
        ans_ok = answer_check(ans)
        ans_preview = ans[:120].replace("\n", " ")
        _fmt(ans_ok, f"{name} -answer check", f'"{ans_preview}"')

        # Sources check (non-empty + metadata format)
        if requires_sources:
            src_ok = bool(sources) and any(
                _source_has_metadata(s) for s in sources
            )
            src_detail = (
                f"{len(sources)} source(s): {sources[0]!r}" if sources
                else "no sources returned"
            )
            _fmt(src_ok, f"{name} -sources check", src_detail)
            results.append(ans_ok and src_ok)
        else:
            results.append(ans_ok)

    passed = sum(results)
    total = len(results)
    print(f"\nDocument: {passed}/{total} passed")
    return passed, total


if __name__ == "__main__":
    passed, total = run()
    sys.exit(0 if passed == total else 1)
