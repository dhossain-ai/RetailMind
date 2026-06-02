"""Postgres operations for app.documents metadata.

Uses DATABASE_URL (postgres/admin role) — never analytics_reader.
"""

import psycopg

from backend.config import settings


def get_or_create_document(filename: str, title: str | None = None) -> int:
    """Return the document_id for filename, inserting a new row if needed."""
    with psycopg.connect(settings.database_url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id FROM app.documents WHERE filename = %s",
                (filename,),
            )
            row = cur.fetchone()
            if row:
                return row[0]
            cur.execute(
                "INSERT INTO app.documents (filename, title) VALUES (%s, %s) RETURNING id",
                (filename, title),
            )
            doc_id = cur.fetchone()[0]
            conn.commit()
            return doc_id


def update_chunk_count(document_id: int, chunk_count: int) -> None:
    """Set chunk_count after ingestion completes."""
    with psycopg.connect(settings.database_url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE app.documents SET chunk_count = %s WHERE id = %s",
                (chunk_count, document_id),
            )
            conn.commit()
