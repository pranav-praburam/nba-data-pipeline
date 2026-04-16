import argparse
import os
import sys
import time
from datetime import datetime, timezone

import pandas as pd
import requests
from nba_api.stats.endpoints import LeagueGameLog
from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert
from app.db.database import Base, SessionLocal, engine
from app.db.models import Game, PipelineRun

DEFAULT_SEASON = os.getenv("NBA_SEASON", "2025-26")
NBA_API_TIMEOUT = int(os.getenv("NBA_API_TIMEOUT", "90"))
NBA_API_RETRIES = int(os.getenv("NBA_API_RETRIES", "3"))

GAME_COLUMNS = [
    "GAME_ID", "GAME_DATE", "SEASON_ID",
    "TEAM_ID", "TEAM_NAME",
    "MATCHUP", "WL", "PTS", "REB", "AST",
    "FG_PCT", "FG3_PCT", "FT_PCT", "OPPONENT",
]


def fetch_games_dataframe(season="2024-25", timeout=NBA_API_TIMEOUT, retries=NBA_API_RETRIES):
    # stats.nba.com is the richer season source, but it can be flaky from CI/cloud
    # networks. Retries plus a CDN fallback keep scheduled ingestion dependable.
    last_error = None
    for attempt in range(1, retries + 1):
        try:
            print(
                f"Fetching NBA games for {season} "
                f"(attempt {attempt}/{retries}, timeout={timeout}s)."
            )
            finder = LeagueGameLog(
                season=season,
                league_id="00",
                player_or_team_abbreviation="T",
                timeout=timeout,
            )
            df = finder.get_data_frames()[0]
            break
        except Exception as error:
            last_error = error
            if attempt == retries:
                print(f"NBA stats API unavailable after {retries} attempts: {error}.")
                print("Falling back to NBA CDN live scoreboard for completed games.")
                return fetch_live_scoreboard_dataframe(season=season, timeout=timeout)
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


def empty_games_dataframe():
    return pd.DataFrame(columns=GAME_COLUMNS)


def season_id_for_game(season, game_id):
    # The NBA encodes season type in the first digit of game_id. Keeping this format
    # lets live CDN rows align with the stats.nba.com rows already in Postgres.
    season_year = season.split("-", 1)[0]
    season_type_prefix = str(game_id)[0] if str(game_id) else "2"
    return f"{season_type_prefix}{season_year}"


def team_full_name(team):
    return f"{team['teamCity']} {team['teamName']}"


def build_live_team_row(game, team_key, opponent_key, season):
    # Convert the NBA live boxscore JSON into the same normalized column contract
    # used by LeagueGameLog so the downstream insert path is source-agnostic.
    team = game[team_key]
    opponent = game[opponent_key]
    stats = team["statistics"]
    team_score = int(team["score"])
    opponent_score = int(opponent["score"])
    team_code = team["teamTricode"]
    opponent_code = opponent["teamTricode"]
    is_home = team_key == "homeTeam"

    return {
        "GAME_ID": game["gameId"],
        "GAME_DATE": pd.to_datetime(game["gameEt"].split("T", 1)[0]),
        "SEASON_ID": season_id_for_game(season, game["gameId"]),
        "TEAM_ID": int(team["teamId"]),
        "TEAM_NAME": team_full_name(team),
        "MATCHUP": (
            f"{team_code} vs. {opponent_code}"
            if is_home
            else f"{team_code} @ {opponent_code}"
        ),
        "WL": "W" if team_score > opponent_score else "L",
        "PTS": stats["points"],
        "REB": stats["reboundsTotal"],
        "AST": stats["assists"],
        "FG_PCT": stats["fieldGoalsPercentage"],
        "FG3_PCT": stats["threePointersPercentage"],
        "FT_PCT": stats["freeThrowsPercentage"],
        "OPPONENT": opponent_code,
    }


def fetch_live_scoreboard_dataframe(season="2025-26", timeout=NBA_API_TIMEOUT):
    # CDN fallback intentionally ingests only completed games. In-progress games
    # would create unstable rows because scores and team stats keep changing.
    scoreboard_url = "https://cdn.nba.com/static/json/liveData/scoreboard/todaysScoreboard_00.json"
    response = requests.get(scoreboard_url, timeout=timeout)
    response.raise_for_status()
    games = response.json().get("scoreboard", {}).get("games", [])

    rows = []
    for game_summary in games:
        if game_summary.get("gameStatus") != 3:
            continue

        game_id = game_summary["gameId"]
        boxscore_url = f"https://cdn.nba.com/static/json/liveData/boxscore/boxscore_{game_id}.json"
        boxscore_response = requests.get(boxscore_url, timeout=timeout)
        boxscore_response.raise_for_status()
        game = boxscore_response.json()["game"]

        rows.append(build_live_team_row(game, "homeTeam", "awayTeam", season))
        rows.append(build_live_team_row(game, "awayTeam", "homeTeam", season))

    if not rows:
        print("NBA CDN fallback found no completed games to ingest.")
        return empty_games_dataframe()

    print(f"NBA CDN fallback found {len(rows)} completed team-game rows.")
    return pd.DataFrame(rows, columns=GAME_COLUMNS)

def get_latest_ingested_game_date(db, season_ids):
    return (
        db.query(func.max(Game.game_date))
        .filter(Game.season.in_(season_ids))
        .scalar()
    )

def build_game_records(df):
    # Translate pandas rows into SQLAlchemy dictionaries. This is the final data
    # contract for the games table regardless of upstream source.
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
    # Pipeline metadata is committed in the same database as the data, making
    # /pipeline/runs and the dashboard useful for operational debugging.
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

def ingest_games(season="2024-25", full_refresh=False, source="stats"):
    db = SessionLocal()
    mode = "full_refresh" if full_refresh else "incremental"

    try:
        Base.metadata.create_all(bind=engine)
        # Scheduled production loads use source="live" because the NBA CDN has
        # been more reliable from Render/GitHub than stats.nba.com.
        if source == "live":
            df = fetch_live_scoreboard_dataframe(season=season).sort_values(
                ["GAME_DATE", "GAME_ID", "TEAM_ID"]
            )
        else:
            df = fetch_games_dataframe(season=season).sort_values(
                ["GAME_DATE", "GAME_ID", "TEAM_ID"]
            )
        season_ids = df["SEASON_ID"].astype(str).unique().tolist()
        latest_game_date = (
            None
            if full_refresh or not season_ids
            else get_latest_ingested_game_date(db, season_ids)
        )

        # Incremental loads only process games newer than the latest date already
        # present for that season, keeping daily runs fast and resume-friendly.
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
        # The unique game/team index turns ingestion into an idempotent upsert:
        # reruns skip existing rows instead of creating duplicates.
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
