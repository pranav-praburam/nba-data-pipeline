from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import requests

from app.api.constants import NBA_TEAMS
from app.config import ODDS_API_KEY

THE_ODDS_API_URL = "https://api.the-odds-api.com/v4/sports/basketball_nba/odds"
ODDS_API_SOURCE = "the-odds-api"

# Keep exact external-name mappings in one place so the eventual picks and
# settlement jobs do not duplicate string cleanup in multiple modules.
ODDS_API_TEAM_NAME_MAP = {
    "Atlanta Hawks": "Atlanta Hawks",
    "Boston Celtics": "Boston Celtics",
    "Brooklyn Nets": "Brooklyn Nets",
    "Charlotte Hornets": "Charlotte Hornets",
    "Chicago Bulls": "Chicago Bulls",
    "Cleveland Cavaliers": "Cleveland Cavaliers",
    "Dallas Mavericks": "Dallas Mavericks",
    "Denver Nuggets": "Denver Nuggets",
    "Detroit Pistons": "Detroit Pistons",
    "Golden State Warriors": "Golden State Warriors",
    "Houston Rockets": "Houston Rockets",
    "Indiana Pacers": "Indiana Pacers",
    "LA Clippers": "LA Clippers",
    "Los Angeles Clippers": "LA Clippers",
    "Los Angeles Lakers": "Los Angeles Lakers",
    "Memphis Grizzlies": "Memphis Grizzlies",
    "Miami Heat": "Miami Heat",
    "Milwaukee Bucks": "Milwaukee Bucks",
    "Minnesota Timberwolves": "Minnesota Timberwolves",
    "New Orleans Pelicans": "New Orleans Pelicans",
    "New York Knicks": "New York Knicks",
    "Oklahoma City Thunder": "Oklahoma City Thunder",
    "Orlando Magic": "Orlando Magic",
    "Philadelphia 76ers": "Philadelphia 76ers",
    "Philadelphia Sixers": "Philadelphia 76ers",
    "Phoenix Suns": "Phoenix Suns",
    "Portland Trail Blazers": "Portland Trail Blazers",
    "Sacramento Kings": "Sacramento Kings",
    "San Antonio Spurs": "San Antonio Spurs",
    "Toronto Raptors": "Toronto Raptors",
    "Utah Jazz": "Utah Jazz",
    "Washington Wizards": "Washington Wizards",
}


@dataclass
class NormalizedOddsEvent:
    game_id: str
    commence_time: str
    home_team: str
    away_team: str
    bookmaker: str
    odds_source: str
    home_moneyline: int
    away_moneyline: int
    implied_home_win_prob: float
    implied_away_win_prob: float


def moneyline_to_prob(moneyline: int | float | str) -> float:
    line = int(moneyline)
    if line == 0:
        raise ValueError("Moneyline cannot be zero.")
    if line > 0:
        return 100 / (line + 100)
    return abs(line) / (abs(line) + 100)


def remove_vig(home_prob: float, away_prob: float) -> tuple[float, float]:
    total = home_prob + away_prob
    if total <= 0:
        raise ValueError("Implied probabilities must sum to more than zero.")
    return home_prob / total, away_prob / total


def normalize_odds_team_name(team_name: str) -> str:
    normalized = ODDS_API_TEAM_NAME_MAP.get(team_name.strip())
    if not normalized:
        raise KeyError(f"Unmapped odds API team name: {team_name}")
    return normalized


def fetch_odds(
    api_key: str | None = None,
    *,
    regions: str = "us",
    markets: str = "h2h",
    odds_format: str = "american",
    date_format: str = "iso",
    timeout: int = 30,
) -> list[dict[str, Any]]:
    effective_api_key = api_key or ODDS_API_KEY
    if not effective_api_key:
        raise ValueError("ODDS_API_KEY is not configured.")

    response = requests.get(
        THE_ODDS_API_URL,
        params={
            "apiKey": effective_api_key,
            "regions": regions,
            "markets": markets,
            "oddsFormat": odds_format,
            "dateFormat": date_format,
        },
        timeout=timeout,
    )
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, list):
        raise ValueError("Unexpected odds API response shape.")
    return payload


def parse_moneyline_events(events: list[dict[str, Any]]) -> list[NormalizedOddsEvent]:
    normalized_events = []

    for event in events:
        home_team = normalize_odds_team_name(event["home_team"])
        away_team = normalize_odds_team_name(event["away_team"])

        bookmakers = event.get("bookmakers") or []
        if not bookmakers:
            continue

        bookmaker = bookmakers[0]
        markets = bookmaker.get("markets") or []
        moneyline_market = next(
            (market for market in markets if market.get("key") == "h2h"),
            None,
        )
        if not moneyline_market:
            continue

        outcome_map = {
            normalize_odds_team_name(outcome["name"]): outcome
            for outcome in moneyline_market.get("outcomes", [])
        }
        if home_team not in outcome_map or away_team not in outcome_map:
            missing = sorted({home_team, away_team} - set(outcome_map))
            raise KeyError(
                f"Missing moneyline outcome(s) for {event.get('id')}: {', '.join(missing)}"
            )

        home_moneyline = int(outcome_map[home_team]["price"])
        away_moneyline = int(outcome_map[away_team]["price"])
        implied_home = moneyline_to_prob(home_moneyline)
        implied_away = moneyline_to_prob(away_moneyline)
        adjusted_home, adjusted_away = remove_vig(implied_home, implied_away)

        normalized_events.append(
            NormalizedOddsEvent(
                game_id=event["id"],
                commence_time=event["commence_time"],
                home_team=home_team,
                away_team=away_team,
                bookmaker=bookmaker.get("key", "unknown"),
                odds_source=ODDS_API_SOURCE,
                home_moneyline=home_moneyline,
                away_moneyline=away_moneyline,
                implied_home_win_prob=adjusted_home,
                implied_away_win_prob=adjusted_away,
            )
        )

    return normalized_events


def validate_team_name_map() -> None:
    mapped_teams = set(ODDS_API_TEAM_NAME_MAP.values())
    missing = sorted(set(NBA_TEAMS) - mapped_teams)
    if missing:
        raise ValueError(f"Odds API team-name map is missing NBA teams: {missing}")
