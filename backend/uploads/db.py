"""Database operations for the uploads pipeline.

Uses DATABASE_URL (postgres/admin role) to write to both:
  app.datasets          — upload metadata
  retail.business_sales — uploaded sales rows

Both inserts happen in a single transaction so a failure leaves no
orphaned rows in either table.
"""
from datetime import datetime

import psycopg

from backend.config import settings


def insert_dataset(
    original_filename: str,
    stored_filename: str,
    valid_rows: list[dict],
    skipped_count: int,
) -> int:
    """Insert dataset metadata and all sales rows atomically.

    Inserts app.datasets first (obtaining dataset_id), then bulk-inserts
    all rows into retail.business_sales, then commits both in one transaction.

    Returns:
        dataset_id (int)

    Raises:
        psycopg.Error on any DB failure (transaction is rolled back automatically).
    """
    row_count = len(valid_rows)

    with psycopg.connect(settings.database_url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO app.datasets
                    (original_filename, stored_filename, row_count, skipped_count)
                VALUES (%s, %s, %s, %s)
                RETURNING id
                """,
                (original_filename, stored_filename, row_count, skipped_count),
            )
            dataset_id: int = cur.fetchone()[0]

            if valid_rows:
                cur.executemany(
                    """
                    INSERT INTO retail.business_sales
                        (dataset_id, sale_date, product, category, store,
                         quantity, unit_price, revenue)
                    VALUES
                        (%(dataset_id)s, %(sale_date)s, %(product)s, %(category)s,
                         %(store)s, %(quantity)s, %(unit_price)s, %(revenue)s)
                    """,
                    [{"dataset_id": dataset_id, **row} for row in valid_rows],
                )

        conn.commit()

    return dataset_id


def list_datasets() -> list[dict]:
    """Return all datasets ordered newest first.

    Returns a list of dicts with keys:
        dataset_id, original_filename, row_count, skipped_count, upload_date
    """
    with psycopg.connect(settings.database_url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, original_filename, row_count, skipped_count, upload_date
                FROM app.datasets
                ORDER BY upload_date DESC
                """
            )
            rows = cur.fetchall()

    return [
        {
            "dataset_id": row[0],
            "original_filename": row[1],
            "row_count": row[2],
            "skipped_count": row[3],
            "upload_date": row[4],
        }
        for row in rows
    ]
