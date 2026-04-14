import os

from fastapi import APIRouter, Header, HTTPException, Query, status


router = APIRouter(prefix="/admin", tags=["admin"])


@router.post("/ingest")
def trigger_ingestion(
    season: str = Query(default="2025-26"),
    full_refresh: bool = False,
    x_api_key: str = Header(default=""),
):
    expected_api_key = os.getenv("INGEST_API_KEY")
    if not expected_api_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="INGEST_API_KEY is not configured on this service.",
        )

    if x_api_key != expected_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid ingestion API key.",
        )

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
