# RetailMind

An internal AI assistant for retail companies with two capabilities:
**Document Q&A** (retrieval-augmented generation over uploaded PDFs) and
**Analytics Q&A** (natural language → SQL over a Postgres retail database).
A router decides which capability handles each question.

See [`docs/01_project_overview.md`](docs/01_project_overview.md) for a full description and
[`docs/02_decisions_log.md`](docs/02_decisions_log.md) for the reasoning behind every architectural choice.

---

## Local development database

The dev database runs in Docker. A fresh container automatically applies the
schema migration and seeds ~5,000 sales rows on first boot.

### Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (or Docker Engine + Compose plugin)

### Start the database

```bash
# Copy the example env file (only needed once)
cp .env.example .env

# Start the Postgres container in the background
docker compose up -d
```

On first start Docker pulls `postgres:16`, creates the `retailmind` database,
and runs the scripts in `scripts/` in alphabetical order:
`001_schema.sql` (schema + roles) then `002_seed.sql` (reference data + ~5,000 sales rows).

This init step only runs on a **fresh volume**. If the volume already exists,
the container starts immediately without re-running the scripts.

> **Warning — editing migration or seed files:**
> If you change `001_schema.sql` or `002_seed.sql`, a plain `docker compose up`
> will **silently ignore your changes** because the data directory already exists.
> You must destroy the volume first:
> ```bash
> docker compose down -v   # deletes the volume — all data is lost
> docker compose up -d     # fresh boot; init scripts run again
> ```

### Connection details

| Setting  | Value                  |
|----------|------------------------|
| Host     | `localhost`            |
| Port     | `5432`                 |
| Database | `retailmind`           |
| User     | `postgres`             |
| Password | value of `POSTGRES_PASSWORD` in `.env` (default: `retailmind_dev`) |

Example `psql` connection:

```bash
psql postgresql://postgres:retailmind_dev@localhost:5432/retailmind
```

### Reset to a clean state (re-run seed)

The seed script starts with `TRUNCATE … RESTART IDENTITY CASCADE`, so it is
safe to re-run at any time. To get a completely fresh container:

```bash
# Stop the container and delete the named volume
docker compose down -v

# Start fresh — init scripts run again from scratch
docker compose up -d
```

---

## Backend

The backend is a FastAPI application in `backend/`.

### Prerequisites

- Python 3.11+
- [pip](https://pip.pypa.io/) or a virtual-environment manager

### Install dependencies

```bash
# From the repo root — creates an editable install of the backend package
pip install -e .
```

### Run the API server

```bash
uvicorn backend.main:app --reload
```

The server starts on `http://localhost:8000` by default.

### Test the health endpoint

```bash
curl http://localhost:8000/health
# {"status":"ok","env":"dev","version":"0.1.0"}
```

Or open `http://localhost:8000/docs` in a browser for the auto-generated OpenAPI UI.

> **Ollama not required for /health.** The health endpoint returns app status only.
> Ollama needs to be running only when an agent actually calls `LLMProvider.complete()`.

### Analytics endpoint

`POST /analytics` accepts a natural-language question and returns generated SQL, the raw result set, and a plain-English answer.

**curl:**

```bash
curl -s -X POST http://localhost:8000/analytics \
  -H "Content-Type: application/json" \
  -d '{"question": "What is the top-selling product?"}'
```

**PowerShell:**

```powershell
Invoke-RestMethod -Method Post -Uri http://localhost:8000/analytics `
  -ContentType "application/json" `
  -Body '{"question": "What is the top-selling product?"}'
```

Example response:

```json
{
  "question": "What is the top-selling product?",
  "sql": "SELECT p.name AS product_name, SUM(s.quantity) AS total_quantity_sold\nFROM retail.sales s\nJOIN retail.products p ON s.product_id = p.id\nGROUP BY 1\nORDER BY 2 DESC\nLIMIT 1",
  "columns": ["product_name", "total_quantity_sold"],
  "rows": [["Coffee Beans", 2110]],
  "answer": "The top-selling product is Coffee Beans, with a total quantity of 2110 sold."
}
```

> **Requires Ollama + Docker Postgres.** The endpoint calls `qwen2.5-coder:7b` to generate
> SQL and the answer. It connects to Postgres as `analytics_reader` (SELECT on `retail.*` only).
>
> **Error responses:**
> - `400` — SQL validation failed (generated SQL was rejected before hitting the DB)
> - `503` — Database or LLM service unavailable

---

## Analytics agent (CLI)

The analytics agent answers natural-language retail questions by generating SQL,
executing it against Postgres as `analytics_reader`, and returning a plain-English answer.

### Prerequisites

- Docker Postgres running (`docker compose up -d`)
- Ollama running with `qwen2.5-coder:7b` pulled:
  ```bash
  ollama pull qwen2.5-coder:7b
  ```
- `.env` file present with `ANALYTICS_DATABASE_URL` set (see `.env.example`)

### Run a question

```bash
py -3.11 -m backend.analytics.cli "What is the top-selling product?"
```

Example output:

```
Question: What is the top-selling product?

─── Generated SQL ────────────────────────────────────────────────────────────
SELECT retail.products.name AS top_selling_product_name,
       SUM(retail.sales.quantity) AS total_units_sold
FROM retail.sales
JOIN retail.products ON retail.sales.product_id = retail.products.id
GROUP BY retail.products.name
ORDER BY total_units_sold DESC
LIMIT 1

─── Result ───────────────────────────────────────────────────────────────────
Columns: ['top_selling_product_name', 'total_units_sold']
Coffee Beans	2110

─── Answer ───────────────────────────────────────────────────────────────────
The top-selling product is Coffee Beans, with a total of 2,110 units sold.
```

> **Security note.** The CLI connects to Postgres as `analytics_reader`,
> which has `SELECT` on `retail.*` only. Generated SQL cannot read
> `app.chat_messages` or `app.documents` even if the question attempts it.

---

## Document agent (CLI)

The document agent ingests PDFs into ChromaDB and answers natural-language questions
by retrieving relevant chunks and passing them to the LLM.

### Prerequisites

- Ollama running with `qwen2.5-coder:7b` pulled
- Docker Postgres running (`docker compose up -d`) — used to store document metadata in `app.documents`
- `.env` file present (see `.env.example`); `CHROMA_PATH`, `EMBEDDING_MODEL`, and `DOCUMENT_TOP_K` have sensible defaults

### Ingest a PDF

```bash
py -3.11 -m backend.documents.cli ingest data/sample_docs/sample_policy.pdf
```

Example output:

```
Ingesting: data/sample_docs/sample_policy.pdf
------------------------------------------------------------------------
Document ID : 1
Chunks      : 13
------------------------------------------------------------------------
Ingestion complete. Run a query to test retrieval.
```

The first run downloads the embedding model (~23 MB). Subsequent runs use the cached model.
ChromaDB data is persisted to `data/chroma/` (git-ignored).

### Query over ingested documents

```bash
py -3.11 -m backend.documents.cli query "What is the return policy?"
```

Example output:

```
Question: What is the return policy?

------------------------------------------------------------------------ Answer
Customers may return any unused, undamaged product within 30 days of purchase
with a valid receipt for a full refund. Holiday purchases (1 Nov–31 Dec) have
a 60-day window. Perishable items and digital downloads are non-returnable.
Defective goods may be returned within 90 days with proof of defect.

------------------------------------------------------------------------ Sources
  [sample_policy.pdf, page 2, chunk 0]
  [sample_policy.pdf, page 2, chunk 1]
  ...
------------------------------------------------------------------------
```

If the question cannot be answered from the ingested documents, the agent responds:

```
I cannot find that information in the available documents.
```

> **Note.** The agent does not use a distance threshold to filter weak results.
> It instructs the LLM to refuse if the retrieved context does not contain an answer.
> This is explained in Decision #13 of `docs/02_decisions_log.md`.

---

## Document agent (API)

The same document pipeline is also available through the FastAPI server.

### Prerequisites

Same as the CLI: Ollama running, Docker Postgres running, `.env` present.
The API server must be running:

```bash
uvicorn backend.main:app --reload
```

### Upload a PDF

**curl:**

```bash
curl -s -X POST http://localhost:8000/documents/upload \
  -F "file=@data/sample_docs/sample_policy.pdf"
```

**PowerShell:**

```powershell
Invoke-RestMethod -Method Post -Uri http://localhost:8000/documents/upload `
  -Form @{ file = Get-Item data/sample_docs/sample_policy.pdf }
```

Example response:

```json
{
  "document_id": 2,
  "filename": "95dad59c_sample_policy.pdf",
  "original_filename": "sample_policy.pdf",
  "chunk_count": 13,
  "status": "ingested"
}
```

Uploaded files are saved to `data/uploads/` with an 8-character hex prefix to avoid
overwrites. `data/uploads/` is git-ignored. Only `.pdf` files are accepted; any other
content type returns `400`.

### Query over ingested documents

**curl:**

```bash
curl -s -X POST http://localhost:8000/documents/query \
  -H "Content-Type: application/json" \
  -d '{"question": "What is the return policy?"}'
```

**PowerShell:**

```powershell
Invoke-RestMethod -Method Post -Uri http://localhost:8000/documents/query `
  -ContentType "application/json" `
  -Body '{"question": "What is the return policy?"}'
```

Example response:

```json
{
  "question": "What is the return policy?",
  "answer": "Customers may return any unused, undamaged product within 30 days ...",
  "sources": [
    "[sample_policy.pdf, page 2, chunk 0]",
    "[sample_policy.pdf, page 2, chunk 1]"
  ]
}
```

> **Error responses:**
> - `400` — uploaded file is not a PDF
> - `503` — database or LLM service unavailable
> - `500` — unexpected ingestion failure (uploaded file is cleaned up automatically)

---

## Folder layout

```
RetailMind/
├── backend/
│   ├── analytics/        # NL→SQL analytics agent
│   │   ├── schema_context.py  # compact retail schema + business term definitions
│   │   ├── sql_validator.py   # static SQL safety checks
│   │   ├── db.py              # query runner (analytics_reader role only)
│   │   ├── agent.py           # LLM pipeline: question → SQL → answer
│   │   └── cli.py             # command-line entry point
│   ├── documents/        # PDF ingestion and document Q&A agent
│   │   ├── extract.py         # page-by-page PDF text extraction (PyMuPDF)
│   │   ├── chunking.py        # character-based text chunking
│   │   ├── embeddings.py      # sentence-transformers embeddings (all-MiniLM-L6-v2)
│   │   ├── vectorstore.py     # ChromaDB persistence (cosine distance)
│   │   ├── db.py              # app.documents metadata (DATABASE_URL, postgres role)
│   │   ├── agent.py           # ingest() and run() pipeline
│   │   └── cli.py             # command-line entry point
│   ├── llm/              # LLM provider abstraction (Ollama + hosted stub)
│   ├── config.py         # pydantic-settings config
│   └── main.py           # FastAPI app + /health endpoint
├── frontend/             # Web UI (framework TBD)
├── data/
│   └── sample_docs/      # Sample PDFs for local development
├── docs/                 # Architecture docs, decisions log, progress notes
├── scripts/              # SQL migrations run by Docker on first boot
│   ├── 001_schema.sql
│   └── 002_seed.sql
├── docker-compose.yml
└── .env.example
```
