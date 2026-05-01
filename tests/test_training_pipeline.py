import pandas as pd

from scripts.train_win_model import FEATURE_COLUMNS, build_training_dataset


def paired_game(game_id, game_date, home_team, away_team, home_points, away_points):
    return [
        {
            "game_id": game_id,
            "game_date": game_date,
            "season": "22025",
            "team_id": abs(hash((game_id, home_team))) % 1000000,
            "team": home_team,
            "opponent": away_team,
            "matchup": f"{home_team} vs. {away_team}",
            "is_home": True,
            "wl": "W" if home_points > away_points else "L",
            "points": home_points,
            "rebounds": 40,
            "assists": 22,
            "fg_pct": 0.50,
            "fg3_pct": 0.40,
            "ft_pct": 0.80,
        },
        {
            "game_id": game_id,
            "game_date": game_date,
            "season": "22025",
            "team_id": abs(hash((game_id, away_team))) % 1000000,
            "team": away_team,
            "opponent": home_team,
            "matchup": f"{away_team} @ {home_team}",
            "is_home": False,
            "wl": "W" if away_points > home_points else "L",
            "points": away_points,
            "rebounds": 38,
            "assists": 19,
            "fg_pct": 0.45,
            "fg3_pct": 0.35,
            "ft_pct": 0.78,
        },
    ]


def test_v2_feature_columns_expand_windows_splits_and_schedule_context():
    assert len(FEATURE_COLUMNS) == 125
    assert "home_avg_points_l5" in FEATURE_COLUMNS
    assert "away_avg_points_l20" in FEATURE_COLUMNS
    assert "home_split_avg_fg3_pct_l10" in FEATURE_COLUMNS
    assert "rest_days_diff" in FEATURE_COLUMNS
    assert "away_b2b" in FEATURE_COLUMNS


def test_build_training_dataset_uses_prior_games_only_for_v2_features():
    rows = []
    rows.extend(paired_game("001", "2026-01-01", "Home Team", "Opp 1", 100, 90))
    rows.extend(paired_game("002", "2026-01-02", "Home Team", "Opp 2", 110, 92))
    rows.extend(paired_game("003", "2026-01-03", "Home Team", "Opp 3", 120, 95))
    rows.extend(paired_game("004", "2026-01-04", "Home Team", "Opp 4", 130, 97))
    rows.extend(paired_game("005", "2026-01-05", "Opp 5", "Away Team", 101, 90))
    rows.extend(paired_game("006", "2026-01-06", "Opp 6", "Away Team", 103, 95))
    rows.extend(paired_game("007", "2026-01-07", "Opp 7", "Away Team", 104, 105))
    rows.extend(paired_game("008", "2026-01-08", "Opp 8", "Away Team", 106, 110))
    rows.extend(paired_game("009", "2026-01-09", "Home Team", "Away Team", 999, 50))

    dataset = build_training_dataset(pd.DataFrame(rows))

    assert len(dataset) == 1
    final_row = dataset.iloc[0]

    # The last matchup should only use pregame history, not the final game's
    # own 999-point outlier, which would indicate leakage.
    assert final_row["home_avg_points_l5"] == 115
    assert final_row["home_split_avg_points_l5"] == 115
    assert final_row["away_avg_points_l5"] == 100
    assert final_row["away_split_avg_points_l5"] == 100

    assert final_row["home_rest_days"] == 5
    assert final_row["away_rest_days"] == 1
    assert final_row["rest_days_diff"] == 4
    assert final_row["home_b2b"] == 0
    assert final_row["away_b2b"] == 1
