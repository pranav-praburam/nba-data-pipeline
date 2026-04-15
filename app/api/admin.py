from fastapi import APIRouter, HTTPException, Query, status


router = APIRouter(prefix="/admin", tags=["admin"])


@router.post("/ingest")
def trigger_ingestion(
    season: str = Query(default="2025-26"),
    full_refresh: bool = False,
):
    from ingest_games import ingest_games

    result = ingest_games(season=season, full_refresh=full_refresh)
    if result and result.get("status") == "failed":
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=result,
        )

    return {
        "status": "ok",
        "trigger": "render_api",
        "result": result,
    }
