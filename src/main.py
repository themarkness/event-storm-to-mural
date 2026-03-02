"""
Event Storm to Mural — CLI entry point.

Usage:
    python -m src.main --input examples/sample.txt --mural-id <board-id>

The MURAL_ID env var is used if --mural-id is not provided.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from src.agents.base_agent import McpClient
from src.agents.document_analyst import DocumentAnalyst
from src.config import mural_id as default_mural_id


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run event storming agents on input docs")
    parser.add_argument("--input", required=True, help="Path to input document")
    parser.add_argument(
        "--mural-id",
        default=None,
        help="Mural board ID (overrides MURAL_ID env var)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Error: input file not found: {input_path}", file=sys.stderr)
        sys.exit(1)

    document = input_path.read_text(encoding="utf-8")
    mural_id = args.mural_id or default_mural_id()

    print(f"Starting event storm on: {input_path.name}")
    print(f"Target Mural board: {mural_id}")
    print()

    mcp = McpClient()
    try:
        analyst = DocumentAnalyst(mcp)
        summary = analyst.analyse(mural_id, document)
        print()
        print(f"[Document Analyst] Done: {summary}")
    finally:
        mcp.close()


if __name__ == "__main__":
    main()
