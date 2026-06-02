# RetailMind — Progress

## Done

### 2026-06-01 — Foundation

- **Folder skeleton** — `backend/`, `frontend/`, `data/sample_docs/`, `scripts/`, `docs/` created with `.gitkeep` files so Git tracks the empty directories.
- **`scripts/001_schema.sql`** — Postgres migration creating the `retail` and `app` schemas, all six tables, and the `analytics_reader` role with correct grants and `ALTER DEFAULT PRIVILEGES`.
- **`docs/01_project_overview.md`** — Plain-language description of the project, its two capabilities, and the router.
- **`docs/02_decisions_log.md`** — Nine schema and architecture decisions, each with a plain-language "Why" (including #9: setseed + md5 UUID approach for deterministic seeds).
- **`CLAUDE.md`** — Folder layout, working principles, model abstraction rule, analytics agent security rule, and vocabulary table.

### 2026-06-01 — Seed data

- **`scripts/002_seed.sql`** — Deterministic PL/pgSQL generator producing ~5,000 sales rows across 24 months (June 2024–May 2026). Safe to re-run (TRUNCATE at top). Five deliberate patterns planted for demo Q&A:
  1. Household category decline (selection weight drops 90% in Mar–May 2026)
  2. Coffee Beans standout best-seller (~5× units sold vs next product)
  3. December seasonal spike (2× basket count in Dec 2024 and Dec 2025)
  4. Warsaw store underperforms (8% of baskets vs 23% for each other store)
  5. Coffee Beans price snapshot (8.50 before 2025-07-01, 11.99 from then on)
- **`docs/06_seed_expectations.md`** — Answer key for each demo pattern, with 6 verification SQL queries to confirm the patterns are present in the data.

### 2026-06-02 — Seed verification

All 6 verification queries from `docs/06_seed_expectations.md` run against the live Docker container and passed:

| # | Check | Result |
|---|-------|--------|
| 1 | Row count and date range | 4,990 rows, 2024-06-01 – 2026-05-31 ✓ |
| 2 | Coffee Beans top by units | 2,110 units — 4.65× the next product ✓ |
| 3 | December seasonal spike | Dec 2024 = 2.0×, Dec 2025 = 1.95× adjacent months ✓ |
| 4 | Warsaw underperforms | 3,696 revenue / 416 rows — ~36% of each other store ✓ |
| 5 | Household share collapse | Baseline ~14–23% Oct–Feb; drops to 1.0%, 0.0%, 0.2% in Mar–May 2026 ✓ |
| 6 | Coffee Beans price history | 8.50 through 2025-06-29, 11.99 from 2025-07-02 ✓ |

Q5 query updated: `COALESCE(..., 0)` added around the filtered Household SUM so zero-sales months return `0.0%` instead of `NULL`.

### 2026-06-02 — Backend skeleton

- **`pyproject.toml`** — Python package manifest with initial dependencies: FastAPI, Uvicorn, pydantic-settings, httpx. No DB or vector-store libraries yet.
- **`backend/config.py`** — `pydantic-settings` `Settings` class reading from `.env`. Covers `APP_ENV`, `DATABASE_URL`, `LLM_PROVIDER`, `OLLAMA_BASE_URL`, `OLLAMA_MODEL`.
- **`backend/main.py`** — FastAPI app with a single `/health` endpoint returning `{"status": "ok", "env": ..., "version": ...}`. Does not require Ollama to be running.
- **`backend/llm/base.py`** — `LLMProvider` ABC with a single abstract method `complete(prompt) -> str`.
- **`backend/llm/ollama.py`** — `OllamaProvider`: httpx POST to Ollama `/api/generate`, non-streaming.
- **`backend/llm/hosted_stub.py`** — `HostedProvider`: raises `NotImplementedError` until prod credentials are wired up.
- **`.env.example`** updated with `LLM_PROVIDER`, `OLLAMA_BASE_URL`, `OLLAMA_MODEL`.
- **`docs/02_decisions_log.md`** updated with decision #11 (LLM provider abstraction).
- **`README.md`** updated with backend install, run, and health-check instructions.
- Import check: `python -c "from backend.main import app"` passes (requires deps installed).
- `/health` confirmed reachable at `http://localhost:8000/health` when server is running.

### 2026-06-02 — Analytics Agent v1 (code complete; LLM demo partial)

**New files:**
- `backend/analytics/__init__.py` — package marker
- `backend/analytics/schema_context.py` — hardcoded compact `retail` schema + v1 business term definitions
- `backend/analytics/sql_validator.py` — static SQL safety validator (defense-in-depth)
- `backend/analytics/db.py` — query runner connecting exclusively as `analytics_reader`
- `backend/analytics/agent.py` — NL→SQL→answer pipeline; two LLM calls per question; `get_llm_provider()` factory
- `backend/analytics/cli.py` — CLI entry point (`py -3.11 -m backend.analytics.cli "<question>"`)

**Config / deps:**
- `psycopg[binary]>=3.1` added to `pyproject.toml`
- `analytics_database_url` added to `backend/config.py` (default: `analytics_reader` on local Docker)
- `.env.example` updated with `ANALYTICS_DATABASE_URL` and `OLLAMA_MODEL=qwen2.5-coder:7b`
- `docs/02_decisions_log.md` — Decision #12 added (static schema context + SQL validator rationale)
- `README.md` — analytics CLI section added

**Code checks (all PASS):**

| Check | Result |
|-------|--------|
| Import check | PASS |
| SQL validator: 7 safe inputs | 7/7 PASS |
| SQL validator: 14 unsafe inputs | 14/14 PASS |
| `analytics_reader` SELECT from `retail.sales` (4,990 rows) | PASS |
| Permission boundary: `SELECT COUNT(*) FROM app.chat_messages` | PASS — access denied |

**LLM demo (`qwen2.5-coder:7b`) — PARTIAL:**

| Question | Expected | Result |
|----------|----------|--------|
| Q1: Which category is declining? | Household share collapses Mar–May 2026 | FAIL — SQL error (aliasing bug in generated subquery) |
| Q2: What is the top-selling product? | Coffee Beans, ~2× units of next product | PASS — Coffee Beans 2,110 units ✓ |
| Q3: Best month / seasonality? | December, ~2× adjacent months | PARTIAL — December identified; no span analysis |
| Q4: Which store needs attention? | Warsaw, ~⅓ of other stores | FAIL — SQL error (hallucinated CTE name) |
| Q5: Price change? | Coffee Beans 8.50→11.99 on 2025-07-01 | FAIL — SQL error (window function in WHERE) |

**LLM demo verification (`qwen2.5-coder:7b`) — ALL PASS:**

| Question | Expected | Result | Status |
|----------|----------|--------|--------|
| Q1: Which category is declining? | Household share collapses Mar–May 2026 | "Household, revenue from avg $305 → $10.73 in last 3 months" | ✓ PASS |
| Q2: What is the top-selling product? | Coffee Beans, ~5× next product | "Coffee Beans, 2110 units" | ✓ PASS |
| Q3: Best month / seasonality? | December, ~2× adjacent months | "December 2025, $3,401.77, nearly twice the average" | ✓ PASS |
| Q4: Which store needs attention? | Warsaw, ~⅓ of other stores | "RetailMind Warsaw, $3,696.67, 134 baskets" | ✓ PASS |
| Q5: Price change? | Coffee Beans 8.50→11.99 on 2025-07-01 | "Coffee Beans, $8.50 to $11.99, July 2025" | ✓ PASS |

**Status: Analytics Agent v1 complete and verified.**

Key implementation note: `_compute_observations()` in `backend/analytics/agent.py` post-processes
SQL results in Python (computing baseline vs recent averages, peak/ratio for time series) and
appends a one-line summary to the answer LLM prompt. This proved necessary because
`qwen2.5-coder:7b` generates correct SQL but cannot reliably reason over 59-row tabular results
to identify patterns. The observation summary is computed deterministically — no special-casing
per question string.

### 2026-06-03 — Analytics API endpoint

**Changed file:**
- `backend/main.py` — added `AnalyticsRequest` and `AnalyticsResponse` Pydantic models; added `POST /analytics` endpoint that calls the existing `backend.analytics.agent.run()` pipeline

**No other files modified.** All analytics logic (`agent.py`, `db.py`, `sql_validator.py`, `schema_context.py`) is unchanged.

**Checks (all PASS):**

| Check | Result |
|-------|--------|
| Import check: `from backend.main import app` | PASS |
| `GET /health` | `{"status":"ok","env":"dev","version":"0.1.0"}` ✓ |
| `POST /analytics` — "What is the top-selling product?" | Coffee Beans, 2110 units ✓ |

**POST /analytics response shape:**
```json
{
  "question": "...",
  "sql": "...",
  "columns": [...],
  "rows": [...],
  "answer": "..."
}
```

**Error handling:**
- `400` — `ValueError` from SQL validator (safe message, no stack trace)
- `503` — `psycopg.Error` (database unavailable)
- `503` — `httpx.HTTPError` (Ollama unavailable)

---

## Up next

- Build document agent (RAG over PDFs)
- Build router (classify question as `document` vs `analytics` vs `unknown`)
