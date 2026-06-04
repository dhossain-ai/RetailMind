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

### 2026-06-03 — Document Agent v1 (standalone)

**New files:**
- `backend/documents/__init__.py` — package marker
- `backend/documents/extract.py` — page-by-page text extraction via PyMuPDF; yields `(page_num, text)` per page
- `backend/documents/chunking.py` — character chunking: 800 chars / 80-char overlap per page
- `backend/documents/embeddings.py` — `sentence-transformers` `all-MiniLM-L6-v2`; lazy-loaded; `embed(texts) -> list[list[float]]`
- `backend/documents/db.py` — `get_or_create_document()` / `update_chunk_count()` via `DATABASE_URL` (postgres role); writes to `app.documents`; never uses `analytics_reader`
- `backend/documents/vectorstore.py` — ChromaDB `PersistentClient` with cosine distance; `ingest_chunks()` and `query()`; distance metric (0–2, lower = more similar) documented inline
- `backend/documents/agent.py` — `ingest()` (extract → chunk → embed → store + Postgres metadata) and `run()` (embed question → retrieve → LLM → answer + citations); LLM instructed to refuse if context lacks the answer
- `backend/documents/cli.py` — `ingest` and `query` subcommands
- `data/sample_docs/sample_policy.pdf` — retail policy document: returns, supplier vetting, store hours, product handling, data privacy (committed; generated by `scripts/generate_sample_doc.py` using PyMuPDF)
- `scripts/generate_sample_doc.py` — one-time PDF generation script

**Config / deps:**
- `pymupdf>=1.24`, `chromadb>=0.5`, `sentence-transformers>=3.0` added to `pyproject.toml`
- `CHROMA_PATH`, `EMBEDDING_MODEL`, `DOCUMENT_TOP_K` added to `backend/config.py` and `.env.example`
- `data/chroma/` added to `.gitignore` (runtime-generated, never committed)
- Decision #13 added to `docs/02_decisions_log.md` (PyMuPDF + sentence-transformers + ChromaDB rationale; no LangChain in v1; retrieval honesty approach)

**Ingestion result:**
- `sample_policy.pdf` → document_id 1, 13 chunks
- `app.documents` row: `id=1, filename=sample_policy.pdf, title=Sample Policy, chunk_count=13`
- `data/chroma/` created with sqlite3 index + HNSW binary files

**Retrieval / query verification (all PASS):**

| # | Question | Expected | Result | Status |
|---|----------|----------|--------|--------|
| Q1 | What is the return policy? | 30-day window, holiday extension, exclusions | Full policy with correct details | PASS |
| Q2 | How long do customers have to return items? | 30 days (60 during holiday) | "30 days... extended to 60 days during holiday season" | PASS |
| Q3 | What are the store operating hours? | Mon–Fri 08:00–20:00, Sat 09:00–18:00, Sun 10:00–16:00 | Correct hours from document | PASS |
| Q4 | What is the supplier vetting process? | 4-step process (docs → audit → CoC → trial order) | All 4 steps listed correctly | PASS |
| Q5 | What is the capital of France? | Honest refusal | "I cannot find that information in the available documents." | PASS |

**Citation check (PASS):** All Q1–Q4 answers include `[sample_policy.pdf, page X, chunk Y]` source references.

**ChromaDB persistence check (PASS):** `data/chroma/` exists with `chroma.sqlite3` (385 KB) and HNSW index files; queries run correctly in a fresh process after ingestion.

**Note:** The en-dash character (`–`) in store hours renders as `?` in the Windows cp1252 console. The data stored in ChromaDB is correct UTF-8; this is a terminal encoding display issue only.

**Status: Document Agent v1 complete and verified.**

---

### 2026-06-03 — Document API endpoints

**Changed files:**
- `backend/main.py` — added `DocumentUploadResponse`, `DocumentQueryRequest`, `DocumentQueryResponse` Pydantic models; added `POST /documents/upload` and `POST /documents/query` endpoints
- `backend/config.py` — added `uploads_path` setting (default `data/uploads`)
- `pyproject.toml` — declared `python-multipart>=0.0.9` explicitly (already installed as transitive dep)
- `.env.example` — added `UPLOADS_PATH` with comment
- `.gitignore` — added `data/uploads/`

**No new modules created.** Both endpoints delegate entirely to the existing `backend.documents.agent.ingest()` and `backend.documents.agent.run()` — no logic duplication.

**File handling:**
- Uploaded PDFs saved to `data/uploads/{8-hex-chars}_{original_name}` — UUID prefix prevents silent overwrites and Chroma duplicate-ID collisions on re-upload of the same file
- Non-PDF files rejected with `400` before any file is written to disk
- On ingestion failure: saved file is deleted before the `5xx` response is returned

**Checks (all PASS):**

| Check | Result |
|-------|--------|
| Import check: `from backend.main import app` | PASS |
| Routes registered | `/health`, `/analytics`, `/documents/upload`, `/documents/query` |
| `GET /health` | `{"status":"ok","env":"dev","version":"0.1.0"}` |
| `POST /analytics` regression | Coffee Beans, 2110 units ✓ |
| `POST /documents/upload` — `sample_policy.pdf` | `document_id:2, chunk_count:13, status:ingested` ✓ |
| `POST /documents/query` — "What is the return policy?" | Full policy with citations ✓ |
| `POST /documents/query` — "What is the capital of France?" | Honest refusal ✓ |
| Non-PDF upload | `400 Only PDF files are accepted.` ✓ |
| `data/uploads/` not in `git status` | ✓ gitignored |

---

### 2026-06-03 — Router v1 + unified POST /chat endpoint

**New files:**
- `backend/router.py` — deterministic weighted classifier; two (regex, weight) rule lists (analytics and document); strong multi-word phrases score 3, generic single keywords score 1; tie or both-zero → `unknown`; includes `__main__` self-test block

**Changed files:**
- `backend/main.py` — added `ChatRequest` / `ChatResponse` Pydantic models; added `POST /chat` endpoint that classifies with the router and delegates to the existing analytics or document agent; consistent response shape with nullable fields for unused domains; `unknown` route returns HTTP 200 with a helpful fallback message
- `docs/02_decisions_log.md` — Decision #14: why deterministic keyword scoring over an LLM router
- `README.md` — `/chat` endpoint section with curl + PowerShell examples and response table

**Router self-test (7/7 PASS):**

| Question | Expected | Score (a / d) | Result |
|----------|----------|---------------|--------|
| What is the top-selling product? | analytics | a=5 / d=0 | ✓ PASS |
| Which category is declining? | analytics | a=5 / d=0 | ✓ PASS |
| Which store needs attention? | analytics | a=4 / d=0 | ✓ PASS |
| What is the return policy? | document | a=0 / d=5 | ✓ PASS |
| What is the supplier vetting process? | document | a=0 / d=5 | ✓ PASS |
| What are the store operating hours? | document | a=1 / d=4 | ✓ PASS |
| What is the capital of France? | unknown | a=0 / d=0 | ✓ PASS |

**Regression checks (all PASS):**

| Check | Result |
|-------|--------|
| Import check: `from backend.main import app` | PASS |
| `GET /health` | `{"status":"ok","env":"dev","version":"0.1.0"}` ✓ |
| `POST /analytics` — "What is the top-selling product?" | Coffee Beans, 2,110 units ✓ |
| `POST /documents/query` — "What is the return policy?" | Full policy with citations ✓ |

**POST /chat test results (all PASS):**

| # | Message | Expected route | Result route | Answer summary |
|---|---------|----------------|--------------|----------------|
| 1 | What is the top-selling product? | analytics | analytics | Coffee Beans, 2,110 units ✓ |
| 2 | Which category is declining? | analytics | analytics | Household, −96.5% revenue ✓ |
| 3 | What is the return policy? | document | document | 30-day window, holiday extension, exclusions + citations ✓ |
| 4 | What is the supplier vetting process? | document | document | 4-step vetting process + citations ✓ |
| 5 | What is the capital of France? | unknown | unknown | Helpful fallback, sql=null, sources=null ✓ |

**Status: Router v1 and POST /chat complete and verified.**

Design note: "store operating hours" correctly routes to document (a=1, d=4) — the strong "operating hours" phrase (+3) outweighs the generic "store" analytics match (+1). This confirms that weighted phrases prevent single-word ambiguity from misrouting.

---

### 2026-06-03 — Evaluation v1

**New files:**
- `scripts/eval_router.py` — 7 classification checks; no external dependencies
- `scripts/eval_analytics.py` — 2 DB security checks + 5 seeded demo question checks (structured rows + answer key-facts); requires Postgres + Ollama
- `scripts/eval_documents.py` — 4 document Q&A checks with source citation validation; auto-ingests `sample_policy.pdf` if ChromaDB is empty; requires Postgres + Ollama
- `scripts/eval_all.py` — runs all three in sequence plus 4 optional API checks (GET /health, POST /chat x3); API checks skipped without server; exits non-zero on any real failure

**Design note:** Decision #15 (see `docs/02_decisions_log.md`): key-fact assertions over exact LLM wording. Analytics checks validate structured output (rows, columns, SQL) first; answer text is a secondary check. No pytest — plain Python scripts runnable with a single command.

**Full eval run results (2026-06-03):**

| Suite | Result |
|-------|--------|
| Router: 7 classification cases | 7/7 PASS |
| Analytics: security boundary (retail.sales readable, app.chat_messages denied) | 2/2 PASS |
| Analytics: declining category (Household in rows + answer) | PASS |
| Analytics: top-selling product (Coffee Beans, rows[0] + answer) | PASS |
| Analytics: best month / seasonality (December in rows + answer) | PASS |
| Analytics: store needing attention (Warsaw in rows[0] + answer) | PASS |
| Analytics: price change (8.50 + 11.99 in rows + answer) | PASS |
| Document: return policy (30 days in answer + sources) | PASS |
| Document: supplier vetting (steps in answer + sources) | PASS |
| Document: store hours (hours in answer + sources) | PASS |
| Document: unrelated question (honest refusal) | PASS |
| API: GET /health | PASS |
| API: POST /chat -> analytics | PASS |
| API: POST /chat -> document | PASS |
| API: POST /chat -> unknown | PASS |
| **TOTAL** | **22/22** |

**Status: Evaluation v1 complete. All 22 checks pass.**

---

### 2026-06-03 — Frontend-backend integration (CORS)

**Changed files:**
- `backend/config.py` — added `cors_origins: list[str]` setting (default: `localhost:3000` and `127.0.0.1:3000`); reads from `CORS_ORIGINS` env var (expects JSON array string)
- `backend/main.py` — added `CORSMiddleware` using `settings.cors_origins`; `allow_methods=["GET","POST"]`, `allow_headers=["Content-Type"]`; no wildcard origins
- `.env.example` — documented `CORS_ORIGINS` with warning against `"*"` in production and example production value

**Root cause:** Browser sends an OPTIONS preflight before every cross-origin POST. Without `CORSMiddleware`, FastAPI returned `405 Method Not Allowed` for OPTIONS, blocking all requests from the frontend at `http://localhost:3000`.

**Import check:** PASS

**CORS preflight verification:**
```
OPTIONS /chat (Origin: http://localhost:3000)
  → HTTP 200
  → access-control-allow-origin: http://localhost:3000
  → access-control-allow-methods: GET, POST
```

**Endpoint spot checks:**

| Check | Result |
|-------|--------|
| `GET /health` | `{"status":"ok","env":"dev","version":"0.1.0"}` ✓ |
| `POST /chat` → document ("What is the return policy?") | `route=document`, 30-day policy + citations ✓ |
| `POST /chat` → unknown ("What is the capital of France?") | `route=unknown`, helpful fallback ✓ |
| `POST /chat` → analytics ("What is the top-selling product?") | See eval results below |

**Note on analytics 503 during parallel tests:** When the document `/chat` test (which cold-loads the sentence-transformers embedding model) ran in parallel with the analytics `/chat` test, the analytics LLM call hit the 60-second httpx timeout while Ollama was backlogged. This is a resource-contention artefact of firing all three queries simultaneously in testing — not a CORS issue and not a regression. The sequential eval run below confirms analytics works correctly.

**Frontend lint:** `npm run lint` — PASS (no output = no errors)

**Frontend build:** `npm run build` — PASS
```
▲ Next.js 16.2.7 (Turbopack)
✓ Compiled successfully in 2.6s
✓ Generating static pages (4/4)
Route (app): / (Static)
```

**Eval results (`py -3.11 scripts/eval_all.py`):**

| Suite | Result |
|-------|--------|
| Router: 7 classification cases | 7/7 PASS |
| Analytics: security boundary (retail.sales readable, app.chat_messages denied) | 2/2 PASS |
| Analytics: declining category | PASS |
| Analytics: top-selling product (Coffee Beans, 2,110 units) | PASS |
| Analytics: best month / seasonality (December 2025) | PASS |
| Analytics: store needing attention (Warsaw) | PASS |
| Analytics: price change (Coffee Beans 8.50→11.99) | PASS |
| Document: return policy (30 days + citations) | PASS |
| Document: supplier vetting (4 steps + citations) | PASS |
| Document: store hours (hours + citations) | PASS |
| Document: unrelated question (honest refusal) | PASS |
| API: GET /health | PASS |
| API: POST /chat → analytics | PASS |
| API: POST /chat → document | PASS |
| API: POST /chat → unknown | PASS |
| **TOTAL** | **22/22** |

**Note on first eval run:** The Postgres Docker container exited mid-run (unrelated infrastructure event), causing 2 analytics security checks to fail with connection timeout. After `docker start retailmind-db-1`, the second run produced 22/22.

**Status: Frontend-backend integration verified. CORS enabled, all checks pass.**

---

---

### 2026-06-04 — Business Data Upload v1 — Phase 1: Database foundation

**New file:**
- `scripts/003_business_sales.sql` — adds `app.datasets` and `retail.business_sales`; creates two indexes; explicit `GRANT SELECT ON retail.business_sales TO analytics_reader`

**Changed files:**
- `docs/02_decisions_log.md` — Decision #16: flat table design, nullable `store`, no cross-schema FK, plain `revenue` column, explicit grant rationale

**No backend or frontend code changes in this phase.**

**Schema additions:**

`app.datasets` — metadata for each uploaded CSV/XLSX (mirrors `app.documents` pattern):
- `id` SERIAL PK, `original_filename`, `stored_filename`, `row_count` (nullable until ingestion completes), `skipped_count`, `upload_date`, `created_at`

`retail.business_sales` — flat fact table for uploaded business sales data:
- `id` SERIAL PK, `dataset_id` INT NOT NULL (app-layer reference to `app.datasets`), `sale_date` DATE, `product` TEXT NOT NULL with non-blank check, `category` TEXT nullable, `store` TEXT nullable, `quantity` INT NOT NULL > 0, `unit_price` NUMERIC nullable ≥ 0, `revenue` NUMERIC NOT NULL ≥ 0, `created_at`
- Indexes: `(dataset_id)` and `(dataset_id, sale_date)`
- Explicit `GRANT SELECT … TO analytics_reader`; `app.datasets` not granted

**Key design decisions (Decision #16):**
- Flat table: no FK joins to demo dimension tables — uploaded data is fully isolated from seed data
- `store` nullable so single-location businesses can omit it without schema changes later
- No cross-schema DB FK: `dataset_id` is enforced at the app layer to preserve the `retail`/`app` isolation boundary
- `revenue` is plain (not generated) because `unit_price` is nullable in many CSV exports

**Verification results:**

| Check | Result |
|-------|--------|
| `\dt retail.*` — `business_sales` present | ✓ |
| `\dt app.*` — `datasets` present | ✓ |
| `\d retail.business_sales` — columns and constraints correct | ✓ |
| `\di retail.*` — both indexes present | ✓ |
| `analytics_reader SELECT FROM retail.business_sales` | ✓ (0 rows, no error) |
| `analytics_reader SELECT FROM app.datasets` | ✓ (permission denied — boundary intact) |
| `eval_all.py` regression | ✓ 18/18 passed (4 API checks skipped — server not running) |

---

---

### 2026-06-04 — Business Data Upload v1 — Phase 2: Backend upload pipeline

**New files:**
- `backend/uploads/__init__.py` — package marker
- `backend/uploads/parser.py` — CSV/XLSX reading, header normalisation, synonym mapping, row-limit check
- `backend/uploads/validator.py` — row-level type coercion (date, numeric), currency stripping, revenue derivation, skip/count
- `backend/uploads/db.py` — single-transaction insert into `app.datasets` + `retail.business_sales`; `list_datasets()` for GET endpoint
- `backend/uploads/agent.py` — `ingest(path, original_filename)` orchestrator
- `data/sample_docs/sample_sales.csv` — 20-row sample for manual verification and future eval fixtures
- `data/sample_docs/sample_sales.xlsx` — XLSX equivalent (5 rows) for format verification

**Modified files:**
- `backend/main.py` — added `DatasetUploadResponse`, `DatasetListItem` models; added `POST /datasets/upload` and `GET /datasets` endpoints
- `pyproject.toml` — added `openpyxl>=3.1`
- `docs/02_decisions_log.md` — Decision #17: no pandas, utf-8-sig, uuid stored filename, skip-invalid-rows rationale

**Key design decisions (Decision #17):**
- stdlib `csv` + `openpyxl`; no pandas
- `utf-8-sig` encoding for CSV to handle Excel BOM headers
- Currency symbol and thousands-comma stripping before Decimal parsing (`$1,200.50`, `€12.50`, `£3.99`)
- uuid-hex stored filename; original filename in metadata only
- 50,000-row hard limit as a constant; invalid rows skipped not rejected
- Single psycopg transaction: `app.datasets` row + `retail.business_sales` bulk insert + commit atomically

**Verification results:**

| Check | Result |
|-------|--------|
| Import check: all new modules | ✓ |
| Routes registered: `/datasets/upload`, `/datasets` | ✓ |
| Upload valid CSV (20 rows) | ✓ `dataset_id=1, row_count=20, skipped_count=0` |
| Upload valid XLSX (5 rows) | ✓ `dataset_id=2, row_count=5, skipped_count=0` |
| `GET /datasets` — newest first, both entries | ✓ |
| DB rows in `retail.business_sales` (dataset 1) | ✓ 20 rows, dates 2024-01-05 → 2024-03-31 |
| DB rows in `retail.business_sales` (dataset 2) | ✓ 5 rows, dates 2024-01-05 → 2024-03-04 |
| Upload missing date column → 400 with field name | ✓ |
| Upload all-invalid rows → 400 with skipped count | ✓ |
| Upload `.xls` → 400 "Only .csv and .xlsx accepted" | ✓ |
| `eval_all.py` regression — router 7/7, document 4/4, API 4/4 | ✓ |
| Analytics 7/7 (re-run after Ollama warm-up) | ✓ |

Note: first `eval_all.py` run showed analytics 2/7 because Ollama returned HTTP 500 during model loading while the newly started server competed for resources. Re-running `eval_analytics.py` in isolation after warm-up confirmed 7/7 — no code regression.

---

---

### 2026-06-04 — Business Data Upload v1 — Phase 3: analytics agent extension

**Changed files:**
- `backend/analytics/schema_context.py` — added `BUSINESS_SCHEMA_CONTEXT_TEMPLATE` (format string; `{dataset_id}` replaced at call time)
- `backend/analytics/sql_validator.py` — refactored shared safety checks into `_standard_checks()`; added `validate_uploaded(sql, dataset_id)` with allowlist and dataset_id filter enforcement
- `backend/analytics/agent.py` — added `dataset_id: int | None = None` param to `run()`; added `_BUSINESS_SQL_PROMPT` with four flat-table templates; routes schema/prompt/validator based on `dataset_id`; `run()` now returns `mode` ("uploaded" or "demo")
- `backend/main.py` — added `dataset_id: int | None = None` (with positive-integer validator) to `AnalyticsRequest` and `ChatRequest`; added `mode: str | None = None` to `AnalyticsResponse` and `ChatResponse`; threaded `dataset_id` to agent calls; `/chat` passes `mode` in analytics responses

**New files:**
- `scripts/eval_uploads.py` — 4 core checks (direct Python calls: upload fixture, top product, total revenue, best month) + 2 optional API checks; demo regression confirms `dataset_id=None` still uses star schema
- `docs/02_decisions_log.md` — Decision #18: why `dataset_id` routing chooses context/prompt/validator, not a separate agent

**Key design decisions (Decision #18):**
- `dataset_id` branches inside `run()`, not a separate agent — single function, minimal footprint
- Allowlist in `validate_uploaded`: any `retail.<table>` other than `business_sales` is rejected (not a blacklist)
- `dataset_id` filter regex allows optional table alias prefix (`bs.dataset_id = N`)
- `mode` field on responses is optional (`str | None`) to remain backwards-compatible with existing clients

**Verification results:**

| Check | Result |
|-------|--------|
| Import check: all modified modules | ✓ |
| POST /analytics with dataset_id=4 — top product | Coffee Beans (13 units), mode=uploaded, SQL uses business_sales ✓ |
| POST /analytics without dataset_id — demo regression | Coffee Beans (2,110 units), mode=demo, SQL uses retail.sales ✓ |
| POST /chat with dataset_id — analytics routing | route=analytics, mode=uploaded, SQL uses business_sales ✓ |
| POST /analytics with dataset_id=0 | 422 "dataset_id must be a positive integer." ✓ |
| POST /analytics with dataset_id=-5 | 422 "dataset_id must be a positive integer." ✓ |
| eval_uploads.py — 4 core + 2 API | 6/6 PASS ✓ |
| eval_all.py — full suite | 28/28 PASS ✓ |

**eval_all.py summary (2026-06-04):**

| Suite | Result |
|-------|--------|
| Router: 7 classification cases | 7/7 PASS |
| Analytics: 2 security + 5 demo questions | 7/7 PASS |
| Document: 4 Q&A checks | 4/4 PASS |
| Uploads: 4 core + 2 API | 6/6 PASS |
| API: GET /health + POST /chat ×3 | 4/4 PASS |
| **TOTAL** | **28/28** |

**Status: Business Data Upload v1 — Phase 3 complete and verified.**

---

## Up next

- Business Data Upload v1 — Phase 4: frontend (dataset upload widget, dataset selector, mode badge)
