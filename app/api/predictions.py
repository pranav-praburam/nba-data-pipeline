from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.services.predictions import recent_team_profile


router = APIRouter()


@router.get("/predictions/matchup")
def matchup_prediction(
    team_a: str,
    team_b: str,
    last_n: int = Query(default=10, ge=3, le=25),
    db: Session = Depends(get_db),
):
    team_a_profile = recent_team_profile(db, team_a, last_n)
    team_b_profile = recent_team_profile(db, team_b, last_n)

    if not team_a_profile or not team_b_profile:
        missing = []
        if not team_a_profile:
            missing.append(team_a)
        if not team_b_profile:
            missing.append(team_b)
        raise HTTPException(
            status_code=404,
            detail=f"No recent games found for: {', '.join(missing)}",
        )

    score_a = team_a_profile["form_score"]
    score_b = team_b_profile["form_score"]
    total_score = score_a + score_b
    team_a_probability = score_a / total_score if total_score else 0.5
    team_b_probability = 1 - team_a_probability
    favorite = team_a if team_a_probability >= team_b_probability else team_b

    return {
        "model_type": "heuristic_recent_form",
        "disclaimer": "This is not a trained ML model. It is a transparent heuristic based on recent wins, scoring, rebounding, assists, and shooting efficiency.",
        "last_n_games": last_n,
        "favorite": favorite,
        "win_probability": {
            team_a: round(team_a_probability, 3),
            team_b: round(team_b_probability, 3),
        },
        "team_profiles": [
            team_a_profile,
            team_b_profile,
        ],
    }
