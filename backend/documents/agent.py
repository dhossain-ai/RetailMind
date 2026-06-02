"""Document Q&A agent: ingest PDFs and answer questions from retrieved chunks."""

from pathlib import Path

from backend.config import settings
from backend.documents import chunking, db, embeddings, extract, vectorstore
from backend.llm.ollama import OllamaProvider
from backend.llm.hosted_stub import HostedProvider


def get_llm_provider():
    if settings.llm_provider == "ollama":
        return OllamaProvider(settings.ollama_base_url, settings.ollama_model)
    return HostedProvider()


def ingest(pdf_path: str | Path) -> dict:
    """Extract, chunk, embed, and store a PDF.

    Writes a metadata row to app.documents and stores chunks in ChromaDB.
    Returns a summary dict with document_id and chunk_count.
    """
    pdf_path = Path(pdf_path)
    filename = pdf_path.name
    title = pdf_path.stem.replace("_", " ").title()

    document_id = db.get_or_create_document(filename, title)

    all_chunks = []
    for page_num, page_text in extract.extract_pages(pdf_path):
        page_chunks = chunking.chunk_text(page_text, page_num, filename)
        all_chunks.extend(page_chunks)

    if not all_chunks:
        return {"document_id": document_id, "chunk_count": 0, "skipped": True}

    texts = [c["text"] for c in all_chunks]
    vectors = embeddings.embed(texts)
    vectorstore.ingest_chunks(all_chunks, vectors, document_id)
    db.update_chunk_count(document_id, len(all_chunks))

    return {"document_id": document_id, "chunk_count": len(all_chunks)}


def run(question: str) -> dict:
    """Answer a question from ingested documents.

    Returns a dict with: answer, sources (list of citation strings).
    If no documents have been ingested, answer honestly.
    """
    question_embedding = embeddings.embed([question])[0]
    chunks = vectorstore.query(question_embedding, settings.document_top_k)

    if not chunks:
        return {
            "answer": "No documents have been ingested yet. Please run the ingest command first.",
            "sources": [],
        }

    context_lines = []
    for i, c in enumerate(chunks, start=1):
        citation = f"[{c['source']}, page {c['page']}, chunk {c['chunk_idx']}]"
        context_lines.append(f"({i}) {c['text'].strip()}\nSource: {citation}")
    context_block = "\n\n".join(context_lines)

    prompt = f"""\
You are a helpful retail assistant. Answer the question using ONLY the context below.
If the context does not contain the information needed to answer, respond with exactly:
"I cannot find that information in the available documents."
Do not invent details not present in the context. Be concise.

Context:
{context_block}

Question: {question}
Answer:"""

    llm = get_llm_provider()
    answer = llm.complete(prompt).strip()

    sources = [
        f"[{c['source']}, page {c['page']}, chunk {c['chunk_idx']}]"
        for c in chunks
    ]

    return {"answer": answer, "sources": sources}
