from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.db.database import get_db
from app.db.models import Game

router = APIRouter()

@router.get("/")
def home():
    return {"message": "NBA Data Pipeline is running"}

@router.get("/health")
def health():
    return {"status": "ok"}

@router.get("/games")
def get_games(limit: int = 20, db: Session = Depends(get_db)):
    games = (
        db.query(Game)
        .order_by(Game.game_date.desc(), Game.game_id.desc(), Game.team_id.asc())
        .limit(limit)
        .all()
    )

    return [
        {
            "game_id": g.game_id,
            "game_date": g.game_date,
            "team": g.team,
            "opponent": g.opponent,
            "matchup": g.matchup,
            "wl": g.wl,
            "points": g.points,
            "rebounds": g.rebounds,
            "assists": g.assists,
            "fg_pct": g.fg_pct,
            "fg3_pct": g.fg3_pct,
            "ft_pct": g.ft_pct,
        }
        for g in games
    ]

@router.get("/teams/{team_name}/summary")
def team_summary(team_name: str, db: Session = Depends(get_db)):
    result = db.query(
        Game.team,
        func.count(Game.id).label("games_played"),
        func.avg(Game.points).label("avg_points"),
        func.avg(Game.rebounds).label("avg_rebounds"),
        func.avg(Game.assists).label("avg_assists"),
        func.avg(Game.fg_pct).label("avg_fg_pct")
    ).filter(Game.team == team_name).group_by(Game.team).first()

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

@router.get("/leaders/points")
def scoring_leaders(db: Session = Depends(get_db)):
    results = db.query(
        Game.team,
        func.avg(Game.points).label("avg_points")
    ).group_by(Game.team).order_by(func.avg(Game.points).desc()).limit(10).all()

    return [
        {
            "team": r.team,
            "avg_points": round(float(r.avg_points), 2)
        }
        for r in results
    ]
