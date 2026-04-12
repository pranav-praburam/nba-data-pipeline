from sqlalchemy.orm import Session

from app.db.models import Game


def recent_team_profile(db: Session, team_name: str, last_n: int):
    games = (
        db.query(Game)
        .filter(Game.team == team_name)
        .order_by(Game.game_date.desc(), Game.game_id.desc())
        .limit(last_n)
        .all()
    )

    if not games:
        return None

    wins = sum(1 for game in games if game.wl == "W")
    avg_points = sum(game.points for game in games) / len(games)
    avg_rebounds = sum((game.rebounds or 0) for game in games) / len(games)
    avg_assists = sum((game.assists or 0) for game in games) / len(games)
    avg_fg_pct = sum((game.fg_pct or 0) for game in games) / len(games)
    avg_fg3_pct = sum((game.fg3_pct or 0) for game in games) / len(games)

    score = (
        (wins / len(games)) * 45
        + avg_points * 0.35
        + avg_rebounds * 0.08
        + avg_assists * 0.15
        + avg_fg_pct * 18
        + avg_fg3_pct * 12
    )

    return {
        "team": team_name,
        "games_used": len(games),
        "wins": wins,
        "losses": len(games) - wins,
        "win_rate": round(wins / len(games), 3),
        "avg_points": round(avg_points, 2),
        "avg_rebounds": round(avg_rebounds, 2),
        "avg_assists": round(avg_assists, 2),
        "avg_fg_pct": round(avg_fg_pct, 3),
        "avg_fg3_pct": round(avg_fg3_pct, 3),
        "form_score": round(score, 3),
    }
