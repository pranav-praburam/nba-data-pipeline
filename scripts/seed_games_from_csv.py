import argparse
import csv
import sys
from pathlib import Path

from sqlalchemy.dialects.postgresql import insert

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app.db.database import Base, SessionLocal, engine  # noqa: E402
from app.db.models import Game  # noqa: E402


DEFAULT_CSV_PATH = PROJECT_ROOT / "data" / "games_seed.csv"


def load_rows(csv_path: Path):
    with csv_path.open(newline="", encoding="utf-8") as csv_file:
        reader = csv.DictReader(csv_file)
        rows = []
        for row in reader:
            rows.append(
                {
                    "game_id": row["game_id"],
                    "game_date": row["game_date"],
                    "season": row["season"],
                    "team_id": int(row["team_id"]),
                    "team": row["team"],
                    "opponent_id": int(row["opponent_id"]),
                    "opponent": row["opponent"],
                    "matchup": row["matchup"],
                    "wl": row["wl"] or None,
                    "points": int(row["points"]),
                    "rebounds": int(row["rebounds"]) if row["rebounds"] else None,
                    "assists": int(row["assists"]) if row["assists"] else None,
                    "fg_pct": float(row["fg_pct"]) if row["fg_pct"] else None,
                    "fg3_pct": float(row["fg3_pct"]) if row["fg3_pct"] else None,
                    "ft_pct": float(row["ft_pct"]) if row["ft_pct"] else None,
                }
            )
    return rows


def main():
    parser = argparse.ArgumentParser(description="Seed the games table from a CSV snapshot.")
    parser.add_argument(
        "--csv-path",
        default=str(DEFAULT_CSV_PATH),
        help="Path to the CSV seed file.",
    )
    args = parser.parse_args()

    csv_path = Path(args.csv_path)
    if not csv_path.exists():
        raise FileNotFoundError(f"Seed file not found: {csv_path}")

    rows = load_rows(csv_path)
    if not rows:
        print("Seed file contained no rows.")
        return 0

    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        statement = insert(Game).values(rows)
        statement = statement.on_conflict_do_nothing(index_elements=["game_id", "team_id"])
        result = db.execute(statement)
        db.commit()
        inserted_count = result.rowcount if result.rowcount and result.rowcount > 0 else 0
        skipped_count = len(rows) - inserted_count
        print(
            f"Seeded games from {csv_path.name}. "
            f"Inserted {inserted_count}, skipped {skipped_count} existing rows."
        )
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
