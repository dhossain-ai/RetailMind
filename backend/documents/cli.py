"""Document agent CLI.

Usage:
    py -3.11 -m backend.documents.cli ingest <path/to/file.pdf>
    py -3.11 -m backend.documents.cli query "<question>"
"""

import argparse
import sys

from backend.documents.agent import ingest, run

SEPARATOR = "-" * 72


def cmd_ingest(args: argparse.Namespace) -> None:
    print(f"Ingesting: {args.pdf_path}")
    result = ingest(args.pdf_path)
    if result.get("skipped"):
        print("No extractable text found — PDF skipped.")
        return
    print(f"\n{SEPARATOR}")
    print(f"Document ID : {result['document_id']}")
    print(f"Chunks      : {result['chunk_count']}")
    print(f"{SEPARATOR}")
    print("Ingestion complete. Run a query to test retrieval.")


def cmd_query(args: argparse.Namespace) -> None:
    print(f"Question: {args.question}\n")
    result = run(args.question)
    print(f"{SEPARATOR} Answer")
    print(result["answer"])
    if result["sources"]:
        print(f"\n{SEPARATOR} Sources")
        for src in result["sources"]:
            print(f"  {src}")
    print(SEPARATOR)


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="backend.documents.cli",
        description="Document agent — ingest PDFs and query over them",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    ingest_p = sub.add_parser("ingest", help="Ingest a PDF into the vector store")
    ingest_p.add_argument("pdf_path", help="Path to the PDF file")

    query_p = sub.add_parser("query", help="Ask a question over ingested documents")
    query_p.add_argument("question", help="Natural-language question")

    args = parser.parse_args()
    if args.command == "ingest":
        cmd_ingest(args)
    elif args.command == "query":
        cmd_query(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
