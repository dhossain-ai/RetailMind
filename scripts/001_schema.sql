-- RetailMind — initial schema
-- Run as a superuser (e.g. postgres) before creating the analytics_reader role.
--
-- gen_random_uuid() is built-in from Postgres 13+.
-- The extension guard below keeps this script compatible with older installs.
CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE SCHEMA IF NOT EXISTS retail;
CREATE SCHEMA IF NOT EXISTS app;

-- ── Dimension tables ───────────────────────────────────────────────────────

CREATE TABLE retail.categories (
    id          SERIAL      PRIMARY KEY,
    name        TEXT        NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE retail.products (
    id          SERIAL        PRIMARY KEY,
    name        TEXT          NOT NULL,
    category_id INT           NOT NULL REFERENCES retail.categories(id),
    -- Current list price. Historical price is captured on each sales row,
    -- so changing this value does not rewrite past revenue figures.
    unit_price  NUMERIC(10,2) NOT NULL,
    created_at  TIMESTAMPTZ   NOT NULL DEFAULT NOW()
);

CREATE TABLE retail.stores (
    id          SERIAL      PRIMARY KEY,
    name        TEXT        NOT NULL,
    city        TEXT        NOT NULL,
    region      TEXT        NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ── Fact table ─────────────────────────────────────────────────────────────

CREATE TABLE retail.sales (
    id              SERIAL        PRIMARY KEY,
    -- transaction_id groups multiple line items into one basket.
    -- NO default: the application or seed script must supply the same UUID
    -- across every row that belongs to the same transaction.
    transaction_id  UUID          NOT NULL,
    product_id      INT           NOT NULL REFERENCES retail.products(id),
    store_id        INT           NOT NULL REFERENCES retail.stores(id),
    quantity        INT           NOT NULL CHECK (quantity > 0),
    -- Snapshot of the price at the moment of sale. Never recalculated from
    -- products.unit_price, so historical revenue figures stay correct.
    unit_price      NUMERIC(10,2) NOT NULL,
    -- Generated column: always quantity * unit_price, stored on disk.
    -- Eliminates any possibility of quantity/price being multiplied
    -- inconsistently across code paths.
    revenue         NUMERIC(10,2) GENERATED ALWAYS AS (quantity * unit_price) STORED,
    sale_date       DATE          NOT NULL,
    created_at      TIMESTAMPTZ   NOT NULL DEFAULT NOW()
);

-- ── App metadata tables ────────────────────────────────────────────────────

CREATE TABLE app.documents (
    id          SERIAL      PRIMARY KEY,
    filename    TEXT        NOT NULL,
    title       TEXT,
    -- chunk_count is populated after the document has been chunked and
    -- ingested into ChromaDB, so it starts NULL.
    chunk_count INT,
    upload_date TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE app.chat_messages (
    id          SERIAL      PRIMARY KEY,
    -- A DEFAULT is provided so callers that do not supply a session_id
    -- automatically get an isolated session rather than silently sharing one.
    session_id  UUID        NOT NULL DEFAULT gen_random_uuid(),
    role        TEXT        NOT NULL CHECK (role IN ('user', 'assistant')),
    content     TEXT        NOT NULL,
    -- 'document'  — answered via RAG over uploaded PDFs
    -- 'analytics' — answered via generated SQL over the retail schema
    -- 'unknown'   — router could not classify (fallback)
    query_type  TEXT        CHECK (query_type IN ('document', 'analytics', 'unknown')),
    document_id INT         REFERENCES app.documents(id),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ── Analytics agent role ───────────────────────────────────────────────────
-- The backend connects as this role when executing generated SQL, so that
-- any SQL injection or prompt-injection attack is confined to SELECT on
-- the retail schema and cannot read app.chat_messages or app.documents.

CREATE ROLE analytics_reader WITH LOGIN PASSWORD 'change_me';

-- Grant access to the retail schema — existing tables and all future ones.
GRANT USAGE  ON SCHEMA retail               TO analytics_reader;
GRANT SELECT ON ALL TABLES IN SCHEMA retail TO analytics_reader;
ALTER DEFAULT PRIVILEGES IN SCHEMA retail
    GRANT SELECT ON TABLES TO analytics_reader;

-- Explicitly deny access to the app schema.
-- This is the hard security boundary: even if generated SQL contains a
-- cross-schema reference, the query will fail at the database layer.
REVOKE ALL ON SCHEMA app FROM analytics_reader;
