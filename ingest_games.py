import sys
import pandas as pd
from nba_api.stats.endpoints import LeagueGameFinder
from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert
from app.db.database import SessionLocal
from app.db.models import Game

def fetch_games_dataframe(season="2024-25"):
    finder = LeagueGameFinder(
        season_nullable=season,
        league_id_nullable="00"
    )
    df = finder.get_data_frames()[0]

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

def ingest_games(season="2024-25", full_refresh=False):
    df = fetch_games_dataframe(season=season).sort_values(["GAME_DATE", "GAME_ID", "TEAM_ID"])
    db = SessionLocal()

    try:
        season_ids = df["SEASON_ID"].astype(str).unique().tolist()
        latest_game_date = None if full_refresh else get_latest_ingested_game_date(db, season_ids)

        if latest_game_date:
            latest_game_date = pd.to_datetime(latest_game_date)
            df = df[df["GAME_DATE"] > latest_game_date]

        if df.empty:
            scope = "full refresh" if full_refresh else "incremental load"
            print(
                f"No new team-game rows found for season {season} during {scope}."
            )
            return

        records = build_game_records(df)

        statement = insert(Game).values(records)
        statement = statement.on_conflict_do_nothing(
            index_elements=["game_id", "team_id"]
        )
        result = db.execute(statement)

        db.commit()
        inserted_count = result.rowcount if result.rowcount and result.rowcount > 0 else 0
        skipped_count = len(records) - inserted_count
        print(
            f"Fetched {len(records)} new team-game rows for season {season}. "
            f"Inserted {inserted_count}, skipped {skipped_count} existing rows."
        )

    except Exception as e:
        db.rollback()
        print("Error inserting games:", e)

    finally:
        db.close()

if __name__ == "__main__":
    season = sys.argv[1] if len(sys.argv) > 1 else "2024-25"
    full_refresh = "--full-refresh" in sys.argv[2:]
    ingest_games(season=season, full_refresh=full_refresh)
