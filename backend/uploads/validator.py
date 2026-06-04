"""Row-level validation and type coercion for uploaded sales data.

Input:  list of dicts with canonical keys and raw string values from parser.py
Output: (valid_rows, skipped_count)

Each valid row is a dict with typed Python values ready for DB insert.
Invalid rows are silently skipped; their count is returned so the API
can report it to the caller.
"""
import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

# Date formats tried in order. ISO first because it is unambiguous.
# DD/MM/YYYY is tried before MM/DD/YYYY to match European retail context.
_DATE_FORMATS = [
    "%Y-%m-%d",
    "%d/%m/%Y",
    "%m/%d/%Y",
    "%Y/%m/%d",
    "%d-%m-%Y",
    "%m-%d-%Y",
    "%d.%m.%Y",
    "%Y.%m.%d",
]

# Strips leading currency symbols and thousands-separator commas so values
# like "$1,200.50", "€12.50", "£3.99" parse cleanly.
_CURRENCY_RE = re.compile(r"^[£€$¥₹\s]+")
_THOUSANDS_RE = re.compile(r",(?=\d{3})")


def _parse_date(raw: str) -> date | None:
    raw = raw.strip()
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    return None


def _parse_numeric(raw: str) -> Decimal | None:
    """Strip currency symbols and thousands commas then parse as Decimal."""
    cleaned = _CURRENCY_RE.sub("", raw).strip()
    cleaned = _THOUSANDS_RE.sub("", cleaned)
    try:
        return Decimal(cleaned)
    except InvalidOperation:
        return None


def validate_rows(
    raw_rows: list[dict[str, str | None]],
) -> tuple[list[dict], int]:
    """Validate and coerce raw rows from the parser.

    Returns:
        (valid_rows, skipped_count)

        valid_rows: list of dicts with typed values:
            sale_date   datetime.date
            product     str
            category    str | None
            store       str | None
            quantity    int
            unit_price  Decimal | None
            revenue     Decimal

    Raises:
        ValueError if all rows are invalid (skipped_count == len(raw_rows)).
    """
    valid: list[dict] = []
    skipped = 0

    for row in raw_rows:
        # ── sale_date ──────────────────────────────────────────────────────────
        raw_date = row.get("sale_date") or ""
        sale_date = _parse_date(raw_date)
        if sale_date is None:
            skipped += 1
            continue

        # ── product ────────────────────────────────────────────────────────────
        product = (row.get("product") or "").strip()
        if not product:
            skipped += 1
            continue

        # ── quantity ───────────────────────────────────────────────────────────
        raw_qty = row.get("quantity") or ""
        try:
            # Accept "3.0" (Excel sometimes exports integers as floats)
            qty_dec = Decimal(str(raw_qty).strip())
            quantity = int(qty_dec)
            if quantity <= 0 or qty_dec != Decimal(quantity):
                raise ValueError
        except (ValueError, InvalidOperation):
            skipped += 1
            continue

        # ── unit_price (optional) ──────────────────────────────────────────────
        raw_price = row.get("unit_price")
        unit_price: Decimal | None = None
        if raw_price is not None and str(raw_price).strip():
            unit_price = _parse_numeric(str(raw_price))
            if unit_price is None or unit_price < 0:
                skipped += 1
                continue

        # ── revenue ────────────────────────────────────────────────────────────
        raw_rev = row.get("revenue")
        revenue: Decimal | None = None
        if raw_rev is not None and str(raw_rev).strip():
            revenue = _parse_numeric(str(raw_rev))
            if revenue is None or revenue < 0:
                skipped += 1
                continue

        # Derive revenue from quantity * unit_price if revenue column absent
        if revenue is None:
            if unit_price is not None:
                revenue = Decimal(quantity) * unit_price
            else:
                # Neither revenue nor unit_price — skip (should be caught at
                # header-mapping stage, but guard here too)
                skipped += 1
                continue

        # ── optional fields ────────────────────────────────────────────────────
        category_raw = (row.get("category") or "").strip()
        category: str | None = category_raw if category_raw else None

        store_raw = (row.get("store") or "").strip()
        store: str | None = store_raw if store_raw else None

        valid.append(
            {
                "sale_date": sale_date,
                "product": product,
                "category": category,
                "store": store,
                "quantity": quantity,
                "unit_price": unit_price,
                "revenue": revenue,
            }
        )

    if not valid:
        raise ValueError(
            f"No valid rows found — all {skipped} row(s) failed validation."
        )

    return valid, skipped
