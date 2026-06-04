"""Upload agent: orchestrates parsing, validation, and DB insertion.

Entry point for POST /datasets/upload. Mirrors the pattern of
backend/documents/agent.py: a single ingest() function that the
endpoint calls, returning a plain dict on success and raising on error.
"""
from pathlib import Path

from backend.uploads.db import insert_dataset
from backend.uploads.parser import parse
from backend.uploads.validator import validate_rows


def ingest(path: Path, original_filename: str) -> dict:
    """Parse, validate, and persist an uploaded CSV or XLSX file.

    Args:
        path: absolute path to the saved upload on disk.
        original_filename: the user-supplied filename (stored as metadata only).

    Returns:
        {
            "dataset_id":        int,
            "original_filename": str,
            "row_count":         int,
            "skipped_count":     int,
        }

    Raises:
        ValueError:    unsupported file type, missing columns, zero valid rows,
                       or row limit exceeded.  Callers should map this to HTTP 400.
        psycopg.Error: DB unavailable.  Callers should map this to HTTP 503.
    """
    raw_rows = parse(path)
    valid_rows, skipped_count = validate_rows(raw_rows)

    dataset_id = insert_dataset(
        original_filename=original_filename,
        stored_filename=path.name,
        valid_rows=valid_rows,
        skipped_count=skipped_count,
    )

    return {
        "dataset_id": dataset_id,
        "original_filename": original_filename,
        "row_count": len(valid_rows),
        "skipped_count": skipped_count,
    }
