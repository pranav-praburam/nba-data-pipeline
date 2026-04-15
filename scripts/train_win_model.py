import argparse
import json
import sys
import warnings
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, log_loss, roc_auc_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app.api.constants import NBA_TEAMS
from app.db.database import SessionLocal
from app.db.models import Game

warnings.filterwarnings("ignore", category=RuntimeWarning, module=r"sklearn\..*")


FEATURE_COLUMNS = [
    "home_win_rate_l10",
    "home_avg_points_l10",
    "home_avg_rebounds_l10",
    "home_avg_assists_l10",
    "home_avg_fg_pct_l10",
    "home_avg_fg3_pct_l10",
    "away_win_rate_l10",
    "away_avg_points_l10",
    "away_avg_rebounds_l10",
    "away_avg_assists_l10",
    "away_avg_fg_pct_l10",
    "away_avg_fg3_pct_l10",
    "diff_win_rate_l10",
    "diff_avg_points_l10",
    "diff_avg_rebounds_l10",
    "diff_avg_assists_l10",
    "diff_avg_fg_pct_l10",
    "diff_avg_fg3_pct_l10",
]


def load_games_dataframe():
    db = SessionLocal()
    try:
        rows = (
            db.query(Game)
            .filter(Game.team.in_(NBA_TEAMS))
            .filter(Game.wl.in_(["W", "L"]))
            .order_by(Game.game_date.asc(), Game.game_id.asc(), Game.team_id.asc())
            .all()
        )
    finally:
        db.close()

    return pd.DataFrame(
        [
            {
                "game_id": row.game_id,
                "game_date": row.game_date,
                "season": row.season,
                "team_id": row.team_id,
                "team": row.team,
                "opponent": row.opponent,
                "matchup": row.matchup,
                "wl": row.wl,
                "points": row.points,
                "rebounds": row.rebounds,
                "assists": row.assists,
                "fg_pct": row.fg_pct,
                "fg3_pct": row.fg3_pct,
                "ft_pct": row.ft_pct,
            }
            for row in rows
        ]
    )


def add_rolling_features(df, window):
    df = df.sort_values(["team", "game_date", "game_id"]).copy()
    df["win"] = (df["wl"] == "W").astype(int)

    rolling_inputs = {
        "win": "win_rate_l10",
        "points": "avg_points_l10",
        "rebounds": "avg_rebounds_l10",
        "assists": "avg_assists_l10",
        "fg_pct": "avg_fg_pct_l10",
        "fg3_pct": "avg_fg3_pct_l10",
    }

    for source_column, feature_column in rolling_inputs.items():
        df[feature_column] = (
            df.groupby("team")[source_column]
            .transform(lambda values: values.shift(1).rolling(window, min_periods=3).mean())
        )

    return df


def build_training_dataset(games_df, window):
    if games_df.empty:
        return pd.DataFrame()

    featured = add_rolling_features(games_df, window=window)
    completed_games = []

    for _, group in featured.groupby("game_id"):
        if len(group) != 2:
            continue

        home_rows = group[group["matchup"].str.contains(" vs. ", regex=False)]
        away_rows = group[group["matchup"].str.contains(" @ ", regex=False)]
        if len(home_rows) != 1 or len(away_rows) != 1:
            continue

        home = home_rows.iloc[0]
        away = away_rows.iloc[0]

        row = {
            "game_id": home["game_id"],
            "game_date": home["game_date"],
            "season": home["season"],
            "home_team": home["team"],
            "away_team": away["team"],
            "home_win": int(home["wl"] == "W"),
        }

        base_features = [
            "win_rate_l10",
            "avg_points_l10",
            "avg_rebounds_l10",
            "avg_assists_l10",
            "avg_fg_pct_l10",
            "avg_fg3_pct_l10",
        ]
        for feature in base_features:
            row[f"home_{feature}"] = home[feature]
            row[f"away_{feature}"] = away[feature]
            row[f"diff_{feature}"] = home[feature] - away[feature]

        completed_games.append(row)

    dataset = pd.DataFrame(completed_games)
    if dataset.empty:
        return dataset

    dataset = dataset.dropna(subset=FEATURE_COLUMNS + ["home_win"])
    dataset[FEATURE_COLUMNS] = dataset[FEATURE_COLUMNS].replace([np.inf, -np.inf], np.nan)
    dataset = dataset.dropna(subset=FEATURE_COLUMNS)
    return dataset.sort_values(["game_date", "game_id"]).reset_index(drop=True)


def train_model(dataset, test_size):
    split_index = int(len(dataset) * (1 - test_size))
    train_df = dataset.iloc[:split_index].copy()
    test_df = dataset.iloc[split_index:].copy()

    model = Pipeline(
        steps=[
            ("scaler", StandardScaler()),
            ("classifier", LogisticRegression(max_iter=1000, random_state=42, solver="liblinear")),
        ]
    )
    model.fit(train_df[FEATURE_COLUMNS], train_df["home_win"])

    test_probabilities = model.predict_proba(test_df[FEATURE_COLUMNS])[:, 1]
    test_predictions = (test_probabilities >= 0.5).astype(int)

    metrics = {
        "accuracy": round(float(accuracy_score(test_df["home_win"], test_predictions)), 4),
        "roc_auc": round(float(roc_auc_score(test_df["home_win"], test_probabilities)), 4),
        "log_loss": round(float(log_loss(test_df["home_win"], test_probabilities)), 4),
    }
    return model, train_df, test_df, metrics


def save_artifacts(model, metrics, dataset, train_df, test_df, output_dir, window):
    output_dir.mkdir(parents=True, exist_ok=True)
    model_path = output_dir / "win_probability_model.joblib"
    metrics_path = output_dir / "win_probability_metrics.json"
    sample_path = output_dir / "training_sample.csv"

    joblib.dump(
        {
            "model": model,
            "feature_columns": FEATURE_COLUMNS,
            "model_type": "logistic_regression",
            "rolling_window_games": window,
            "trained_at": datetime.now(timezone.utc).isoformat(),
        },
        model_path,
    )

    metadata = {
        **metrics,
        "model_type": "logistic_regression",
        "target": "home_team_win",
        "rolling_window_games": window,
        "feature_columns": FEATURE_COLUMNS,
        "rows_total": len(dataset),
        "rows_train": len(train_df),
        "rows_test": len(test_df),
        "date_range": {
            "start": str(dataset["game_date"].min()),
            "end": str(dataset["game_date"].max()),
        },
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "artifact": str(model_path),
    }

    metrics_path.write_text(json.dumps(metadata, indent=2) + "\n")
    dataset.tail(50).to_csv(sample_path, index=False)
    return model_path, metrics_path, sample_path, metadata


def main():
    parser = argparse.ArgumentParser(description="Train a baseline NBA win probability model.")
    parser.add_argument("--output-dir", default="models", help="Directory for model artifacts.")
    parser.add_argument("--rolling-window", type=int, default=10, help="Past games per team for rolling features.")
    parser.add_argument("--test-size", type=float, default=0.2, help="Chronological holdout share.")
    args = parser.parse_args()

    games_df = load_games_dataframe()
    dataset = build_training_dataset(games_df, window=args.rolling_window)

    if len(dataset) < 100:
        raise ValueError(f"Not enough training rows. Found {len(dataset)} rows.")

    model, train_df, test_df, metrics = train_model(dataset, test_size=args.test_size)
    _, metrics_path, _, metadata = save_artifacts(
        model=model,
        metrics=metrics,
        dataset=dataset,
        train_df=train_df,
        test_df=test_df,
        output_dir=Path(args.output_dir),
        window=args.rolling_window,
    )

    print(json.dumps(metadata, indent=2))
    print(f"Saved metrics to {metrics_path}")


if __name__ == "__main__":
    main()
