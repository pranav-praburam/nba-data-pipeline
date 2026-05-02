import argparse
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app.db.database import SessionLocal  # noqa: E402
from app.services.picks import settle_model_picks  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description="Settle model picks using the games table.")
    parser.add_argument(
        "--settle-before-date",
        default=None,
        help="Settle picks with game_date strictly before this YYYY-MM-DD (defaults to today).",
    )
    args = parser.parse_args()

    db = SessionLocal()
    try:
        result = settle_model_picks(db, settle_before_date=args.settle_before_date)
    finally:
        db.close()

    print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

