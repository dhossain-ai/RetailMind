# RetailMind — Decisions Log

Each entry records an architectural or schema decision and explains the reasoning in plain language. The goal is that every decision can be explained and defended without consulting notes.

---

## 1. Two Postgres schemas: `retail` and `app`

Business data (`categories`, `products`, `stores`, `sales`) lives in the `retail` schema. Application data (`documents`, `chat_messages`) lives in the `app` schema.

**Why.** The analytics agent's read-only role (`analytics_reader`) is granted `SELECT` on `retail` only. This means any SQL the agent generates — including SQL produced by prompt injection — physically cannot read chat history or document metadata. The security boundary is enforced at the database layer, not just in application code. If it were enforced only in code, a bug or injection could bypass it; at the schema level there is nothing to bypass.

---

## 2. Star-schema-lite: dimension tables + one fact table

The `retail` schema uses three dimension tables (`categories`, `products`, `stores`) and one fact table (`sales`), rather than a normalised OLTP structure with separate `orders` and `order_lines` tables.

**Why.** Analytics queries naturally aggregate fact rows and join to dimensions. A text-to-SQL model produces more reliable SQL against a flat star schema because the join pattern is predictable and the table count is low. Deeply normalised schemas require multi-level joins that are harder for a model to infer correctly and harder for a human to debug. Star schemas are also the standard pattern taught in data warehousing, so the design is immediately recognisable to anyone reviewing the project.

---

## 3. `unit_price` exists on both `products` and `sales`

`products.unit_price` is the current list price — the price the application uses when recording a new sale. `sales.unit_price` is a snapshot of what the customer actually paid, captured at the moment of the transaction and never updated.

**Why.** Prices change over time. If `sales` looked up the price from `products` at query time, every historical revenue figure would silently recalculate at the new price — making past reports wrong. Storing the price on each `sales` row means a price change on a product has no effect on completed sales. The two columns serve different purposes: one is "what does this product cost today", the other is "what did this customer pay".

---

## 4. `transaction_id` on `sales` rows

Each row in `sales` carries a `transaction_id` UUID. Multiple rows with the same `transaction_id` are line items in the same basket.

**Why.** A basket (one customer visit, one receipt) can contain multiple products. Without `transaction_id` there is no way to group line items into a basket without adding a separate `orders` table and `order_id` foreign key. The `transaction_id` field achieves the same thing with no extra table, keeping the schema flat. Basket-level aggregations use `GROUP BY transaction_id`. The column has no `DEFAULT`; the application or seed script supplies the same UUID for every line item in a given transaction, which makes the grouping explicit and traceable.

---

## 5. `revenue` is a generated column

`sales.revenue` is defined as `GENERATED ALWAYS AS (quantity * unit_price) STORED`.

**Why.** If `revenue` were a plain column, every code path that inserts a sale row would need to compute `quantity * unit_price` correctly. Bugs in that calculation would produce silent data corruption (wrong values that look valid). A generated column delegates the arithmetic to Postgres, which computes it identically every time and stores it on disk so queries can read it without recalculating. There is no application code to get wrong.

---

## 6. `app.documents` stores metadata only; chunks and embeddings live in ChromaDB

The `app.documents` table stores filename, title, upload date, and chunk count. The actual text chunks and their vector embeddings are stored in ChromaDB and linked back via `document_id`.

**Why.** Postgres is not designed for high-dimensional vector search. ChromaDB is purpose-built for it, with efficient approximate nearest-neighbour indices. Storing embeddings in Postgres (e.g. with `pgvector`) is a valid alternative, but adds an extension dependency and couples the vector index to the relational database. Keeping them separate means each system does what it is optimised for. The `document_id` link is sufficient to join metadata from Postgres to chunks from ChromaDB when constructing a retrieval response.

---

## 7. No date dimension in v1

There is no `retail.date_dim` table in this version. Date rollups are handled with Postgres built-in functions (`date_trunc`, `EXTRACT`, `to_char`).

**Why.** A proper date dimension (with pre-computed columns for year, quarter, month, week, day-of-week, fiscal period, etc.) is a standard data warehouse pattern and eliminates complex `EXTRACT` chains in queries. It is omitted in v1 because it requires a seed-data generation step, adds schema complexity, and the analytical queries expected in v1 are straightforward enough that `date_trunc('month', sale_date)` is readable and reliable.

**Known limitation.** If query complexity grows — especially fiscal-year rollups or non-Gregorian calendar requirements — a date dimension should be added. This is a deliberate deferral, not an oversight.

---

## 8. `stores.region` instead of `stores.state`

The column is named `region`, not `state`.

**Why.** The system targets European retail contexts. "State" implies a US administrative division. "Region" is the correct and more portable term for a sub-national geographic grouping in a European context.

---

## 9. Deterministic seed data: `setseed()` + `md5`-based transaction IDs

The seed script (`scripts/002_seed.sql`) uses `SELECT setseed(0.42)` before any `random()` call. This pins PostgreSQL's PRNG so that every call to `random()` produces an identical sequence on every run, giving the same ~5,000 sales rows every time the script is executed. Deterministic data means demo answers never change between sessions.

**Why `md5(...)::uuid` instead of `gen_random_uuid()` for transaction IDs.** `gen_random_uuid()` draws from the kernel's CSPRNG (the OS entropy pool). This source is completely separate from PostgreSQL's PRNG — `setseed()` has no effect on it. Calling `gen_random_uuid()` after `setseed()` would produce different UUIDs on every run, breaking reproducibility. Instead, transaction IDs are generated as `md5(month_idx::text || ':' || basket_idx::text)::uuid`. This is a deterministic hash: the same (month, basket) pair always produces the same UUID, so baskets are stable across runs while still being unique.

---

## 10. Docker Postgres for dev, Supabase for prod; same migrations against both

Local development uses a `postgres:16` container managed by `docker-compose.yml`. Production uses Supabase (hosted Postgres). The same migration files (`scripts/001_schema.sql`, `scripts/002_seed.sql`) run against both environments.

**Why split dev and prod this way.** Running a real Postgres locally (not SQLite, not mocks) means the dev schema is byte-for-byte identical to prod. Type mismatches, generated-column behaviour, and role-based access are all tested locally before anything reaches Supabase. The `DATABASE_URL` environment variable is the only thing that changes between environments — the backend code and migrations are untouched.

**Why Supabase for prod.** Supabase provides managed Postgres with connection pooling (pgBouncer), row-level security hooks, and a dashboard for quick data inspection — useful during demo and interview settings. It is also free at the scale of this project. The alternative (self-hosted Postgres on a VPS) adds operational overhead with no benefit for a portfolio project.

**Why not Docker in prod.** Keeping prod infra out of scope means the portfolio project stays focused on the AI/backend code. Supabase abstracts the database operations layer away.

---

## 11. LLM provider abstraction: ABC interface with Ollama adapter and hosted stub

All LLM calls go through a single `LLMProvider` ABC defined in `backend/llm/base.py`. Local development uses `OllamaProvider` (httpx calls to a local Ollama instance). Production swaps in a hosted adapter. A `HostedProvider` stub raises `NotImplementedError` until prod credentials are wired up.

**Why.** A single interface means agents never import Ollama or Anthropic directly — they depend only on the abstraction. Swapping providers for prod is a one-line config change (`LLM_PROVIDER=hosted`), not a code change. Using an ABC (rather than Protocol) makes the contract explicit: any subclass that omits `complete()` fails at class-definition time, not at runtime.

**Why httpx for the Ollama adapter.** httpx is sync/async-capable, is the standard HTTP client in the FastAPI ecosystem, and is already a transitive dependency of many FastAPI projects. Adding requests would be redundant.

---

## 12. Static schema context and SQL validator for Analytics Agent v1

The analytics agent uses a hardcoded string in `backend/analytics/schema_context.py` to describe the `retail` schema to the LLM, rather than querying `information_schema` at runtime. A lightweight SQL validator in `backend/analytics/sql_validator.py` checks the generated SQL before it reaches the database.

**Why static schema context.** The `retail` schema is stable and known at design time. Querying `information_schema` on every request adds a DB round-trip in the prompt path, complexity, and the risk of exposing internal schema metadata to the LLM unnecessarily. A hardcoded context is faster, simpler, and can include human-authored business-term definitions (e.g. what "top-selling" means) that `information_schema` cannot provide. When the schema changes, the context is updated alongside the migration.

**Why a SQL validator.** The validator is defense-in-depth. It rejects obviously dangerous SQL (DML/DDL keywords, `app.` schema references, system catalog access, multiple statements) before the query reaches the database, providing a fast fail with a clear error message. It is not the primary security boundary — Decision #1 establishes that `analytics_reader` physically cannot reach `app.*` at the database layer regardless of what SQL is generated. The validator and the role together form a layered defence: the validator catches obvious cases quickly, and the database role stops anything that slips through.

---

## 13. Document agent: PyMuPDF + sentence-transformers + ChromaDB; no LangChain in v1

PDF extraction uses PyMuPDF (`fitz`). Embedding uses `sentence-transformers` with `all-MiniLM-L6-v2` (384-dim, ~23 MB, CPU-only). Vector storage uses ChromaDB with a persistent local client and cosine distance.

**Why PyMuPDF.** It is a pure-Python + compiled-C library with no external service dependency. It extracts text page by page with page-number metadata in a single call, which is exactly what the chunker needs. It is also the library already chosen for the generator script (`scripts/generate_sample_doc.py`), so no extra dependency is introduced.

**Why sentence-transformers + all-MiniLM-L6-v2.** Local embeddings require no API key and no network round-trip. `all-MiniLM-L6-v2` is one of the most widely cited small embedding models: 384 dimensions, 23 MB on disk, strong benchmark scores on semantic similarity tasks relative to its size. The model is lazy-loaded once per process so the startup cost is paid only when the first embed call arrives.

**Why ChromaDB.** Decision #6 already specified ChromaDB as the vector store. It provides a persistent local client with no server process, approximate nearest-neighbour search out of the box, and a simple Python API. The collection is created with `hnsw:space=cosine` so the distance metric matches what the embedding model optimises for. With cosine distance, Chroma returns `distance = 1 - cosine_similarity` (range 0–2; lower = more similar); this is documented inline in `vectorstore.py`.

**Why not LangChain or LlamaIndex in v1.** The pipeline is five steps: extract → chunk → embed → store / embed → retrieve → prompt → LLM. Each step is a function with a clear input and output. An orchestration framework would hide these steps behind abstractions, making the pipeline harder to explain in an interview and harder to debug when a step produces unexpected output. The three focused libraries cover the steps with no magic. LangChain or LlamaIndex can be added later if the pipeline grows complex enough to justify them.

**Retrieval honesty — no hardcoded threshold.** Chroma always returns the top-k nearest neighbours regardless of how poor the match is. Rather than picking a magic distance cutoff, the agent instructs the LLM to answer "I cannot find that information in the available documents" if the retrieved context does not contain a relevant answer. The LLM makes the relevance judgement from the text, which is more reliable than a distance threshold whose meaning depends on the specific model and collection. If the collection is empty (no documents ingested), the agent returns a plain message before calling the LLM at all.

---

## 14. Router v1 uses weighted keyword scoring rather than an LLM call

The router (`backend/router.py`) classifies each incoming question as `analytics`, `document`, or `unknown` using a list of (regex, weight) rules — no LLM call. Strong multi-word phrases score 3; generic single keywords score 1. The domain with the higher total score wins. A tie or both-zero score returns `unknown`.

**Why deterministic rules, not an LLM classifier.** An LLM-based router would add a full round-trip to Ollama (or a hosted provider) before every query — roughly doubling latency on questions that end up routed to a fast path. Deterministic rules are instantaneous, testable without a running LLM, and produce predictable output that can be verified with a static table of cases. For v1, the two domains (analytics = sales/products/stores/revenue, document = policies/suppliers/hours/PDFs) have sufficiently distinct vocabularies that a scored keyword matcher is accurate enough without a neural model.

**Why weighted phrases, not raw token counts.** Some single words are genuinely ambiguous: "store" can mean a retail location (analytics) or store operations (document); "hours" alone is weaker evidence than "operating hours". Multi-word phrases such as "return policy", "supplier vetting", and "top-selling product" carry unambiguous intent and are scored at 3× a generic keyword match. Generic single keywords still contribute at weight 1, so a question with several analytics terms (e.g. "revenue", "category", "trend") accumulates enough score to beat a single weak document term. This avoids both false routes from a single ambiguous word and false `unknown` returns from questions that use no strong phrases but clearly belong to one domain.

**Why tie → `unknown`, not a default route.** Guessing the wrong agent produces a worse experience than returning a clear fallback: an analytics question sent to the document agent produces a "cannot find that information" response, and a document question sent to the analytics agent generates SQL against the wrong schema. A brief clarification ("I can answer questions about uploaded documents or retail analytics…") costs the user one extra message rather than a confusing wrong answer. The `unknown` response is always HTTP 200 — it is a valid outcome, not an error.

---

## 15. Evaluation v1 uses deterministic seed answers and key-fact assertions, not exact LLM wording

The evaluation scripts (`scripts/eval_router.py`, `eval_analytics.py`, `eval_documents.py`, `eval_all.py`) do not compare LLM responses to fixed expected strings. Instead they assert that key facts appear in the response — for example, that the answer to "which category is declining?" contains "household", or that the price-change rows include both 8.50 and 11.99.

**Why key-fact assertions, not exact strings.** LLM outputs vary across model versions, temperature, and prompt changes. An exact-string assertion would break on every model upgrade or phrasing improvement even when the semantic answer is correct. Key-fact assertions are stable: "Household" will appear in any correct answer to the declining-category question regardless of how the sentence is structured. For the analytics checks, the structured result (rows, columns, SQL) is checked first because it is deterministic database output; the answer text is a secondary check that catches LLM reasoning failures.

**Why no pytest.** The scripts are short enough to read in one sitting, have no complex fixtures or parametrization requirements, and need to be runnable with a plain `py -3.11 scripts/eval_all.py` command that any developer can invoke after reading the README. Adding pytest would require understanding its discovery rules and conftest conventions before being able to run or modify the checks — an unnecessary barrier for a project where explainability is a stated goal.

---

## 16. Business sales schema: flat table, no cross-schema FK, plain revenue column, explicit grant

`retail.business_sales` is a flat fact table for uploaded CSV/XLSX sales data. It stores all dimension values (product, category, store) inline as free text rather than as foreign keys to `retail.products`, `retail.stores`, and `retail.categories`.

**Why a new table rather than reusing `retail.sales`.** The existing `retail.sales` table requires every row to reference normalised dimension rows in `retail.products`, `retail.stores`, and `retail.categories`. Populating those tables for every uploaded CSV would either corrupt demo data or require per-upload shadow dimension rows — neither is acceptable. A flat table is simpler, honest about the data it holds, and easier to explain. The demo data and uploaded data remain completely isolated: the analytics agent queries one or the other based on a `dataset_id` parameter, never both at once.

**Why `store` is nullable.** Single-location businesses are the common v1 case and often omit a store column entirely. Making it nullable costs nothing: queries that group or filter by store work correctly when the column is populated, and queries that ignore it are unaffected when it is `NULL`. Adding the column now avoids a schema migration later when a multi-location business uploads data with a branch column. Omitting it now and adding it later would require a nullable column migration anyway — so the cost is the same, but the benefit of having it in place from the start is real.

**Why no DB-level foreign key from `retail.business_sales.dataset_id` to `app.datasets.id`.** The `retail` and `app` schemas are intentionally isolated (Decision #1). A cross-schema foreign key would create a structural dependency from the analytics-queryable schema into the app schema, which is the hard security boundary. Referential integrity is enforced at the application layer: the upload endpoint inserts the `app.datasets` row and all `retail.business_sales` rows in a single transaction. An orphaned `dataset_id` cannot be produced by the application code.

**Why `revenue` is a plain column rather than `GENERATED ALWAYS AS (quantity * unit_price)`.** In `retail.sales`, both `quantity` and `unit_price` are always non-null, so the generated expression is safe. In `retail.business_sales`, `unit_price` is nullable — many small-business CSV exports carry only a total amount column without breaking it into quantity and unit price. When `unit_price` is present the upload pipeline computes `quantity * unit_price`; when only a total amount is available, that value is stored directly. A generated column cannot handle both cases.

**Why an explicit `GRANT SELECT ON retail.business_sales TO analytics_reader`.** `001_schema.sql` includes `ALTER DEFAULT PRIVILEGES IN SCHEMA retail GRANT SELECT ON TABLES TO analytics_reader`, which covers tables created in the future. The explicit grant in `003_business_sales.sql` is belt-and-suspenders: if this migration is applied on an environment where the default privileges differ (e.g. a fresh Supabase project not bootstrapped from `001_schema.sql`), `analytics_reader` can still query the table without a separate step. `app.datasets` is intentionally not granted to `analytics_reader` — the `app` schema security boundary is preserved unchanged.

---

## 17. Upload pipeline: stdlib csv + openpyxl, no pandas; utf-8-sig; uuid stored filename

The upload pipeline (`backend/uploads/`) uses Python's stdlib `csv` module for `.csv` files and `openpyxl` for `.xlsx` files. `.xls` (legacy binary Excel format) is explicitly not supported in v1.

**Why no pandas.** Pandas is a 25 MB install with NumPy as a transitive dependency. The pipeline needs exactly three things from a data-reading library: read rows, expose headers, iterate cells. Both `csv` and `openpyxl` do this with no magic. The pipeline is about 80 lines of plain Python that a reader can trace step-by-step without knowing any DataFrame API. A future maintainer can add pandas later if the processing needs grow; removing a dependency is always harder than adding one.

**Why utf-8-sig for CSV.** Excel saves CSVs with a UTF-8 BOM (byte-order mark) prepended to the file. Without `utf-8-sig` encoding, the BOM becomes part of the first column header — so `"date"` becomes `"﻿date"`, which does not match the synonym table and causes a false missing-column error. `utf-8-sig` strips the BOM transparently; plain UTF-8 files are unaffected.

**Why uuid-hex stored filename, not original filename.** The original filename is user-supplied and untrusted. Storing it directly risks path traversal (e.g. `../../etc/passwd`), silent overwrites of existing files, and OS-specific character restrictions. The upload endpoint generates a random `uuid.uuid4().hex` stored name and keeps the original filename only as metadata in `app.datasets`. This is the same pattern used for PDF uploads in `POST /documents/upload`.

**Why the row limit is a constant in parser.py, not a config setting.** 50,000 rows is a hard v1 constraint, not a per-deployment tuning parameter. Exposing it as an env var would imply operators should adjust it, which invites misconfiguration without any agreed-upon safe upper bound. When the project is ready to lift the limit, it is a one-line code change in a clearly named constant.

**Why skip invalid rows rather than reject the whole file.** Real small-business CSV exports routinely contain summary/subtotal rows, blank rows, and header repetitions that are not sales records. Rejecting the whole file on a single bad row would make the tool unusable for common real-world inputs. Skipping and reporting `skipped_count` gives the caller enough information to investigate without blocking a valid upload. The whole upload is only rejected when zero valid rows remain — i.e., the file contained no usable data at all.
