"""Analytics agent: natural language → SQL → plain-English answer.

Two LLM calls per question:
  1. Generate SQL from the question + schema context.
  2. Summarise the query result in plain English.

The real DB security boundary is analytics_reader. The SQL validator is a
fast defense-in-depth layer that rejects obviously bad SQL before execution.
"""
import re

from backend.analytics.db import run_query
from backend.analytics.schema_context import BUSINESS_SCHEMA_CONTEXT_TEMPLATE, SCHEMA_CONTEXT
from backend.analytics.sql_validator import validate, validate_uploaded
from backend.config import settings
from backend.llm.base import LLMProvider
from backend.llm.ollama import OllamaProvider

_SQL_PROMPT = """\
You are a SQL assistant. Write a single PostgreSQL SELECT query to answer the retail question.

{schema}

STRICT RULES:
1. Qualify ALL tables with the retail. prefix (retail.sales, retail.stores, etc.).
2. Only use column names from the schema. Date column on retail.sales is sale_date (not transaction_date).
3. For year-month labels: use to_char(sale_date, 'YYYY-MM'). Do NOT use LPAD(EXTRACT(...)).
4. Use aliases consistently — if a table is aliased as s, never write retail.sales.column in the same query.
5. In a CTE: the outer SELECT can only reference columns defined in that CTE's SELECT list.
6. Window functions (LAG, RANK, etc.) cannot appear in WHERE — wrap them in a CTE or subquery first.
7. Output ONLY the raw SQL — no explanation, no markdown, no code fences.
8. For category decline or category-comparison questions: use Template A (plain SELECT, no WITH clause,
   no window functions). The monthly revenue totals alone are sufficient to identify the declining
   category — do not add LAG, CTEs, or any calculation beyond SUM(s.revenue).

TEMPLATES — copy the closest match and adapt it:

Template A — Category revenue by month (declining category, category comparison):
-- USE EXACTLY AS WRITTEN. No CTEs, no LAG, no window functions, no extra WHERE conditions.
-- Returns ALL months for ALL categories. The declining category is the one with revenue
-- dropping to near zero in the most recent months while others remain high.
SELECT to_char(s.sale_date, 'YYYY-MM') AS month,
       c.name AS category,
       SUM(s.revenue) AS revenue
FROM retail.sales s
JOIN retail.products p ON s.product_id = p.id
JOIN retail.categories c ON p.category_id = c.id
WHERE s.sale_date >= date_trunc('month', CURRENT_DATE) - INTERVAL '12 months'
GROUP BY 1, 2
ORDER BY month ASC, revenue DESC

Template B — Compare all stores/products/categories (which needs attention, which is worst):
-- Returns ALL rows ordered from worst to best. Do NOT add LIMIT 1.
SELECT st.name, SUM(s.revenue) AS total_revenue, COUNT(DISTINCT s.transaction_id) AS baskets
FROM retail.sales s
JOIN retail.stores st ON s.store_id = st.id
GROUP BY st.name
ORDER BY total_revenue ASC

Template C — Monthly trend or seasonality (best month, is there a seasonal pattern):
-- Returns ALL months in chronological order. Do NOT add LIMIT 1.
-- The complete monthly series lets the answer identify the peak and whether it repeats.
SELECT to_char(s.sale_date, 'YYYY-MM') AS month,
       SUM(s.revenue) AS total_revenue
FROM retail.sales s
WHERE s.sale_date >= date_trunc('month', CURRENT_DATE) - INTERVAL '12 months'
GROUP BY month
ORDER BY month ASC

Template D — Price change detection (only products with >1 distinct price; use s.unit_price):
WITH price_hist AS (
    SELECT p.name, s.unit_price, MIN(s.sale_date) AS first_seen, MAX(s.sale_date) AS last_seen
    FROM retail.sales s
    JOIN retail.products p ON s.product_id = p.id
    GROUP BY p.name, s.unit_price
)
SELECT name, unit_price, first_seen, last_seen
FROM price_hist
WHERE name IN (SELECT name FROM price_hist GROUP BY name HAVING COUNT(*) > 1)
ORDER BY name, first_seen

Question: {question}

SQL:"""

_ANSWER_PROMPT = """\
A retail analytics question was answered with SQL. Write a concise plain-English answer.

Question: {question}

SQL used:
{sql}

Result columns: {columns}
Result rows (first {nrows} shown):
{rows_text}

Answer ONLY the question asked, in 2-4 sentences with specific numbers. Do not add analysis for topics not asked about. Do not mention SQL or technical terms.

Interpretation guides — apply only the one relevant to the question:
- "Best month" means the month with the HIGHEST value in the results (not the lowest).
- "Declining category" means the category whose revenue is near zero in the MOST RECENT months while all other categories remain at normal levels. A temporary dip in one month is not a decline.
- "Store needs attention" means the single store with the LOWEST total revenue.
- "Price change" means a product that appears with two or more different unit_price values.
- "Seasonality" means any month whose revenue is roughly 1.5× or more above the adjacent months.\
"""

# SQL generation prompt for uploaded business data (retail.business_sales).
# {schema}, {dataset_id}, and {question} are substituted before sending to the LLM.
# The SQL templates embed the actual dataset_id so the LLM sees concrete examples.
_BUSINESS_SQL_PROMPT = """\
You are a SQL assistant. Write a single PostgreSQL SELECT query to answer the business sales question.

{schema}

STRICT RULES:
1. Query ONLY retail.business_sales. Do not join any other table.
2. Always include WHERE dataset_id = {dataset_id} in your query.
   If you alias the table (e.g. AS bs), write WHERE bs.dataset_id = {dataset_id}.
3. Qualify the table with the retail. prefix: retail.business_sales.
4. Only use column names from the schema above.
5. For year-month labels: use to_char(sale_date, 'YYYY-MM').
6. Output ONLY the raw SQL — no explanation, no markdown, no code fences.

TEMPLATES — copy the closest match and adapt it:

Template A — Top-selling product (highest units sold):
SELECT product, SUM(quantity) AS total_units
FROM retail.business_sales
WHERE dataset_id = {dataset_id}
GROUP BY product
ORDER BY total_units DESC
LIMIT 10

Template B — Total revenue (all products):
SELECT product, SUM(revenue) AS total_revenue
FROM retail.business_sales
WHERE dataset_id = {dataset_id}
GROUP BY product
ORDER BY total_revenue DESC

Template C — Revenue by month (trend):
SELECT to_char(sale_date, 'YYYY-MM') AS month, SUM(revenue) AS total_revenue
FROM retail.business_sales
WHERE dataset_id = {dataset_id}
GROUP BY month
ORDER BY month ASC

Template D — Revenue by category:
SELECT category, SUM(revenue) AS total_revenue
FROM retail.business_sales
WHERE dataset_id = {dataset_id}
GROUP BY category
ORDER BY total_revenue DESC

Question: {question}

SQL:"""


def _extract_sql(text: str) -> str:
    """Pull the SQL out of an LLM response that may include prose or fences."""
    m = re.search(r"```(?:sql)?\s*([\s\S]+?)```", text, re.IGNORECASE)
    if m:
        return m.group(1).strip()
    m = re.search(r"((?:WITH|SELECT)\b[\s\S]+)", text, re.IGNORECASE)
    if m:
        return m.group(1).strip()
    return text.strip()


def _format_rows(columns: list[str], rows: list[list], limit: int = 20) -> str:
    header = " | ".join(columns)
    sep = "-" * len(header)
    lines = [header, sep] + [
        " | ".join(str(v) for v in row) for row in rows[:limit]
    ]
    return "\n".join(lines)


def _compute_observations(columns: list[str], rows: list[list]) -> str:
    """Compute key facts from the result set in Python before passing to the answer LLM.

    Handles two shapes:
    - Time series with a category dimension (e.g. monthly revenue per category):
      computes recent-vs-baseline change per category so the LLM reads one line.
    - Simple time series (e.g. monthly total revenue):
      computes the peak month, avg of others, and the ratio.

    Only runs when the result has a 'month' column and more than 4 rows.
    Returns an empty string for result shapes that don't match.
    """
    if len(rows) < 4:
        return ""

    col_lower = [c.lower() for c in columns]

    # Locate the month column (expects 'YYYY-MM' strings)
    try:
        month_idx = col_lower.index("month")
    except ValueError:
        return ""

    # Identify numeric vs categorical non-month columns
    numeric_idxs: list[int] = []
    cat_idx: int | None = None
    for i, c in enumerate(col_lower):
        if i == month_idx:
            continue
        try:
            for r in rows[:5]:
                if r[i] is not None:
                    float(r[i])
            numeric_idxs.append(i)
        except (TypeError, ValueError):
            if cat_idx is None and isinstance(rows[0][i], str):
                cat_idx = i

    if not numeric_idxs:
        return ""

    num_idx = numeric_idxs[0]  # primary metric column

    months_sorted = sorted({r[month_idx] for r in rows if r[month_idx] is not None})
    if len(months_sorted) < 2:
        return ""

    # ── Case A: time series + category ─────────────────────────────────────
    if cat_idx is not None:
        recent = set(months_sorted[-3:])
        earlier = set(months_sorted[:-3])
        categories = list(dict.fromkeys(r[cat_idx] for r in rows))

        lines = [
            f"KEY OBSERVATIONS (computed from all {len(rows)} result rows):",
            f"  Comparing the 3 most recent months ({', '.join(sorted(recent))})"
            f" to the {len(earlier)} earlier months:",
        ]
        summaries: list[tuple] = []
        for cat in categories:
            cat_rows = [r for r in rows if r[cat_idx] == cat]
            r_vals = [float(r[num_idx]) for r in cat_rows
                      if r[month_idx] in recent and r[num_idx] is not None]
            e_vals = [float(r[num_idx]) for r in cat_rows
                      if r[month_idx] in earlier and r[num_idx] is not None]
            r_avg = sum(r_vals) / len(r_vals) if r_vals else 0.0
            e_avg = sum(e_vals) / len(e_vals) if e_vals else 0.0
            pct = (r_avg - e_avg) / e_avg * 100 if e_avg else 0.0
            summaries.append((cat, e_avg, r_avg, pct))

        summaries.sort(key=lambda x: x[3])  # most negative first
        for cat, base, rec, pct in summaries:
            flag = " ← MOST DECLINING" if pct == min(s[3] for s in summaries) and pct < -30 else ""
            lines.append(
                f"  {cat}: baseline avg ${base:.2f} → recent avg ${rec:.2f}"
                f" ({pct:+.1f}%){flag}"
            )
        return "\n".join(lines)

    # ── Case B: simple time series ──────────────────────────────────────────
    month_vals = {
        r[month_idx]: float(r[num_idx])
        for r in rows
        if r[month_idx] is not None and r[num_idx] is not None
    }
    if not month_vals:
        return ""

    peak_month = max(month_vals, key=month_vals.get)
    peak_val = month_vals[peak_month]
    others = [v for m, v in month_vals.items() if m != peak_month]
    avg_others = sum(others) / len(others) if others else peak_val
    ratio = peak_val / avg_others if avg_others else 1.0
    seasonal = "YES" if ratio >= 1.5 else "no strong pattern"

    return (
        f"KEY OBSERVATIONS (computed from all {len(rows)} result rows):\n"
        f"  Peak month: {peak_month} (${peak_val:.2f})\n"
        f"  Average of all other months: ${avg_others:.2f}\n"
        f"  Peak / avg-others ratio: {ratio:.2f}×\n"
        f"  Seasonality: {seasonal}"
    )


def get_llm_provider() -> LLMProvider:
    if settings.llm_provider == "ollama":
        return OllamaProvider(settings.ollama_base_url, settings.ollama_model)
    raise NotImplementedError(
        f"LLM provider {settings.llm_provider!r} is not configured. "
        "Set LLM_PROVIDER=ollama for local development."
    )


def run(question: str, llm: LLMProvider, dataset_id: int | None = None) -> dict:
    """Run the full NL→SQL→answer pipeline.

    Args:
        question:   Natural-language question from the user.
        llm:        LLM provider to use for SQL generation and answer summarisation.
        dataset_id: When provided (> 0), queries retail.business_sales filtered to
                    that dataset. When None, queries the demo star schema.

    Returns:
        {
            "sql":      str  — the validated SQL that was executed,
            "columns":  list — column names from the result,
            "rows":     list — result rows (each a list of values),
            "answer":   str  — plain-English answer from the LLM,
            "mode":     str  — "uploaded" or "demo",
        }

    Raises:
        ValueError  if the generated SQL fails validation.
        psycopg.*   if the DB query fails.
        httpx.*     if the LLM call fails.
    """
    if dataset_id is not None:
        schema = BUSINESS_SCHEMA_CONTEXT_TEMPLATE.format(dataset_id=dataset_id)
        sql_prompt = _BUSINESS_SQL_PROMPT.format(
            schema=schema, dataset_id=dataset_id, question=question
        )
    else:
        sql_prompt = _SQL_PROMPT.format(schema=SCHEMA_CONTEXT, question=question)

    raw = llm.complete(sql_prompt)
    sql = _extract_sql(raw)

    if dataset_id is not None:
        sql = validate_uploaded(sql, dataset_id)
    else:
        sql = validate(sql)  # may raise ValueError; may append LIMIT

    result = run_query(sql)
    columns, rows = result["columns"], result["rows"]

    rows_text = _format_rows(columns, rows, limit=150)
    observations = _compute_observations(columns, rows)
    if observations:
        rows_text = rows_text + "\n\n" + observations

    answer_prompt = _ANSWER_PROMPT.format(
        question=question,
        sql=sql,
        columns=", ".join(columns),
        nrows=min(len(rows), 150),
        rows_text=rows_text,
    )
    answer = llm.complete(answer_prompt).strip()

    mode = "uploaded" if dataset_id is not None else "demo"
    return {"sql": sql, "columns": columns, "rows": rows, "answer": answer, "mode": mode}
