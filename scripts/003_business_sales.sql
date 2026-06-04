-- RetailMind — business sales schema
-- Adds:
--   app.datasets          — metadata for each uploaded CSV/XLSX
--   retail.business_sales — fact rows from uploaded business data
--
-- Run as a superuser (e.g. postgres) after 001_schema.sql has been applied.
-- IF NOT EXISTS guards make this script safe to run on an existing installation.

-- ── app.datasets ───────────────────────────────────────────────────────────────
-- Metadata table for each uploaded CSV/XLSX file.
-- Mirrors the pattern of app.documents: application metadata lives in the app
-- schema; queryable business data lives in the retail schema.
-- analytics_reader has REVOKE ALL on app (Decision #1), so this table is
-- invisible to generated SQL — consistent with the security boundary.

CREATE TABLE IF NOT EXISTS app.datasets (
    id                SERIAL      PRIMARY KEY,
    original_filename TEXT        NOT NULL,
    stored_filename   TEXT        NOT NULL,
    row_count         INT,
    skipped_count     INT         NOT NULL DEFAULT 0,
    upload_date       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ── retail.business_sales ─────────────────────────────────────────────────────
-- Flat fact table for uploaded business sales data.
-- No FK joins to retail.products, retail.stores, or retail.categories —
-- all dimension values are stored inline as free text. See Decision #16.

CREATE TABLE IF NOT EXISTS retail.business_sales (
    id          SERIAL        PRIMARY KEY,

    -- dataset_id links to app.datasets(id) at the application layer only.
    -- No DB-level foreign key: the retail and app schemas are intentionally
    -- isolated (Decision #1). Referential integrity is enforced by the upload
    -- endpoint, which always inserts the app.datasets row before any
    -- retail.business_sales rows in the same transaction.
    dataset_id  INT           NOT NULL,

    sale_date   DATE          NOT NULL,
    product     TEXT          NOT NULL CHECK (btrim(product) <> ''),
    category    TEXT,
    -- store is nullable: single-location businesses often omit it, but
    -- retaining the column preserves the analytics path for store/branch
    -- performance questions without requiring a schema change later.
    store       TEXT,
    quantity    INT           NOT NULL CHECK (quantity > 0),
    unit_price  NUMERIC(10,2) CHECK (unit_price IS NULL OR unit_price >= 0),
    -- revenue is a plain column, not GENERATED ALWAYS: unit_price is nullable
    -- (some CSV exports contain only a total amount), so the expression
    -- quantity * unit_price cannot always be evaluated. The upload pipeline
    -- either reads revenue directly from the source column or computes it
    -- from quantity * unit_price when both are present. See Decision #16.
    revenue     NUMERIC(10,2) NOT NULL CHECK (revenue >= 0),

    created_at  TIMESTAMPTZ   NOT NULL DEFAULT NOW()
);

-- ── Indexes ───────────────────────────────────────────────────────────────────

-- Covers fast row counts, dataset-scoped SELECTs, and future DELETE sweeps.
CREATE INDEX IF NOT EXISTS business_sales_dataset_id_idx
    ON retail.business_sales (dataset_id);

-- Covers the most common analytics query shape: aggregate over a date range
-- for one dataset.
CREATE INDEX IF NOT EXISTS business_sales_dataset_date_idx
    ON retail.business_sales (dataset_id, sale_date);

-- ── Grants ────────────────────────────────────────────────────────────────────
-- Explicit grant even though ALTER DEFAULT PRIVILEGES in 001_schema.sql already
-- covers future retail.* tables. This makes the migration self-contained: if it
-- is applied on an environment where default privileges differ, analytics_reader
-- can still query the table without a separate grant step.
GRANT SELECT ON retail.business_sales TO analytics_reader;

-- app.datasets is intentionally NOT granted to analytics_reader.
-- The app schema security boundary (Decision #1) applies here too.
