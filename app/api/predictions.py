from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db.models import ModelPrediction
from app.services.predictions import (
    predict_matchup_win_probability,
    recent_team_profile,
    record_model_prediction,
)


router = APIRouter()


@router.get("/predictions/matchup")
def matchup_prediction(
    team_a: str,
    team_b: str,
    last_n: int = Query(default=10, ge=3, le=25),
    db: Session = Depends(get_db),
):
    prediction = predict_matchup_win_probability(db, team_a, team_b, last_n)
    if prediction:
        saved_prediction = record_model_prediction(db, prediction)
        return {
            **prediction,
            "prediction_id": saved_prediction.id,
            "disclaimer": "Baseline ML model trained on historical rolling team form. This is for portfolio/demo use and is not betting advice.",
        }

    missing = []
    team_a_profile = recent_team_profile(db, team_a, last_n)
    team_b_profile = recent_team_profile(db, team_b, last_n)
    if not team_a_profile:
        missing.append(team_a)
    if not team_b_profile:
        missing.append(team_b)

    raise HTTPException(
        status_code=404,
        detail=f"No recent games found for: {', '.join(missing)}",
    )


@router.get("/predictions/history")
def prediction_history(
    limit: int = Query(default=10, ge=1, le=50),
    db: Session = Depends(get_db),
):
    predictions = (
        db.query(ModelPrediction)
        .order_by(ModelPrediction.created_at.desc(), ModelPrediction.id.desc())
        .limit(limit)
        .all()
    )

    return [
        {
            "id": prediction.id,
            "model_name": prediction.model_name,
            "model_version": prediction.model_version,
            "team_a": prediction.team_a,
            "team_b": prediction.team_b,
            "favorite": prediction.favorite,
            "win_probability": {
                prediction.team_a: round(prediction.team_a_probability, 3),
                prediction.team_b: round(prediction.team_b_probability, 3),
            },
            "last_n_games": prediction.last_n_games,
            "created_at": prediction.created_at,
        }
        for prediction in predictions
    ]
