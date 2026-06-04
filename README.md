# RetailMind

**Portfolio-grade AI chat assistant for small retail businesses** — ask natural-language questions about your sales data and policy documents, or upload your own CSV/XLSX for instant analytics.

> This is a portfolio-grade MVP, not production SaaS. See [Known limitations](#known-limitations).

---

## What it does

RetailMind is a single chat interface with two capabilities. **Analytics Q&A** translates natural-language questions into SQL, runs them against Postgres, and returns a plain-English answer with the generated SQL and result table. **Document Q&A** retrieves relevant chunks from uploaded PDFs and produces a grounded answer with source citations. A lightweight keyword router decides which capability handles each question — no extra LLM call per request.

A third capability — **business data upload** — lets users upload their own CSV or XLSX sales files directly from the frontend. Rows are validated and loaded into Postgres for immediate analytics. A dataset selector in the sidebar switches between a pre-seeded demo dataset and any uploaded dataset.

## Why I built it

Small retailers and service businesses often have sales data and policy documents, but no data team or internal analytics tooling. A conversational interface lets non-technical staff query their own data without writing SQL or reading through documents manually.

Technically, I built RetailMind to demonstrate AI/backend engineering skills end-to-end: FastAPI, Postgres schema design and SQL safety, retrieval-augmented generation (RAG), natural-language-to-SQL, LLM routing, CSV/XLSX ingestion, React frontend integration, and evaluation. It is a portfolio-grade MVP.

## Key features

- **Natural language → SQL** over a seeded 4,990-row demo retail dataset (star schema: sales, products, stores, categories)
- **PDF document Q&A** with source citations — upload policy docs, supplier contracts, or catalogues
- **CSV/XLSX business data upload** — rows validated and stored in Postgres for instant analytics
- **Dataset selector** — switch between demo data and any uploaded dataset; each chat request carries the correct `dataset_id`
- **Source mode badge** on every analytics response — *Analytics · Demo Data* or *Analytics · Uploaded · filename.csv*
- **Deterministic keyword router** — no extra LLM call; classifies analytics, document, and unknown questions
- **Security boundary** — the `analytics_reader` role has `SELECT` on `retail.*` only; generated SQL physically cannot reach chat history or document metadata, even under prompt injection
- **28/28 evaluation suite** — router, analytics, document, and uploads checks with structured assertions

---

## Architecture

```
Browser
  │
  ▼
Next.js frontend  (React, Tailwind CSS)
  │  POST /chat  { message, dataset_id? }
  ▼
FastAPI backend
  ├── Router  (keyword scorer — no LLM call)
  │     ├── analytics  →  Analytics Agent
  │     │     ├── NL → SQL prompt  (Ollama LLM)
  │     │     ├── SQL validator    (static safety checks)
  │     │     └── Postgres         analytics_reader role
  │     └── document  →  Document Agent
  │           ├── Embed question   (sentence-transformers)
  │           ├── ChromaDB         similarity search
  │           └── LLM answer       (Ollama)
  │
  ├── POST /datasets/upload  →  Upload Pipeline
  │     ├── CSV/XLSX parse + row-level validation
  │     └── Postgres  retail.business_sales
  │
  └── POST /documents/upload  →  PDF Ingest Pipeline
        ├── PyMuPDF extract + character chunking
        └── ChromaDB  vector store
```

The LLM abstraction layer (`backend/llm/`) means swapping Ollama for a hosted provider (Anthropic, OpenAI) is a one-line config change — no agent code changes required.

---

## Two analytics modes

**Demo mode** (default — no setup beyond Docker): 4,990 seeded sales rows across 24 months, stored in a normalised star schema. Five deliberate patterns are planted — a standout bestseller, a declining category, a seasonal spike, an underperforming store, and a historical price change — so demo queries always return interesting answers. Selecting *Demo Data* in the sidebar sends no `dataset_id` to the backend.

**Uploaded mode**: Upload a CSV or XLSX from the sidebar. Rows are validated row-by-row and loaded into `retail.business_sales`, a flat fact table fully isolated from the demo schema. After upload, the new dataset is auto-selected. Each chat request sends `dataset_id`; the analytics agent switches to a different schema context, SQL templates, and SQL validator that allows only `retail.business_sales`.

The two datasets are completely isolated. A query against uploaded data cannot touch the demo star schema, and vice versa.

---

## Two upload paths

| | PDF documents | Sales data |
|---|---|---|
| Accepted formats | `.pdf` | `.csv`, `.xlsx` |
| Stored in | ChromaDB (text chunks + embeddings) | Postgres (`retail.business_sales`) |
| Queried via | Vector similarity → LLM answer | NL → SQL → Postgres |
| Use case | Policy Q&A, supplier docs, catalogues | Revenue, product, store analytics |
| Validation | Extension check | Row-level type coercion; invalid rows skipped, `skipped_count` returned |

PDFs go to ChromaDB because the query pattern is "find text that matches this question." Sales data goes to Postgres because the query pattern is "aggregate rows that match this filter." Both use the same `/chat` endpoint; the router decides which pipeline runs.

---

## Demo workflows

### Demo analytics

Select *Demo Data* in the sidebar (the default), then ask:

- *"Which category is declining?"*
- *"What is the top-selling product?"*
- *"Which store needs the most attention?"*
- *"Did any product have a price change?"*

The response shows the generated SQL, the result table, a plain-English answer, and an *Analytics · Demo Data* badge.

### Uploaded CSV/XLSX analytics

1. Click *Upload Sales Data* in the sidebar and drop a `.csv` or `.xlsx` file.
2. After upload, the dataset auto-selects in the selector below.
3. Ask *"What is the top-selling product?"* — the same question now runs against your data.
4. The badge shows *Analytics · Uploaded · your_file.csv*.
5. Click *Demo Data* to switch back to the seeded dataset.

A sample file is available at `data/sample_docs/sample_sales.csv`.

### PDF document Q&A

1. Click *Upload Document* in the sidebar and drop a PDF.
2. Ask *"What is the return policy?"* or *"What is the supplier vetting process?"*
3. The response shows a grounded answer with source citations (`[filename.pdf, page N, chunk N]`).

A sample policy document is available at `data/sample_docs/sample_policy.pdf`.

---

## Screenshots

> Screenshots below are from a local development instance with the seeded demo data and `sample_policy.pdf` ingested. Capture your own after running locally (see `docs/screenshots/`).

*Screenshots coming soon — add captures to `docs/screenshots/` and update this section.*

<!--
Planned captures:
  docs/screenshots/01_demo_analytics.png     — analytics query, SQL + table, "Analytics · Demo Data" badge
  docs/screenshots/02_uploaded_analytics.png — uploaded CSV query, "Analytics · Uploaded · filename.csv" badge
  docs/screenshots/03_document_qa.png        — document Q&A with source citations
  docs/screenshots/04_dataset_selector.png   — sidebar showing Demo Data + uploaded dataset
  docs/screenshots/05_csv_upload_success.png — upload feedback with row count
-->

---

## Tech stack

| Layer | Technology |
|---|---|
| Frontend | Next.js 16, React 19, Tailwind CSS 4 |
| Backend | Python 3.11, FastAPI, Pydantic v2 |
| Relational DB | PostgreSQL 16 (Docker in dev) |
| Vector DB | ChromaDB (local persistent client) |
| Embeddings | `sentence-transformers` / `all-MiniLM-L6-v2` (384-dim, ~23 MB) |
| PDF extraction | PyMuPDF |
| Spreadsheet parsing | stdlib `csv` + `openpyxl` (no pandas) |
| Local LLM | Ollama — `qwen2.5-coder:7b` |
| LLM abstraction | Custom ABC: `OllamaProvider` (dev) + `HostedProvider` stub |
| HTTP client | httpx |

---

## Local setup

### Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) — runs Postgres
- Python 3.11+
- [Ollama](https://ollama.com/) — runs the local LLM
- Node.js 18+ — runs the frontend

### Steps

```bash
# 1. Clone and configure
git clone https://github.com/dhossain-ai/RetailMind.git
cd RetailMind
cp .env.example .env          # defaults work for local dev; no changes required

# 2. Start Postgres  (seeds ~5,000 demo rows automatically on first boot)
docker compose up -d

# 3. Install Python dependencies and start the API server
pip install -e .
uvicorn backend.main:app --reload
# API:      http://localhost:8000
# OpenAPI:  http://localhost:8000/docs

# 4. Pull the local LLM  (one-time download, ~4 GB)
ollama pull qwen2.5-coder:7b

# 5. Ingest the sample policy document  (auto-skipped if already ingested)
py -3.11 -m backend.documents.cli ingest data/sample_docs/sample_policy.pdf

# 6. Install frontend dependencies and start the dev server
cd frontend
npm install
npm run dev                   # → http://localhost:3000
```

Open http://localhost:3000. The sidebar has document upload and sales data upload. Demo data is pre-loaded — analytics works immediately after the API server and Ollama are running.

### Database reset

The seed script starts with `TRUNCATE … RESTART IDENTITY CASCADE` and is safe to re-run. To get a completely fresh container:

```bash
docker compose down -v   # deletes the volume — all data is lost
docker compose up -d     # fresh boot; init scripts run again
```

> **Editing migration files:** If you change `001_schema.sql` or `002_seed.sql`, a plain `docker compose up` silently ignores the changes because the data directory already exists. Use `docker compose down -v` first.

---

## Evaluation

The evaluation suite verifies the router, analytics agent, document agent, and upload pipeline against deterministic fixtures.

### Run all checks

```bash
py -3.11 scripts/eval_all.py
```

Expected output (with server running):

```
============================================================
RetailMind - Evaluation v1
============================================================
...
  Router:    7/7
  Analytics: 7/7
  Document:  4/4
  Uploads:   6/6
  API:       4/4
  ------------------------------
  TOTAL:     28/28 passed
============================================================
```

Exit code 0 on full pass, 1 on any failure. The four API checks (`GET /health`, `POST /chat` × 3) are silently skipped when the server is not running; the remaining 24 checks run regardless.

### Individual scripts

| Script | Dependencies | What it checks |
|---|---|---|
| `py -3.11 scripts/eval_router.py` | none | 7 classification cases |
| `py -3.11 scripts/eval_analytics.py` | Postgres + Ollama | 2 security boundary checks + 5 seeded demo Q&A |
| `py -3.11 scripts/eval_documents.py` | Postgres + Ollama + ChromaDB | 4 document Q&A + source citations |
| `py -3.11 scripts/eval_uploads.py` | Postgres + Ollama | 4 uploaded dataset checks + 2 optional API checks |
| `py -3.11 scripts/eval_all.py` | all of the above | all checks in sequence |

### Design note

Analytics checks validate structured output first (SQL, rows, columns) — deterministic database output. Answer text is asserted on key facts ("Coffee Beans", "Household", "Warsaw") rather than exact strings, so the suite stays stable across model versions. See [Decision #15](docs/02_decisions_log.md) for the full rationale.

---

## Design decisions

Every non-obvious decision is recorded in [`docs/02_decisions_log.md`](docs/02_decisions_log.md) with a plain-language explanation. Highlights:

- **Two Postgres schemas (`retail` / `app`)** — `analytics_reader` has `SELECT` on `retail.*` only; generated SQL cannot reach chat history or document metadata even under prompt injection. ([Decision #1](docs/02_decisions_log.md))
- **Flat table for uploaded data (`retail.business_sales`), not reusing the demo star schema** — the two datasets are completely isolated; the agent routes to one or the other based on `dataset_id`. ([Decision #16](docs/02_decisions_log.md))
- **Deterministic keyword router, not an LLM classifier** — no extra round-trip per query; fully testable without a running LLM. ([Decision #14](docs/02_decisions_log.md))
- **Static schema context, not `information_schema` queries** — faster, allows human-authored business-term definitions, no runtime DB dependency in the prompt path. ([Decision #12](docs/02_decisions_log.md))
- **No LangChain/LlamaIndex** — the RAG pipeline is five explicit steps (extract → chunk → embed → retrieve → answer); plain functions are easier to trace and explain. ([Decision #13](docs/02_decisions_log.md))
- **No pandas in the upload pipeline** — stdlib `csv` + `openpyxl` covers all parsing needs; avoids a 25 MB dependency. ([Decision #17](docs/02_decisions_log.md))

---

## Known limitations

This is a portfolio-grade MVP, not production software.

- **Single-business, local mode only.** No authentication, no multi-tenancy. All uploaded datasets are visible to anyone with access to the running app.
- **Local LLM only.** The hosted provider stub (`backend/llm/hosted_stub.py`) exists but is not wired up. Requires a local Ollama installation.
- **No persistent chat history.** Conversations are in-memory only. Refreshing the page clears the session.
- **Keyword router accuracy is high but not 100%.** Genuinely ambiguous questions may be misrouted. The eval suite passes 7/7; real-world coverage is broader.
- **No row-level validation report for uploaded files.** Skipped rows are counted (`skipped_count` in the upload response) but not reported line-by-line. There is no UI indication of which rows failed validation.
- **No delete dataset UI.** Uploaded datasets persist until removed directly from the database.
- **`.xls` format not supported.** Only `.csv` and `.xlsx` are accepted. Legacy binary Excel files return `400`.
- **ChromaDB is local and file-based.** Not suitable for concurrent multi-user access; appropriate for single-user local use.
- **No date dimension.** Fiscal-year or non-Gregorian calendar rollups are not supported. Date maths uses Postgres built-in functions only.

---

## Folder layout

```
RetailMind/
├── backend/
│   ├── analytics/       # NL→SQL pipeline: schema context, SQL validator, DB, agent, CLI
│   ├── documents/       # PDF pipeline: extract, chunk, embed, vectorstore, agent, CLI
│   ├── uploads/         # CSV/XLSX pipeline: parser, row validator, DB, agent
│   ├── llm/             # LLM provider abstraction (OllamaProvider + HostedProvider stub)
│   ├── config.py        # pydantic-settings config (reads from .env)
│   ├── router.py        # Deterministic keyword classifier
│   └── main.py          # FastAPI app — all endpoints
├── frontend/
│   ├── app/             # Next.js App Router (layout, page)
│   ├── components/      # ChatPage, DocumentUpload, DatasetUpload, DatasetSelector, …
│   └── lib/api.ts       # Typed API client
├── data/
│   ├── sample_docs/     # sample_policy.pdf, sample_sales.csv, sample_sales.xlsx
│   └── uploads/         # runtime upload storage (git-ignored)
├── docs/
│   ├── 01_project_overview.md
│   ├── 02_decisions_log.md    # 18 architectural decisions with plain-language rationale
│   ├── 05_progress.md         # phase-by-phase build log
│   └── screenshots/           # UI screenshots (add manually)
├── scripts/
│   ├── 001_schema.sql         # Postgres schema + roles + grants
│   ├── 002_seed.sql           # ~5,000 seeded demo sales rows (deterministic)
│   ├── 003_business_sales.sql # uploaded data tables
│   ├── eval_router.py
│   ├── eval_analytics.py
│   ├── eval_documents.py
│   ├── eval_uploads.py
│   └── eval_all.py
├── docker-compose.yml
├── pyproject.toml
└── .env.example
```

---

## API reference

Interactive documentation is available at http://localhost:8000/docs when the server is running.

### Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/health` | Server status |
| `POST` | `/chat` | Unified chat — routes to analytics or document agent |
| `POST` | `/analytics` | Analytics Q&A (direct, bypasses router) |
| `POST` | `/documents/upload` | Upload and ingest a PDF |
| `POST` | `/documents/query` | Document Q&A (direct) |
| `POST` | `/datasets/upload` | Upload and ingest a CSV/XLSX sales file |
| `GET` | `/datasets` | List uploaded datasets (newest first) |

### POST /chat — request and response shapes

```json
// Request — demo mode (no dataset_id)
{ "message": "What is the top-selling product?" }

// Request — uploaded mode
{ "message": "What is the top-selling product?", "dataset_id": 7 }
```

```json
// Analytics response (demo)
{
  "route": "analytics",
  "answer": "The top-selling product is Coffee Beans, with 2,110 units sold.",
  "sql": "SELECT p.name, SUM(s.quantity) FROM retail.sales s JOIN ...",
  "columns": ["product_name", "total_quantity_sold"],
  "rows": [["Coffee Beans", 2110]],
  "sources": null,
  "mode": "demo"
}

// Analytics response (uploaded)
{
  "route": "analytics",
  "answer": "The top-selling product is Coffee Beans, with 13 units sold.",
  "sql": "SELECT product, SUM(quantity) FROM retail.business_sales WHERE dataset_id = 7 ...",
  "columns": ["product", "total_units"],
  "rows": [["Coffee Beans", 13]],
  "sources": null,
  "mode": "uploaded"
}

// Document response
{
  "route": "document",
  "answer": "Customers may return any unused, undamaged product within 30 days ...",
  "sql": null,
  "columns": null,
  "rows": null,
  "sources": ["[sample_policy.pdf, page 2, chunk 0]", "..."],
  "mode": null
}

// Unknown route
{
  "route": "unknown",
  "answer": "I can answer questions about uploaded documents or retail sales analytics ...",
  "sql": null,
  "columns": null,
  "rows": null,
  "sources": null,
  "mode": null
}
```

**Error responses:** `400` — SQL validation failed or unsupported file type. `422` — invalid `dataset_id` (must be a positive integer). `503` — database or LLM service unavailable.
