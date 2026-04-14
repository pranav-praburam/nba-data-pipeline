import argparse
import os
import sys
import time
from datetime import datetime, timezone

import pandas as pd
from nba_api.stats.endpoints import LeagueGameFinder
from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert
from app.db.database import Base, SessionLocal, engine
from app.db.models import Game, PipelineRun

DEFAULT_SEASON = os.getenv("NBA_SEASON", "2025-26")
NBA_API_TIMEOUT = int(os.getenv("NBA_API_TIMEOUT", "90"))
NBA_API_RETRIES = int(os.getenv("NBA_API_RETRIES", "3"))


def fetch_games_dataframe(season="2024-25", timeout=NBA_API_TIMEOUT, retries=NBA_API_RETRIES):
    last_error = None
    for attempt in range(1, retries + 1):
        try:
            print(
                f"Fetching NBA games for {season} "
                f"(attempt {attempt}/{retries}, timeout={timeout}s)."
            )
            finder = LeagueGameFinder(
                season_nullable=season,
                league_id_nullable="00",
                timeout=timeout,
            )
            df = finder.get_data_frames()[0]
            break
        except Exception as error:
            last_error = error
            if attempt == retries:
                raise
            sleep_seconds = attempt * 10
            print(f"NBA API fetch failed: {error}. Retrying in {sleep_seconds}s.")
            time.sleep(sleep_seconds)
    else:
        raise last_error

    columns_needed = [
        "GAME_ID", "GAME_DATE", "SEASON_ID",
        "TEAM_ID", "TEAM_NAME",
        "MATCHUP", "WL", "PTS", "REB", "AST",
        "FG_PCT", "FG3_PCT", "FT_PCT"
    ]
    df = df[columns_needed].copy()

    def parse_opponent(matchup: str) -> str:
        parts = matchup.replace(" vs. ", " @ ").split(" @ ")
        return parts[1] if len(parts) > 1 else "Unknown"

    df["OPPONENT"] = df["MATCHUP"].apply(parse_opponent)
    df["GAME_DATE"] = pd.to_datetime(df["GAME_DATE"])

    return df

def get_latest_ingested_game_date(db, season_ids):
    return (
        db.query(func.max(Game.game_date))
        .filter(Game.season.in_(season_ids))
        .scalar()
    )

def build_game_records(df):
    records = []
    for _, row in df.iterrows():
        records.append(
            {
                "game_id": row["GAME_ID"],
                "game_date": row["GAME_DATE"].strftime("%Y-%m-%d"),
                "season": str(row["SEASON_ID"]),
                "team_id": int(row["TEAM_ID"]),
                "team": row["TEAM_NAME"],
                "opponent_id": 0,
                "opponent": row["OPPONENT"],
                "matchup": row["MATCHUP"],
                "wl": row["WL"],
                "points": int(row["PTS"]) if pd.notna(row["PTS"]) else 0,
                "rebounds": int(row["REB"]) if pd.notna(row["REB"]) else None,
                "assists": int(row["AST"]) if pd.notna(row["AST"]) else None,
                "fg_pct": float(row["FG_PCT"]) if pd.notna(row["FG_PCT"]) else None,
                "fg3_pct": float(row["FG3_PCT"]) if pd.notna(row["FG3_PCT"]) else None,
                "ft_pct": float(row["FT_PCT"]) if pd.notna(row["FT_PCT"]) else None,
            }
        )
    return records

def record_pipeline_run(
    db,
    season,
    mode,
    rows_fetched,
    rows_inserted,
    rows_skipped,
    status,
    error_message=None,
):
    run = PipelineRun(
        pipeline_name="games_ingestion",
        season=season,
        mode=mode,
        rows_fetched=rows_fetched,
        rows_inserted=rows_inserted,
        rows_skipped=rows_skipped,
        status=status,
        error_message=error_message,
        completed_at=datetime.now(timezone.utc),
    )
    db.add(run)

def ingest_games(season="2024-25", full_refresh=False):
    db = SessionLocal()
    mode = "full_refresh" if full_refresh else "incremental"

    try:
        Base.metadata.create_all(bind=engine)
        df = fetch_games_dataframe(season=season).sort_values(["GAME_DATE", "GAME_ID", "TEAM_ID"])
        season_ids = df["SEASON_ID"].astype(str).unique().tolist()
        latest_game_date = None if full_refresh else get_latest_ingested_game_date(db, season_ids)

        if latest_game_date:
            latest_game_date = pd.to_datetime(latest_game_date)
            df = df[df["GAME_DATE"] > latest_game_date]

        if df.empty:
            record_pipeline_run(
                db=db,
                season=season,
                mode=mode,
                rows_fetched=0,
                rows_inserted=0,
                rows_skipped=0,
                status="success",
            )
            db.commit()
            scope = "full refresh" if full_refresh else "incremental load"
            print(
                f"No new team-game rows found for season {season} during {scope}."
            )
            return {
                "season": season,
                "mode": mode,
                "rows_fetched": 0,
                "rows_inserted": 0,
                "rows_skipped": 0,
                "status": "success",
            }

        records = build_game_records(df)

        statement = insert(Game).values(records)
        statement = statement.on_conflict_do_nothing(
            index_elements=["game_id", "team_id"]
        )
        result = db.execute(statement)

        inserted_count = result.rowcount if result.rowcount and result.rowcount > 0 else 0
        skipped_count = len(records) - inserted_count
        record_pipeline_run(
            db=db,
            season=season,
            mode=mode,
            rows_fetched=len(records),
            rows_inserted=inserted_count,
            rows_skipped=skipped_count,
            status="success",
        )
        db.commit()
        print(
            f"Fetched {len(records)} new team-game rows for season {season}. "
            f"Inserted {inserted_count}, skipped {skipped_count} existing rows."
        )
        return {
            "season": season,
            "mode": mode,
            "rows_fetched": len(records),
            "rows_inserted": inserted_count,
            "rows_skipped": skipped_count,
            "status": "success",
        }

    except Exception as e:
        error_message = str(e)
        try:
            db.rollback()
            record_pipeline_run(
                db=db,
                season=season,
                mode=mode,
                rows_fetched=0,
                rows_inserted=0,
                rows_skipped=0,
                status="failed",
                error_message=error_message[:2000],
            )
            db.commit()
        except Exception as record_error:
            db.rollback()
            print("Could not record failed pipeline run:", record_error)
        print("Error inserting games:", e)
        return {
            "season": season,
            "mode": mode,
            "rows_fetched": 0,
            "rows_inserted": 0,
            "rows_skipped": 0,
            "status": "failed",
            "error_message": error_message[:2000],
        }

    finally:
        db.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingest NBA team-game rows.")
    parser.add_argument(
        "season",
        nargs="?",
        default=DEFAULT_SEASON,
        help="NBA season to ingest, such as 2025-26.",
    )
    parser.add_argument(
        "--full-refresh",
        action="store_true",
        help="Fetch the full season and rely on idempotent upsert logic.",
    )
    args = parser.parse_args()

    result = ingest_games(season=args.season, full_refresh=args.full_refresh)
    if result and result.get("status") == "failed":
        sys.exit(1)
