# RetailMind — Seed Data Expectations

This file is the answer key for the five demo patterns planted in `scripts/002_seed.sql`. Use it to verify the analytics agent's responses and to check the seeded data after running the script.

---

## Expected demo answers

### 1. Which category is declining?

**Household**

Household products (Washing-Up Liquid, Paper Towels, Laundry Detergent, Kitchen Roll) have their product-selection weight reduced from 1.0 to 0.10 in months 21–23 of the generation loop — March, April, and May 2026. This represents an ~85% reduction in selections.

The correct metric for this question is **Household's share of total monthly revenue** (not absolute revenue). Using share neutralises the December seasonal spike: if December doubles all categories equally, shares stay flat and the comparison is clean.

Expected pattern: Household share is stable at roughly **15–17%** of monthly revenue from October 2025 through February 2026, then collapses to roughly **2%** in March–May 2026.

### 2. What is the top-selling product?

**Coffee Beans**

"Best-selling" is defined as **total units sold** (not revenue). This is consistent with the 5× selection weight assigned in the generator and is independent of the mid-stream price change (which would inflate Coffee Beans' revenue advantage and muddy the comparison).

Coffee Beans carries a weight of 5.0 versus 1.0 for all other products. With 20 products and a total normal weight of ~24, Coffee Beans is selected approximately 21% of the time versus ~4% for each other product — roughly **5× the units** of the next best seller.

### 3. What is the best month? / Is there seasonality?

**December** — both December 2024 and December 2025

The generator produces 128 baskets in any December month versus 64 in all other months. This doubles row count and revenue for those two months, creating a clear seasonal spike visible in any monthly revenue rollup.

Expected pattern: December 2024 and December 2025 each show roughly **2× the revenue** of adjacent months.

### 4. Which store needs attention?

**RetailMind Warsaw** (Warsaw, Masovian Voivodeship)

Warsaw is assigned to 8% of baskets; the other four stores (Paris, Amsterdam, Berlin, Madrid) are each assigned 23%. Over ~5,000 rows this produces roughly **400 rows** for Warsaw versus **~1,150 rows** for each other store.

Expected pattern: Warsaw is clearly last in both row count and total revenue, at roughly **one-third** of the other stores.

### 5. Did any product have a price change? Which one, and when?

**Coffee Beans — price increased from £8.50 to £11.99 on 2025-07-01**

The generator writes `unit_price = 8.50` on every Coffee Beans sales row where `sale_date < 2025-07-01`, and `unit_price = 11.99` on all rows from that date onward. The current list price in `products.unit_price` is 11.99.

This demonstrates decision #3 in the decisions log: historical revenue figures stay correct because the price at the time of sale is captured on each sales row, not looked up from the current product price.

Expected pattern: two distinct `unit_price` values in Coffee Beans sales rows — 8.50 (June 2024 through June 2025) and 11.99 (July 2025 through May 2026).

---

## Verification queries

Run these against the seeded database to confirm each pattern is present before trusting the analytics agent.

```sql
-- ── 1. Sanity check: row count and date range ────────────────────────────
SELECT COUNT(*)    AS total_rows,
       MIN(sale_date) AS earliest,
       MAX(sale_date) AS latest
FROM retail.sales;
-- Expect: ~5 000 rows, 2024-06-01 to 2026-05-31


-- ── 2. Top 5 products by UNITS SOLD ─────────────────────────────────────
-- Uses quantity (not revenue) — consistent with the 5× selection-weight
-- definition. Revenue is not used because the price change inflates Coffee
-- Beans' revenue advantage beyond the planted 5× ratio.
SELECT p.name,
       SUM(s.quantity) AS total_units
FROM retail.sales s
JOIN retail.products p ON s.product_id = p.id
GROUP BY p.name
ORDER BY total_units DESC
LIMIT 5;
-- Expect: Coffee Beans #1, roughly 5× the next entry


-- ── 3. Monthly revenue — spot the December spikes ───────────────────────
SELECT date_trunc('month', sale_date)      AS month,
       SUM(revenue)::NUMERIC(12,2)         AS revenue
FROM retail.sales
GROUP BY 1
ORDER BY 1;
-- Expect: Dec 2024 and Dec 2025 roughly 2× the adjacent months


-- ── 4. Revenue by store — spot Warsaw ───────────────────────────────────
SELECT st.name,
       SUM(s.revenue)::NUMERIC(12,2) AS revenue,
       COUNT(*)                       AS rows
FROM retail.sales s
JOIN retail.stores st ON s.store_id = st.id
GROUP BY st.name
ORDER BY revenue DESC;
-- Expect: Warsaw last, roughly one-third of the other four stores


-- ── 5. Household share of monthly revenue — Dec-spike-neutral decline ───
-- Measuring share (%) rather than absolute revenue means the December
-- spike — which lifts all categories equally — does not contaminate the
-- baseline used for comparison.
SELECT date_trunc('month', sale_date)                              AS month,
       ROUND(
           100.0
           * SUM(revenue) FILTER (WHERE c.name = 'Household')
           / SUM(revenue),
       1)                                                          AS household_pct
FROM retail.sales s
JOIN retail.products  p ON s.product_id   = p.id
JOIN retail.categories c ON p.category_id = c.id
WHERE sale_date >= '2025-10-01'
GROUP BY 1
ORDER BY 1;
-- Expect: ~15-17% in Oct 2025–Feb 2026, collapsing to ~2% in Mar–May 2026


-- ── 6. Coffee Beans price history ────────────────────────────────────────
SELECT s.unit_price,
       MIN(sale_date) AS first_seen,
       MAX(sale_date) AS last_seen,
       COUNT(*)       AS rows
FROM retail.sales s
JOIN retail.products p ON s.product_id = p.id
WHERE p.name = 'Coffee Beans'
GROUP BY s.unit_price
ORDER BY first_seen;
-- Expect: unit_price 8.50 with last_seen around 2025-06-xx,
--         unit_price 11.99 with first_seen 2025-07-xx
```
