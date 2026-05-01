import pytest

from app.services.odds import (
    NormalizedOddsEvent,
    moneyline_to_prob,
    normalize_odds_team_name,
    parse_moneyline_events,
    remove_vig,
    validate_team_name_map,
)


def test_moneyline_to_prob_handles_positive_and_negative_lines():
    assert moneyline_to_prob(150) == pytest.approx(0.4)
    assert moneyline_to_prob(-150) == pytest.approx(0.6)


def test_remove_vig_normalizes_two_way_market():
    home, away = remove_vig(0.60, 0.50)

    assert home == pytest.approx(0.5454545)
    assert away == pytest.approx(0.4545454)
    assert home + away == pytest.approx(1.0)


def test_normalize_odds_team_name_maps_known_external_variants():
    assert normalize_odds_team_name("Los Angeles Clippers") == "LA Clippers"
    assert normalize_odds_team_name("Philadelphia Sixers") == "Philadelphia 76ers"


def test_validate_team_name_map_covers_all_official_nba_teams():
    validate_team_name_map()


def test_parse_moneyline_events_returns_normalized_matchups():
    events = [
        {
            "id": "evt_1",
            "commence_time": "2026-05-01T00:00:00Z",
            "home_team": "Los Angeles Clippers",
            "away_team": "Philadelphia Sixers",
            "bookmakers": [
                {
                    "key": "draftkings",
                    "markets": [
                        {
                            "key": "h2h",
                            "outcomes": [
                                {"name": "Los Angeles Clippers", "price": -140},
                                {"name": "Philadelphia Sixers", "price": 120},
                            ],
                        }
                    ],
                }
            ],
        }
    ]

    parsed = parse_moneyline_events(events)

    assert len(parsed) == 1
    event = parsed[0]
    assert isinstance(event, NormalizedOddsEvent)
    assert event.home_team == "LA Clippers"
    assert event.away_team == "Philadelphia 76ers"
    assert event.bookmaker == "draftkings"
    assert event.implied_home_win_prob + event.implied_away_win_prob == pytest.approx(1.0)


def test_parse_moneyline_events_raises_on_unmapped_team_names():
    events = [
        {
            "id": "evt_2",
            "commence_time": "2026-05-01T00:00:00Z",
            "home_team": "Seattle Supersonics",
            "away_team": "Chicago Bulls",
            "bookmakers": [],
        }
    ]

    with pytest.raises(KeyError, match="Unmapped odds API team name"):
        parse_moneyline_events(events)
