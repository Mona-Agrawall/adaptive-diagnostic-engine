"""Command-line entry point: validate the question bank and upsert it into MongoDB.

Usage (from the backend directory):
    python -m app.seed            # validate and upsert
    python -m app.seed --check    # validate the file only, no database access
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from pydantic import ValidationError
from pymongo.errors import PyMongoError

from .config import ConfigurationError, get_settings
from .db import Database
from .question_bank import DEFAULT_BANK_PATH, load_bank, seed_questions


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--file", type=Path, default=DEFAULT_BANK_PATH, help="Question bank JSON file.")
    parser.add_argument("--check", action="store_true", help="Validate the file without touching the database.")
    args = parser.parse_args(argv)

    try:
        bank = load_bank(args.file)
    except (OSError, ValueError, ValidationError) as exc:
        print(f"Question bank is invalid: {exc}", file=sys.stderr)
        return 1
    print(f"Validated {len(bank.questions)} questions across {len(bank.topics)} topics.")
    if args.check:
        return 0

    try:
        settings = get_settings()
    except ConfigurationError as exc:
        print(exc, file=sys.stderr)
        return 1
    db = Database(settings)
    try:
        db.ensure_indexes()
        stats = seed_questions(db.questions, db.topics, bank)
    except PyMongoError as exc:
        print(f"Could not reach MongoDB ({type(exc).__name__}). Check MONGODB_URI.", file=sys.stderr)
        return 1
    finally:
        db.close()
    print(
        f"Seed complete: {stats['inserted']} inserted, {stats['modified']} updated, "
        f"{stats['matched'] - stats['modified']} unchanged. Existing assessments were not modified."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
