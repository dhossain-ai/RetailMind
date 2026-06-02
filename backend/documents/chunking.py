MAX_CHUNK_SIZE = 800
CHUNK_OVERLAP = 80


def chunk_text(
    text: str,
    page_num: int,
    source: str,
    *,
    max_size: int = MAX_CHUNK_SIZE,
    overlap: int = CHUNK_OVERLAP,
) -> list[dict]:
    """Split text into overlapping chunks of at most max_size characters.

    Returns a list of dicts with keys: text, page, source, chunk_idx.
    Overlap avoids hard-cutting a sentence at a chunk boundary.
    """
    chunks = []
    start = 0
    chunk_idx = 0
    while start < len(text):
        end = start + max_size
        chunk = text[start:end]
        if chunk.strip():
            chunks.append(
                {
                    "text": chunk,
                    "page": page_num,
                    "source": source,
                    "chunk_idx": chunk_idx,
                }
            )
            chunk_idx += 1
        start = end - overlap
    return chunks
