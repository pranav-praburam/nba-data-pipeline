from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import case, func
from sqlalchemy.orm import Session

from app.api.constants import NBA_TEAMS
from app.api.query_helpers import (
    latest_season_year,
    nba_team_query,
    season_display_name,
    season_query,
)
from app.db.database import get_db
from app.db.models import Game


router = APIRouter()


@router.get("/analytics/team-rankings")
def team_rankings(
    metric: str = Query(default="points", pattern="^(points|rebounds|assists|fg_pct|fg3_pct)$"),
    limit: int = Query(default=10, ge=1, le=30),
    season: Optional[str] = None,
    db: Session = Depends(get_db),
):
    metric_columns = {
        "points": Game.points,
        "rebounds": Game.rebounds,
        "assists": Game.assists,
        "fg_pct": Game.fg_pct,
        "fg3_pct": Game.fg3_pct,
    }
    metric_column = metric_columns[metric]
    avg_metric = func.avg(metric_column).label("average")

    query = db.query(
        Game.team,
        func.count(Game.id).label("games_played"),
        avg_metric,
        func.sum(case((Game.wl == "W", 1), else_=0)).label("wins"),
    )

    results = (
        season_query(nba_team_query(query), season)
        .group_by(Game.team)
        .order_by(avg_metric.desc())
        .limit(limit)
        .all()
    )

    return [
        {
            "rank": index + 1,
            "team": row.team,
            "metric": metric,
            "average": round(float(row.average), 3) if row.average is not None else None,
            "games_played": row.games_played,
            "wins": int(row.wins or 0),
        }
        for index, row in enumerate(results)
    ]


@router.get("/data-quality/summary")
def data_quality_summary(db: Session = Depends(get_db)):
    total_rows = db.query(func.count(Game.id)).scalar()
    unique_games = db.query(func.count(func.distinct(Game.game_id))).scalar()
    unique_teams = db.query(func.count(func.distinct(Game.team))).scalar()
    official_nba_rows = nba_team_query(db.query(func.count(Game.id))).scalar()
    official_nba_teams = nba_team_query(db.query(func.count(func.distinct(Game.team)))).scalar()
    non_nba_teams = [
        row.team
        for row in db.query(Game.team)
        .filter(~Game.team.in_(NBA_TEAMS))
        .group_by(Game.team)
        .order_by(Game.team)
        .all()
    ]
    min_date, max_date = db.query(
        func.min(Game.game_date),
        func.max(Game.game_date),
    ).one()
    duplicate_rows = (
        db.query(
            Game.game_id,
            Game.team_id,
            func.count(Game.id).label("row_count"),
        )
        .group_by(Game.game_id, Game.team_id)
        .having(func.count(Game.id) > 1)
        .count()
    )
    null_stat_rows = (
        db.query(func.count(Game.id))
        .filter(
            (Game.points.is_(None))
            | (Game.rebounds.is_(None))
            | (Game.assists.is_(None))
        )
        .scalar()
    )
    status = "fail" if duplicate_rows else "warning" if non_nba_teams else "pass"

    return {
        "total_team_game_rows": total_rows,
        "unique_games": unique_games,
        "unique_teams": unique_teams,
        "official_nba_team_rows": official_nba_rows,
        "official_nba_teams": official_nba_teams,
        "non_nba_or_event_teams": non_nba_teams,
        "date_range": {
            "start": min_date,
            "end": max_date,
        },
        "latest_season": season_display_name(latest_season_year(db)),
        "duplicate_game_team_rows": duplicate_rows,
        "rows_missing_core_stats": null_stat_rows,
        "status": status,
    }
