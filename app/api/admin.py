from fastapi import APIRouter, BackgroundTasks, Query


router = APIRouter(prefix="/admin", tags=["admin"])


def run_ingestion_job(season: str, full_refresh: bool):
    from ingest_games import ingest_games

    ingest_games(season=season, full_refresh=full_refresh)


@router.post("/ingest")
def trigger_ingestion(
    background_tasks: BackgroundTasks,
    season: str = Query(default="2025-26"),
    full_refresh: bool = False,
):
    background_tasks.add_task(run_ingestion_job, season, full_refresh)

    return {
        "status": "accepted",
        "trigger": "render_api",
        "season": season,
        "full_refresh": full_refresh,
        "message": "Ingestion started in the background. Check /pipeline/runs for the recorded result.",
    }
