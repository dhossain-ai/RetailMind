SCHEMA_CONTEXT = """\
DATABASE SCHEMA (retail schema only — never query the app schema):

  retail.categories : id (int PK), name (text)
  retail.products   : id (int PK), name (text), category_id (int FK→categories.id),
                      unit_price (numeric — CURRENT list price only; does not reflect past prices)
  retail.stores     : id (int PK), name (text), city (text), region (text)
  retail.sales      : id (int PK), transaction_id (uuid — groups basket line items),
                      product_id (int FK→products.id), store_id (int FK→stores.id),
                      quantity (int), unit_price (numeric — HISTORICAL price at time of sale),
                      revenue (numeric — generated = quantity * unit_price),
                      sale_date (date)

JOIN PATHS — retail.sales has no category_id or store_name column:
  Sale → product name : JOIN retail.products p ON s.product_id = p.id
  Sale → category     : JOIN retail.products p ON s.product_id = p.id
                        JOIN retail.categories c ON p.category_id = c.id
  Sale → store name   : JOIN retail.stores st ON s.store_id = st.id

PRICE NOTE: s.unit_price (on retail.sales) is the snapshot price at the time of sale.
  p.unit_price (on retail.products) is the current list price only.
  For price-change analysis, always use s.unit_price — not p.unit_price.

BUSINESS TERM DEFINITIONS (v1):
  - "top-selling product" = highest SUM(quantity) (units sold), not revenue.
  - "category decline" = each category's share of total monthly revenue, not absolute revenue.\
"""
