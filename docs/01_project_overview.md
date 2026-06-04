# RetailMind — Project Overview

RetailMind is an internal AI assistant for retail companies. It gives analysts and operations staff a conversational interface to two distinct knowledge sources: uploaded policy and product documents, and a live Postgres database of retail transaction data. A router component inspects each incoming question and decides which capability to invoke, so the user interacts with a single chat interface regardless of where the answer comes from.

## Capabilities

**Document Q&A** answers questions about uploaded PDFs (supplier contracts, store policies, product catalogues, etc.). Documents are chunked, embedded, and stored in ChromaDB. At query time the relevant chunks are retrieved and passed to a language model to produce a grounded answer with source citations.

**Analytics Q&A** answers questions about sales, products, stores, and categories by translating natural language into SQL, running it against a read-only Postgres view of the `retail` schema, and returning the result in plain language. The SQL is executed as a least-privilege role (`analytics_reader`) that has `SELECT` on `retail` only — it physically cannot reach chat history or document metadata.

**Business data upload** lets users upload their own CSV or XLSX sales files directly from the frontend. Rows are validated and loaded into `retail.business_sales`, a flat fact table isolated from the seeded demo data. A dataset selector in the UI switches between the demo dataset and any uploaded dataset. Uploaded sales data is queried via the same NL→SQL pipeline using a `dataset_id` filter.

**Router** classifies each message as a document question, an analytics question, or unknown, then delegates to the appropriate agent. Unknown queries fall back gracefully with a clarifying prompt.

## Frontend

The project includes a Next.js web frontend (`frontend/`) with a single-page chat interface. The sidebar contains a document upload widget (PDF → ChromaDB), a sales data upload widget (CSV/XLSX → Postgres), and a dataset selector. Every chat message is sent to `POST /chat`; the frontend displays the route badge, generated SQL and result table for analytics responses, and source citations for document responses.

## Portfolio context

This project is built to demonstrate mid-level AI/backend engineering skills. Every architectural decision is recorded in `docs/02_decisions_log.md` with a plain-language explanation of the reasoning. The goal is that any decision can be explained and defended in an interview without consulting notes. No patterns or abstractions are introduced beyond what the current feature set requires. It is a portfolio-grade MVP, not production software.
