"""CSV/XLSX file parsing and column mapping for uploaded sales data.

Reads the file, normalises column headers, maps them to canonical field
names, and returns a list of dicts with canonical keys and raw string
values ready for the validator.

Supported formats: .csv, .xlsx  (.xls is intentionally not supported in v1)
Row limit: 50,000 rows (MAX_ROWS)
"""
import csv
from pathlib import Path

import openpyxl

SUPPORTED_EXTENSIONS = {".csv", ".xlsx"}
MAX_ROWS = 50_000

# Required canonical fields.
# At least one of REVENUE_FIELDS must be present.
REQUIRED_FIELDS = {"sale_date", "product", "quantity"}
REVENUE_FIELDS = {"revenue", "unit_price"}

# Maps every accepted column name (after normalisation) to its canonical name.
_SYNONYMS: dict[str, str] = {
    # sale_date
    "date": "sale_date",
    "sale_date": "sale_date",
    "order_date": "sale_date",
    "transaction_date": "sale_date",
    # product
    "product": "product",
    "item": "product",
    "product_name": "product",
    "item_name": "product",
    "sku": "product",
    "description": "product",
    "service": "product",
    "name": "product",
    # quantity
    "quantity": "quantity",
    "qty": "quantity",
    "units": "quantity",
    "count": "quantity",
    "units_sold": "quantity",
    "sold": "quantity",
    # revenue
    "revenue": "revenue",
    "amount": "revenue",
    "total": "revenue",
    "sales": "revenue",
    "net_sales": "revenue",
    "total_price": "revenue",
    "total_amount": "revenue",
    # unit_price
    "unit_price": "unit_price",
    "price": "unit_price",
    "unit_price_each": "unit_price",
    "price_each": "unit_price",
    "unit_cost": "unit_price",
    "cost": "unit_price",
    # category
    "category": "category",
    "category_name": "category",
    "department": "category",
    "dept": "category",
    "type": "category",
    # store
    "store": "store",
    "branch": "store",
    "location": "store",
    "shop": "store",
    "outlet": "store",
}

# Human-readable accepted names per canonical field (used in error messages).
_ACCEPTED: dict[str, list[str]] = {
    "sale_date": ["date", "sale_date", "order_date", "transaction_date"],
    "product": ["product", "item", "product_name", "item_name", "sku", "description"],
    "quantity": ["quantity", "qty", "units", "units_sold", "sold"],
    "revenue": ["revenue", "amount", "total", "sales", "net_sales", "total_price", "total_amount"],
    "unit_price": ["unit_price", "price", "price_each", "unit_cost", "cost"],
}


def _normalize(header: str) -> str:
    """Lowercase, strip whitespace, replace spaces and hyphens with underscores."""
    return header.lower().strip().replace(" ", "_").replace("-", "_")


def _map_headers(raw_headers: list[str]) -> dict[str, int]:
    """Return {canonical_name: column_index} for recognised columns.

    First occurrence wins when two columns map to the same canonical name.
    Raises ValueError if any required canonical field is missing.
    """
    mapping: dict[str, int] = {}
    for idx, raw in enumerate(raw_headers):
        canonical = _SYNONYMS.get(_normalize(raw))
        if canonical and canonical not in mapping:
            mapping[canonical] = idx

    # Check required fields
    missing = REQUIRED_FIELDS - mapping.keys()
    for field in sorted(missing):
        accepted = ", ".join(_ACCEPTED.get(field, [field]))
        raise ValueError(
            f"Required column not found: '{field}'. "
            f"Accepted names: {accepted}."
        )

    # Check revenue / unit_price — at least one must be present
    if not (REVENUE_FIELDS & mapping.keys()):
        rev_accepted = ", ".join(_ACCEPTED["revenue"])
        price_accepted = ", ".join(_ACCEPTED["unit_price"])
        raise ValueError(
            f"Required column not found: 'revenue' or 'unit_price'. "
            f"At least one must be present. "
            f"Revenue accepted names: {rev_accepted}. "
            f"Unit price accepted names: {price_accepted}."
        )

    return mapping


def _rows_to_dicts(
    headers: list[str],
    data_rows: list[list[str]],
) -> list[dict[str, str | None]]:
    """Apply header mapping and return a list of canonical-keyed dicts."""
    col_map = _map_headers(headers)
    result = []
    for row in data_rows:
        record: dict[str, str | None] = {}
        for canonical, idx in col_map.items():
            value = row[idx] if idx < len(row) else None
            # Treat empty strings as None for optional fields
            record[canonical] = value if value and value.strip() else None
        result.append(record)
    return result


def _read_csv(path: Path) -> tuple[list[str], list[list[str]]]:
    """Read a CSV file and return (headers, data_rows).

    Uses utf-8-sig so a BOM at the start of the file does not pollute the
    first column header (common in Excel-exported CSVs).
    """
    with path.open(encoding="utf-8-sig", newline="") as fh:
        reader = csv.reader(fh)
        headers = next(reader, None)
        if not headers:
            raise ValueError("CSV file is empty or has no header row.")
        rows = list(reader)
    return headers, rows


def _read_xlsx(path: Path) -> tuple[list[str], list[list[str]]]:
    """Read the first sheet of an XLSX file and return (headers, data_rows).

    Converts all cell values to strings. Empty rows (all-None) are skipped.
    """
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    ws = wb.worksheets[0]
    all_rows = list(ws.iter_rows(values_only=True))
    wb.close()

    if not all_rows:
        raise ValueError("XLSX file is empty or has no rows.")

    raw_headers = [str(cell) if cell is not None else "" for cell in all_rows[0]]

    data_rows: list[list[str]] = []
    for raw_row in all_rows[1:]:
        # Skip entirely empty rows (common at the end of Excel exports)
        if all(cell is None for cell in raw_row):
            continue
        data_rows.append([str(cell) if cell is not None else "" for cell in raw_row])

    return raw_headers, data_rows


def parse(path: Path) -> list[dict[str, str | None]]:
    """Parse a CSV or XLSX file into a list of canonical-keyed dicts.

    Each dict has canonical field names as keys and raw string values
    (or None for missing/empty cells). Values are not yet type-coerced —
    that is the validator's job.

    Raises:
        ValueError: unsupported extension, empty file, missing required columns,
                    or row count exceeding MAX_ROWS.
    """
    ext = path.suffix.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise ValueError(
            f"Unsupported file type: '{ext}'. Only .csv and .xlsx files are accepted."
        )

    if ext == ".csv":
        headers, data_rows = _read_csv(path)
    else:
        headers, data_rows = _read_xlsx(path)

    if len(data_rows) > MAX_ROWS:
        raise ValueError(
            f"File exceeds the {MAX_ROWS:,}-row limit ({len(data_rows):,} data rows found)."
        )

    if not data_rows:
        raise ValueError("File has a header row but no data rows.")

    return _rows_to_dicts(headers, data_rows)
