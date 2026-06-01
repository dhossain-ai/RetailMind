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

## Up next

### Backend skeleton — `backend/`

Core Python package structure and dependency setup:
- `pyproject.toml` or `requirements.txt` with initial dependencies (FastAPI, psycopg2/asyncpg, chromadb, httpx for Ollama)
- Provider abstraction layer: a minimal `LLMProvider` interface with a local Ollama adapter and a stub hosted adapter
- Initial FastAPI app entry point with a `/health` endpoint

This sets up the foundation before building the analytics agent (NL→SQL) or the document pipeline (chunking + ChromaDB ingestion).
