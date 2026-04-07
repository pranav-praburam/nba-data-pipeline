from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.db.models import Game

router = APIRouter()

@router.get("/")
def home():
    return {"message": "NBA Data Pipeline is running"}

@router.get("/health")
def health():
    return {"status": "ok"}

@router.post("/games")
def create_game(team: str, opponent: str, points: int, db: Session = Depends(get_db)):
    new_game = Game(
        team=team,
        opponent=opponent,
        points=points
    )

    db.add(new_game)
    db.commit()
    db.refresh(new_game)

    return {"message": "game added", "id": new_game.id}

@router.get("/games")
def get_games(db: Session = Depends(get_db)):
    games = db.query(Game).all()

    return [
        {
            "id": g.id,
            "team": g.team,
            "opponent": g.opponent,
            "points": g.points
        }
        for g in games
    ]