import ingest_games


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


def test_live_scoreboard_fallback_builds_completed_team_game_rows(monkeypatch):
    scoreboard_payload = {
        "scoreboard": {
            "games": [
                {"gameId": "0022500001", "gameStatus": 3},
                {"gameId": "0022500002", "gameStatus": 2},
            ]
        }
    }
    boxscore_payload = {
        "game": {
            "gameId": "0022500001",
            "gameEt": "2026-04-14T19:30:00-04:00",
            "homeTeam": {
                "teamId": 1610612754,
                "teamCity": "Indiana",
                "teamName": "Pacers",
                "teamTricode": "IND",
                "score": 120,
                "statistics": {
                    "points": 120,
                    "reboundsTotal": 44,
                    "assists": 31,
                    "fieldGoalsPercentage": 0.51,
                    "threePointersPercentage": 0.39,
                    "freeThrowsPercentage": 0.82,
                },
            },
            "awayTeam": {
                "teamId": 1610612760,
                "teamCity": "Oklahoma City",
                "teamName": "Thunder",
                "teamTricode": "OKC",
                "score": 114,
                "statistics": {
                    "points": 114,
                    "reboundsTotal": 40,
                    "assists": 25,
                    "fieldGoalsPercentage": 0.47,
                    "threePointersPercentage": 0.35,
                    "freeThrowsPercentage": 0.76,
                },
            },
        }
    }

    def fake_get(url, timeout):
        if "todaysScoreboard" in url:
            return FakeResponse(scoreboard_payload)
        return FakeResponse(boxscore_payload)

    monkeypatch.setattr(ingest_games.requests, "get", fake_get)

    df = ingest_games.fetch_live_scoreboard_dataframe(season="2025-26")

    assert len(df) == 2
    assert df.iloc[0]["TEAM_NAME"] == "Indiana Pacers"
    assert df.iloc[0]["MATCHUP"] == "IND vs. OKC"
    assert df.iloc[0]["WL"] == "W"
    assert df.iloc[1]["TEAM_NAME"] == "Oklahoma City Thunder"
    assert df.iloc[1]["MATCHUP"] == "OKC @ IND"
    assert df.iloc[1]["WL"] == "L"
