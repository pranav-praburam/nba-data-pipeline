import argparse
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app.db.database import SessionLocal  # noqa: E402
from app.services.picks import generate_model_picks  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description="Generate model picks from odds API.")
    parser.add_argument("--game-date", default=None, help="YYYY-MM-DD; defaults to odds event date.")
    parser.add_argument("--last-n", type=int, default=10, help="Recent games window for model serving.")
    parser.add_argument("--edge-threshold", type=float, default=0.03, help="Minimum edge to record a pick.")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        result = generate_model_picks(
            db,
            target_date=args.game_date,
            last_n=args.last_n,
            edge_threshold=args.edge_threshold,
        )
    finally:
        db.close()

    print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

