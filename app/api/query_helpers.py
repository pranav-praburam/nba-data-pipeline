from typing import Optional

from sqlalchemy.orm import Session

from app.api.constants import NBA_TEAMS
from app.db.models import Game


def nba_team_query(query):
    return query.filter(Game.team.in_(NBA_TEAMS))


def normalize_season_year(season: Optional[str]) -> Optional[str]:
    if not season:
        return None
    if "-" in season:
        return season.split("-", 1)[0]
    if len(season) == 5 and season[1:].isdigit():
        return season[1:]
    if len(season) == 4 and season.isdigit():
        return season
    return None


def season_query(query, season: Optional[str]):
    season_year = normalize_season_year(season)
    if season_year:
        return query.filter(Game.season.like(f"%{season_year}"))
    if season:
        return query.filter(Game.season == season)
    return query


def latest_season_year(db: Session) -> Optional[str]:
    season_ids = [row[0] for row in db.query(Game.season).distinct().all()]
    season_years = [
        season_id[1:]
        for season_id in season_ids
        if season_id and len(season_id) == 5 and season_id[1:].isdigit()
    ]
    return max(season_years) if season_years else None


def season_display_name(season_year: Optional[str]) -> str:
    if not season_year:
        return "all seasons"
    return f"{season_year}-{str(int(season_year[-2:]) + 1).zfill(2)}"
