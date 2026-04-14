import argparse
import os
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from ingest_games import ingest_games  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description="Run scheduled NBA game ingestion.")
    parser.add_argument(
        "--season",
        default=os.getenv("NBA_SEASON", "2025-26"),
        help="NBA season to ingest, such as 2025-26.",
    )
    parser.add_argument(
        "--full-refresh",
        action="store_true",
        help="Fetch the full season and rely on idempotent upsert logic.",
    )
    args = parser.parse_args()

    season = args.season
    print(f"Starting scheduled NBA ingestion for season {season}.")

    result = ingest_games(season=season, full_refresh=args.full_refresh)
    if result and result.get("status") == "failed":
        print(f"Scheduled ingestion failed: {result.get('error_message')}")
        return 1

    print(f"Scheduled ingestion completed: {result}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
