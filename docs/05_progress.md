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

## Up next

### Analytics agent standalone script — `backend/analytics/`

Build the NL→SQL pipeline as a standalone, runnable script before wiring it into FastAPI:

- Connect to Postgres as the `analytics_reader` role (read-only, `retail` schema only).
- Accept a natural-language question, call `LLMProvider.complete()` to generate SQL, execute it, return the result in plain language.
- Test against the seed data using the five demo patterns from `docs/06_seed_expectations.md`.
- **Hard rule:** the `analytics_reader` role must be used for all queries — never `postgres` or any role with write access.
- Add a decision log entry for the NL→SQL prompting strategy once it is chosen.
