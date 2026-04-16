import json
from functools import lru_cache
from pathlib import Path

import joblib
import pandas as pd
from sqlalchemy.orm import Session

from app.db.models import Game, ModelPrediction

PROJECT_ROOT = Path(__file__).resolve().parents[2]
MODEL_PATH = PROJECT_ROOT / "models" / "win_probability_model.joblib"
METRICS_PATH = PROJECT_ROOT / "models" / "win_probability_metrics.json"


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


@lru_cache(maxsize=1)
def load_win_probability_artifact():
    return joblib.load(MODEL_PATH)


@lru_cache(maxsize=1)
def load_win_probability_metrics():
    if not METRICS_PATH.exists():
        return {}
    return json.loads(METRICS_PATH.read_text())


def model_team_features(db: Session, team_name: str, last_n: int):
    profile = recent_team_profile(db, team_name, last_n)
    if not profile:
        return None

    return {
        "win_rate_l10": profile["win_rate"],
        "avg_points_l10": profile["avg_points"],
        "avg_rebounds_l10": profile["avg_rebounds"],
        "avg_assists_l10": profile["avg_assists"],
        "avg_fg_pct_l10": profile["avg_fg_pct"],
        "avg_fg3_pct_l10": profile["avg_fg3_pct"],
        "profile": profile,
    }


def build_matchup_feature_row(team_a_features, team_b_features):
    base_features = [
        "win_rate_l10",
        "avg_points_l10",
        "avg_rebounds_l10",
        "avg_assists_l10",
        "avg_fg_pct_l10",
        "avg_fg3_pct_l10",
    ]

    row = {}
    for feature in base_features:
        row[f"home_{feature}"] = team_a_features[feature]
        row[f"away_{feature}"] = team_b_features[feature]
        row[f"diff_{feature}"] = team_a_features[feature] - team_b_features[feature]
    return row


def predict_matchup_win_probability(db: Session, team_a: str, team_b: str, last_n: int):
    team_a_features = model_team_features(db, team_a, last_n)
    team_b_features = model_team_features(db, team_b, last_n)

    if not team_a_features or not team_b_features:
        return None

    artifact = load_win_probability_artifact()
    model = artifact["model"]
    feature_columns = artifact["feature_columns"]
    feature_row = build_matchup_feature_row(team_a_features, team_b_features)
    features_df = pd.DataFrame([feature_row], columns=feature_columns)

    team_a_probability = float(model.predict_proba(features_df)[0][1])
    team_b_probability = 1 - team_a_probability
    favorite = team_a if team_a_probability >= team_b_probability else team_b

    return {
        "model_type": artifact.get("model_type", "logistic_regression"),
        "model_version": artifact.get("trained_at"),
        "rolling_window_games": artifact.get("rolling_window_games"),
        "training_metrics": load_win_probability_metrics(),
        "last_n_games": last_n,
        "favorite": favorite,
        "win_probability": {
            team_a: round(team_a_probability, 3),
            team_b: round(team_b_probability, 3),
        },
        "feature_inputs": feature_row,
        "team_profiles": [
            team_a_features["profile"],
            team_b_features["profile"],
        ],
    }


def record_model_prediction(db: Session, prediction):
    probabilities = prediction["win_probability"]
    team_a, team_b = list(probabilities.keys())
    saved_prediction = ModelPrediction(
        model_name=prediction["model_type"],
        model_version=prediction.get("model_version"),
        team_a=team_a,
        team_b=team_b,
        favorite=prediction["favorite"],
        team_a_probability=probabilities[team_a],
        team_b_probability=probabilities[team_b],
        last_n_games=prediction["last_n_games"],
        feature_inputs=json.dumps(prediction["feature_inputs"], sort_keys=True),
    )
    db.add(saved_prediction)
    db.commit()
    db.refresh(saved_prediction)
    return saved_prediction
