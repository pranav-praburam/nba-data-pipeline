from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db.models import PipelineRun


router = APIRouter()


@router.get("/pipeline/runs")
def get_pipeline_runs(limit: int = 10, db: Session = Depends(get_db)):
    runs = (
        db.query(PipelineRun)
        .order_by(PipelineRun.started_at.desc(), PipelineRun.id.desc())
        .limit(limit)
        .all()
    )

    return [
        {
            "pipeline_name": run.pipeline_name,
            "season": run.season,
            "mode": run.mode,
            "rows_fetched": run.rows_fetched,
            "rows_inserted": run.rows_inserted,
            "rows_skipped": run.rows_skipped,
            "status": run.status,
            "error_message": run.error_message,
            "started_at": run.started_at,
            "completed_at": run.completed_at,
        }
        for run in runs
    ]
