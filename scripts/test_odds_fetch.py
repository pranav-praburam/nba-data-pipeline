import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app.services.odds import fetch_odds, parse_moneyline_events, validate_team_name_map  # noqa: E402


def main():
    validate_team_name_map()
    raw_events = fetch_odds()
    normalized_events = parse_moneyline_events(raw_events)

    print(
        json.dumps(
            {
                "raw_event_count": len(raw_events),
                "normalized_event_count": len(normalized_events),
                "sample_events": [
                    {
                        "game_id": event.game_id,
                        "home_team": event.home_team,
                        "away_team": event.away_team,
                        "home_moneyline": event.home_moneyline,
                        "away_moneyline": event.away_moneyline,
                        "implied_home_win_prob": round(event.implied_home_win_prob, 4),
                        "implied_away_win_prob": round(event.implied_away_win_prob, 4),
                        "bookmaker": event.bookmaker,
                    }
                    for event in normalized_events[:3]
                ],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
