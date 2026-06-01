-- RetailMind — seed data
--
-- Deterministic: setseed(0.42) pins PostgreSQL's PRNG so every random() call
-- produces an identical sequence on every run.  Transaction IDs use
-- md5(...)::uuid rather than gen_random_uuid() because gen_random_uuid() draws
-- from the kernel's CSPRNG, which ignores setseed().
--
-- Safe to re-run: TRUNCATE resets all retail tables and their sequences, so
-- running this script twice yields the same data as running it once.

TRUNCATE retail.sales, retail.products, retail.stores, retail.categories
    RESTART IDENTITY CASCADE;

-- ── Reference data ─────────────────────────────────────────────────────────

INSERT INTO retail.categories (name) VALUES
    ('Beverages'),   -- id 1
    ('Dairy'),       -- id 2
    ('Bakery'),      -- id 3
    ('Produce'),     -- id 4
    ('Household');   -- id 5

-- products.unit_price is the CURRENT list price.
-- Sales rows store their own snapshot, so a price change here does not
-- rewrite historical revenue figures.
-- Coffee Beans (id 3): current price is 11.99; sales before 2025-07-01
-- use the old price (8.50) captured as a snapshot on each sales row.
INSERT INTO retail.products (name, category_id, unit_price) VALUES
    ('Mineral Water',      1,  0.89),  -- id 1
    ('Orange Juice',       1,  2.49),  -- id 2
    ('Coffee Beans',       1, 11.99),  -- id 3  ← price was 8.50 before 2025-07-01
    ('Sparkling Water',    1,  1.29),  -- id 4
    ('Full-Fat Milk',      2,  1.35),  -- id 5
    ('Greek Yoghurt',      2,  1.89),  -- id 6
    ('Butter',             2,  2.79),  -- id 7
    ('Cheddar Cheese',     2,  4.99),  -- id 8
    ('Sourdough Bread',    3,  3.49),  -- id 9
    ('Croissants',         3,  2.29),  -- id 10
    ('Chocolate Cake',     3,  5.99),  -- id 11
    ('Baguette',           3,  1.09),  -- id 12
    ('Bananas',            4,  1.49),  -- id 13
    ('Tomatoes',           4,  2.19),  -- id 14
    ('Potatoes',           4,  1.99),  -- id 15
    ('Apples',             4,  2.39),  -- id 16
    ('Washing-Up Liquid',  5,  2.49),  -- id 17 ╮
    ('Paper Towels',       5,  3.49),  -- id 18  │ Household: selection weight
    ('Laundry Detergent',  5,  7.99),  -- id 19  │ drops to 0.10 in Mar–May 2026
    ('Kitchen Roll',       5,  2.99);  -- id 20 ╯

INSERT INTO retail.stores (name, city, region) VALUES
    ('RetailMind Paris',     'Paris',     'Île-de-France'),        -- id 1
    ('RetailMind Amsterdam', 'Amsterdam', 'Noord-Holland'),        -- id 2
    ('RetailMind Berlin',    'Berlin',    'Berlin'),               -- id 3
    ('RetailMind Madrid',    'Madrid',    'Community of Madrid'),  -- id 4
    ('RetailMind Warsaw',    'Warsaw',    'Masovian Voivodeship'); -- id 5 ← underperformer

-- ── Sales generation ───────────────────────────────────────────────────────
-- Date range  : 2024-06-01 – 2026-05-31  (24 months, loop indices 0–23)
-- Volume      : 64 baskets/month normally, 128 in December → ~5 000 rows total
-- Basket      : 1–5 line items, same store and sale_date per transaction_id
-- Quantity    : 1–3 units per line item
--
-- Planted patterns
--   1. Household decline  : product ids 17-20 weight drops from 1.0 → 0.10
--                           in months 21-23 (Mar–May 2026)
--   2. Coffee Beans       : weight 5.0 vs 1.0 for all other products
--                           (~5× the units sold of the next best seller)
--   3. December spike     : 128 baskets instead of 64 in Dec 2024 and Dec 2025
--   4. Warsaw underperforms: assigned 8% of baskets vs 23% for other stores
--   5. Price snapshot     : Coffee Beans (id 3) unit_price = 8.50 before
--                           2025-07-01, 11.99 from 2025-07-01 onward

DO $$
DECLARE
    -- Current prices for product ids 1..20 (array is 1-indexed in PostgreSQL)
    p_prices  NUMERIC(10,2)[] := ARRAY[
                   0.89,  2.49, 11.99,  1.29,   -- ids  1-4  Beverages
                   1.35,  1.89,  2.79,  4.99,   -- ids  5-8  Dairy
                   3.49,  2.29,  5.99,  1.09,   -- ids  9-12 Bakery
                   1.49,  2.19,  1.99,  2.39,   -- ids 13-16 Produce
                   2.49,  3.49,  7.99,  2.99    -- ids 17-20 Household
               ];

    v_month_idx      INT;
    v_month_start    DATE;
    v_days_in_month  INT;
    v_basket_count   INT;
    v_is_decline     BOOLEAN;

    v_weights        FLOAT[];
    v_total_weight   FLOAT;
    v_cumsum         FLOAT[];
    v_running        FLOAT;

    v_basket_idx     INT;
    v_transaction_id UUID;
    v_store_id       INT;
    v_sale_date      DATE;
    v_basket_size    INT;
    v_line_idx       INT;
    v_product_id     INT;
    v_quantity       INT;
    v_unit_price     NUMERIC(10,2);
    v_r              FLOAT;
    k                INT;
BEGIN
    PERFORM setseed(0.42);

    FOR v_month_idx IN 0..23 LOOP
        v_month_start   := DATE '2024-06-01' + (v_month_idx * INTERVAL '1 month');
        v_days_in_month := (v_month_start + INTERVAL '1 month')::DATE - v_month_start;

        -- Double baskets in December for a visible seasonal spike
        v_basket_count := CASE
                            WHEN EXTRACT(MONTH FROM v_month_start) = 12 THEN 128
                            ELSE 64
                          END;

        -- Months 21-23 = Mar-May 2026: Household products decline sharply
        v_is_decline := (v_month_idx >= 21);

        -- Product selection weights (index = product_id)
        -- Coffee Beans (id 3) = 5.0; everything else = 1.0
        v_weights := ARRAY[1.0, 1.0, 5.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0,
                           1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0]::FLOAT[];
        IF v_is_decline THEN
            v_weights[17] := 0.10;
            v_weights[18] := 0.10;
            v_weights[19] := 0.10;
            v_weights[20] := 0.10;
        END IF;

        -- Normalise into a cumulative distribution for O(n) product selection
        v_total_weight := 0.0;
        FOR k IN 1..20 LOOP
            v_total_weight := v_total_weight + v_weights[k];
        END LOOP;

        v_cumsum  := ARRAY[]::FLOAT[];
        v_running := 0.0;
        FOR k IN 1..20 LOOP
            v_running := v_running + v_weights[k] / v_total_weight;
            v_cumsum  := array_append(v_cumsum, v_running);
        END LOOP;

        FOR v_basket_idx IN 1..v_basket_count LOOP
            -- Deterministic UUID: same (month, basket) pair → same UUID every run.
            -- md5() is deterministic; gen_random_uuid() is not (see decisions log #9).
            v_transaction_id := md5(v_month_idx::TEXT || ':' || v_basket_idx::TEXT)::UUID;

            -- Store assignment: Warsaw 8%, Paris/Amsterdam/Berlin/Madrid 23% each
            v_r := random();
            IF    v_r < 0.08 THEN v_store_id := 5;   -- Warsaw (underperformer)
            ELSIF v_r < 0.31 THEN v_store_id := 1;   -- Paris
            ELSIF v_r < 0.54 THEN v_store_id := 2;   -- Amsterdam
            ELSIF v_r < 0.77 THEN v_store_id := 3;   -- Berlin
            ELSE                   v_store_id := 4;   -- Madrid
            END IF;

            -- Random date within the month (uniform, not weighted to days of week)
            v_sale_date := v_month_start + FLOOR(random() * v_days_in_month)::INT;

            -- Basket size: 1–5 line items per transaction
            v_basket_size := 1 + FLOOR(random() * 5)::INT;

            FOR v_line_idx IN 1..v_basket_size LOOP
                -- Select product: scan cumulative weights
                v_r          := random();
                v_product_id := 20;             -- fallback (Kitchen Roll)
                FOR k IN 1..20 LOOP
                    IF v_r <= v_cumsum[k] THEN
                        v_product_id := k;
                        EXIT;
                    END IF;
                END LOOP;

                -- Quantity: 1–3 units per line item
                v_quantity := 1 + FLOOR(random() * 3)::INT;

                -- Price snapshot: capture the price at time of sale.
                -- Coffee Beans price increased from 8.50 to 11.99 on 2025-07-01.
                IF v_product_id = 3 AND v_sale_date < DATE '2025-07-01' THEN
                    v_unit_price := 8.50;
                ELSE
                    v_unit_price := p_prices[v_product_id];
                END IF;

                INSERT INTO retail.sales
                    (transaction_id, product_id, store_id, quantity, unit_price, sale_date)
                VALUES
                    (v_transaction_id, v_product_id, v_store_id,
                     v_quantity, v_unit_price, v_sale_date);
            END LOOP;  -- line items
        END LOOP;  -- baskets
    END LOOP;  -- months
END $$;
