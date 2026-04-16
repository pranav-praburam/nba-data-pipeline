from fastapi import APIRouter, BackgroundTasks, Query


router = APIRouter(prefix="/admin", tags=["admin"])


def run_ingestion_job(season: str, full_refresh: bool, source: str):
    # Import lazily so normal API startup does not pay the nba_api/pandas import cost.
    from ingest_games import ingest_games

    ingest_games(season=season, full_refresh=full_refresh, source=source)


@router.post("/ingest")
def trigger_ingestion(
    background_tasks: BackgroundTasks,
    season: str = Query(default="2025-26"),
    full_refresh: bool = False,
    source: str = Query(default="live", pattern="^(live|stats)$"),
):
    # GitHub Actions and manual Render checks call this endpoint to trigger
    # ingestion without exposing database credentials outside the deployed service.
    background_tasks.add_task(run_ingestion_job, season, full_refresh, source)

    return {
        "status": "accepted",
        "trigger": "render_api",
        "season": season,
        "full_refresh": full_refresh,
        "source": source,
        "message": "Ingestion started in the background. Check /pipeline/runs for the recorded result.",
    }
