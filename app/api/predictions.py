from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.services.predictions import predict_matchup_win_probability, recent_team_profile


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
        return {
            **prediction,
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
