"""Analytics agent command-line interface.

Usage:
    py -3.11 -m backend.analytics.cli "What is the top-selling product?"

Output:
    - Generated SQL
    - Result columns and rows
    - Plain-English answer
"""
import sys

from backend.analytics.agent import get_llm_provider, run


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: py -3.11 -m backend.analytics.cli <question>", file=sys.stderr)
        sys.exit(1)

    question = " ".join(sys.argv[1:])
    llm = get_llm_provider()

    print(f"Question: {question}\n")

    try:
        result = run(question, llm)
    except ValueError as exc:
        print(f"SQL validation error: {exc}", file=sys.stderr)
        sys.exit(1)

    print("─── Generated SQL " + "─" * 60)
    print(result["sql"])

    print("\n─── Result " + "─" * 67)
    print("Columns:", result["columns"])
    for row in result["rows"]:
        print("\t".join(str(v) for v in row))

    print("\n─── Answer " + "─" * 67)
    print(result["answer"])


if __name__ == "__main__":
    main()
