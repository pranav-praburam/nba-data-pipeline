from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db.models import ModelPick
from app.services.picks import serialize_pick


router = APIRouter(tags=["picks"])


@router.get("/picks")
def list_picks(
    limit: int = Query(default=25, ge=1, le=200),
    game_date: str = None,
    settled: bool = None,
    db: Session = Depends(get_db),
):
    query = db.query(ModelPick).order_by(ModelPick.game_date.desc(), ModelPick.id.desc())
    if game_date:
        query = query.filter(ModelPick.game_date == game_date)
    if settled is not None:
        query = query.filter(ModelPick.settled.is_(settled))

    rows = query.limit(limit).all()
    return [serialize_pick(row) for row in rows]
