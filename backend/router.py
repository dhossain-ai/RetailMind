"""Classify an incoming question as 'analytics', 'document', or 'unknown'.

Each rule is a (compiled_regex, weight) pair. A rule fires at most once per
question (re.search, not findall). Strong multi-word phrases score 3;
generic single keywords score 1. Higher total score wins. Tie or both-zero
→ 'unknown' — we prefer an honest fallback over a wrong guess.
"""
from __future__ import annotations
import re

# ---------------------------------------------------------------------------
# Analytics rules
# ---------------------------------------------------------------------------
_ANALYTICS_RULES: list[tuple[re.Pattern, int]] = [
    # Strong phrases — weight 3
    (re.compile(r"\btop[- ]sell\w*", re.I), 3),
    (re.compile(r"\bbest[- ]sell\w*", re.I), 3),
    (re.compile(r"\bcategor\w*.{0,20}declin\w*", re.I | re.DOTALL), 3),
    (re.compile(r"\bstore\s+needs?\s+attention\b", re.I), 3),
    (re.compile(r"\bsales?\s+by\s+store\b", re.I), 3),
    (re.compile(r"\brevenu\w*\s+by\s+categor\w*", re.I), 3),
    (re.compile(r"\bprice\s+change\b", re.I), 3),
    (re.compile(r"\bseasonalit\w*", re.I), 3),
    (re.compile(r"\bbest\s+month\b", re.I), 3),
    # Generic keywords — weight 1
    (re.compile(r"\bsales?\b", re.I), 1),
    (re.compile(r"\brevenu\w*\b", re.I), 1),
    (re.compile(r"\bproducts?\b", re.I), 1),
    (re.compile(r"\bstores?\b", re.I), 1),
    (re.compile(r"\bcategor(?:y|ies)\b", re.I), 1),
    (re.compile(r"\bmonths?\b", re.I), 1),
    (re.compile(r"\btrend\w*\b", re.I), 1),
    (re.compile(r"\bseasonal\b", re.I), 1),
    (re.compile(r"\bpric(?:e|es|ing)\b", re.I), 1),
    (re.compile(r"\btop\b", re.I), 1),
    (re.compile(r"\bbest\b", re.I), 1),
    (re.compile(r"\bworst\b", re.I), 1),
    (re.compile(r"\bbottom\b", re.I), 1),
    (re.compile(r"\b(?:lowest|highest)\b", re.I), 1),
    (re.compile(r"\bdeclin(?:e|ing|ed)\b", re.I), 1),
    (re.compile(r"\bquantit(?:y|ies)\b", re.I), 1),
    (re.compile(r"\bsold\b", re.I), 1),
    (re.compile(r"\bunits?\b", re.I), 1),
    (re.compile(r"\bbaskets?\b", re.I), 1),
    (re.compile(r"\btransactions?\b", re.I), 1),
    (re.compile(r"\bperformance\b", re.I), 1),
    (re.compile(r"\bgrowth\b", re.I), 1),
]

# ---------------------------------------------------------------------------
# Document rules
# ---------------------------------------------------------------------------
_DOCUMENT_RULES: list[tuple[re.Pattern, int]] = [
    # Strong phrases — weight 3
    (re.compile(r"\breturn\s+polic\w*", re.I), 3),
    (re.compile(r"\bsupplier\s+vett\w*", re.I), 3),
    (re.compile(r"\bstore\s+hours?\b", re.I), 3),
    (re.compile(r"\boperating\s+hours?\b", re.I), 3),
    (re.compile(r"\bprivacy\s+polic\w*", re.I), 3),
    (re.compile(r"\buploaded?\s+documents?\b", re.I), 3),
    (re.compile(r"\bpdf\b", re.I), 3),
    (re.compile(r"\bdata\s+privac\w*", re.I), 3),
    # Generic keywords — weight 1
    (re.compile(r"\bpolic(?:y|ies)\b", re.I), 1),
    (re.compile(r"\breturns?\b", re.I), 1),
    (re.compile(r"\brefunds?\b", re.I), 1),
    (re.compile(r"\bsuppliers?\b", re.I), 1),
    (re.compile(r"\bvendors?\b", re.I), 1),
    (re.compile(r"\bvett\w*\b", re.I), 1),
    (re.compile(r"\bhours?\b", re.I), 1),
    (re.compile(r"\bhandbook\b", re.I), 1),
    (re.compile(r"\bmanual\b", re.I), 1),
    (re.compile(r"\bprocedures?\b", re.I), 1),
    (re.compile(r"\bguidelines?\b", re.I), 1),
    (re.compile(r"\bprivac(?:y|ies)\b", re.I), 1),
    (re.compile(r"\bcompliance\b", re.I), 1),
    (re.compile(r"\bdocuments?\b", re.I), 1),
    (re.compile(r"\buploads?\b", re.I), 1),
    (re.compile(r"\bcontracts?\b", re.I), 1),
    (re.compile(r"\bcatalou?g\w*\b", re.I), 1),
    (re.compile(r"\bhandling\b", re.I), 1),
]

# ---------------------------------------------------------------------------
# Public interface
# ---------------------------------------------------------------------------
UNKNOWN_ANSWER = (
    "I can answer questions about uploaded documents or retail sales analytics. "
    "Please ask about a policy or document, "
    "or about sales, products, stores, or categories."
)


def _score(question: str, rules: list[tuple[re.Pattern, int]]) -> int:
    return sum(w for pat, w in rules if pat.search(question))


def classify(question: str) -> str:
    """Return 'analytics', 'document', or 'unknown'.

    Higher weighted score wins. Tie or both-zero → 'unknown'.
    """
    a = _score(question, _ANALYTICS_RULES)
    d = _score(question, _DOCUMENT_RULES)
    if a > d:
        return "analytics"
    if d > a:
        return "document"
    return "unknown"


# ---------------------------------------------------------------------------
# Self-test  (python -m backend.router)
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    _TESTS = [
        ("What is the top-selling product?", "analytics"),
        ("Which category is declining?", "analytics"),
        ("Which store needs attention?", "analytics"),
        ("What is the return policy?", "document"),
        ("What is the supplier vetting process?", "document"),
        ("What are the store operating hours?", "document"),
        ("What is the capital of France?", "unknown"),
    ]
    passed = 0
    for question, expected in _TESTS:
        a = _score(question, _ANALYTICS_RULES)
        d = _score(question, _DOCUMENT_RULES)
        got = classify(question)
        ok = got == expected
        passed += ok
        status = "PASS" if ok else "FAIL"
        print(f"{status}  [{got:10s}]  a={a} d={d}  {question}")
    print(f"\n{passed}/{len(_TESTS)} passed")
