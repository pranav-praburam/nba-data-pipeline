from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.query_helpers import season_query
from app.db.database import get_db
from app.db.models import Game


router = APIRouter()


@router.get("/games")
def get_games(
    limit: int = Query(default=20, ge=1, le=100),
    team: Optional[str] = None,
    season: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    result: Optional[str] = None,
    db: Session = Depends(get_db),
):
    query = db.query(Game)

    if team:
        query = query.filter(Game.team.ilike(f"%{team}%"))

    query = season_query(query, season)

    if start_date:
        if len(start_date) != 10:
            raise HTTPException(status_code=400, detail="start_date must be YYYY-MM-DD")
        query = query.filter(Game.game_date >= start_date)

    if end_date:
        if len(end_date) != 10:
            raise HTTPException(status_code=400, detail="end_date must be YYYY-MM-DD")
        query = query.filter(Game.game_date <= end_date)

    if result:
        if result not in {"W", "L"}:
            raise HTTPException(status_code=400, detail="result must be W or L")
        query = query.filter(Game.wl == result)

    games = (
        query.order_by(Game.game_date.desc(), Game.game_id.desc(), Game.team_id.asc())
        .limit(limit)
        .all()
    )

    return [
        {
            "game_id": game.game_id,
            "game_date": game.game_date,
            "season": game.season,
            "team_id": game.team_id,
            "team": game.team,
            "opponent": game.opponent,
            "matchup": game.matchup,
            "wl": game.wl,
            "points": game.points,
            "rebounds": game.rebounds,
            "assists": game.assists,
            "fg_pct": game.fg_pct,
            "fg3_pct": game.fg3_pct,
            "ft_pct": game.ft_pct,
        }
        for game in games
    ]


@router.get("/teams/{team_name}/summary")
def team_summary(team_name: str, db: Session = Depends(get_db)):
    result = (
        db.query(
            Game.team,
            func.count(Game.id).label("games_played"),
            func.avg(Game.points).label("avg_points"),
            func.avg(Game.rebounds).label("avg_rebounds"),
            func.avg(Game.assists).label("avg_assists"),
            func.avg(Game.fg_pct).label("avg_fg_pct"),
        )
        .filter(Game.team == team_name)
        .group_by(Game.team)
        .first()
    )

    if not result:
        return {"error": "Team not found"}

    return {
        "team": result.team,
        "games_played": result.games_played,
        "avg_points": round(float(result.avg_points), 2) if result.avg_points is not None else None,
        "avg_rebounds": round(float(result.avg_rebounds), 2) if result.avg_rebounds is not None else None,
        "avg_assists": round(float(result.avg_assists), 2) if result.avg_assists is not None else None,
        "avg_fg_pct": round(float(result.avg_fg_pct), 3) if result.avg_fg_pct is not None else None,
    }


@router.get("/teams/{team_name}/trends")
def team_trends(
    team_name: str,
    last_n: int = Query(default=10, ge=1, le=25),
    db: Session = Depends(get_db),
):
    recent_games = (
        db.query(Game)
        .filter(Game.team == team_name)
        .order_by(Game.game_date.desc(), Game.game_id.desc())
        .limit(last_n)
        .all()
    )

    if not recent_games:
        return {"error": "Team not found"}

    wins = sum(1 for game in recent_games if game.wl == "W")
    losses = sum(1 for game in recent_games if game.wl == "L")
    avg_points = sum(game.points for game in recent_games) / len(recent_games)
    avg_rebounds = sum((game.rebounds or 0) for game in recent_games) / len(recent_games)
    avg_assists = sum((game.assists or 0) for game in recent_games) / len(recent_games)
    fg_pct_values = [game.fg_pct for game in recent_games if game.fg_pct is not None]
    fg3_pct_values = [game.fg3_pct for game in recent_games if game.fg3_pct is not None]

    return {
        "team": team_name,
        "sample_size": len(recent_games),
        "record": f"{wins}-{losses}",
        "wins": wins,
        "losses": losses,
        "avg_points": round(avg_points, 2),
        "avg_rebounds": round(avg_rebounds, 2),
        "avg_assists": round(avg_assists, 2),
        "avg_fg_pct": round(sum(fg_pct_values) / len(fg_pct_values), 3) if fg_pct_values else None,
        "avg_fg3_pct": round(sum(fg3_pct_values) / len(fg3_pct_values), 3) if fg3_pct_values else None,
        "recent_games": [
            {
                "game_date": game.game_date,
                "opponent": game.opponent,
                "matchup": game.matchup,
                "wl": game.wl,
                "points": game.points,
                "rebounds": game.rebounds,
                "assists": game.assists,
            }
            for game in recent_games
        ],
    }


@router.get("/leaders/points")
def scoring_leaders(db: Session = Depends(get_db)):
    results = (
        db.query(Game.team, func.avg(Game.points).label("avg_points"))
        .group_by(Game.team)
        .order_by(func.avg(Game.points).desc())
        .limit(10)
        .all()
    )

    return [
        {
            "team": row.team,
            "avg_points": round(float(row.avg_points), 2),
        }
        for row in results
    ]
