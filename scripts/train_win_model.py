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
from sklearn.metrics import (
    accuracy_score,
    brier_score_loss,
    f1_score,
    log_loss,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import GridSearchCV, TimeSeriesSplit
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
    # Train only on official NBA teams and completed win/loss rows; this filters
    # out All-Star/exhibition noise that can appear in NBA source data.
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
    # Shift before rolling so a game's own result never leaks into the features
    # used to predict that same game.
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
    # Reconstruct each matchup as one row with home-team target and both teams'
    # pre-game rolling form. Games with incomplete pairs are skipped.
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


def evaluate_model(test_df, probabilities):
    predictions = (probabilities >= 0.5).astype(int)
    confident_mask = (probabilities >= 0.6) | (probabilities <= 0.4)
    confident_accuracy = None
    confident_coverage = 0.0
    if confident_mask.any():
        confident_accuracy = accuracy_score(
            test_df["home_win"][confident_mask],
            predictions[confident_mask],
        )
        confident_coverage = confident_mask.mean()

    home_baseline = np.ones(len(test_df), dtype=int)
    majority_baseline = np.full(
        len(test_df),
        int(test_df["home_win"].mean() >= 0.5),
        dtype=int,
    )

    return {
        "accuracy": round(float(accuracy_score(test_df["home_win"], predictions)), 4),
        "precision": round(float(precision_score(test_df["home_win"], predictions, zero_division=0)), 4),
        "recall": round(float(recall_score(test_df["home_win"], predictions, zero_division=0)), 4),
        "f1": round(float(f1_score(test_df["home_win"], predictions, zero_division=0)), 4),
        "roc_auc": round(float(roc_auc_score(test_df["home_win"], probabilities)), 4),
        "log_loss": round(float(log_loss(test_df["home_win"], probabilities)), 4),
        "brier_score": round(float(brier_score_loss(test_df["home_win"], probabilities)), 4),
        "high_confidence_accuracy": (
            round(float(confident_accuracy), 4)
            if confident_accuracy is not None
            else None
        ),
        "high_confidence_coverage": round(float(confident_coverage), 4),
        "home_team_baseline_accuracy": round(float(accuracy_score(test_df["home_win"], home_baseline)), 4),
        "majority_class_baseline_accuracy": round(float(accuracy_score(test_df["home_win"], majority_baseline)), 4),
    }


def train_model(dataset, test_size):
    # Chronological holdout is more realistic than random splitting for sports
    # data because future games should not influence past predictions.
    split_index = int(len(dataset) * (1 - test_size))
    train_df = dataset.iloc[:split_index].copy()
    test_df = dataset.iloc[split_index:].copy()

    model = Pipeline(
        steps=[
            ("scaler", StandardScaler()),
            ("classifier", LogisticRegression(max_iter=1000, random_state=42, solver="liblinear")),
        ]
    )
    search = GridSearchCV(
        estimator=model,
        param_grid={
            "classifier__C": [0.01, 0.05, 0.1, 0.5, 1.0, 2.0, 5.0],
            "classifier__class_weight": [None, "balanced"],
        },
        cv=TimeSeriesSplit(n_splits=5),
        scoring="roc_auc",
    )
    search.fit(train_df[FEATURE_COLUMNS], train_df["home_win"])
    tuned_model = search.best_estimator_

    test_probabilities = tuned_model.predict_proba(test_df[FEATURE_COLUMNS])[:, 1]
    metrics = evaluate_model(test_df, test_probabilities)
    metrics["cv_best_roc_auc"] = round(float(search.best_score_), 4)
    metrics["best_params"] = search.best_params_

    return tuned_model, train_df, test_df, metrics


def save_artifacts(model, metrics, dataset, train_df, test_df, output_dir, window):
    # Save the model, metrics, and a small sample so reviewers can inspect both
    # the artifact and the data shape used to train it.
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
